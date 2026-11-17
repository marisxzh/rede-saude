"""Leitura, obtenção e preparação dos dados do SIH-SUS e de apoio."""

import ftplib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from .config import CAPITULOS, COD_UF, COLUNAS, FTP_HOST, FTP_PASTAS, ROTULO_COMPLEX, URL_CNES, URL_COORD

def baixar_do_ftp(ftp, pastas, arquivo, destino):
    """Tenta baixar 'arquivo' de cada pasta do FTP ate dar certo. Devolve True/False."""
    for caminho in pastas:
        try:
            with open(destino, "wb") as f:
                ftp.retrbinary(f"RETR {caminho}/{arquivo}", f.write)
            return True
        except ftplib.error_perm:
            Path(destino).unlink(missing_ok=True)
    return False


def baixar(uf, ano, pasta):
    import datasus_dbc
    from dbfread import DBF

    pasta_dbc = pasta / "dbc"
    pasta_dbc.mkdir(parents=True, exist_ok=True)
    partes = []
    ftp = None

    for mes in range(1, 13):
        nome = f"RD{uf}{ano % 100:02d}{mes:02d}"
        dbc = pasta_dbc / f"{nome}.dbc"

        if not dbc.exists():  # so baixa se ainda nao tiver
            if ftp is None:
                ftp = ftplib.FTP(FTP_HOST, timeout=60)
                ftp.login()
            ok = baixar_do_ftp(ftp, FTP_PASTAS, f"{nome}.dbc", dbc)
            if not ok:
                print(f"  [aviso] {nome}.dbc nao encontrado no FTP; pulando.")
                continue

        dbf = dbc.with_suffix(".dbf")
        datasus_dbc.decompress(str(dbc), str(dbf))
        tabela = DBF(str(dbf), encoding="latin-1", load=False,
                     ignore_missing_memofile=True)
        campos = [c for c in COLUNAS if c in tabela.field_names]
        linhas = [[reg[c] for c in campos] for reg in tabela]
        partes.append(pd.DataFrame(linhas, columns=campos))
        dbf.unlink(missing_ok=True)
        print(f"  {nome}: {len(linhas)} internacoes")

    if not partes:
        sys.exit("Nada baixado. Baixe os .dbc a mao e coloque em "
                 f"'{pasta_dbc}' (nomes como RDMG2501.dbc), depois rode de novo.")

    df = pd.concat(partes, ignore_index=True)
    saida = pasta / f"rd_{uf}_{ano}.csv.gz"
    df.to_csv(saida, index=False)
    print(f"Salvo: {saida} ({len(df)} linhas)")


def carregar_coordenadas(pasta):
    arq = pasta / "municipios_coord.csv"
    if not arq.exists():
        pasta.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL_COORD, arq)
    c = pd.read_csv(arq, dtype={"codigo_ibge": str})
    c["cod"] = c["codigo_ibge"].str[:6]
    return c.rename(columns={"latitude": "lat", "longitude": "lon"})[["cod", "nome", "lat", "lon"]]


def ler_planilha(caminho):
    p = pd.read_excel(caminho, header=2)
    p.columns = [str(c).strip() for c in p.columns]
    col = lambda ch, nao="": [c for c in p.columns if ch in c.upper() and (not nao or nao not in c.upper())][0]
    p = p.rename(columns={col("DATASUS"): "cod", col("POPULA"): "pop",
                          col("MICRORREGI", "CÓDIGO"): "micro",
                          col("MACRORREGI", "CÓDIGO"): "macro"})
    p = p[pd.to_numeric(p["cod"], errors="coerce").notna()].copy()
    p["cod"] = p["cod"].astype(int).astype(str).str.zfill(6)
    return p[["cod", "pop", "micro", "macro"]]


def ler_nomes_arquivo(caminho):
    """
    Le um arquivo com codigo CNES e nome do estabelecimento. Aceita:
      - planilha/CSV com colunas tipo 'CNES' e 'Nome Fantasia' (como a do site do CNES);
      - CSV no estilo TABNET, com linhas como  "2126494 NOME DO HOSPITAL";1234
    """
    caminho = Path(caminho)
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        tabela = pd.read_excel(caminho, dtype=str)
    else:
        texto = None
        for enc in ("utf-8-sig", "latin-1"):
            try:
                texto = caminho.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        achados = re.findall(r'^\s*"?(\d{7})[\s\-–]+([^";\n]+)', texto, flags=re.M)
        if len(achados) >= 10:                                   # formato TABNET
            return {c: n.strip() for c, n in achados}
        sep = ";" if texto.count(";") > texto.count(",") else ","
        tabela = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)
    col_cnes = next((c for c in tabela.columns if "cnes" in str(c).lower()), None)
    col_nome = escolher_coluna_nome(list(tabela.columns))
    if col_cnes is None or col_nome is None:
        sys.exit(f"Nao achei colunas de CNES e de nome em '{caminho}'. Colunas: {list(tabela.columns)}")
    t = tabela[[col_cnes, col_nome]].dropna()
    return dict(zip(t[col_cnes].str.strip().str.zfill(7), t[col_nome].str.strip()))


def escolher_coluna_nome(campos):
    """Escolhe, entre os nomes de colunas, a que tem o nome do estabelecimento."""
    baixo = {c: str(c).lower() for c in campos}
    for chave in ("fant", "nome", "razao", "razão"):
        for c, b in baixo.items():
            if chave in b and "cnes" not in b and "municip" not in b and "munic" not in b:
                return c
    return None


def _consultar_cnes(cnes):
    """Pergunta a API publica do CNES o nome de um estabelecimento. Devolve None se a rede falhar."""
    url = URL_CNES.format(int(cnes))
    dado = None
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={"accept": "application/json", "User-Agent": "fluxos_saude"})
            with urllib.request.urlopen(req, timeout=20) as r:
                dado = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:                                   # codigo que nao existe no CNES
                return cnes, "(não encontrado no CNES)"
            time.sleep(1 + tentativa)
        except Exception:
            time.sleep(1 + tentativa)
    if dado is None:
        return None
    if isinstance(dado, dict) and "estabelecimentos" in dado:   # a API embrulha o resultado numa lista
        dado = dado["estabelecimentos"]
    if isinstance(dado, list):
        dado = dado[0] if dado else None
    if not isinstance(dado, dict):
        return cnes, "(não encontrado no CNES)"
    return cnes, dado.get("nome_fantasia") or dado.get("nome_razao_social") or "(sem nome)"


def carregar_nomes_cnes(uf, pasta, codigos, arquivo_usuario=None, sem_nomes=False):
    """
    Devolve {CNES: nome do hospital}. Ordem de prioridade:
      1) arquivo do usuario (--cnes-nomes), se informado;
      2) cache local (dados/cnes_nomes_UF.csv): so consulta o que ainda nao tem;
      3) API publica de dados abertos do Ministerio da Saude (precisa de internet).
    Se nada der certo, a tabela de hospitais sai so com os codigos.
    """
    cache = pasta / f"cnes_nomes_{uf}.csv"
    if arquivo_usuario:
        nomes = ler_nomes_arquivo(arquivo_usuario)
        pd.Series(nomes, name="nome").rename_axis("cnes").to_csv(cache)
        print(f"Nomes de hospitais: {len(nomes)} lidos de {arquivo_usuario}")
        return nomes
    nomes = {}
    if cache.exists():
        c = pd.read_csv(cache, dtype=str)
        nomes = dict(zip(c["cnes"], c["nome"]))
    if sem_nomes:
        return nomes
    faltam = [c for c in codigos if c not in nomes]
    if faltam:
        print(f"Buscando o nome de {len(faltam)} hospitais na API do CNES (so na primeira vez)...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            resultados = list(pool.map(_consultar_cnes, faltam))
        achados = [r for r in resultados if r]
        nomes.update(dict(achados))
        if achados:
            pd.Series(nomes, name="nome").rename_axis("cnes").to_csv(cache)
        if len(achados) < len(faltam):
            print(f"[aviso] {len(faltam) - len(achados)} consultas falharam (internet ou API fora do ar). "
                  "Rode de novo mais tarde para completar, ou use --cnes-nomes arquivo.xlsx")
    return nomes


def preparar(df, uf, coord):
    """Limpa: so AIH normal, so residentes da UF, so municipios validos."""
    n0 = len(df)
    for c in ["MUNIC_RES", "MUNIC_MOV", "DIAG_PRINC", "COMPLEX", "IDENT", "CNES"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    if "IDENT" in df.columns:               # 1 = AIH normal; 5 = continuacao (longa permanencia)
        df = df[df["IDENT"] == "1"]
    df = df[df["MUNIC_RES"].str.startswith(COD_UF[uf])]
    validos = set(coord["cod"])
    df = df[df["MUNIC_RES"].isin(validos) & df["MUNIC_MOV"].isin(validos)].copy()
    if "VAL_TOT" in df.columns:
        df["VAL_TOT"] = pd.to_numeric(df["VAL_TOT"], errors="coerce").fillna(0)
    print(f"Registros: {n0} lidos -> {len(df)} usados (AIH normal, residentes de {uf}, municipios validos)")
    return df


def capitulo_do_cid(cid):
    """Transforma um CID (ex.: C509, I21) no capitulo do CID-10 (ex.: 'II - Neoplasias')."""
    letra = cid[:1].upper()
    try:
        num = int(cid[1:3])
    except ValueError:
        return "Não informado"
    if letra in "AB":
        cap = "I"
    elif letra == "C":
        cap = "II"
    elif letra == "D":
        cap = "II" if num <= 48 else "III"
    elif letra == "H":
        cap = "VII" if num <= 59 else "VIII"
    elif letra in "VWXY":
        cap = "XX"
    elif letra in "ST":
        cap = "XIX"
    else:
        cap = {"E": "IV", "F": "V", "G": "VI", "I": "IX", "J": "X", "K": "XI", "L": "XII",
               "M": "XIII", "N": "XIV", "O": "XV", "P": "XVI", "Q": "XVII", "R": "XVIII",
               "Z": "XXI"}.get(letra)
    return f"{cap} - {CAPITULOS[cap]}" if cap else "Não informado"


def rotular_capitulos(serie):
    """Aplica capitulo_do_cid so nos valores unicos (rapido mesmo com milhoes de linhas)."""
    mapa = {c: capitulo_do_cid(c) for c in serie.dropna().unique()}
    return serie.map(mapa)

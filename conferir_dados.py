#!/usr/bin/env python3
"""
conferir_dados.py - Duas conferencias dos dados baixados (rode DEPOIS do 'baixar').

  1) TOTAL: compara as internacoes que voce baixou com o TABNET (por local de internacao).
  2) COMPLEX: lista os procedimentos mais frequentes de cada nivel de complexidade, com o link
     do SIGTAP (tabela oficial do SUS) para voce ver se o nivel esta certo.

Uso:
  python conferir_dados.py --uf MG --ano 2025 --tabnet tabnet_2025.csv
  python conferir_dados.py --uf MG --ano 2025                  # so a conferencia do COMPLEX
"""
import argparse
import re
from pathlib import Path

import pandas as pd


def ler_tabnet(caminho):
    """Le o CSV do TABNET (linhas como "310010 ABADIA DOS DOURADOS";47 e "Total";507243)."""
    texto = Path(caminho).read_bytes().decode("latin-1")
    periodo = re.search(r"Per[ií]odo:\s*(.+)", texto)
    por_municipio = {c: int(n) for c, n in re.findall(r'^"(\d{6}) [^"]*";\s*(\d+)', texto, flags=re.M)}
    total = re.search(r'^"Total";\s*(\d+)', texto, flags=re.M)
    return por_municipio, int(total.group(1)) if total else sum(por_municipio.values()), \
        periodo.group(1).strip() if periodo else "?"


def conferir_total(df, caminho_tabnet):
    tab, total_tab, periodo = ler_tabnet(caminho_tabnet)
    print("=" * 70)
    print("1) CONFERENCIA DO TOTAL COM O TABNET")
    print("=" * 70)
    print(f"Periodo no arquivo do TABNET: {periodo}")
    print("(Precisa ser Jan a Dez do ano inteiro. Se listar so alguns meses, baixe de novo.)\n")
    candidatos = {"Todas as AIH (qualquer tipo)": df}
    if "IDENT" in df.columns:
        candidatos["So AIH normal (IDENT = 1)"] = df[df["IDENT"].str.strip() == "1"]
    print(f"TABNET (Total): {total_tab:,}".replace(",", "."))
    melhor = None
    for nome, parte in candidatos.items():
        n = len(parte)
        dif = 100 * (n - total_tab) / total_tab
        print(f"  Seu arquivo - {nome}: {n:,}  (diferenca {dif:+.2f}%)".replace(",", "."))
        if melhor is None or abs(dif) < melhor[0]:
            melhor = (abs(dif), nome, parte)

    _, nome, parte = melhor
    meu = parte.groupby(parte["MUNIC_MOV"].str.strip()).size()
    cmp = pd.DataFrame({"tabnet": pd.Series(tab), "meu": meu}).fillna(0).astype(int)
    cmp["dif"] = cmp["meu"] - cmp["tabnet"]
    iguais = (cmp["dif"] == 0).mean() * 100
    print(f"\nPor municipio (comparando com '{nome}'): {len(cmp)} municipios, "
          f"{iguais:.0f}% com valor exatamente igual.")
    pior = cmp.reindex(cmp["dif"].abs().sort_values(ascending=False).index).head(8)
    if pior["dif"].abs().max() > 0:
        print("Maiores diferencas:")
        print(pior.to_string())
    print("\nComo ler: diferenca abaixo de ~1% no total e a maioria dos municipios iguais = dados OK.")
    print("Se for maior, confira: periodo completo no TABNET e conteudo 'Internacoes' (nao 'AIH aprovadas').")


def conferir_complex(df, ano):
    if "COMPLEX" not in df.columns or "PROC_REA" not in df.columns:
        print("\n[aviso] O arquivo nao tem as colunas COMPLEX/PROC_REA.")
        return
    print("\n" + "=" * 70)
    print("2) CONFERENCIA DO CAMPO COMPLEX COM O SIGTAP")
    print("=" * 70)
    print("Em cada nivel de COMPLEX, abra os links e veja o campo 'Complexidade' do procedimento.")
    print("Hipotese a confirmar: 02 = Media complexidade, 03 = Alta complexidade.\n")
    d = df.assign(COMPLEX=df["COMPLEX"].str.strip(), PROC_REA=df["PROC_REA"].str.strip().str.zfill(10))
    for nivel, parte in d.groupby("COMPLEX"):
        print(f"--- COMPLEX = {nivel}: {len(parte):,} internacoes ({100 * len(parte) / len(d):.1f}%)".replace(",", "."))
        for proc, n in parte["PROC_REA"].value_counts().head(6).items():
            print(f"   {proc}  ({n:,} internacoes)  "
                  f"http://sigtap.datasus.gov.br/tabela-unificada/app/sec/procedimento/exibir/{proc}/12/{ano}"
                  .replace(",", "."))
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uf", default="MG")
    ap.add_argument("--ano", type=int, default=2025)
    ap.add_argument("--dados", default="dados")
    ap.add_argument("--tabnet", help="CSV baixado do TABNET (por local de internacao, Jan a Dez do ano)")
    a = ap.parse_args()

    arq = Path(a.dados) / f"rd_{a.uf.upper()}_{a.ano}.csv.gz"
    df = pd.read_csv(arq, dtype=str)
    if a.tabnet:
        conferir_total(df, a.tabnet)
    conferir_complex(df, a.ano)

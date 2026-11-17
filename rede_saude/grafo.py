"""Modelagem dos fluxos e algoritmos sobre o grafo."""

import re

import numpy as np
import pandas as pd

from .config import ROTULO_COMPLEX

def haversine(lat1, lon1, lat2, lon2):
    """Distancia em linha reta (km) - a mesma ideia dos artigos de 2004 e 2013."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def montar_pares(df, coord):
    """Cada linha = uma aresta: mora em 'res', internado em 'mov', 'n' pacientes, 'dist_km'."""
    pares = (df.groupby(["MUNIC_RES", "MUNIC_MOV"]).size().reset_index(name="n")
             .rename(columns={"MUNIC_RES": "res", "MUNIC_MOV": "mov"}))
    c = coord.set_index("cod")[["lat", "lon"]]
    pares = pares.join(c.add_suffix("_r"), on="res").join(c.add_suffix("_m"), on="mov")
    pares["dist_km"] = haversine(pares["lat_r"], pares["lon_r"], pares["lat_m"], pares["lon_m"])
    return pares[["res", "mov", "n", "dist_km"]]


def mediana_ponderada(valores, pesos):
    v, w = np.asarray(valores, float), np.asarray(pesos, float)
    if w.sum() == 0:
        return float("nan")
    o = np.argsort(v)
    acumulado = np.cumsum(w[o])
    return float(v[o][np.searchsorted(acumulado, acumulado[-1] / 2)])


def metricas(pares):
    """Numeros-resumo do deslocamento de um conjunto de internacoes."""
    total = pares["n"].sum()
    sai = pares[pares["res"] != pares["mov"]]
    if sai["n"].sum() == 0:
        media = mediana = float("nan")
    else:
        media = round(float((sai["dist_km"] * sai["n"]).sum() / sai["n"].sum()), 1)
        mediana = round(mediana_ponderada(sai["dist_km"], sai["n"]), 1)
    return {
        "internacoes": int(total),
        "pct_fora_do_municipio": round(100 * sai["n"].sum() / total, 1),
        "dist_media_km_quem_sai": media,
        "dist_mediana_km_quem_sai": mediana,
        "pct_mais_de_60km": round(100 * pares.loc[pares["dist_km"] > 60, "n"].sum() / total, 1),
        "pct_mais_de_100km": round(100 * pares.loc[pares["dist_km"] > 100, "n"].sum() / total, 1),
    }


def hierarquia(pares, tamanho, min_fluxo=2):
    """
    Regra: o maior fluxo de saida de cada municipio aponta para o seu 'chefe',
    mas so se o chefe for MAIOR (tamanho = valor pago das internacoes no municipio).
    Sem chefe maior -> o municipio e independente (raiz, nivel 1).
    """
    fora = pares[(pares["res"] != pares["mov"]) & (pares["n"] >= min_fluxo)]
    # Em caso de empate, escolhe o menor código de destino para que o resultado
    # seja determinístico e reproduzível.
    maior = (fora.sort_values(["res", "n", "mov"], ascending=[True, False, True])
             .drop_duplicates("res"))
    chefe = {}
    for r in maior.itertuples():
        if tamanho.get(r.mov, 0) > tamanho.get(r.res, 0):
            chefe[r.res] = r.mov

    nos = set(pares["res"]) | set(pares["mov"])
    memo = {}

    def nivel_raiz(c):
        """Sobe a cadeia de chefes e memoriza nível e raiz sem recursão profunda."""
        caminho, visitados = [], set()
        atual = c
        while atual not in memo:
            if atual in visitados:
                raise ValueError(f"Ciclo inesperado na hierarquia de fluxo dominante: {atual}")
            visitados.add(atual)
            if atual not in chefe:
                memo[atual] = (1, atual)
                break
            caminho.append(atual)
            atual = chefe[atual]
        nivel, raiz = memo[atual]
        for no in reversed(caminho):
            nivel += 1
            memo[no] = (nivel, raiz)
        return memo[c]

    linhas = [(c, chefe.get(c), *nivel_raiz(c)) for c in sorted(nos)]
    return pd.DataFrame(linhas, columns=["cod", "chefe", "nivel", "raiz"])


def interpretar_nicho(item):
    """Lê NOME=CID[,CID] e, opcionalmente, NOME=CID@COMPLEXIDADE."""
    if "=" not in item:
        raise ValueError(f"Nicho inválido '{item}'. Use Nome=CID, por exemplo Neoplasias=C.")
    nome, filtro = item.split("=", 1)
    nome = nome.strip()
    if not nome:
        raise ValueError(f"Nicho inválido '{item}': informe um nome antes de '='.")
    nivel = None
    if "@" in filtro:
        filtro, nivel = filtro.rsplit("@", 1)
        nivel = nivel.strip().zfill(2)
        if nivel not in ROTULO_COMPLEX:
            raise ValueError(f"Complexidade '{nivel}' inválida no nicho '{nome}'. Use 01, 02 ou 03.")
    descricao_cid = filtro.strip().upper()
    prefixos = []
    for token in descricao_cid.split(","):
        token = token.strip()
        intervalo = re.fullmatch(r"([A-Z])(\d{2})-([A-Z])?(\d{2})", token)
        if intervalo:
            letra_ini, inicio, letra_fim, fim = intervalo.groups()
            if (letra_fim and letra_fim != letra_ini) or int(inicio) > int(fim):
                raise ValueError(f"Intervalo CID inválido '{token}' no nicho '{nome}'.")
            prefixos.extend(f"{letra_ini}{numero:02d}" for numero in range(int(inicio), int(fim) + 1))
        elif re.fullmatch(r"[A-Z][A-Z0-9]*", token):
            prefixos.append(token)
        else:
            raise ValueError(f"CID inválido no nicho '{nome}'. Exemplo: Mama=C50 ou Neoplasias=C,D00-D48.")
    if not prefixos:
        raise ValueError(f"Informe ao menos um prefixo CID no nicho '{nome}'.")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_-")
    if not slug:
        raise ValueError(f"Nome inválido para gerar arquivos do nicho '{nome}'.")
    return nome, tuple(prefixos), nivel, slug, descricao_cid


def detectar_comunidades_louvain(pares, municipios, resolucao=1.0, seed=42):
    """Detecta comunidades na projeção não direcionada dos fluxos intermunicipais."""
    if resolucao <= 0:
        raise ValueError("A resolução do Louvain precisa ser maior que zero.")
    try:
        import networkx as nx
    except ImportError as erro:
        raise RuntimeError("Para detectar comunidades, instale as dependências: python -m pip install -r requirements.txt") from erro

    # O grafo original mantém direção, peso e distância. A projeção soma os
    # fluxos A->B e B->A para agrupar municípios que trocam mais internações.
    dirigido = nx.DiGraph()
    codigos = municipios["cod"].astype(str).str.zfill(6)
    dirigido.add_nodes_from(codigos)
    intermunicipais = pares[pares["res"] != pares["mov"]]
    for linha in pares.itertuples(index=False):
        dirigido.add_edge(str(linha.res).zfill(6), str(linha.mov).zfill(6),
                          weight=int(linha.n), distance_km=float(linha.dist_km))

    ativos = set(intermunicipais["res"].astype(str).str.zfill(6)) | set(
        intermunicipais["mov"].astype(str).str.zfill(6))
    nao_direcionado = nx.Graph()
    nao_direcionado.add_nodes_from(sorted(ativos))
    for origem, destino, dados_aresta in dirigido.edges(data=True):
        if origem == destino:
            continue
        peso = int(dados_aresta["weight"])
        if nao_direcionado.has_edge(origem, destino):
            nao_direcionado[origem][destino]["weight"] += peso
        else:
            nao_direcionado.add_edge(origem, destino, weight=peso)

    if nao_direcionado.number_of_edges():
        grupos = nx.community.louvain_communities(
            nao_direcionado, weight="weight", resolution=resolucao, seed=seed
        )
        modularidade = nx.community.modularity(nao_direcionado, grupos, weight="weight")
    else:
        grupos, modularidade = [], float("nan")

    # IDs estáveis para apresentação: ordena os grupos pelo menor código SUS.
    grupos = sorted(grupos, key=lambda grupo: min(grupo))
    comunidade_por_codigo = {
        codigo: indice for indice, grupo in enumerate(grupos, start=1) for codigo in grupo
    }
    resultado = municipios.copy()
    resultado["cod"] = resultado["cod"].astype(str).str.zfill(6)
    resultado["comunidade"] = resultado["cod"].map(comunidade_por_codigo).fillna(0).astype(int)

    fluxos = intermunicipais.copy()
    fluxos["comunidade_res"] = fluxos["res"].astype(str).str.zfill(6).map(comunidade_por_codigo).fillna(0).astype(int)
    fluxos["comunidade_mov"] = fluxos["mov"].astype(str).str.zfill(6).map(comunidade_por_codigo).fillna(0).astype(int)
    resumo = []
    for identificador in range(1, len(grupos) + 1):
        membros = resultado[resultado["comunidade"] == identificador].copy()
        if membros.empty:
            continue
        polo = membros.sort_values(["entradas", "cod"], ascending=[False, True]).iloc[0]
        internos = fluxos[(fluxos["comunidade_res"] == identificador)
                          & (fluxos["comunidade_mov"] == identificador)]["n"].sum()
        externos = fluxos[((fluxos["comunidade_res"] == identificador)
                           | (fluxos["comunidade_mov"] == identificador))
                          & (fluxos["comunidade_res"] != fluxos["comunidade_mov"])]["n"].sum()

        def regiao_dominante(coluna):
            if coluna not in membros.columns:
                return "", float("nan")
            valores = membros[coluna].dropna().astype(str).str.strip()
            valores = valores[valores != ""]
            if valores.empty:
                return "", float("nan")
            frequencias = valores.value_counts()
            return frequencias.index[0], round(100 * frequencias.iloc[0] / len(membros), 1)

        macro, pct_macro = regiao_dominante("macro")
        micro, pct_micro = regiao_dominante("micro")
        populacao = (pd.to_numeric(membros["pop"], errors="coerce").sum()
                     if "pop" in membros.columns else float("nan"))
        resumo.append({
            "comunidade": identificador,
            "municipios": len(membros),
            "populacao": populacao,
            "polo_nome": polo["nome"],
            "polo_entradas": int(polo["entradas"]),
            "entradas_totais": int(membros["entradas"].sum()),
            "saidas_totais": int(membros["fora"].sum()),
            "fluxos_internos": int(internos),
            "fluxos_externos": int(externos),
            "macro_dominante": macro,
            "pct_macro_dominante": pct_macro,
            "micro_dominante": micro,
            "pct_micro_dominante": pct_micro,
            "modularidade_global": round(float(modularidade), 4) if pd.notna(modularidade) else float("nan"),
        })

    sem_fluxo = resultado[resultado["comunidade"] == 0]
    if not sem_fluxo.empty:
        populacao_sem_fluxo = (pd.to_numeric(sem_fluxo["pop"], errors="coerce").sum()
                               if "pop" in sem_fluxo.columns else float("nan"))
        resumo.append({
            "comunidade": 0, "municipios": len(sem_fluxo),
            "populacao": populacao_sem_fluxo,
            "polo_nome": "Sem fluxo intermunicipal no recorte", "polo_entradas": 0,
            "entradas_totais": 0, "saidas_totais": 0, "fluxos_internos": 0,
            "fluxos_externos": 0, "macro_dominante": "", "pct_macro_dominante": float("nan"),
            "micro_dominante": "", "pct_micro_dominante": float("nan"),
            "modularidade_global": round(float(modularidade), 4) if pd.notna(modularidade) else float("nan"),
        })
    return resultado, pd.DataFrame(resumo)

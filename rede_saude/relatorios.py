"""Tabelas analíticas, gráficos e exportação para Gephi."""

import pandas as pd

from .config import (COL_FLUXOS, COL_HOSPITAIS, COL_METRICAS, COL_MUNICIPIOS,
                     COL_NOS_COMUNIDADE, COL_RESUMO_COMUNIDADES, ROTULO_COMPLEX)
from .grafo import metricas, montar_pares

def salvar(df, caminho, nomes):
    """Salva CSV so com as colunas conhecidas, ja com os nomes completos."""
    cols = [c for c in nomes if c in df.columns]
    df[cols].rename(columns=nomes).to_csv(caminho, index=False, encoding="utf-8-sig")


def tabela_municipios(pares, coord, hier, planilha=None):
    p = pares.assign(n_fora=pares["n"].where(pares["res"] != pares["mov"], 0),
                     n_local=pares["n"].where(pares["res"] == pares["mov"], 0),
                     n_dist=pares["n"] * pares["dist_km"])
    t = p.groupby("res").agg(internacoes=("n", "sum"), fora=("n_fora", "sum"),
                             locais=("n_local", "sum"),
                             soma_dist=("n_dist", "sum")).reset_index().rename(columns={"res": "cod"})
    t["pct_fora"] = (100 * t["fora"] / t["internacoes"]).round(1)
    t["dist_media_km"] = (t["soma_dist"] / t["internacoes"]).round(1)
    t = t.drop(columns=["soma_dist"])
    entradas = (pares[pares["res"] != pares["mov"]].groupby("mov")["n"].sum())

    # Mantém os municípios sem internações no recorte, inclusive nos nichos.
    base = planilha if planilha is not None else pd.DataFrame({"cod": coord["cod"]})
    base = base[base["cod"].isin(coord["cod"])]
    t = base.merge(t, on="cod", how="left")
    for coluna in ["internacoes", "fora", "locais"]:
        t[coluna] = t[coluna].fillna(0).astype(int)
    t["entradas"] = t["cod"].map(entradas).fillna(0).astype(int)
    # O SIH registra fluxos observados, não a disponibilidade permanente do serviço.
    t["recebeu_fluxos"] = t["entradas"].gt(0).map({True: "Sim", False: "Não"})
    nomes = coord.set_index("cod")["nome"]
    t = t.merge(hier, on="cod", how="left")
    t["nome"] = t["cod"].map(nomes)
    t["chefe_nome"] = t["chefe"].map(nomes)
    t["raiz_nome"] = t["raiz"].map(nomes)
    if "pop" in t.columns:
        t["internacoes_por_1000hab"] = (1000 * t["internacoes"] / t["pop"]).round(1)
        t["saidas_por_1000hab"] = (1000 * t["fora"] / t["pop"]).round(1)
        t["entradas_por_1000hab"] = (1000 * t["entradas"] / t["pop"]).round(1)
    return t


def tabela_diagnosticos(df, coord):
    """Deslocamento por tipo de doenca (capitulo do CID-10) - analise geral."""
    total = len(df)
    linhas = []
    for cap, parte in df.groupby("cap"):
        m = metricas(montar_pares(parte, coord))
        linhas.append({"grupo": cap, "pct_do_total": round(100 * len(parte) / total, 1), **m})
    return pd.DataFrame(linhas).sort_values("internacoes", ascending=False)


def tabela_hospitais(df, nomes_mun, nomes_cnes=None):
    """Perfil de cada hospital (CNES): de onde vem os pacientes e qual doenca predomina."""
    if "CNES" not in df.columns:
        return None
    d = df[df["CNES"].str.len() > 0].copy()
    d["CNES"] = d["CNES"].str.zfill(7)
    d["de_fora"] = d["MUNIC_RES"] != d["MUNIC_MOV"]
    g = d.groupby("CNES")
    t = pd.DataFrame({
        "internacoes": g.size(),
        "municipio": g["MUNIC_MOV"].first().map(nomes_mun),
        "pct_de_fora": 100 * g["de_fora"].mean(),
        "municipios_origem": g["MUNIC_RES"].nunique(),
        "dist_media_de_fora": d[d["de_fora"]].groupby("CNES")["dist_km"].mean(),
    })
    if "cx" in d.columns:
        t["pct_alta"] = 100 * (d["cx"] == ROTULO_COMPLEX["03"]).groupby(d["CNES"]).mean()
    if "cap" in d.columns:
        c = d.groupby(["CNES", "cap"]).size().rename("n").reset_index()
        topo = c.loc[c.groupby("CNES")["n"].idxmax()].set_index("CNES")
        t["cap_principal"] = topo["cap"]
        t["pct_cap_principal"] = 100 * topo["n"] / t["internacoes"]
    if nomes_cnes:
        t.insert(0, "nome", t.index.map(nomes_cnes))
    t = t.round(1).sort_values("internacoes", ascending=False)
    t.index.name = "cnes"
    return t.reset_index()


def exportar_tabelas_gephi(pares, municipios, coord, pasta_saida, identificador,
                           quantidade_polos=20):
    """Exporta a rede completa, o top 20 de polos e um polo por comunidade."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    codigos = municipios["cod"].astype(str).str.zfill(6)
    nos = pd.DataFrame({"Id": codigos, "Label": municipios["nome"].astype(str)})
    for origem, destino in [("pop", "Populacao"), ("micro", "Microrregiao"), ("macro", "Macrorregiao"),
                            ("recebeu_fluxos", "Recebeu_internacoes_de_outros_municipios"),
                            ("comunidade", "Comunidade_Louvain"),
                            ("fora", "Saidas_intermunicipais"), ("entradas", "Entradas_intermunicipais"),
                            ("saidas_por_1000hab", "Saidas_por_1000_habitantes"),
                            ("entradas_por_1000hab", "Entradas_por_1000_habitantes")]:
        if origem in municipios.columns:
            nos[destino] = municipios[origem].values
    coords = coord.set_index("cod")
    nos["Latitude"] = nos["Id"].map(coords["lat"])
    nos["Longitude"] = nos["Id"].map(coords["lon"])

    nomes = coord.set_index("cod")["nome"]
    arestas = pd.DataFrame({
        "Source": pares["res"].astype(str).str.zfill(6),
        "Target": pares["mov"].astype(str).str.zfill(6),
        "Weight": pares["n"].astype(int),
        "Distance_km": pares["dist_km"].round(1),
    })
    arestas["Source_label"] = arestas["Source"].map(nomes)
    arestas["Target_label"] = arestas["Target"].map(nomes)
    nos.to_csv(pasta_saida / f"gephi_nos_{identificador}.csv", index=False, encoding="utf-8-sig")
    arestas.to_csv(pasta_saida / f"gephi_arestas_{identificador}.csv", index=False, encoding="utf-8-sig")

    if "entradas" in municipios.columns:
        entradas = pd.to_numeric(municipios["entradas"], errors="coerce").fillna(0)
        candidatos = municipios[["cod", "nome"]].copy()
        candidatos["entradas"] = entradas.loc[candidatos.index]
        candidatos["Id"] = candidatos["cod"].astype(str).str.zfill(6)

        # Tipo 2: maiores polos do estado/recorte, sem balanceamento por comunidade.
        top20 = (candidatos[candidatos["entradas"] > 0]
                 .sort_values(["entradas", "nome", "Id"],
                              ascending=[False, True, True], kind="stable")
                 .head(quantidade_polos)["Id"])
        nos_top20 = nos.copy()
        nos_top20["Label"] = nos_top20["Label"].where(nos_top20["Id"].isin(set(top20)), "")
        nos_top20.to_csv(
            pasta_saida / f"gephi_nos_top20_{identificador}.csv",
            index=False, encoding="utf-8-sig",
        )
        arestas.to_csv(
            pasta_saida / f"gephi_arestas_top20_{identificador}.csv",
            index=False, encoding="utf-8-sig",
        )

        # Tipo 3: exatamente um representante por comunidade Louvain detectada.
        selecionados_comunidades = []
        if "comunidade" in municipios.columns:
            candidatos["comunidade"] = pd.to_numeric(
                municipios["comunidade"], errors="coerce"
            ).fillna(0).astype(int)
            comunidades = candidatos[candidatos["comunidade"] > 0]
            for _, membros in comunidades.groupby("comunidade", sort=True):
                representante = membros.sort_values(
                    ["entradas", "nome", "Id"], ascending=[False, True, True], kind="stable"
                ).iloc[0]
                selecionados_comunidades.append(representante["Id"])

        nos_comunidades = nos.copy()
        nos_comunidades["Label"] = nos_comunidades["Label"].where(
            nos_comunidades["Id"].isin(set(selecionados_comunidades)), ""
        )
        nos_comunidades.to_csv(
            pasta_saida / f"gephi_nos_polos_comunidades_{identificador}.csv",
            index=False, encoding="utf-8-sig",
        )
        arestas.to_csv(
            pasta_saida / f"gephi_arestas_polos_comunidades_{identificador}.csv",
            index=False, encoding="utf-8-sig",
        )


def grafico(res, arquivo, ordenar_por=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"[aviso] Matplotlib não está instalado; gráfico não gerado: {arquivo}")
        return
    if ordenar_por:
        res = res.sort_values(ordenar_por, ascending=False)
    campos = [("dist_mediana_km_quem_sai", "Distância mediana de quem se desloca (km)"),
              ("pct_fora_do_municipio", "% internados fora do município de residência"),
              ("pct_mais_de_60km", "% das internações a mais de 60 km")]
    altura = max(4.5, 0.45 * len(res) + 1.5)
    fig, eixos = plt.subplots(1, 3, figsize=(18, altura))
    for i, (ax, (campo, titulo)) in enumerate(zip(eixos, campos)):
        ax.barh(res.index, res[campo].astype(float))
        ax.set_title(titulo, fontsize=10)
        ax.invert_yaxis()
        if i > 0:
            ax.set_yticklabels([])
    plt.tight_layout()
    fig.savefig(arquivo, dpi=150)

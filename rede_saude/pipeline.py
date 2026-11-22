"""Orquestra a análise geral e a repetição para cada nicho solicitado."""

from pathlib import Path

import pandas as pd

from .config import (COL_FLUXOS, COL_HOSPITAIS, COL_METRICAS, COL_MUNICIPIOS,
                     COL_NOS_COMUNIDADE, COL_RESUMO_COMUNIDADES, ROTULO_COMPLEX)
from .dados import (carregar_coordenadas, carregar_nomes_cnes, ler_planilha, preparar,
                    rotular_capitulos)
from .grafo import (detectar_comunidades_louvain, haversine, hierarquia, interpretar_nicho,
                    metricas, montar_pares)
from .relatorios import (exportar_tabelas_gephi, grafico, salvar, tabela_diagnosticos,
                         tabela_hospitais, tabela_municipios)

def analisar(uf, ano, dados, saida, planilha_path, nichos, min_fluxo, cnes_arquivo=None,
             sem_nomes=False, excluir_proc=None, louvain_resolucao=1.0, louvain_semente=42):
    try:
        import networkx  # noqa: F401 - valida dependência antes de ler a base grande
    except ImportError as erro:
        raise RuntimeError("Para analisar com Louvain, instale as dependências: python -m pip install -r requirements.txt") from erro
    saida.mkdir(parents=True, exist_ok=True)
    pasta_gephi = saida / "gephi"
    coord = carregar_coordenadas(dados)
    nomes = coord.set_index("cod")["nome"]
    df = pd.read_csv(dados / f"rd_{uf}_{ano}.csv.gz", dtype=str)
    df = preparar(df, uf, coord)
    planilha = ler_planilha(planilha_path) if planilha_path else None

    # distancia de cada internacao (usada na tabela de hospitais)
    lat, lon = coord.set_index("cod")["lat"], coord.set_index("cod")["lon"]
    df["dist_km"] = haversine(df["MUNIC_RES"].map(lat).to_numpy(), df["MUNIC_RES"].map(lon).to_numpy(),
                              df["MUNIC_MOV"].map(lat).to_numpy(), df["MUNIC_MOV"].map(lon).to_numpy())
    if "COMPLEX" in df.columns:
        df["cx"] = df["COMPLEX"].str.zfill(2).map(ROTULO_COMPLEX)
    if "DIAG_PRINC" in df.columns:
        df["cap"] = rotular_capitulos(df["DIAG_PRINC"])

    def exportar_fluxos(p, caminho):
        p = p.assign(res_nome=p["res"].map(nomes), mov_nome=p["mov"].map(nomes),
                     dist_km=p["dist_km"].round(1))
        salvar(p, caminho, COL_FLUXOS)

    # A) Visao geral
    pares = montar_pares(df, coord)
    exportar_fluxos(pares, saida / "fluxos_geral.csv")               # lista de arestas (o grafo)
    resultados = {"Geral (todas as internações)": metricas(pares)}

    tamanho = (df.groupby("MUNIC_MOV")["VAL_TOT"].sum() if "VAL_TOT" in df.columns
               else df.groupby("MUNIC_MOV").size()).to_dict()
    hier = hierarquia(pares, tamanho, min_fluxo)
    tab = tabela_municipios(pares, coord, hier, planilha)
    tab, resumo_comunidades = detectar_comunidades_louvain(
        pares, tab, resolucao=louvain_resolucao, seed=louvain_semente
    )
    salvar(tab, saida / "municipios_geral.csv", COL_MUNICIPIOS)
    salvar(tab, saida / "municipios_comunidades_geral.csv", COL_NOS_COMUNIDADE)
    salvar(resumo_comunidades, saida / "comunidades_geral.csv", COL_RESUMO_COMUNIDADES)
    exportar_tabelas_gephi(pares, tab, coord, pasta_gephi, "geral")

    grupos_detectados = resumo_comunidades[resumo_comunidades["comunidade"] > 0]
    modularidade = (grupos_detectados["modularidade_global"].iloc[0]
                    if not grupos_detectados.empty else float("nan"))
    print(f"\nLouvain: {len(grupos_detectados)} comunidades com fluxo intermunicipal; "
          f"modularidade global = {modularidade:.4f}.")
    print("10 maiores polos comunitários por força de entrada:")
    print(grupos_detectados.sort_values("polo_entradas", ascending=False)[
        ["comunidade", "municipios", "polo_nome", "polo_entradas", "macro_dominante"]
    ].head(10).to_string(index=False))

    redes = hier[hier["nivel"] > 1].groupby("raiz").size().sort_values(ascending=False)
    print(f"\nHierarquia: {len(redes)} redes com subordinados. Maiores polos:")
    for raiz, k in redes.head(5).items():
        print(f"  {nomes[raiz]}: {k} municipios subordinados")
    print(f"Municipios sem recebimento intermunicipal registrado: "
          f"{(tab['recebeu_fluxos'] == 'Não').sum()} de {len(tab)}.")

    # B) Por complexidade (hipotese: mais complexo = mais deslocamento)
    if "cx" in df.columns:
        print("\nValores do campo COMPLEX encontrados:")
        print(df["COMPLEX"].value_counts().to_string())
        for rotulo, parte in df.dropna(subset=["cx"]).groupby("cx"):
            resultados[rotulo] = metricas(montar_pares(parte, coord))
        # Teste de robustez: refaz a comparacao sem certos procedimentos (ex.: --excluir-proc 0415)
        if excluir_proc and "PROC_REA" in df.columns:
            proc = df["PROC_REA"].str.strip().str.zfill(10)
            fora_do_teste = proc.str.startswith(tuple(excluir_proc))
            print(f"\nTeste de robustez: {fora_do_teste.sum()} internações "
                  f"({100 * fora_do_teste.mean():.1f}%) com procedimento iniciado em {', '.join(excluir_proc)} excluídas.")
            for rotulo, parte in df[~fora_do_teste].dropna(subset=["cx"]).groupby("cx"):
                resultados[f"{rotulo} (sem proc. {'/'.join(excluir_proc)})"] = metricas(montar_pares(parte, coord))
    else:
        print("\n[aviso] Coluna COMPLEX ausente: bloco de complexidade foi pulado.")

    # C) Por tipo de doenca (capitulo do CID-10)
    if "cap" in df.columns:
        diag = tabela_diagnosticos(df, coord)
        salvar(diag, saida / "por_tipo_de_doenca.csv", COL_METRICAS)
        grafico(diag.set_index("grupo"), saida / "por_tipo_de_doenca.png", ordenar_por="pct_mais_de_60km")

    # D) Por hospital (CNES)
    codigos = sorted(c.zfill(7) for c in df["CNES"].dropna().unique() if c) if "CNES" in df.columns else []
    nomes_cnes = carregar_nomes_cnes(uf, dados, codigos, cnes_arquivo, sem_nomes)
    hosp = tabela_hospitais(df, nomes, nomes_cnes)
    if hosp is not None:
        salvar(hosp, saida / "por_hospital.csv", COL_HOSPITAIS)
        cols = [c for c in ["cnes", "nome", "municipio", "internacoes", "pct_de_fora"] if c in hosp.columns]
        print("\nMaiores hospitais por nº de internações:")
        print(hosp.head(10)[cols].rename(columns=COL_HOSPITAIS).to_string(index=False))

    # E) Nichos (opcional, ex.: --nicho "Mama=C50")
    for item in nichos:
        nome, prefixos, nivel, slug, descricao_cid = interpretar_nicho(item)
        if "DIAG_PRINC" not in df.columns:
            raise ValueError("Não é possível analisar nichos: a coluna DIAG_PRINC não existe nos dados.")
        parte = df[df["DIAG_PRINC"].str.upper().str.startswith(prefixos)]
        if nivel:
            if "COMPLEX" not in parte.columns:
                raise ValueError(f"O nicho '{nome}' pede complexidade, mas a coluna COMPLEX não existe.")
            parte = parte[parte["COMPLEX"].str.zfill(2) == nivel.strip().zfill(2)]
            print(f"\nNicho {nome} (CID {descricao_cid}, complexidade {nivel}): {len(parte)} internações.")
        elif "cx" in parte.columns and len(parte):
            mix = (parte["cx"].value_counts(normalize=True) * 100).round(1)
            print(f"\nNicho {nome} (CID {descricao_cid}): {len(parte)} internações. Complexidade: "
                  + ", ".join(f"{k} {v}%" for k, v in mix.items()))
        if parte.empty:
            print(f"\n[aviso] Nicho '{nome}': nenhuma internacao com CID {descricao_cid}.")
            continue
        p_n = montar_pares(parte, coord)
        resultados[f"Nicho: {nome}"] = metricas(p_n)
        exportar_fluxos(p_n, saida / f"fluxos_nicho_{slug}.csv")
        tam_n = (parte.groupby("MUNIC_MOV")["VAL_TOT"].sum().to_dict() if "VAL_TOT" in parte
                 else parte.groupby("MUNIC_MOV").size().to_dict())
        h_n = hierarquia(p_n, tam_n, min_fluxo)
        tab_n = tabela_municipios(p_n, coord, h_n, planilha)
        tab_n, resumo_n = detectar_comunidades_louvain(
            p_n, tab_n, resolucao=louvain_resolucao, seed=louvain_semente
        )
        salvar(tab_n, saida / f"municipios_nicho_{slug}.csv", COL_MUNICIPIOS)
        salvar(tab_n, saida / f"municipios_comunidades_nicho_{slug}.csv", COL_NOS_COMUNIDADE)
        salvar(resumo_n, saida / f"comunidades_nicho_{slug}.csv", COL_RESUMO_COMUNIDADES)
        exportar_tabelas_gephi(p_n, tab_n, coord, pasta_gephi, f"nicho_{slug}")

    # Resultado final
    res = pd.DataFrame(resultados).T
    res.index.name = "grupo"
    res["internacoes"] = res["internacoes"].astype(int)
    res["pct_do_total"] = (100 * res["internacoes"] / res["internacoes"].iloc[0]).round(1)
    salvar(res.reset_index(), saida / "comparacao.csv", COL_METRICAS)
    grafico(res, saida / "comparacao.png")
    print("\n=== COMPARACAO DO DESLOCAMENTO ===")
    print(res.reset_index().rename(columns=COL_METRICAS).to_string(index=False))
    print(f"\nArquivos gerados em: {saida}/")

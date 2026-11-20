"""Constantes, códigos e nomes padronizados das colunas."""

FTP_HOST = "ftp.datasus.gov.br"


FTP_PASTAS = ["/dissemin/publicos/SIHSUS/200801_/Dados", "/dissemin/publicos/SIHSUS/200801_"]


URL_CNES = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/{}"   # nome do hospital pelo codigo CNES


COLUNAS = ["N_AIH", "IDENT", "MUNIC_RES", "MUNIC_MOV", "DIAG_PRINC",
           "PROC_REA", "COMPLEX", "VAL_TOT", "CNES"]


COD_UF = {"RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16",
          "TO": "17", "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25",
          "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
          "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50",
          "MT": "51", "GO": "52", "DF": "53"}


ROTULO_COMPLEX = {"01": "Básica complexidade", "02": "Média complexidade", "03": "Alta complexidade"}


CAPITULOS = {
    "I": "Doenças infecciosas e parasitárias",
    "II": "Neoplasias (tumores)",
    "III": "Doenças do sangue e do sistema imunitário",
    "IV": "Doenças endócrinas, nutricionais e metabólicas",
    "V": "Transtornos mentais e comportamentais",
    "VI": "Doenças do sistema nervoso",
    "VII": "Doenças do olho e anexos",
    "VIII": "Doenças do ouvido",
    "IX": "Doenças do aparelho circulatório",
    "X": "Doenças do aparelho respiratório",
    "XI": "Doenças do aparelho digestivo",
    "XII": "Doenças da pele",
    "XIII": "Doenças do sistema osteomuscular",
    "XIV": "Doenças do aparelho geniturinário",
    "XV": "Gravidez, parto e puerpério",
    "XVI": "Afecções do período perinatal",
    "XVII": "Malformações congênitas",
    "XVIII": "Sintomas e achados anormais",
    "XIX": "Lesões, envenenamentos e outras causas externas",
    "XX": "Causas externas de morbidade",
    "XXI": "Fatores que influenciam o estado de saúde",
}


COL_FLUXOS = {
    "res_nome": "Município de residência (onde o paciente mora)",
    "mov_nome": "Município de internação (onde foi internado)",
    "n": "Nº de internações",
    "dist_km": "Distância em linha reta (km)",
    "res": "Código do município de residência",
    "mov": "Código do município de internação",
}


COL_MUNICIPIOS = {
    "nome": "Município",
    "cod": "Código do município (SUS, 6 dígitos)",
    "micro": "Microrregião de saúde",
    "macro": "Macrorregião de saúde",
    "pop": "População (IBGE 2025)",
    "internacoes": "Internações de moradores do município",
    "locais": "Internações realizadas no próprio município",
    "fora": "Internações intermunicipais de moradores do município",
    "entradas": "Internações intermunicipais recebidas pelo município",
    "saidas_por_1000hab": "Saídas intermunicipais por 1.000 habitantes",
    "entradas_por_1000hab": "Entradas intermunicipais por 1.000 habitantes",
    "pct_fora": "% das internações feitas fora do município",
    "dist_media_km": "Distância média percorrida até o hospital (km; internação local conta 0 km)",
    "dist_media_quem_sai_km": "Distância média das internações fora do município (km)",
    "dificuldade_acesso_distancia": "Faixa de distância média no recorte",
    "limite_q75_dist_media_km": "Limite para maiores distâncias no recorte (km)",
    "internacoes_por_1000hab": "Internações por 1.000 habitantes",
    "recebeu_fluxos": "Recebeu internações de outros municípios neste recorte?",
    "comunidade": "Comunidade detectada pelo Louvain",
    "nivel": "Nível na hierarquia (1 = polo independente)",
    "chefe_nome": "Município polo imediato (superior na hierarquia)",
    "raiz_nome": "Polo principal da rede (topo da hierarquia)",
    "chefe": "Código do município polo imediato",
    "raiz": "Código do polo principal",
}


COL_NOS_COMUNIDADE = {
    "cod": "Código SUS do município",
    "nome": "Município",
    "comunidade": "Comunidade Louvain",
    "micro": "Microrregião de saúde",
    "macro": "Macrorregião de saúde",
    "pop": "População (IBGE 2025)",
    "fora": "Força de saída intermunicipal (internações)",
    "entradas": "Força de entrada intermunicipal (internações)",
    "saidas_por_1000hab": "Saídas por 1.000 habitantes",
    "entradas_por_1000hab": "Entradas por 1.000 habitantes",
}


COL_RESUMO_COMUNIDADES = {
    "comunidade": "Comunidade Louvain (0 = sem fluxo intermunicipal)",
    "municipios": "Número de municípios",
    "populacao": "População somada (IBGE 2025)",
    "polo_nome": "Polo com maior força de entrada",
    "polo_entradas": "Internações intermunicipais recebidas pelo polo",
    "entradas_totais": "Entradas intermunicipais dos municípios do grupo",
    "saidas_totais": "Saídas intermunicipais dos municípios do grupo",
    "fluxos_internos": "Internações entre municípios da mesma comunidade",
    "fluxos_externos": "Internações entre municípios do grupo e outros grupos",
    "macro_dominante": "Macrorregião mais frequente",
    "pct_macro_dominante": "% dos municípios na macrorregião mais frequente",
    "micro_dominante": "Microrregião mais frequente",
    "pct_micro_dominante": "% dos municípios na microrregião mais frequente",
    "modularidade_global": "Modularidade global da rede",
}


COL_METRICAS = {
    "grupo": "Grupo analisado",
    "internacoes": "Nº de internações",
    "pct_do_total": "% do total de internações",
    "pct_fora_do_municipio": "% internados fora do município de residência",
    "dist_media_km_quem_sai": "Distância média de quem se desloca (km)",
    "dist_mediana_km_quem_sai": "Distância mediana de quem se desloca (km)",
    "pct_mais_de_60km": "% das internações a mais de 60 km",
    "pct_mais_de_100km": "% das internações a mais de 100 km",
}


COL_HOSPITAIS = {
    "cnes": "Código do hospital (CNES)",
    "nome": "Nome do hospital (nome fantasia no CNES)",
    "municipio": "Município do hospital",
    "internacoes": "Internações no hospital",
    "pct_de_fora": "% de pacientes vindos de outros municípios",
    "municipios_origem": "Nº de municípios de onde vêm os pacientes",
    "dist_media_de_fora": "Distância média dos pacientes de outros municípios (km)",
    "pct_alta": "% de internações de alta complexidade",
    "cap_principal": "Tipo de doença mais frequente (capítulo do CID-10)",
    "pct_cap_principal": "% das internações do hospital nesse tipo de doença",
}

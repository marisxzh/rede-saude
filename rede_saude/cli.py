"""Interface de linha de comando do projeto."""

import argparse
import time
from pathlib import Path

from .dados import baixar
from .pipeline import analisar


def criar_parser():
    """Define os comandos e argumentos aceitos pelo programa."""
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("comando", choices=["baixar", "analisar"])
    ap.add_argument("--uf", default="MG")
    ap.add_argument("--ano", type=int, default=2025)
    ap.add_argument("--dados", default="dados", help="pasta dos dados baixados")
    ap.add_argument("--saida", default="saida", help="pasta dos resultados")
    ap.add_argument("--planilha", help="Planilha de Regionalização, opcional")
    ap.add_argument(
        "--nicho", action="append", default=[],
        help='ex.: --nicho "Mama=C50"; aceita vários CIDs e intervalos, '
             'como "Neoplasias=C,D00-D48"; complexidade opcional: "Neoplasias_Alta=C,D00-D48@03"',
    )
    ap.add_argument(
        "--cnes-nomes",
        help="planilha/CSV opcional com códigos CNES e nomes dos hospitais",
    )
    ap.add_argument(
        "--min-fluxo", type=int, default=2,
        help="fluxo mínimo usado na hierarquia dominante (padrão 2)",
    )
    ap.add_argument(
        "--louvain-resolucao", type=float, default=1.0,
        help="resolução Louvain; valores maiores tendem a gerar comunidades menores",
    )
    ap.add_argument(
        "--louvain-semente", type=int, default=42,
        help="semente aleatória para tornar a partição reproduzível",
    )
    ap.add_argument(
        "--excluir-proc", action="append", default=[],
        help="prefixo de procedimento excluído no teste de robustez (pode repetir)",
    )
    ap.add_argument(
        "--sem-nomes", action="store_true",
        help="não consulta a API do CNES para nomes de hospitais",
    )
    return ap


def formatar_tempo(segundos):
    """Formata segundos como HH:MM:SS.ss."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    resto = segundos % 60
    return f"{horas:02d}:{minutos:02d}:{resto:05.2f}"


def main(argv=None):
    args = criar_parser().parse_args(argv)
    inicio = time.perf_counter()
    try:
        pasta_dados = Path(args.dados)
        pasta_saida = Path(args.saida)
        if args.comando == "baixar":
            pasta_dados.mkdir(parents=True, exist_ok=True)
            baixar(args.uf.upper(), args.ano, pasta_dados)
        else:
            analisar(
                args.uf.upper(), args.ano, pasta_dados, pasta_saida,
                args.planilha, args.nicho, args.min_fluxo, args.cnes_nomes,
                args.sem_nomes, args.excluir_proc,
                args.louvain_resolucao, args.louvain_semente,
            )
    finally:
        decorrido = time.perf_counter() - inicio
        print(f"\nTempo total de execução (HH:MM:SS.ss): {formatar_tempo(decorrido)}")

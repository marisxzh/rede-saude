"""Gera a tabela municipal usada pelo projeto a partir dos KMLs do IBGE.

Uso:
    python scripts/gerar_coordenadas_ibge.py CAMINHO/PARA/Localidades_Municipios_kml/kml

O caminho pode apontar para a pasta extraída ou para um ZIP com os KMLs.
"""

import argparse
import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


KML_NS = "{http://www.opengis.net/kml/2.2}"


def _valor(placemark, nome):
    for item in placemark.iter(f"{KML_NS}SimpleData"):
        if item.attrib.get("name") == nome:
            return (item.text or "").strip()
    return ""


def _linhas_kml(conteudo, origem):
    raiz = ET.fromstring(conteudo)
    for pasta in raiz.iter(f"{KML_NS}Folder"):
        if "Sede Municipal" not in pasta.attrib.get("id", ""):
            continue
        for ponto in pasta.iter(f"{KML_NS}Placemark"):
            codigo = _valor(ponto, "CD_MUN")
            nome = _valor(ponto, "NM_MUN")
            lat = _valor(ponto, "LAT_LOCALIDADE")
            lon = _valor(ponto, "LONG_LOCALIDADE")
            if codigo and nome and lat and lon:
                yield codigo, nome, lat, lon, origem


def gerar(entrada, saida):
    pasta = Path(entrada)
    registros = {}

    if pasta.is_dir():
        arquivos = pasta.rglob("*.kml")
        for arquivo in arquivos:
            for codigo, nome, lat, lon, origem in _linhas_kml(
                arquivo.read_bytes(), str(arquivo)
            ):
                if codigo in registros:
                    raise ValueError(f"Código municipal repetido: {codigo}")
                registros[codigo] = (codigo, nome, lat, lon)
    elif zipfile.is_zipfile(pasta):
        with zipfile.ZipFile(pasta) as arquivo_zip:
            nomes = (n for n in arquivo_zip.namelist() if n.lower().endswith(".kml"))
            for nome_arquivo in nomes:
                for codigo, nome, lat, lon, origem in _linhas_kml(
                    arquivo_zip.read(nome_arquivo), nome_arquivo
                ):
                    if codigo in registros:
                        raise ValueError(f"Código municipal repetido: {codigo}")
                    registros[codigo] = (codigo, nome, lat, lon)
    else:
        raise FileNotFoundError(f"Entrada não encontrada ou não é ZIP: {pasta}")

    if not registros:
        raise ValueError("Nenhuma Sede Municipal com coordenadas foi encontrada.")

    codigos_invalidos = [cod for cod in registros if not re.fullmatch(r"\d{7}", cod)]
    if codigos_invalidos:
        raise ValueError(f"Códigos IBGE inesperados: {codigos_invalidos[:5]}")

    destino = Path(saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["codigo_ibge", "nome", "latitude", "longitude"])
        escritor.writerows(registros[cod] for cod in sorted(registros))
    return len(registros)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", help="Pasta de KMLs ou arquivo ZIP do IBGE")
    parser.add_argument(
        "--saida", default="dados/municipios_coord.csv", help="CSV de saída"
    )
    args = parser.parse_args()
    total = gerar(args.entrada, args.saida)
    print(f"Salvo {args.saida}: {total} sedes municipais do IBGE.")


if __name__ == "__main__":
    main()

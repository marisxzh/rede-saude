# Guia do código de fluxos de saúde

## Objetivo

O `fluxos_saude.py` transforma registros de internação do SIH-SUS em uma análise dos deslocamentos entre municípios. Ele sempre processa a base geral; com `--nicho`, repete a análise para um ou mais recortes diagnósticos e/ou níveis de complexidade.

O código não desenha o grafo. Ele constrói e analisa a rede como dados e salva tabelas. Os arquivos `gephi_nos_*.csv` e `gephi_arestas_*.csv` podem ser importados no Gephi para criar a ilustração da rede.

## Como o problema vira um grafo

- **Nó:** município, identificado pelo código SUS de seis dígitos.
- **Aresta direcionada:** município onde o paciente reside → município onde ocorreu a internação.
- **Peso da aresta:** número de internações observadas naquele par de municípios.
- **Atributo da aresta:** distância em linha reta, em quilômetros, entre as coordenadas dos municípios.
- **Atributos do nó:** nome, população, microrregião, macrorregião, coordenadas, comunidade Louvain e volumes/taxas de entrada e saída intermunicipais.

Essa modelagem mantém separadas duas informações: a ligação representa o fluxo observado e a distância descreve a separação geográfica entre os municípios. A distância não é uma estimativa de rota ou tempo de viagem por estrada.

## Como o programa está organizado

O programa foi separado em módulos por responsabilidade. O comando continua sendo executado por `fluxos_saude.py`, que encaminha a execução para o pacote `rede_saude`:

- `rede_saude/config.py`: códigos, URLs e nomes das colunas.
- `rede_saude/dados.py`: leitura, download e preparação dos dados, coordenadas, regionalização e códigos CID.
- `rede_saude/grafo.py`: agregação das arestas, distâncias, métricas, hierarquia de fluxo e Louvain.
- `rede_saude/relatorios.py`: tabelas analíticas, gráficos e exportação dos arquivos para o Gephi.
- `rede_saude/pipeline.py`: coordena a análise geral e repete o processo para cada nicho informado.
- `rede_saude/cli.py`: argumentos de terminal e contador de tempo total.
- `fluxos_saude.py`: ponto de entrada compatível com os comandos já usados.

Essa separação deixa cada módulo concentrado em uma parte do trabalho. Os dados e os algoritmos continuam os mesmos; o pipeline faz as partes executarem na ordem correta.

O programa mostra o tempo total decorrido no final, no formato `HH:MM:SS.ss`. O contador inclui o comando completo de análise ou download.

As etapas da análise são:

1. **Leitura e preparação:** carrega os dados do ano e estado escolhidos; mantém AIHs normais, residentes da UF e códigos de município válidos.
2. **Coordenadas e regionalização:** carrega coordenadas municipais e, quando informada, a planilha de população, microrregião e macrorregião.
3. **Agregação dos fluxos:** `montar_pares` agrupa as internações por município de residência e município de internação. Cada par vira uma aresta com contagem e distância.
4. **Métricas de deslocamento e dificuldade de acesso:** `metricas` calcula total de internações, percentual realizado fora do município, média e mediana ponderadas entre quem se deslocou, e proporções acima de 60 km e 100 km. No resumo municipal, `dist_media_km` é a distância média por internação de residentes, contando internações locais como 0 km; `dist_media_quem_sai_km` considera somente as internações feitas fora do município. A coluna `dificuldade_acesso_distancia` marca como `Maiores distâncias` os municípios cuja distância média por internação está entre as maiores (igual ou acima do percentil 75) dos municípios com internações no mesmo recorte; os demais são identificados como `Demais municípios`. `limite_q75_dist_media_km` registra um único ponto de corte em quilômetros para cada recorte analisado. Essa classificação é relativa aos municípios de Minas Gerais e ao recorte analisado, e indica maior distância observada, não falta de serviço ou demanda não atendida. Distâncias são em linha reta, não rotas rodoviárias.
5. **Forças e taxas:** as saídas e entradas intermunicipais são somas dos pesos das arestas que saem/chegam a cada município. Arestas locais são excluídas dessas medidas, pois não representam deslocamento entre municípios. O código divide os volumes pela população e multiplica por 1.000; os totais absolutos também são preservados.
6. **Comunidades Louvain:** `detectar_comunidades_louvain` constrói o grafo direcionado ponderado dos fluxos e uma projeção não direcionada para o algoritmo. Na projeção, o peso entre dois municípios é a soma dos fluxos nos dois sentidos; laços locais são excluídos. NetworkX executa Louvain com peso de internações. A semente padrão 42 torna a execução reproduzível na mesma versão/configuração. A resolução padrão 1.0 controla o tamanho dos grupos; valores maiores tendem a produzir grupos menores.
7. **Polos e regionalização:** dentro de cada comunidade, o polo é o município com maior força de entrada intermunicipal. O resumo mostra também as macrorregiões e microrregiões mais frequentes e a porcentagem de municípios que pertencem à região dominante. Essa porcentagem permite comparar comunidades encontradas pelo algoritmo com as divisões oficiais.
8. **Distância e complexidade:** além da base geral, o programa calcula médias/medianas ponderadas e proporções acima de 60 km e 100 km para complexidades e nichos. A distância permanece como atributo de fluxo; ela não é usada como peso do Louvain. Neoplasias aceita `C,D00-D48`, correspondente ao capítulo II classificado no código.
9. **Hierarquia complementar:** a hierarquia de fluxo dominante já existente continua sendo exportada como análise complementar; a detecção de comunidades passa a ser o algoritmo central para esse novo objetivo.
10. **Exportação:** grava CSVs analíticos e dois CSVs para o Gephi: nós (`Id`, `Label`) e arestas (`Source`, `Target`, `Weight`). Mantém laços locais no arquivo de visualização, embora o Louvain não os use.

## Por que usar essa abordagem

O grafo representa diretamente os deslocamentos que aparecem no SIH-SUS, sem inventar ligações entre municípios. A força de saída mede o volume de internações de residentes realizadas fora; a força de entrada mede o volume de internações recebido de outros municípios. As taxas por mil habitantes ajudam a comparar municípios de tamanhos diferentes. Louvain agrupa municípios pela intensidade de intercâmbio, e a força de entrada aponta o polo dentro de cada grupo.

O grafo de fluxos continua direcionado para medir entradas e saídas. A projeção não direcionada é usada somente para detectar comunidades que trocam pacientes nos dois sentidos. As internações SIH-SUS não necessariamente equivalem a pessoas únicas. “Saída” é aqui uma internação de residente em outro município; “entrada” é uma internação no município de alguém residente fora. Os resultados não medem diretamente oferta total, necessidade de atendimento, capacidade hospitalar ou acessibilidade por estrada.

## Como executar

Na pasta do projeto, para analisar a base geral de Minas Gerais em 2025:

```bash
python3 fluxos_saude.py analisar \
  --uf MG \
  --ano 2025 \
  --dados dados \
  --saida saida_geral \
  --planilha Planilha-de-Regionalizacao_Versao-2026.xlsx \
  --sem-nomes
```

Para repetir a análise geral e também analisar neoplasias em alta e média complexidade:

```bash
python3 fluxos_saude.py analisar \
  --uf MG \
  --ano 2025 \
  --dados dados \
  --saida saida_neoplasias \
  --planilha Planilha-de-Regionalizacao_Versao-2026.xlsx \
  --sem-nomes \
  --nicho "Neoplasias=C,D00-D48" \
  --nicho "Neoplasias_Alta=C,D00-D48@03" \
  --nicho "Neoplasias_Media=C,D00-D48@02"
```

`C,D00-D48` seleciona o capítulo CID de neoplasias adotado pelo código: códigos começados por C e códigos D00 a D48. O filtro aceita prefixos e intervalos CID. `@03` seleciona alta complexidade e `@02`, média. Para outro recorte, informe outro prefixo, por exemplo `Mama=C50` ou múltiplos prefixos separados por vírgula, como `Pulmao=C33,C34`. É possível repetir `--nicho` quantas vezes forem necessárias.

O limite padrão `--min-fluxo 2` é aplicado igualmente à hierarquia geral e às hierarquias dos nichos. Ele não remove as internações dos CSVs de fluxo nem altera as métricas de distância; só evita que uma ligação baseada em uma internação isolada determine a hierarquia.

O Louvain inclui todos os fluxos intermunicipais agregados, mesmo os de uma internação, pois o peso reduz a influência de ligações fracas. `--louvain-resolucao 1.0` e `--louvain-semente 42` são os padrões; registre esses valores ao relatar os resultados.

## Arquivos gerados

Na pasta indicada por `--saida`:

- `fluxos_geral.csv` e `municipios_geral.csv`: fluxos e resumo municipal da base geral.
- `comparacao.csv`: métricas da base geral, por complexidade, por nicho e demais grupos calculados.
- `por_tipo_de_doenca.csv` e `por_hospital.csv`: resumos da base geral.
- `fluxos_nicho_<nome>.csv` e `municipios_nicho_<nome>.csv`: tabelas de cada nicho.
- `municipios_comunidades_geral.csv` e `comunidades_geral.csv`: comunidade de cada município e resumo de cada grupo, incluindo polo e compatibilidade com regiões oficiais.
- `municipios_comunidades_nicho_<nome>.csv` e `comunidades_nicho_<nome>.csv`: mesmos resultados para cada nicho.
- Na subpasta `gephi/`: `gephi_nos_geral.csv` e `gephi_arestas_geral.csv`, com nós e arestas da base geral.
- Na subpasta `gephi/`: `gephi_nos_nicho_<nome>.csv` e `gephi_arestas_nicho_<nome>.csv`, com nós e arestas de cada nicho.
- Para cada identificador geral ou nicho, também são gerados dois pares especializados: `gephi_nos_top20_<identificador>.csv` e `gephi_arestas_top20_<identificador>.csv` deixam rótulos apenas nos 20 municípios com mais entradas intermunicipais (ou em menos, se o recorte tiver menos de 20 municípios com entradas); `gephi_nos_polos_comunidades_<identificador>.csv` e `gephi_arestas_polos_comunidades_<identificador>.csv` deixam exatamente um rótulo por comunidade Louvain detectada, escolhendo o município com maior entrada dentro de cada grupo. Os três tipos mantêm todos os nós e fluxos; os arquivos gerais continuam com o nome de todos os municípios.
- Gráficos PNG são gerados quando Matplotlib está instalado. A falta dele não impede a análise nem a exportação dos CSVs.

No resumo municipal, a classificação de distância usa apenas `dist_media_km` — a distância média por internação de residentes, com internações locais contando como zero. `Maiores distâncias` identifica os municípios com médias iguais ou acima do percentil 75 do recorte, sujeito a empates no ponto de corte; os demais aparecem como `Demais municípios`. Há um único limiar em quilômetros para cada recorte, registrado na coluna `limite_q75_dist_media_km`. Municípios sem internações no recorte ficam sem classificação. Essa medida representa distância observada em linha reta e não deve ser interpretada como tempo de viagem, distância por estrada ou prova de ausência de oferta.

No Gephi, abra a subpasta `gephi/` dentro da pasta indicada por `--saida` e importe o par de nós e arestas com o mesmo identificador. Use `gephi_nos_<identificador>.csv` com `gephi_arestas_<identificador>.csv` para a rede completa; o par com `top20` para os 20 maiores polos; ou o par com `polos_comunidades` para um polo de cada comunidade. Escolha `Source` e `Target` como origem e destino, marque o grafo como direcionado e use `Weight` como peso. A posição visual gerada por um layout do Gephi não é um mapa geográfico; Latitude e Longitude são atributos para eventual uso em uma visualização geográfica apropriada.

## Dependências

Instale as dependências com `python3 -m pip install -r requirements.txt`. `networkx` fornece a implementação Louvain; `openpyxl` lê a planilha Excel; `matplotlib` gera gráficos PNG; `datasus-dbc` e `dbfread` são usados pelo comando opcional `baixar`.


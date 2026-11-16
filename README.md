# Preços de revenda de combustíveis no Brasil (2001–2023)

**Evolução, desigualdade regional e paridade etanol/gasolina — uma análise reprodutível dos dados da ANP**

![Licença do código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-1e3a8a)
![Licença dos dados e do texto: CC BY 4.0](https://img.shields.io/badge/dados%20e%20texto-CC%20BY%204.0-1e3a8a)
![Python 3.13](https://img.shields.io/badge/python-3.13-1e3a8a)
![pandas 3.0.5](https://img.shields.io/badge/pandas-3.0.5-1e3a8a)
![FAIR](https://img.shields.io/badge/ci%C3%AAncia%20aberta-FAIR-1e3a8a)

| | |
|---|---|
| **Autores** | Luan Fernando, Miguel Marreiros |
| **Instituição** | [Nome da Instituição] — Bacharelado em Sistemas de Informação |
| **Disciplina** | Linguagem de Programação VI — Análise e Visualização de Dados com Python (6º período) |
| **Semestre** | [Semestre] |
| **Artigo (GitHub Pages)** | <https://luanfernand0.github.io/precos-combustiveis-brasil/> |
| **Fonte original dos dados** | <https://www.kaggle.com/datasets/fidelissauro/combustiveis-brasil> (dado primário: ANP) |

## Resumo executivo

Este repositório contém o Projeto Final da disciplina: um pipeline determinístico em Python que trata 258 meses
(julho/2001 a janeiro/2023) de preços nominais de revenda de sete combustíveis — nos recortes Brasil, regiões e
estados — e um artigo acadêmico em HTML que comunica os resultados.

**Perguntas de pesquisa e principais achados**

| | Pergunta | Achado central |
|---|---|---|
| **RQ1** | Como evoluíram os preços e quando se concentram os choques? | Os preços mudam em degraus; os meses atípicos da gasolina concentram-se em 2001–2005 e 2020–2022 (27 de 39). O maior movimento da gasolina é a queda de 16,6 % em julho/2022. O diesel foi o que mais encareceu (+663 %) e ultrapassou a gasolina em 2022. |
| **RQ2** | Qual a magnitude e a persistência da desigualdade entre estados? | Moderada para gasolina e diesel (CV de 5–6 %), cerca do dobro para etanol e GLP (9–11 %). O Acre teve a gasolina mais cara em 75 % dos meses; São Paulo e Paraná ficam na base. |
| **RQ3** | Onde e quando o etanol compensa frente à gasolina (razão ≤ 0,70)? | Em 69 % dos meses na média nacional, mas em só 30 % das observações estaduais — concentradas em MT, SP, GO e PR. A competitividade piorou a partir de 2011 e é maior na safra (jun–set). |

**Palavras-chave:** preços de combustíveis; ANP; análise exploratória de dados; pandas; paridade etanol-gasolina; princípios FAIR.

## Estrutura do repositório

```
precos-combustiveis-brasil/
├── README.md                    # este arquivo
├── LICENSE                      # MIT (código)
├── LICENSE-DATA.md              # CC BY 4.0 (dados tratados e texto) + licença dos dados brutos
├── CITATION.cff                 # metadados de citação
├── requirements.txt             # dependências com versões fixadas
├── .gitignore / .gitattributes
│
├── data/
│   ├── raw/                     # 3 CSVs originais (1,1 MB), nunca editados + README com SHA-256
│   ├── processed/
│   │   ├── precos_combustiveis.csv.gz        # 44.798 linhas — formato longo (tidy)
│   │   ├── paridade_etanol_gasolina.csv.gz   # 8.498 linhas — razão etanol/gasolina
│   │   └── relatorio_qualidade.json          # auditoria do ETL
│   └── data_dictionary.md       # dicionário de variáveis (FAIR)
│
├── notebooks/
│   └── analise_exploratoria.ipynb   # exploração, validação do ETL e protótipos dos gráficos
│
├── src/
│   ├── __init__.py
│   ├── etl.py                   # extract → transform → load
│   ├── analise.py               # agregações e métricas reutilizáveis
│   └── figuras.py               # figuras estáticas + dados dos gráficos interativos
│
└── docs/                        # artigo publicado via GitHub Pages
    ├── index.html
    └── assets/                  # PNGs, dados_graficos.js, numeros_chave.json
```

## Como reproduzir

Pré-requisitos: Git e Python 3.13. Nenhuma credencial é necessária — os dados brutos acompanham o repositório.

```bash
git clone https://github.com/LuanFernand0/precos-combustiveis-brasil.git
cd precos-combustiveis-brasil

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.etl                  # data/raw  ->  data/processed
python -m src.figuras              # data/processed  ->  docs/assets
```

Saída esperada do ETL:

```
INFO  extraído combustiveis-brasil.csv    258 linhas × 24 colunas
INFO  extraído combustiveis-regioes.csv  1290 linhas × 25 colunas
INFO  extraído combustiveis-estados.csv  6966 linhas × 26 colunas
INFO  chaves órfãs: 16 encontradas, 16 recuperadas, 0 descartadas
INFO  formato longo: 44798 observações (células vazias omitidas: 14800)
INFO  inconsistências mín ≤ média ≤ máx: 0
INFO  gravado precos_combustiveis.csv.gz            44798 linhas
INFO  gravado paridade_etanol_gasolina.csv.gz        8498 linhas
INFO  gravado relatorio_qualidade.json
INFO  concluído: 2001-07 a 2023-01, 258 meses
```

Para abrir o notebook, instale o Jupyter no mesmo ambiente (`pip install notebook`) e execute
`jupyter notebook notebooks/analise_exploratoria.ipynb`. Para ver o artigo localmente, abra `docs/index.html` no navegador.

## O que o pipeline faz

1. **Leitura tipada e integridade** — codificação, separador e tipos declarados; SHA-256 e esquema conferidos.
2. **Recuperação de chaves órfãs** — 16 linhas do arquivo de estados vêm sem mês e sem UF; são reatribuídas ao Amapá por uma regra determinística (mês da linha anterior + única UF ausente no mês) e marcadas com `chave_recuperada`.
3. **Normalização** — região e UF com nome oficial e sigla.
4. **Formato longo** — uma linha por nível geográfico × local × mês × combustível.
5. **Ausentes** — nenhum preço é imputado; ausências estruturais não geram registro e são contabilizadas.
6. **Métricas derivadas** — amplitude, variação mensal e em 12 meses (por calendário, pois setembro/2020 não foi pesquisado), razão etanol/gasolina.
7. **Auditoria** — tudo o que foi recuperado, omitido ou sinalizado fica em `data/processed/relatorio_qualidade.json`.

Detalhes de cada variável: [`data/data_dictionary.md`](data/data_dictionary.md).

## Princípios FAIR

| Princípio | Como é atendido |
|---|---|
| **Findable** | README com resumo, palavras-chave e link perene da fonte; autoria, disciplina, semestre e instituição no cabeçalho dos artefatos; `CITATION.cff` e metadados *schema.org* no artigo |
| **Accessible** | Repositório público; dados brutos incluídos; nenhum passo exige autenticação; artigo no GitHub Pages, responsivo |
| **Interoperable** | `data/data_dictionary.md`; dados tratados em `.csv.gz` (UTF-8) e relatório em JSON; datas ISO 8601; siglas oficiais de UF |
| **Reusable** | MIT (código) e CC BY 4.0 (dados tratados e texto); proveniência documentada; `requirements.txt` com versões fixadas; pipeline determinístico |

## Limitações

Preços **nominais** (sem correção pela inflação); base agregada por terceiros e encerrada em janeiro/2023; análise descritiva, sem inferência causal. Ver Seção 4 do artigo.

## Licenças

- Código: [MIT](LICENSE)
- Dados tratados, figuras e texto: [CC BY 4.0](LICENSE-DATA.md)
- Dados brutos: ANP (dados abertos) / Matheus Fidelis — Economia Popular (CDLA-Permissive-1.0)

## Como citar

> FERNANDO, Luan; MARREIROS, Miguel. **Preços de revenda de combustíveis no Brasil (2001–2023)**: evolução, desigualdade regional e paridade etanol/gasolina. [Cidade]: [Nome da Instituição], 2026. Disponível em: https://github.com/LuanFernand0/precos-combustiveis-brasil.

## Referência dos dados

- ANP — Série histórica do levantamento de preços: <https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/serie-historica-do-levantamento-de-precos>
- FIDELIS, Matheus. *Preços de Combustíveis Brasil*. Kaggle, 2023: <https://www.kaggle.com/datasets/fidelissauro/combustiveis-brasil>

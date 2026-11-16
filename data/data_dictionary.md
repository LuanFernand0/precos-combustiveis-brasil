# Dicionário de dados

**Projeto:** Preços de revenda de combustíveis no Brasil (2001–2023): evolução, desigualdade regional e paridade etanol/gasolina
**Disciplina:** Linguagem de Programação (Análise e Visualização de Dados com Python) (6º período, Sistemas de Informação)
**Autores:** Luan Fernando, Miguel Marreiros — UniLaSalle Rio de Janeiro, 2026.2

Este documento descreve todas as variáveis dos dados brutos (`data/raw/`) e dos dados tratados (`data/processed/`).

## 1. Metadados gerais

| Item | Descrição |
|---|---|
| Fonte primária | ANP — Levantamento de Preços de Combustíveis (LPC), pesquisa semanal de preços de revenda em postos e revendas de GLP |
| Fonte de acesso | Kaggle, *Preços de Combustíveis Brasil* (Matheus Fidelis / Economia Popular): <https://www.kaggle.com/datasets/fidelissauro/combustiveis-brasil> |
| Cobertura temporal | julho/2001 a janeiro/2023 (258 meses; setembro/2020 não foi pesquisado pela ANP) |
| Cobertura geográfica | Brasil, 5 grandes regiões e 27 unidades da federação |
| Granularidade | 1 registro por **mês × local × combustível** |
| Unidade monetária | Reais correntes (R$ **nominais**, sem correção pela inflação) |
| Codificação dos arquivos | UTF-8; separador `,`; decimal `.`; quebra de linha LF |
| Valores ausentes | Campo vazio nos CSVs |
| Licenças | Código: MIT · Dados tratados e texto: CC BY 4.0 · Dados brutos: CDLA-Permissive-1.0 (ver `LICENSE-DATA.md`) |

## 2. Dados brutos — `data/raw/`

Três arquivos com a mesma estrutura de colunas de preço, em formato **largo** (uma coluna por combustível × estatística).

| Arquivo | Colunas de chave | Linhas |
|---|---|---:|
| `combustiveis-brasil.csv` | `referencia`, `ano`, `mes` | 258 |
| `combustiveis-regioes.csv` | `referencia`, `ano`, `mes`, `regiao` | 1.290 |
| `combustiveis-estados.csv` | `referencia`, `ano`, `mes`, `regiao`, `estado` | 6.966 |

### 2.1 Chaves

| Variável | Significado | Tipo | Formato / domínio |
|---|---|---|---|
| `referencia` | Mês de referência da medição | texto | `AAAA-MM` (ex.: `2015-03`) |
| `ano` | Ano da medição | inteiro (lido como texto) | `2001`–`2023` |
| `mes` | Mês da medição | texto | `01`–`12`, com zero à esquerda |
| `regiao` | Grande região | texto | `NORTE`, `NORDESTE`, `CENTRO OESTE`, `SUDESTE`, `SUL` (maiúsculas, sem hífen) |
| `estado` | Unidade da federação | texto | nome em maiúsculas e sem acentos (ex.: `SAO PAULO`, `AMAPA`) |

### 2.2 Preços (21 colunas)

O nome segue o padrão `<combustivel>_preco_revenda_<estatistica>`.

| `<combustivel>` | Produto | Unidade | Série disponível |
|---|---|---|---|
| `gasolina_comum` | Gasolina C comum | R$/litro | jul/2001–jan/2023 |
| `gasolina_aditivada` | Gasolina C aditivada | R$/litro | out/2020–jan/2023 |
| `etanol_hidratado` | Etanol hidratado combustível | R$/litro | jul/2001–jan/2023 |
| `oleo_diesel` | Óleo diesel B comum (não S10) | R$/litro | jul/2001–jan/2023 |
| `oleo_diesel_s10` | Óleo diesel B S10 | R$/litro | dez/2012–jan/2023 |
| `gas_cozinha_glp` | Gás liquefeito de petróleo, botijão de 13 kg | R$/botijão de 13 kg | jul/2001–jan/2023 |
| `gas_natural_veicular_gnv` | Gás natural veicular | R$/m³ | jul/2001–jan/2023 (não disponível em todas as UFs) |

| `<estatistica>` | Significado | Tipo |
|---|---|---|
| `avg` | Preço médio de revenda ao consumidor no mês e no recorte geográfico | decimal (até 4 casas) |
| `min` | Menor preço de revenda observado no mês e no recorte | decimal |
| `max` | Maior preço de revenda observado no mês e no recorte | decimal |

### 2.3 Problemas de qualidade conhecidos nos brutos

| Problema | Onde | Tratamento no ETL |
|---|---|---|
| 16 linhas com as cinco chaves vazias, mas com preços válidos | `combustiveis-estados.csv` | Chave recuperada (mês da linha anterior + única UF ausente no mês — sempre o Amapá) e linha marcada com `chave_recuperada = True` |
| Mês de setembro/2020 inexistente | os três arquivos | Mantido como lacuna; variações calculadas por calendário |
| Produto não pesquisado em parte do período ou em algumas UFs | `gasolina_aditivada`, `oleo_diesel_s10`, `gas_natural_veicular_gnv` | Células vazias não geram registro no formato longo (contagem no relatório de qualidade) |
| Rótulos geográficos sem acentuação e sem sigla | `regiao`, `estado` | Normalizados para nome oficial + sigla da UF |

## 3. Dados tratados — `data/processed/`

### 3.1 `precos_combustiveis.csv.gz` (44.798 linhas × 19 colunas)

Formato **longo** (*tidy*): uma linha por nível geográfico × local × mês × combustível.
Chave primária: (`nivel_geografico`, `regiao`, `uf`, `combustivel`, `data`).

| Variável | Significado (negócio / pesquisa) | Tipo primitivo | Formato / unidade / domínio | Nulos |
|---|---|---|---|---|
| `nivel_geografico` | Recorte geográfico do registro | texto | `BRASIL`, `REGIAO`, `ESTADO` | não |
| `referencia` | Mês de referência | texto | `AAAA-MM` | não |
| `data` | Primeiro dia do mês de referência (facilita séries temporais) | data | ISO 8601, `AAAA-MM-DD` | não |
| `ano` | Ano de referência | inteiro | `2001`–`2023` | não |
| `mes` | Mês de referência | inteiro | `1`–`12` | não |
| `regiao` | Grande região do local | texto | `Norte`, `Nordeste`, `Centro-Oeste`, `Sudeste`, `Sul` | vazio quando `nivel_geografico = BRASIL` |
| `uf` | Sigla da unidade da federação | texto | 2 letras maiúsculas (ex.: `SP`) | vazio quando o nível não é `ESTADO` |
| `estado` | Nome oficial da UF, com acentuação | texto | ex.: `São Paulo` | vazio quando o nível não é `ESTADO` |
| `combustivel` | Código do produto | texto | um dos 7 códigos da seção 2.2 | não |
| `unidade` | Unidade de medida do preço | texto | `R$/L`, `R$/13 kg`, `R$/m³` | não |
| `preco_medio` | Preço médio de revenda no mês e local | decimal | reais nominais por `unidade` | não |
| `preco_minimo` | Menor preço observado no mês e local | decimal | reais nominais por `unidade` | não |
| `preco_maximo` | Maior preço observado no mês e local | decimal | reais nominais por `unidade` | não |
| `amplitude_abs` | Amplitude de preços no local: `preco_maximo − preco_minimo` | decimal | reais nominais por `unidade` | não |
| `amplitude_rel_pct` | Amplitude relativa: `amplitude_abs ÷ preco_medio × 100` | decimal | % | não |
| `var_mensal_pct` | Variação do `preco_medio` frente ao mês-calendário anterior | decimal | % | vazio no 1º mês da série e quando o mês anterior não existe (ex.: out/2020) |
| `var_12m_pct` | Variação do `preco_medio` frente ao mesmo mês do ano anterior | decimal | % | vazio nos 12 primeiros meses e quando o mês de comparação não existe |
| `chave_recuperada` | Indica que a chave geográfica/temporal do registro foi recuperada pelo ETL (ver 2.3) | booleano | `True` / `False` | não |
| `flag_inconsistente` | Indica violação de `preco_minimo ≤ preco_medio ≤ preco_maximo` ou preço não positivo | booleano | `True` / `False` (nenhum caso na versão atual) | não |

### 3.2 `paridade_etanol_gasolina.csv.gz` (8.498 linhas × 12 colunas)

Uma linha por nível geográfico × local × mês em que há preço de gasolina comum **e** de etanol hidratado.

| Variável | Significado (negócio / pesquisa) | Tipo primitivo | Formato / unidade / domínio | Nulos |
|---|---|---|---|---|
| `nivel_geografico`, `referencia`, `data`, `ano`, `mes`, `regiao`, `uf`, `estado` | Mesmas definições da tabela 3.1 | — | — | idem 3.1 |
| `preco_gasolina` | Preço médio de revenda da gasolina comum | decimal | R$/L nominais | não |
| `preco_etanol` | Preço médio de revenda do etanol hidratado | decimal | R$/L nominais | não |
| `razao_etanol_gasolina` | `preco_etanol ÷ preco_gasolina` — indicador de competitividade do etanol | decimal | adimensional, 4 casas | não |
| `etanol_vantajoso` | Etanol economicamente vantajoso pela regra prática de paridade energética (`razao ≤ 0,70`) | booleano | `True` / `False` | não |

### 3.3 `relatorio_qualidade.json`

Registro de auditoria emitido a cada execução do ETL.

| Chave | Conteúdo |
|---|---|
| `ambiente` | Versões de Python, pandas e numpy usadas na execução |
| `entradas` | Por arquivo bruto: nome, SHA-256, número de linhas e colunas |
| `auditoria.chaves_orfas` | Lista das linhas com chave vazia: número da linha no CSV, mês e UF atribuídos, ação tomada |
| `auditoria.celulas_vazias_omitidas` | Por combustível e nível: quantas células sem preço deixaram de gerar registro |
| `auditoria.meses_sem_coleta_nacional` | Meses ausentes da série nacional |
| `auditoria.lacunas_de_calendario` | Por nível, local e combustível: meses sem observação dentro do intervalo da série |
| `auditoria.inconsistencias_min_med_max` | Número de registros com `flag_inconsistente = True` |
| `saidas` | Por arquivo gerado: linhas, colunas e SHA-256 |
| `cobertura` | Primeiro e último mês, total de meses e contagem de observações por nível e por combustível |

## 4. Métricas calculadas em tempo de análise (`src/analise.py`)

| Métrica | Definição | Uso |
|---|---|---|
| Índice base 100 | `preco_medio ÷ preco_medio do primeiro mês × 100` | Comparar combustíveis de unidades diferentes (RQ1) |
| Outlier de variação | `var_mensal_pct` fora de `[Q1 − 1,5·IQR, Q3 + 1,5·IQR]` do próprio combustível | Localizar choques de preço (RQ1) |
| Coeficiente de variação interestadual | desvio-padrão ÷ média do `preco_medio` entre as UFs, no mês | Medir a desigualdade entre estados (RQ2) |
| Índice relativo | `preco_medio da UF ÷ mediana das UFs no mês × 100` | Comparar posições das UFs sem efeito da inflação (RQ2) |
| % de meses com etanol vantajoso | média de `etanol_vantajoso` × 100, por UF e período | Competitividade do etanol (RQ3) |

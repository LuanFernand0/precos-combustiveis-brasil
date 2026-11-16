# Dados brutos

Arquivos originais, **sem nenhuma modificação**, do dataset *Preços de Combustíveis Brasil*
(Matheus Fidelis / Economia Popular), obtidos em 16/11/2026 de
<https://www.kaggle.com/datasets/fidelissauro/combustiveis-brasil> (versão 2, arquivos datados de 18/02/2023).
A fonte primária é o Levantamento de Preços de Combustíveis da ANP.

| Arquivo | Recorte | Linhas | Colunas | SHA-256 |
|---|---|---:|---:|---|
| `combustiveis-brasil.csv` | Brasil | 258 | 24 | `a097057959e3f2ddd955f8afb22badfdcd8cbace93c059853827d891e44a980b` |
| `combustiveis-regioes.csv` | 5 grandes regiões | 1.290 | 25 | `72be1e7651e65e64eb2244ff870a2640b270fb25add314171e052d4864a0c64a` |
| `combustiveis-estados.csv` | 27 unidades da federação | 6.966 | 26 | `44bb23eada3619fe859ede06f2ceb0ba5eb565971764f61cb901eb133ece0c6b` |

Formato: CSV, codificação UTF-8 (somente caracteres ASCII), separador vírgula, ponto como separador decimal, quebra de linha LF.

O ETL (`src/etl.py`) confere o SHA-256 antes de processar. Para baixar de novo, sem credenciais:

```bash
curl -L -o archive.zip https://www.kaggle.com/api/v1/datasets/download/fidelissauro/combustiveis-brasil
unzip -o archive.zip -d data/raw/
```

Estes arquivos nunca são editados: toda correção acontece no ETL e fica registrada em
`data/processed/relatorio_qualidade.json`.

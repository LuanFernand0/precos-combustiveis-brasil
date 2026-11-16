"""Pipeline de ETL — Preços de revenda de combustíveis no Brasil (ANP, 2001–2023).

Projeto Final — Linguagem de Programação VI (Análise e Visualização de Dados
com Python), Bacharelado em Sistemas de Informação, 6º período.

O pipeline é determinístico: dadas as mesmas entradas em ``data/raw/`` ele
produz sempre as mesmas tabelas em ``data/processed/`` (sem aleatoriedade,
sem dependência de data/hora e com ordenação estável).

Etapas
------
1. **Extract**  — leitura dos três CSVs brutos (Brasil, regiões, estados) com
   codificação, separador e tipos declarados; verificação de integridade
   (SHA-256) e de esquema.
2. **Transform** — recuperação rastreável de linhas com chave ausente,
   normalização de rótulos geográficos, conversão wide → long (tidy data),
   tipagem, validações de consistência e métricas derivadas.
3. **Load**     — persistência em formato aberto (``.csv.gz``) e emissão de um
   relatório de qualidade (``relatorio_qualidade.json``) que registra tudo o
   que foi recuperado, descartado ou sinalizado.

Nenhum valor de preço é imputado ou alterado. As únicas linhas que deixam de
existir na saída são células estruturalmente vazias (produto não pesquisado
naquele local/mês), e a contagem delas fica registrada no relatório.

Uso
---
    python -m src.etl            # a partir da raiz do repositório
    python -m src.etl --help
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("etl")

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"

#: nível geográfico -> (arquivo bruto, SHA-256 esperado)
FONTES: dict[str, tuple[str, str]] = {
    "BRASIL": (
        "combustiveis-brasil.csv",
        "a097057959e3f2ddd955f8afb22badfdcd8cbace93c059853827d891e44a980b",
    ),
    "REGIAO": (
        "combustiveis-regioes.csv",
        "72be1e7651e65e64eb2244ff870a2640b270fb25add314171e052d4864a0c64a",
    ),
    "ESTADO": (
        "combustiveis-estados.csv",
        "44bb23eada3619fe859ede06f2ceb0ba5eb565971764f61cb901eb133ece0c6b",
    ),
}

#: código do combustível (prefixo das colunas brutas) -> (rótulo, unidade)
COMBUSTIVEIS: dict[str, tuple[str, str]] = {
    "gasolina_comum": ("Gasolina comum", "R$/L"),
    "gasolina_aditivada": ("Gasolina aditivada", "R$/L"),
    "etanol_hidratado": ("Etanol hidratado", "R$/L"),
    "oleo_diesel": ("Óleo diesel", "R$/L"),
    "oleo_diesel_s10": ("Óleo diesel S10", "R$/L"),
    "gas_cozinha_glp": ("GLP (botijão 13 kg)", "R$/13 kg"),
    "gas_natural_veicular_gnv": ("GNV", "R$/m³"),
}

#: nome bruto (maiúsculo, sem acento) -> (sigla da UF, nome oficial)
ESTADOS: dict[str, tuple[str, str]] = {
    "ACRE": ("AC", "Acre"),
    "ALAGOAS": ("AL", "Alagoas"),
    "AMAPA": ("AP", "Amapá"),
    "AMAZONAS": ("AM", "Amazonas"),
    "BAHIA": ("BA", "Bahia"),
    "CEARA": ("CE", "Ceará"),
    "DISTRITO FEDERAL": ("DF", "Distrito Federal"),
    "ESPIRITO SANTO": ("ES", "Espírito Santo"),
    "GOIAS": ("GO", "Goiás"),
    "MARANHAO": ("MA", "Maranhão"),
    "MATO GROSSO": ("MT", "Mato Grosso"),
    "MATO GROSSO DO SUL": ("MS", "Mato Grosso do Sul"),
    "MINAS GERAIS": ("MG", "Minas Gerais"),
    "PARA": ("PA", "Pará"),
    "PARAIBA": ("PB", "Paraíba"),
    "PARANA": ("PR", "Paraná"),
    "PERNAMBUCO": ("PE", "Pernambuco"),
    "PIAUI": ("PI", "Piauí"),
    "RIO DE JANEIRO": ("RJ", "Rio de Janeiro"),
    "RIO GRANDE DO NORTE": ("RN", "Rio Grande do Norte"),
    "RIO GRANDE DO SUL": ("RS", "Rio Grande do Sul"),
    "RONDONIA": ("RO", "Rondônia"),
    "RORAIMA": ("RR", "Roraima"),
    "SANTA CATARINA": ("SC", "Santa Catarina"),
    "SAO PAULO": ("SP", "São Paulo"),
    "SERGIPE": ("SE", "Sergipe"),
    "TOCANTINS": ("TO", "Tocantins"),
}

#: nome bruto da região -> nome oficial
REGIOES: dict[str, str] = {
    "NORTE": "Norte",
    "NORDESTE": "Nordeste",
    "CENTRO OESTE": "Centro-Oeste",
    "SUDESTE": "Sudeste",
    "SUL": "Sul",
}

CHAVES_BRUTAS = ["referencia", "ano", "mes", "regiao", "estado"]
ESTATISTICAS = {"avg": "preco_medio", "min": "preco_minimo", "max": "preco_maximo"}

#: limiar clássico de paridade energética etanol/gasolina
LIMIAR_PARIDADE = 0.70

COLUNAS_SAIDA = [
    "nivel_geografico", "referencia", "data", "ano", "mes", "regiao", "uf",
    "estado", "combustivel", "unidade", "preco_medio", "preco_minimo",
    "preco_maximo", "amplitude_abs", "amplitude_rel_pct", "var_mensal_pct",
    "var_12m_pct", "chave_recuperada", "flag_inconsistente",
]


# --------------------------------------------------------------------------
# Extract
# --------------------------------------------------------------------------
def sha256_arquivo(caminho: Path) -> str:
    """Retorna o SHA-256 hexadecimal de um arquivo."""
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def colunas_preco() -> list[str]:
    """Lista, na ordem do arquivo bruto, as 21 colunas de preço esperadas."""
    return [
        f"{cod}_preco_revenda_{est}" for cod in COMBUSTIVEIS for est in ESTATISTICAS
    ]


def extrair(
    dir_raw: Path = DIR_RAW, verificar_integridade: bool = True
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Lê os três arquivos brutos sem alterar nenhum valor.

    As chaves são lidas como texto (``"07"`` não vira ``7``) e os preços como
    ``float64``. O esquema e o SHA-256 de cada arquivo são conferidos.
    """
    brutos: dict[str, pd.DataFrame] = {}
    meta: dict = {}
    precos = colunas_preco()
    for nivel, (arquivo, sha_esperado) in FONTES.items():
        caminho = dir_raw / arquivo
        if not caminho.exists():
            raise FileNotFoundError(
                f"Arquivo bruto ausente: {caminho}. Consulte data/raw/README.md."
            )
        sha = sha256_arquivo(caminho)
        if verificar_integridade and sha != sha_esperado:
            raise ValueError(
                f"SHA-256 de {arquivo} difere do esperado ({sha}). O arquivo foi "
                "alterado ou é outra versão do dataset; use --ignorar-checksum "
                "para prosseguir assim mesmo."
            )
        chaves = [c for c in CHAVES_BRUTAS if c in pd.read_csv(caminho, nrows=0).columns]
        df = pd.read_csv(
            caminho,
            sep=",",
            encoding="utf-8",
            decimal=".",
            dtype={**{c: "string" for c in chaves}, **{c: "float64" for c in precos}},
        )
        faltantes = set(chaves + precos) - set(df.columns)
        extras = set(df.columns) - set(chaves + precos)
        if faltantes or extras:
            raise ValueError(
                f"Esquema inesperado em {arquivo}: faltam {sorted(faltantes)}, "
                f"sobram {sorted(extras)}"
            )
        brutos[nivel] = df
        meta[nivel] = {
            "arquivo": arquivo,
            "sha256": sha,
            "linhas": int(len(df)),
            "colunas": int(df.shape[1]),
        }
        log.info("extraído %-24s %5d linhas × %d colunas", arquivo, *df.shape)
    return brutos, meta


# --------------------------------------------------------------------------
# Transform
# --------------------------------------------------------------------------
def recuperar_chaves_orfas(estados: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Recupera linhas do arquivo de estados cuja chave veio vazia.

    No arquivo bruto, 16 linhas trazem preços válidos mas ``referencia``,
    ``ano``, ``mes``, ``regiao`` e ``estado`` vazios. Elas aparecem sempre ao
    final do bloco de um mês, e nesse mês falta exatamente uma UF. A regra de
    recuperação é, portanto, determinística:

    * o mês é herdado da linha imediatamente anterior (o arquivo é ordenado
      por mês);
    * a UF é a única ausente naquele mês.

    A linha só é recuperada se as duas condições forem satisfeitas sem
    ambiguidade; do contrário é descartada. Todo caso é registrado e a linha
    recuperada recebe ``chave_recuperada = True``.
    """
    df = estados.copy()
    df["chave_recuperada"] = False
    orfas = df.index[df[CHAVES_BRUTAS].isna().all(axis=1)]
    parciais = df[CHAVES_BRUTAS].isna().any(axis=1) & ~df[CHAVES_BRUTAS].isna().all(axis=1)
    if parciais.any():
        raise ValueError(f"{int(parciais.sum())} linhas com chave parcialmente nula")

    todas_ufs = set(df["estado"].dropna().unique())
    regiao_da_uf = (
        df.dropna(subset=["estado"]).drop_duplicates("estado").set_index("estado")["regiao"]
    )
    referencia_herdada = df["referencia"].ffill()
    registro: list[dict] = []
    descartar: list[int] = []
    for i in orfas:
        ref = referencia_herdada.loc[i]
        presentes = set(df.loc[df["referencia"] == ref, "estado"].dropna())
        ausentes = sorted(todas_ufs - presentes)
        caso = {"linha_csv": int(i) + 2, "referencia": None, "estado": None, "acao": "descartada"}
        if pd.notna(ref) and len(ausentes) == 1:
            uf = ausentes[0]
            df.loc[i, ["referencia", "ano", "mes", "regiao", "estado"]] = [
                ref, ref[:4], ref[5:7], regiao_da_uf[uf], uf,
            ]
            df.loc[i, "chave_recuperada"] = True
            caso.update(referencia=str(ref), estado=uf, acao="recuperada")
        else:
            descartar.append(i)
        registro.append(caso)
    if descartar:
        df = df.drop(index=descartar)
    log.info(
        "chaves órfãs: %d encontradas, %d recuperadas, %d descartadas",
        len(orfas), len(orfas) - len(descartar), len(descartar),
    )
    return df.reset_index(drop=True), registro


def empilhar_niveis(brutos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Une os três recortes geográficos em uma única tabela larga."""
    partes = []
    for nivel, df in brutos.items():
        parte = df.copy()
        parte.insert(0, "nivel_geografico", nivel)
        for coluna in ("regiao", "estado"):
            if coluna not in parte:
                parte[coluna] = pd.array([pd.NA] * len(parte), dtype="string")
        if "chave_recuperada" not in parte:
            parte["chave_recuperada"] = False
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def normalizar_geografia(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza região e UF (sigla + nome oficial com acentuação)."""
    df = df.copy()
    desconhecidas = set(df["regiao"].dropna()) - set(REGIOES)
    desconhecidos = set(df["estado"].dropna()) - set(ESTADOS)
    if desconhecidas or desconhecidos:
        raise ValueError(f"Rótulos fora do domínio: {desconhecidas | desconhecidos}")
    bruto = df["estado"]
    df["regiao"] = df["regiao"].map(REGIOES).astype("string")
    df["uf"] = bruto.map({k: v[0] for k, v in ESTADOS.items()}).astype("string")
    df["estado"] = bruto.map({k: v[1] for k, v in ESTADOS.items()}).astype("string")
    return df


def para_formato_longo(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Converte wide → long: uma linha por (nível, local, mês, combustível).

    Células em que média, mínimo e máximo são simultaneamente nulos indicam
    que o produto não foi pesquisado naquele local/mês; elas não geram linha
    (a ausência é representada pela ausência do registro) e são contabilizadas.
    """
    ids = ["nivel_geografico", "referencia", "ano", "mes", "regiao", "uf", "estado",
           "chave_recuperada"]
    blocos = []
    vazias: dict[str, dict[str, int]] = {}
    for cod, (_, unidade) in COMBUSTIVEIS.items():
        origem = {f"{cod}_preco_revenda_{e}": destino for e, destino in ESTATISTICAS.items()}
        bloco = df[ids + list(origem)].rename(columns=origem)
        bloco.insert(len(ids), "combustivel", cod)
        bloco.insert(len(ids) + 1, "unidade", unidade)
        sem_preco = bloco[list(ESTATISTICAS.values())].isna().all(axis=1)
        parcial = bloco[list(ESTATISTICAS.values())].isna().any(axis=1) & ~sem_preco
        if parcial.any():
            raise ValueError(f"{cod}: {int(parcial.sum())} linhas com preço parcialmente nulo")
        vazias[cod] = {
            nivel: int(n)
            for nivel, n in sem_preco.groupby(bloco["nivel_geografico"]).sum().items()
        }
        blocos.append(bloco[~sem_preco])
    longo = pd.concat(blocos, ignore_index=True)
    log.info("formato longo: %d observações (células vazias omitidas: %d)",
             len(longo), sum(sum(v.values()) for v in vazias.values()))
    return longo, vazias


def tipar(df: pd.DataFrame) -> pd.DataFrame:
    """Converte chaves textuais para tipos adequados e cria a coluna ``data``."""
    df = df.copy()
    df["data"] = pd.to_datetime(df["referencia"] + "-01", format="%Y-%m-%d", errors="raise")
    df["ano"] = df["ano"].astype("int16")
    df["mes"] = df["mes"].astype("int8")
    if not ((df["data"].dt.year == df["ano"]) & (df["data"].dt.month == df["mes"])).all():
        raise ValueError("Colunas ano/mes divergem de referencia")
    return df


def _local(df: pd.DataFrame) -> pd.Series:
    """Identificador único do recorte: 'BR', nome da região ou sigla da UF."""
    return df["uf"].fillna(df["regiao"]).fillna("BR")


def _variacao(df: pd.DataFrame, meses: int, nome: str) -> pd.DataFrame:
    """Variação percentual do preço médio frente a ``meses`` meses antes.

    A comparação é feita por calendário (junção com a data deslocada), e não
    por posição: se o mês de comparação não existe na série, o resultado é
    nulo em vez de comparar com um mês errado.
    """
    chave = ["nivel_geografico", "_local", "combustivel", "data"]
    anterior = df[chave + ["preco_medio"]].rename(columns={"preco_medio": "_anterior"})
    anterior["data"] = anterior["data"] + pd.DateOffset(months=meses)
    saida = df.merge(anterior, on=chave, how="left", validate="one_to_one")
    saida[nome] = ((saida["preco_medio"] / saida["_anterior"] - 1) * 100).round(4)
    return saida.drop(columns="_anterior")


def derivar_metricas(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta amplitudes, variações temporais e a flag de consistência."""
    df = df.copy()
    df["_local"] = _local(df)
    duplicadas = df.duplicated(["nivel_geografico", "_local", "combustivel", "data"])
    if duplicadas.any():
        raise ValueError(f"{int(duplicadas.sum())} observações duplicadas")

    df["amplitude_abs"] = (df["preco_maximo"] - df["preco_minimo"]).round(4)
    df["amplitude_rel_pct"] = (df["amplitude_abs"] / df["preco_medio"] * 100).round(4)
    df = _variacao(df, 1, "var_mensal_pct")
    df = _variacao(df, 12, "var_12m_pct")

    tol = 1e-9
    df["flag_inconsistente"] = (
        (df["preco_minimo"] > df["preco_medio"] + tol)
        | (df["preco_medio"] > df["preco_maximo"] + tol)
        | (df[["preco_medio", "preco_minimo", "preco_maximo"]] <= 0).any(axis=1)
    )
    ordem_nivel = {"BRASIL": 0, "REGIAO": 1, "ESTADO": 2}
    ordem_comb = {c: i for i, c in enumerate(COMBUSTIVEIS)}
    df = (
        df.assign(_n=df["nivel_geografico"].map(ordem_nivel), _c=df["combustivel"].map(ordem_comb))
        .sort_values(["_n", "_local", "_c", "data"], kind="mergesort")
        .drop(columns=["_n", "_c", "_local"])
        .reset_index(drop=True)
    )
    return df[COLUNAS_SAIDA]


def calcular_paridade(precos: pd.DataFrame) -> pd.DataFrame:
    """Tabela derivada com a razão de preços etanol/gasolina por local e mês.

    O etanol hidratado rende, em média, cerca de 70 % do que rende a gasolina;
    por isso ``razao <= 0,70`` é a regra prática de vantagem econômica.
    """
    ids = ["nivel_geografico", "referencia", "data", "ano", "mes", "regiao", "uf", "estado"]
    base = precos[precos["combustivel"].isin(["gasolina_comum", "etanol_hidratado"])].copy()
    base["_local"] = _local(base)
    larga = base.pivot(
        index=["nivel_geografico", "_local", "data"], columns="combustivel", values="preco_medio"
    ).dropna()
    larga = larga.rename(
        columns={"gasolina_comum": "preco_gasolina", "etanol_hidratado": "preco_etanol"}
    ).reset_index()
    chaves = base.drop_duplicates(["nivel_geografico", "_local", "data"])[ids + ["_local"]]
    out = chaves.merge(larga, on=["nivel_geografico", "_local", "data"], how="inner",
                       validate="one_to_one")
    out["razao_etanol_gasolina"] = (out["preco_etanol"] / out["preco_gasolina"]).round(4)
    out["etanol_vantajoso"] = out["razao_etanol_gasolina"] <= LIMIAR_PARIDADE
    ordem_nivel = {"BRASIL": 0, "REGIAO": 1, "ESTADO": 2}
    out = (
        out.assign(_n=out["nivel_geografico"].map(ordem_nivel))
        .sort_values(["_n", "_local", "data"], kind="mergesort")
        .drop(columns=["_n", "_local"])
        .reset_index(drop=True)
    )
    return out[ids + ["preco_gasolina", "preco_etanol", "razao_etanol_gasolina",
                      "etanol_vantajoso"]]


def lacunas_de_calendario(precos: pd.DataFrame) -> dict:
    """Meses sem observação dentro do intervalo coberto por cada série."""
    df = precos.assign(_local=_local(precos))
    resumo: dict[str, dict] = {}
    for (nivel, local, comb), g in df.groupby(["nivel_geografico", "_local", "combustivel"]):
        esperado = pd.period_range(g["data"].min(), g["data"].max(), freq="M")
        faltam = sorted(set(esperado.astype(str)) - set(g["referencia"]))
        if faltam:
            resumo.setdefault(nivel, {}).setdefault(local, {})[comb] = faltam
    return resumo


def transformar(brutos: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Executa toda a etapa de transformação e devolve as tabelas + auditoria."""
    brutos = dict(brutos)
    brutos["ESTADO"], orfas = recuperar_chaves_orfas(brutos["ESTADO"])
    largo = normalizar_geografia(empilhar_niveis(brutos))
    longo, vazias = para_formato_longo(largo)
    precos = derivar_metricas(tipar(longo))
    paridade = calcular_paridade(precos)

    lacunas = lacunas_de_calendario(precos)
    mes_sem_coleta = sorted(
        set(pd.period_range(precos["data"].min(), precos["data"].max(), freq="M").astype(str))
        - set(precos.loc[precos["nivel_geografico"] == "BRASIL", "referencia"])
    )
    auditoria = {
        "chaves_orfas": orfas,
        "celulas_vazias_omitidas": vazias,
        "meses_sem_coleta_nacional": mes_sem_coleta,
        "lacunas_de_calendario": lacunas,
        "inconsistencias_min_med_max": int(precos["flag_inconsistente"].sum()),
        "observacoes_com_chave_recuperada": int(precos["chave_recuperada"].sum()),
    }
    log.info("inconsistências mín ≤ média ≤ máx: %d", auditoria["inconsistencias_min_med_max"])
    return precos, paridade, auditoria


# --------------------------------------------------------------------------
# Load
# --------------------------------------------------------------------------
def salvar_csv_gz(df: pd.DataFrame, caminho: Path) -> dict:
    """Grava CSV comprimido (gzip) sem carimbo de data/hora no cabeçalho."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        caminho,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        date_format="%Y-%m-%d",
        compression={"method": "gzip", "mtime": 0, "compresslevel": 9},
    )
    info = {
        "arquivo": caminho.name,
        "linhas": int(len(df)),
        "colunas": int(df.shape[1]),
        "sha256": sha256_arquivo(caminho),
    }
    log.info("gravado %-36s %6d linhas", caminho.name, len(df))
    return info


def carregar(
    precos: pd.DataFrame,
    paridade: pd.DataFrame,
    auditoria: dict,
    meta_entrada: dict,
    dir_saida: Path = DIR_PROCESSED,
) -> dict:
    """Persiste as tabelas tratadas e o relatório de qualidade."""
    relatorio = {
        "ambiente": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "entradas": meta_entrada,
        "auditoria": auditoria,
        "saidas": {
            "precos_combustiveis": salvar_csv_gz(precos, dir_saida / "precos_combustiveis.csv.gz"),
            "paridade_etanol_gasolina": salvar_csv_gz(
                paridade, dir_saida / "paridade_etanol_gasolina.csv.gz"
            ),
        },
        "cobertura": {
            "primeiro_mes": precos["referencia"].min(),
            "ultimo_mes": precos["referencia"].max(),
            "meses_distintos": int(precos["referencia"].nunique()),
            "observacoes_por_nivel": {
                k: int(v) for k, v in precos["nivel_geografico"].value_counts().sort_index().items()
            },
            "observacoes_por_combustivel": {
                k: int(v) for k, v in precos["combustivel"].value_counts().sort_index().items()
            },
        },
    }
    destino = dir_saida / "relatorio_qualidade.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.info("gravado %s", destino.name)
    return relatorio


# --------------------------------------------------------------------------
# Leitura dos dados tratados (reutilizada pelo notebook e pelas figuras)
# --------------------------------------------------------------------------
def ler_precos(dir_processed: Path = DIR_PROCESSED) -> pd.DataFrame:
    """Lê ``precos_combustiveis.csv.gz`` restaurando os tipos."""
    return pd.read_csv(
        dir_processed / "precos_combustiveis.csv.gz",
        parse_dates=["data"],
        dtype={"referencia": "string", "regiao": "string", "uf": "string", "estado": "string",
               "nivel_geografico": "string", "combustivel": "string", "unidade": "string",
               "ano": "int16", "mes": "int8"},
    )


def ler_paridade(dir_processed: Path = DIR_PROCESSED) -> pd.DataFrame:
    """Lê ``paridade_etanol_gasolina.csv.gz`` restaurando os tipos."""
    return pd.read_csv(
        dir_processed / "paridade_etanol_gasolina.csv.gz",
        parse_dates=["data"],
        dtype={"referencia": "string", "regiao": "string", "uf": "string", "estado": "string",
               "nivel_geografico": "string", "ano": "int16", "mes": "int8"},
    )


# --------------------------------------------------------------------------
# Orquestração
# --------------------------------------------------------------------------
def executar(
    dir_raw: Path = DIR_RAW,
    dir_saida: Path = DIR_PROCESSED,
    verificar_integridade: bool = True,
) -> dict:
    """Roda o pipeline completo (extract → transform → load)."""
    brutos, meta = extrair(dir_raw, verificar_integridade)
    precos, paridade, auditoria = transformar(brutos)
    return carregar(precos, paridade, auditoria, meta, dir_saida)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--raw", type=Path, default=DIR_RAW, help="pasta dos CSVs brutos")
    parser.add_argument("--saida", type=Path, default=DIR_PROCESSED, help="pasta de saída")
    parser.add_argument("--ignorar-checksum", action="store_true",
                        help="não interrompe se o SHA-256 dos brutos divergir")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    relatorio = executar(args.raw, args.saida, not args.ignorar_checksum)
    cob = relatorio["cobertura"]
    log.info("concluído: %s a %s, %d meses", cob["primeiro_mes"], cob["ultimo_mes"],
             cob["meses_distintos"])


if __name__ == "__main__":
    main()

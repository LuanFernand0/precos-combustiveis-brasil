"""Agregações e métricas reutilizáveis sobre os dados tratados.

Todas as funções recebem os DataFrames produzidos por ``src.etl`` e devolvem
novos DataFrames, sem efeitos colaterais. São usadas tanto pelo notebook de
análise exploratória quanto pelo gerador de figuras do artigo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.etl import COMBUSTIVEIS

#: combustíveis com série completa (jul/2001–jan/2023) nos três níveis
COMBUSTIVEIS_SERIE_LONGA = [
    "gasolina_comum", "etanol_hidratado", "oleo_diesel", "gas_cozinha_glp",
    "gas_natural_veicular_gnv",
]

ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]


def rotulo(combustivel: str) -> str:
    """Nome legível de um código de combustível."""
    return COMBUSTIVEIS[combustivel][0]


# --------------------------------------------------------------------------
# RQ1 — evolução temporal e choques
# --------------------------------------------------------------------------
def serie_nacional(precos: pd.DataFrame, coluna: str = "preco_medio") -> pd.DataFrame:
    """Tabela mês × combustível com a série nacional de ``coluna``."""
    br = precos[precos["nivel_geografico"] == "BRASIL"]
    return br.pivot(index="data", columns="combustivel", values=coluna)[list(COMBUSTIVEIS)]


def indice_base_100(serie: pd.DataFrame) -> pd.DataFrame:
    """Reescala cada coluna para 100 na sua primeira observação válida."""
    return serie.apply(lambda s: s / s.dropna().iloc[0] * 100)


def resumo_periodo(precos: pd.DataFrame) -> pd.DataFrame:
    """Preço inicial, final, pico e variação acumulada da série nacional."""
    linhas = []
    for comb, s in serie_nacional(precos).items():
        s = s.dropna()
        linhas.append({
            "combustivel": comb,
            "inicio": s.index[0].strftime("%Y-%m"),
            "preco_inicial": s.iloc[0],
            "preco_final": s.iloc[-1],
            "variacao_acumulada_pct": (s.iloc[-1] / s.iloc[0] - 1) * 100,
            "pico": s.max(),
            "mes_do_pico": s.idxmax().strftime("%Y-%m"),
            "meses": len(s),
        })
    return pd.DataFrame(linhas).set_index("combustivel")


def estatisticas_variacao(precos: pd.DataFrame) -> pd.DataFrame:
    """Medidas de posição e dispersão da variação mensal (%) nacional."""
    var = serie_nacional(precos, "var_mensal_pct")
    est = var.agg(["count", "mean", "median", "std", "min", "max"]).T
    q1, q3 = var.quantile(0.25), var.quantile(0.75)
    est["q1"], est["q3"], est["iqr"] = q1, q3, q3 - q1
    return est


def outliers_variacao(precos: pd.DataFrame, k: float = 1.5) -> pd.DataFrame:
    """Meses cuja variação mensal nacional foge das cercas de Tukey.

    Um mês é outlier quando a variação fica abaixo de ``Q1 − k·IQR`` ou acima
    de ``Q3 + k·IQR`` da distribuição do próprio combustível.
    """
    var = serie_nacional(precos, "var_mensal_pct")
    q1, q3 = var.quantile(0.25), var.quantile(0.75)
    iqr = q3 - q1
    inferior, superior = q1 - k * iqr, q3 + k * iqr
    longo = var.stack().rename("var_mensal_pct").reset_index()
    longo["limite_inferior"] = longo["combustivel"].map(inferior)
    longo["limite_superior"] = longo["combustivel"].map(superior)
    fora = longo[
        (longo["var_mensal_pct"] < longo["limite_inferior"])
        | (longo["var_mensal_pct"] > longo["limite_superior"])
    ].copy()
    fora["sentido"] = np.where(fora["var_mensal_pct"] > 0, "alta", "queda")
    return fora.sort_values(["combustivel", "data"]).reset_index(drop=True)


def correlacao_variacoes(precos: pd.DataFrame) -> pd.DataFrame:
    """Correlação de Pearson entre as variações mensais nacionais."""
    return serie_nacional(precos, "var_mensal_pct")[COMBUSTIVEIS_SERIE_LONGA].corr()


# --------------------------------------------------------------------------
# RQ2 — desigualdade entre estados
# --------------------------------------------------------------------------
def dispersao_interestadual(precos: pd.DataFrame) -> pd.DataFrame:
    """Dispersão do preço médio entre UFs, por mês e combustível.

    ``cv_pct`` é o coeficiente de variação (desvio-padrão / média) e
    ``razao_max_min`` é quanto a UF mais cara custa em relação à mais barata.
    """
    es = precos[precos["nivel_geografico"] == "ESTADO"]
    g = es.groupby(["combustivel", "data"])["preco_medio"]
    out = g.agg(n_ufs="count", media="mean", desvio="std", minimo="min", maximo="max")
    out["cv_pct"] = out["desvio"] / out["media"] * 100
    out["razao_max_min"] = out["maximo"] / out["minimo"]
    out["uf_mais_cara"] = es.loc[g.idxmax(), "uf"].to_numpy()
    out["uf_mais_barata"] = es.loc[g.idxmin(), "uf"].to_numpy()
    return out.reset_index()


def indice_relativo(precos: pd.DataFrame, combustivel: str) -> pd.DataFrame:
    """Preço de cada UF em relação à mediana das UFs no mesmo mês (= 100).

    Por ser uma razão dentro do mês, o índice não é afetado pela inflação e
    permite comparar posições relativas ao longo de duas décadas.
    """
    es = precos[(precos["nivel_geografico"] == "ESTADO") & (precos["combustivel"] == combustivel)]
    es = es[["data", "ano", "regiao", "uf", "estado", "preco_medio"]].copy()
    es["indice_relativo"] = es["preco_medio"] / es.groupby("data")["preco_medio"].transform("median") * 100
    return es


def indice_relativo_anual(precos: pd.DataFrame, combustivel: str) -> pd.DataFrame:
    """Tabela UF × ano com a média anual do índice relativo."""
    rel = indice_relativo(precos, combustivel)
    return rel.pivot_table(index="uf", columns="ano", values="indice_relativo", aggfunc="mean")


def ranking_estados(precos: pd.DataFrame, combustivel: str,
                    inicio: str | None = None, fim: str | None = None) -> pd.DataFrame:
    """Ranking das UFs pelo índice relativo médio em um intervalo de datas."""
    rel = indice_relativo(precos, combustivel)
    if inicio:
        rel = rel[rel["data"] >= inicio]
    if fim:
        rel = rel[rel["data"] <= fim]
    out = (
        rel.groupby(["uf", "estado", "regiao"])["indice_relativo"]
        .agg(indice_medio="mean", desvio="std", meses="count")
        .reset_index()
        .sort_values("indice_medio", ascending=False)
        .reset_index(drop=True)
    )
    out.insert(0, "posicao", out.index + 1)
    return out


def persistencia_ranking(precos: pd.DataFrame, combustivel: str,
                         periodo_a: tuple[str, str], periodo_b: tuple[str, str]) -> float:
    """Correlação de postos (Spearman) entre os rankings de dois períodos."""
    a = ranking_estados(precos, combustivel, *periodo_a).set_index("uf")["indice_medio"]
    b = ranking_estados(precos, combustivel, *periodo_b).set_index("uf")["indice_medio"]
    return float(a.rank().corr(b.rank()))


# --------------------------------------------------------------------------
# RQ3 — paridade etanol/gasolina
# --------------------------------------------------------------------------
def paridade_anual_por_uf(paridade: pd.DataFrame) -> pd.DataFrame:
    """Por UF e ano: razão média e % de meses com etanol vantajoso."""
    es = paridade[paridade["nivel_geografico"] == "ESTADO"]
    out = es.groupby(["regiao", "uf", "estado", "ano"]).agg(
        razao_media=("razao_etanol_gasolina", "mean"),
        pct_meses_vantajoso=("etanol_vantajoso", lambda s: s.mean() * 100),
        meses=("etanol_vantajoso", "size"),
    )
    return out.reset_index()


def paridade_resumo_por_uf(paridade: pd.DataFrame) -> pd.DataFrame:
    """Por UF, em todo o período: razão média/mediana e % de meses vantajosos."""
    es = paridade[paridade["nivel_geografico"] == "ESTADO"]
    out = es.groupby(["regiao", "uf", "estado"]).agg(
        razao_media=("razao_etanol_gasolina", "mean"),
        razao_mediana=("razao_etanol_gasolina", "median"),
        pct_meses_vantajoso=("etanol_vantajoso", lambda s: s.mean() * 100),
        meses=("etanol_vantajoso", "size"),
    )
    return out.reset_index().sort_values("pct_meses_vantajoso", ascending=False).reset_index(drop=True)


def paridade_por_regiao(paridade: pd.DataFrame) -> pd.DataFrame:
    """Tabela mês × região (mais a coluna 'Brasil') com a razão etanol/gasolina."""
    rg = paridade[paridade["nivel_geografico"] == "REGIAO"].pivot(
        index="data", columns="regiao", values="razao_etanol_gasolina"
    )[ORDEM_REGIOES]
    br = paridade[paridade["nivel_geografico"] == "BRASIL"].set_index("data")["razao_etanol_gasolina"]
    rg.insert(0, "Brasil", br)
    return rg


def sazonalidade_paridade(paridade: pd.DataFrame) -> pd.Series:
    """Razão etanol/gasolina nacional média por mês do ano (1–12)."""
    br = paridade[paridade["nivel_geografico"] == "BRASIL"]
    return br.groupby("mes")["razao_etanol_gasolina"].mean()


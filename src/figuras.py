"""Gera os artefatos visuais do artigo a partir dos dados tratados.

Saídas (todas em ``docs/assets/``):

* ``fig_*.png`` — versão estática (Matplotlib, 200 dpi) de cada uma das seis
  figuras do artigo, usada quando o gráfico interativo não pode ser carregado;
* ``dados_graficos.js`` — séries já agregadas que alimentam os gráficos
  interativos (Plotly.js) de ``docs/index.html``;
* ``numeros_chave.json`` — todos os números citados no texto do artigo, para
  que cada afirmação possa ser conferida contra os dados.

Uso
---
    python -m src.figuras        # depois de ``python -m src.etl``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from src import analise  # noqa: E402
from src.etl import LIMIAR_PARIDADE, RAIZ, ler_paridade, ler_precos  # noqa: E402

log = logging.getLogger("figuras")
DIR_ASSETS = RAIZ / "docs" / "assets"

# Paleta categórica fixa: a cor acompanha a entidade em todas as figuras.
COR = {
    "gasolina_comum": "#2a78d6",
    "etanol_hidratado": "#1baf7a",
    "oleo_diesel": "#eb6834",
    "gas_cozinha_glp": "#6250d6",
    "gas_natural_veicular_gnv": "#eda100",
}
COR_REGIAO = {
    "Norte": "#2a78d6", "Nordeste": "#eb6834", "Centro-Oeste": "#1baf7a",
    "Sudeste": "#6250d6", "Sul": "#eda100",
}
TINTA, TINTA_SUAVE, GRADE = "#1f2937", "#4b5563", "#e2e8f0"


def _estilo() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRADE,
        "axes.labelcolor": TINTA_SUAVE, "axes.titlecolor": TINTA, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.8,
        "xtick.color": TINTA_SUAVE, "ytick.color": TINTA_SUAVE, "figure.facecolor": "white",
        "axes.facecolor": "white", "savefig.dpi": 200, "savefig.bbox": "tight",
    })


def _rotulos_finais(ax, finais: dict[str, float], x, folga: float) -> None:
    """Rotula o fim de cada linha, afastando rótulos que ficariam sobrepostos."""
    y_anterior = -np.inf
    for nome, y in sorted(finais.items(), key=lambda par: par[1]):
        y_rotulo = max(y, y_anterior + folga)
        ax.annotate(nome, (x, y), xytext=(x + pd.Timedelta(days=90), y_rotulo),
                    textcoords="data", va="center", fontsize=9, color=TINTA)
        y_anterior = y_rotulo


# --------------------------------------------------------------------------
# Figuras estáticas (versões em PNG dos mesmos seis gráficos do artigo)
# --------------------------------------------------------------------------
COMBUSTIVEIS_POR_LITRO = ["gasolina_comum", "etanol_hidratado", "oleo_diesel"]
COMBUSTIVEIS_RANKING = ["gasolina_comum", "etanol_hidratado", "oleo_diesel", "gas_cozinha_glp"]


def fig_serie_nacional(precos: pd.DataFrame, destino: Path) -> None:
    """Linhas: preço médio nacional dos três combustíveis vendidos por litro."""
    serie = analise.serie_nacional(precos)[COMBUSTIVEIS_POR_LITRO]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for comb in COMBUSTIVEIS_POR_LITRO:
        ax.plot(serie.index, serie[comb], color=COR[comb], linewidth=2, label=analise.rotulo(comb))
    ax.set_ylim(0, None)
    ax.set_ylabel("R$ por litro (nominal)")
    ax.set_title("Preço médio nacional de revenda, jul/2001–jan/2023")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", frameon=False)
    fig.savefig(destino)
    plt.close(fig)


def fig_variacao_mensal(precos: pd.DataFrame, destino: Path) -> None:
    """Barras: variação mensal da gasolina, com os meses atípicos em destaque."""
    var = analise.serie_nacional(precos, "var_mensal_pct")["gasolina_comum"].dropna()
    fora = analise.outliers_variacao(precos)
    atipico = var.index.isin(fora.loc[fora["combustivel"] == "gasolina_comum", "data"])
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(var.index[~atipico], var[~atipico], width=25, color="#9ec5f4", label="mês comum")
    ax.bar(var.index[atipico], var[atipico], width=25, color="#104281", label="mês atípico (Tukey)")
    ax.axhline(0, color=TINTA_SUAVE, linewidth=0.8)
    ax.set_ylabel("Variação frente ao mês anterior (%)")
    ax.set_title("Gasolina comum — variação mensal do preço médio nacional")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", ncol=2, frameon=False)
    fig.savefig(destino)
    plt.close(fig)


def _barras_por_uf(ax, ufs, valores, regioes) -> None:
    """Barras horizontais por UF, coloridas pela região, com legenda."""
    ax.barh(ufs, valores, color=[COR_REGIAO[r] for r in regioes], height=0.72)
    ax.invert_yaxis()
    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=8)
    legenda = [Patch(facecolor=COR_REGIAO[r], label=r) for r in analise.ORDEM_REGIOES]
    ax.legend(handles=legenda, loc="lower right", frameon=False, fontsize=9)


def fig_ranking_estados(precos: pd.DataFrame, destino: Path) -> None:
    """Barras: quanto a gasolina de cada UF custa acima/abaixo da mediana das UFs."""
    r = analise.ranking_estados(precos, "gasolina_comum")
    fig, ax = plt.subplots(figsize=(9, 6.8))
    _barras_por_uf(ax, r["uf"], r["indice_medio"] - 100, r["regiao"])
    ax.axvline(0, color=TINTA, linewidth=1)
    ax.set_xlabel("Diferença média em relação à mediana das UFs (%)")
    ax.set_title("Gasolina comum — preço de cada UF frente à mediana, jul/2001–jan/2023")
    fig.savefig(destino)
    plt.close(fig)


def fig_etanol_por_uf(paridade: pd.DataFrame, destino: Path) -> None:
    """Barras: % dos meses em que o etanol foi vantajoso em cada UF."""
    r = analise.paridade_resumo_por_uf(paridade)
    fig, ax = plt.subplots(figsize=(9, 6.8))
    _barras_por_uf(ax, r["uf"], r["pct_meses_vantajoso"], r["regiao"])
    ax.axvline(50, color=TINTA, linewidth=1, linestyle=(0, (4, 3)))
    ax.set_xlim(0, 100)
    ax.set_xlabel("% dos meses com razão etanol/gasolina ≤ 0,70")
    ax.set_title("Meses em que o etanol foi vantajoso, por UF, jul/2001–jan/2023")
    fig.savefig(destino)
    plt.close(fig)


def fig_dispersao_interestadual(precos: pd.DataFrame, destino: Path) -> None:
    """Coeficiente de variação entre UFs (média móvel de 12 meses)."""
    disp = analise.dispersao_interestadual(precos)
    combs = ["etanol_hidratado", "gas_cozinha_glp", "oleo_diesel", "gasolina_comum"]
    tabela = disp.pivot(index="data", columns="combustivel", values="cv_pct")[combs]
    suave = tabela.rolling(12, min_periods=6).mean()
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for comb in combs:
        ax.plot(suave.index, suave[comb], color=COR[comb], linewidth=2, label=analise.rotulo(comb))
    _rotulos_finais(ax, {analise.rotulo(c).split(" (")[0]: suave[c].dropna().iloc[-1] for c in combs},
                    suave.index[-1], folga=0.75)
    ax.set_ylim(0, None)
    ax.set_xlim(suave.dropna(how="all").index[0], pd.Timestamp("2025-06-01"))
    ax.set_ylabel("Coeficiente de variação entre as 27 UFs (%)")
    ax.set_title("Dispersão interestadual do preço médio (média móvel de 12 meses)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.1))
    fig.savefig(destino)
    plt.close(fig)


def fig_paridade_regioes(paridade: pd.DataFrame, destino: Path) -> None:
    """Razão etanol/gasolina por região (média móvel de 12 meses) e limiar 0,70."""
    tabela = analise.paridade_por_regiao(paridade)[analise.ORDEM_REGIOES]
    suave = tabela.rolling(12, min_periods=6).mean()
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axhspan(0, LIMIAR_PARIDADE, color="#1baf7a", alpha=0.07, linewidth=0)
    ax.axhline(LIMIAR_PARIDADE, color=TINTA, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate("faixa em que o etanol é vantajoso (razão ≤ 0,70)",
                (suave.dropna(how="all").index[0], 0.5), xytext=(8, 8),
                textcoords="offset points", fontsize=9, color=TINTA)
    for regiao in analise.ORDEM_REGIOES:
        ax.plot(suave.index, suave[regiao], color=COR_REGIAO[regiao], linewidth=2, label=regiao)
    _rotulos_finais(ax, {r: suave[r].dropna().iloc[-1] for r in analise.ORDEM_REGIOES},
                    suave.index[-1], folga=0.016)
    ax.set_ylim(0.5, 0.92)
    ax.set_xlim(suave.dropna(how="all").index[0], pd.Timestamp("2025-06-01"))
    ax.set_ylabel("Preço do etanol ÷ preço da gasolina")
    ax.set_title("Razão de preços etanol/gasolina por região (média móvel de 12 meses)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.1))
    fig.savefig(destino)
    plt.close(fig)


# --------------------------------------------------------------------------
# Dados dos gráficos interativos
# --------------------------------------------------------------------------
def _lista(valores, casas: int = 3) -> list:
    """Converte para lista JSON, trocando NaN por ``None``."""
    return [None if pd.isna(v) else round(float(v), casas) for v in valores]


def _datas(indice: pd.DatetimeIndex) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in indice]


def dados_interativos(precos: pd.DataFrame, paridade: pd.DataFrame) -> dict:
    """Monta o dicionário consumido pelo Plotly.js em ``docs/index.html``."""
    # Figura 1 — série nacional (R$/L)
    serie = analise.serie_nacional(precos)[COMBUSTIVEIS_POR_LITRO]
    fig1 = {
        "datas": _datas(serie.index),
        "series": [{"nome": analise.rotulo(c), "cor": COR[c], "y": _lista(serie[c], 4)}
                   for c in COMBUSTIVEIS_POR_LITRO],
    }

    # Figura 2 — variação mensal da gasolina e meses atípicos
    var = analise.serie_nacional(precos, "var_mensal_pct")["gasolina_comum"].dropna()
    fora = analise.outliers_variacao(precos)
    fora = fora[fora["combustivel"] == "gasolina_comum"]
    fig2 = {
        "datas": _datas(var.index), "y": _lista(var, 2),
        "atipico": [bool(v) for v in var.index.isin(fora["data"])],
        "limites": [round(float(fora["limite_inferior"].iloc[0]), 2),
                    round(float(fora["limite_superior"].iloc[0]), 2)],
    }

    # Figura 3 — diferença de cada UF em relação à mediana, por combustível
    fig3 = {}
    for comb in COMBUSTIVEIS_RANKING:
        r = analise.ranking_estados(precos, comb)
        fig3[comb] = {
            "nome": analise.rotulo(comb), "ufs": r["uf"].tolist(), "estados": r["estado"].tolist(),
            "regioes": r["regiao"].tolist(), "y": _lista(r["indice_medio"] - 100, 1),
        }

    # Figura 4 — dispersão entre UFs (média móvel de 12 meses)
    disp = analise.dispersao_interestadual(precos)
    combs = ["etanol_hidratado", "gas_cozinha_glp", "oleo_diesel", "gasolina_comum"]
    cv = disp.pivot(index="data", columns="combustivel", values="cv_pct")[combs]
    cv = cv.rolling(12, min_periods=6).mean().dropna(how="all")
    fig4 = {
        "datas": _datas(cv.index),
        "series": [{"nome": analise.rotulo(c), "cor": COR[c], "y": _lista(cv[c], 2)} for c in combs],
    }

    # Figura 5 — % de meses com etanol vantajoso, por UF
    r = analise.paridade_resumo_por_uf(paridade)
    fig5 = {
        "ufs": r["uf"].tolist(), "estados": r["estado"].tolist(), "regioes": r["regiao"].tolist(),
        "y": _lista(r["pct_meses_vantajoso"], 1), "razao": _lista(r["razao_media"], 3),
    }

    # Figura 6 — razão etanol/gasolina por região (média móvel de 12 meses)
    reg = analise.paridade_por_regiao(paridade)[analise.ORDEM_REGIOES]
    reg = reg.rolling(12, min_periods=6).mean().dropna(how="all")
    fig6 = {
        "datas": _datas(reg.index), "limiar": LIMIAR_PARIDADE,
        "series": [{"nome": rg, "cor": COR_REGIAO[rg], "y": _lista(reg[rg], 3)}
                   for rg in analise.ORDEM_REGIOES],
    }
    return {"cor_regiao": COR_REGIAO, "ordem_regioes": analise.ORDEM_REGIOES,
            "fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig5": fig5, "fig6": fig6}


# --------------------------------------------------------------------------
# Números citados no artigo
# --------------------------------------------------------------------------
def numeros_chave(precos: pd.DataFrame, paridade: pd.DataFrame) -> dict:
    """Reúne, em um só lugar, os números usados no texto do artigo."""
    resumo = analise.resumo_periodo(precos)
    est = analise.estatisticas_variacao(precos)
    fora = analise.outliers_variacao(precos)
    var = analise.serie_nacional(precos, "var_mensal_pct")
    disp = analise.dispersao_interestadual(precos)
    disp["ano"] = disp["data"].dt.year
    corr = analise.correlacao_variacoes(precos)
    serie = analise.serie_nacional(precos)

    n: dict = {"rq1": {}, "rq2": {}, "rq3": {}, "base": {}}
    n["base"] = {
        "observacoes_precos": int(len(precos)),
        "observacoes_paridade": int(len(paridade)),
        "primeiro_mes": precos["referencia"].min(), "ultimo_mes": precos["referencia"].max(),
        "meses": int(precos["referencia"].nunique()),
        "chaves_recuperadas_linhas_brutas": int(
            precos[precos["chave_recuperada"]].drop_duplicates(["referencia", "uf"]).shape[0]),
    }
    n["rq1"]["resumo"] = {
        c: {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v)
            for k, v in linha.items()}
        for c, linha in resumo.to_dict("index").items()
    }
    n["rq1"]["variacao_mensal"] = {
        c: {k: round(float(v), 2) for k, v in linha.items()} for c, linha in est.to_dict("index").items()
    }
    gas = fora[fora["combustivel"] == "gasolina_comum"]
    n["rq1"]["outliers"] = {
        "por_combustivel": {k: int(v) for k, v in fora.groupby("combustivel").size().items()},
        "gasolina_total": int(len(gas)),
        "gasolina_2001_2005": int((gas["data"].dt.year <= 2005).sum()),
        "gasolina_2006_2019": int(gas["data"].dt.year.between(2006, 2019).sum()),
        "gasolina_2020_2022": int(gas["data"].dt.year.between(2020, 2022).sum()),
        "gasolina_extremos": {
            d.strftime("%Y-%m"): round(float(v), 2)
            for d, v in var["gasolina_comum"].dropna().sort_values(key=abs, ascending=False).head(6).items()
        },
        "limites_gasolina": [round(float(gas["limite_inferior"].iloc[0]), 2),
                             round(float(gas["limite_superior"].iloc[0]), 2)],
    }
    n["rq1"]["meses_citados"] = {
        f"{c}|{m}": round(float(var.loc[pd.Timestamp(m + "-01"), c]), 2)
        for c, m in [("gasolina_comum", "2002-01"), ("gasolina_comum", "2002-11"),
                     ("oleo_diesel", "2002-11"), ("etanol_hidratado", "2002-11"),
                     ("oleo_diesel", "2018-05"), ("oleo_diesel", "2018-06"),
                     ("gasolina_comum", "2020-04"), ("gasolina_comum", "2020-05"),
                     ("oleo_diesel", "2022-03"), ("gasolina_comum", "2021-03"),
                     ("gasolina_comum", "2022-07"), ("gasolina_comum", "2022-08"),
                     ("gasolina_comum", "2022-09"), ("oleo_diesel", "2022-07"),
                     ("etanol_hidratado", "2022-07")]
    }
    n["rq1"]["precos_citados"] = {
        f"{c}|{m}": round(float(serie.loc[pd.Timestamp(m + "-01"), c]), 3)
        for c, m in [("gasolina_comum", "2020-05"), ("gasolina_comum", "2022-05"),
                     ("gasolina_comum", "2022-06"), ("gasolina_comum", "2022-09"),
                     ("gasolina_comum", "2022-07"), ("oleo_diesel", "2022-07"),
                     ("oleo_diesel", "2020-05")]
    }
    diesel_acima = serie["oleo_diesel"] > serie["gasolina_comum"]
    n["rq1"]["diesel_acima_da_gasolina"] = {
        "meses": int(diesel_acima.sum()),
        "primeiro": serie.index[diesel_acima][0].strftime("%Y-%m") if diesel_acima.any() else None,
    }
    n["rq1"]["correlacao"] = {
        f"{a}|{b}": round(float(corr.loc[a, b]), 2)
        for a, b in [("gasolina_comum", "oleo_diesel"), ("gasolina_comum", "etanol_hidratado"),
                     ("etanol_hidratado", "oleo_diesel"), ("gasolina_comum", "gas_cozinha_glp"),
                     ("oleo_diesel", "gas_cozinha_glp"), ("etanol_hidratado", "gas_cozinha_glp")]
    }

    combs = ["gasolina_comum", "etanol_hidratado", "oleo_diesel", "gas_cozinha_glp"]
    n["rq2"]["cv_medio_periodo"] = {
        c: round(float(disp.loc[disp["combustivel"] == c, "cv_pct"].mean()), 2) for c in combs}
    n["rq2"]["razao_max_min_media"] = {
        c: round(float(disp.loc[disp["combustivel"] == c, "razao_max_min"].mean()), 2) for c in combs}
    cv_anual = disp[disp["combustivel"].isin(combs)].pivot_table(
        index="ano", columns="combustivel", values="cv_pct", aggfunc="mean")
    n["rq2"]["cv_anual"] = {
        c: {str(a): round(float(cv_anual.loc[a, c]), 2) for a in (2002, 2010, 2013, 2019, 2020, 2021, 2022)}
        for c in combs}
    gasolina = disp[disp["combustivel"] == "gasolina_comum"]
    n["rq2"]["uf_mais_cara_gasolina"] = {k: int(v) for k, v in gasolina["uf_mais_cara"].value_counts().head(4).items()}
    n["rq2"]["uf_mais_barata_gasolina"] = {k: int(v) for k, v in gasolina["uf_mais_barata"].value_counts().head(4).items()}
    n["rq2"]["meses_gasolina"] = int(len(gasolina))
    n["rq2"]["ranking"] = {}
    n["rq2"]["persistencia_spearman"] = {}
    for c in combs:
        r = analise.ranking_estados(precos, c)
        n["rq2"]["ranking"][c] = {
            "mais_caras": [(u, round(float(v), 1)) for u, v in zip(r["uf"].head(5), r["indice_medio"].head(5))],
            "mais_baratas": [(u, round(float(v), 1)) for u, v in zip(r["uf"].tail(5), r["indice_medio"].tail(5))],
            "norte_no_top5": int((r.head(5)["regiao"] == "Norte").sum()),
        }
        n["rq2"]["persistencia_spearman"][c] = round(analise.persistencia_ranking(
            precos, c, ("2001-07-01", "2006-12-01"), ("2017-01-01", "2023-01-01")), 2)

    br = paridade[paridade["nivel_geografico"] == "BRASIL"]
    es = paridade[paridade["nivel_geografico"] == "ESTADO"]
    por_uf = analise.paridade_resumo_por_uf(paridade)
    regioes = analise.paridade_por_regiao(paridade)
    anual_br = br.groupby("ano")["razao_etanol_gasolina"].mean()
    saz = analise.sazonalidade_paridade(paridade)
    n["rq3"] = {
        "brasil_razao_media": round(float(br["razao_etanol_gasolina"].mean()), 3),
        "brasil_razao_min": [br.loc[br["razao_etanol_gasolina"].idxmin(), "referencia"],
                             round(float(br["razao_etanol_gasolina"].min()), 3)],
        "brasil_razao_max": [br.loc[br["razao_etanol_gasolina"].idxmax(), "referencia"],
                             round(float(br["razao_etanol_gasolina"].max()), 3)],
        "brasil_pct_meses_vantajoso": round(float(br["etanol_vantajoso"].mean() * 100), 1),
        "estados_pct_observacoes_vantajoso": round(float(es["etanol_vantajoso"].mean() * 100), 1),
        "estados_observacoes": int(len(es)),
        "por_uf_pct": {u: round(float(v), 1) for u, v in zip(por_uf["uf"], por_uf["pct_meses_vantajoso"])},
        "por_uf_razao_media": {u: round(float(v), 3) for u, v in zip(por_uf["uf"], por_uf["razao_media"])},
        "ufs_maioria_dos_meses": por_uf.loc[por_uf["pct_meses_vantajoso"] > 50, "uf"].tolist(),
        "ufs_abaixo_de_5pct": por_uf.loc[por_uf["pct_meses_vantajoso"] < 5, "uf"].tolist(),
        "brasil_media_2001_2010": round(float(br.loc[br["ano"] <= 2010, "razao_etanol_gasolina"].mean()), 3),
        "brasil_media_2011_2022": round(float(br.loc[br["ano"].between(2011, 2022), "razao_etanol_gasolina"].mean()), 3),
        "brasil_pct_vantajoso_2001_2010": round(float(br.loc[br["ano"] <= 2010, "etanol_vantajoso"].mean() * 100), 1),
        "brasil_pct_vantajoso_2011_2022": round(float(br.loc[br["ano"].between(2011, 2022), "etanol_vantajoso"].mean() * 100), 1),
        "brasil_anual": {str(a): round(float(anual_br.loc[a]), 3) for a in (2009, 2011, 2015, 2021, 2022)},
        "regioes_media": {r: round(float(regioes[r].mean()), 3) for r in analise.ORDEM_REGIOES},
        "sazonalidade": {str(int(m)): round(float(v), 3) for m, v in saz.items()},
    }
    return n


# --------------------------------------------------------------------------
# Orquestração
# --------------------------------------------------------------------------
def executar(dir_assets: Path = DIR_ASSETS) -> dict:
    """Gera todas as figuras, os dados interativos e o arquivo de números."""
    _estilo()
    dir_assets.mkdir(parents=True, exist_ok=True)
    precos, paridade = ler_precos(), ler_paridade()

    fig_serie_nacional(precos, dir_assets / "fig_serie_nacional.png")
    fig_variacao_mensal(precos, dir_assets / "fig_variacao_mensal.png")
    fig_ranking_estados(precos, dir_assets / "fig_ranking_estados.png")
    fig_dispersao_interestadual(precos, dir_assets / "fig_dispersao_interestadual.png")
    fig_etanol_por_uf(paridade, dir_assets / "fig_etanol_por_uf.png")
    fig_paridade_regioes(paridade, dir_assets / "fig_paridade_regioes.png")

    dados = dados_interativos(precos, paridade)
    conteudo = ("// Gerado por src/figuras.py — não editar manualmente.\n"
                "window.DADOS_ARTIGO = " + json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
                + ";\n")
    (dir_assets / "dados_graficos.js").write_text(conteudo, encoding="utf-8")

    numeros = numeros_chave(precos, paridade)
    (dir_assets / "numeros_chave.json").write_text(
        json.dumps(numeros, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for arquivo in sorted(dir_assets.iterdir()):
        log.info("gerado docs/assets/%-34s %7.1f kB", arquivo.name, arquivo.stat().st_size / 1024)
    return numeros


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    executar()

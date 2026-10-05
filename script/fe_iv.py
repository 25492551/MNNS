"""가구 고정효과 + 시점 고정효과 OLS/2SLS (04_fit.py, 05_validate.py 공용).

불균형 패널에서 가구 평균을 뺀 뒤 시점 더미(역시 가구 평균 제거)를 외생변수로 넣는다.
FWL 정리로 이원 고정효과와 같다. 표준오차는 district 군집이다.
한 번만 관측된 가구는 within 변동이 없어 뺀다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.iv import IV2SLS, IVLIML

WAVE_DUMMIES = ["y2010", "y2012", "y2014", "y2016"]


def prepare(df: pd.DataFrame, cols: list[str], group: str = "hhid") -> pd.DataFrame:
    d = df.dropna(subset=cols).copy()
    d = d[d.groupby(group)[group].transform("size") > 1].copy()
    for y in (2010, 2012, 2014, 2016):
        d[f"y{y}"] = (d.wave == y).astype(float)
    allc = list(dict.fromkeys(cols + WAVE_DUMMIES))
    dm = d[allc] - d.groupby(group)[allc].transform("mean")
    keep = [c for c in WAVE_DUMMIES if dm[c].abs().sum() > 0]
    if keep and (d[keep].sum(axis=1) == 1).all():
        keep = keep[1:]
    dm = dm.drop(columns=[c for c in WAVE_DUMMIES if c not in keep])
    dm[group] = d[group].values
    dm["district"] = d["district"].values
    dm["tinh"] = d["tinh"].values
    dm["wave"] = d["wave"].values
    dm.attrs["wave_cols"] = keep
    return dm


def fit(df: pd.DataFrame, y: str, exog: list[str], endog: list[str] | None = None,
        instr: list[str] | None = None, method: str = "2sls", group: str = "hhid"):
    endog = endog or []
    instr = instr or []
    cols = [y] + exog + endog + instr
    dm = prepare(df, cols, group)
    x = exog + dm.attrs["wave_cols"]
    model_cls = IVLIML if method == "liml" else IV2SLS
    m = model_cls(dm[y], dm[x], dm[endog] if endog else None, dm[instr] if instr else None)
    res = m.fit(cov_type="clustered", clusters=dm["district"])
    res.n_hh = dm[group].nunique()
    res.n_cl = dm.district.nunique()
    return res


def coef_table(res, names: list[str]) -> pd.DataFrame:
    t = pd.DataFrame({"coef": res.params, "se": res.std_errors, "p": res.pvalues})
    return t.loc[[n for n in names if n in t.index]]


def stars(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def fmt(res, names: list[str], digits: int = 3) -> list[str]:
    t = coef_table(res, names)
    return [f"{n}: {r.coef:.{digits}f}{stars(r.p)} ({r.se:.{digits}f})" for n, r in t.iterrows()]


def iv_diag(res) -> dict:
    out = dict(nobs=int(res.nobs), n_hh=res.n_hh, n_cl=res.n_cl)
    try:
        fs = res.first_stage.diagnostics
        out["fs_F"] = float(fs["f.stat"].iloc[0])
        out["fs_F_p"] = float(fs["f.pval"].iloc[0])
        out["fs_partial_r2"] = float(fs["partial.rsquared"].iloc[0])
    except Exception:  # noqa: BLE001
        pass
    try:
        ov = res.wooldridge_overid
        out["overid_stat"], out["overid_p"] = float(ov.stat), float(ov.pval)
    except Exception:  # noqa: BLE001
        pass
    try:
        en = res.wooldridge_regression
        out["endog_stat"], out["endog_p"] = float(en.stat), float(en.pval)
    except Exception:  # noqa: BLE001
        pass
    return out

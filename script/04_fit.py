"""제안식 (R1)·(R2)·(R3) 피팅.

입력: data/derived/panel_hh.csv (03_build_panel.py)
출력: data/derived/results/fit_*.csv, data/derived/results/fit_summary.txt

부호: 제안식은 우변을 -θ ln(1+V), -π_D D 처럼 적는다. 여기 표의 계수 b는 회귀가 낸 값이고
θ = -b, π_D = -b_D, π_W = -b_W 이다.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fe_iv import coef_table, fit, iv_diag, prepare  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DER = ROOT / "data" / "derived"
RES = DER / "results"

X = ["a0_14", "a15_65", "a66p"]
PV = ["ln_urea", "ln_wage"]
PF = ["ln_pr", "ln_p_pork", "ln_p_chicken", "ln_p_fish"]
Z = ["D", "W"]
LINES: list[str] = []


def out(*a) -> None:
    s = " ".join(str(x) for x in a)
    LINES.append(s)
    print(s)


def sample(p: pd.DataFrame) -> pd.DataFrame:
    s = p[(p.rice_grower == 1)].copy()
    need = ["hdds", "asf", "lnV1"] + X + PV + PF + Z
    s = s.dropna(subset=need)
    s = s[s.groupby("hhid").hhid.transform("size") > 1]
    return s


def describe(s: pd.DataFrame) -> pd.DataFrame:
    cols = ["hdds", "asf", "V", "lnV1", "kg_recent", "uv", "D", "W", "Z", "a0_14", "a15_65", "a66p",
            "wage_m", "ln_pr", "p_pork", "p_chicken", "p_fish", "urea_usd_per_mt"]
    t = s[cols].describe(percentiles=[0.5]).T[["count", "mean", "std", "min", "50%", "max"]]
    by = s.groupby("wave")[["hdds", "asf", "lnV1", "D", "W"]].mean().T
    by.columns = [f"mean_{c}" for c in by.columns]
    return t.join(by, how="left")


def row(tag: str, res, names: list[str], extra: dict | None = None) -> list[dict]:
    t = coef_table(res, names)
    base = dict(spec=tag, nobs=int(res.nobs), n_hh=res.n_hh, n_cl=res.n_cl)
    base.update(extra or {})
    return [dict(base, var=n, coef=r.coef, se=r.se, p=r.p) for n, r in t.iterrows()]


def main() -> None:
    RES.mkdir(parents=True, exist_ok=True)
    p = pd.read_csv(DER / "panel_hh.csv")
    s = sample(p)
    out("estimation sample: hh-waves", len(s), "households", s.hhid.nunique(),
        "districts", s.district.nunique(), "by wave", s.groupby("wave").size().to_dict())
    out("rain level share (DIST)", round((s.rain_level == "DIST").mean(), 3))
    describe(s).round(3).to_csv(RES / "fit_describe.csv")

    rows, diags = [], []

    # (R2) 1단계, 문서 명세 그대로(식품가격 제외)
    r2 = fit(s, "lnV1", Z + PV + X)
    rows += row("R2_first_stage", r2, Z + PV + X)
    wt = r2.wald_test(formula="D = W = 0")
    diags.append(dict(spec="R2_first_stage", joint_F=float(wt.stat) / 2, joint_p=float(wt.pval),
                      nobs=int(r2.nobs)))
    out("[R2] first stage (doc spec)"); out(coef_table(r2, Z + PV + X).round(4).to_string())
    out("  joint Wald D=W=0: chi2", round(float(wt.stat), 2), "p", round(float(wt.pval), 4))

    for yv in ("hdds", "asf"):
        # (R1) 2SLS
        iv = fit(s, yv, PF + PV + X, ["lnV1"], Z)
        d = iv_diag(iv)
        rows += row(f"R1_2SLS_{yv}", iv, ["lnV1"] + PF + PV + X)
        diags.append(dict(spec=f"R1_2SLS_{yv}", **d))
        out(f"[R1 2SLS] {yv}"); out(coef_table(iv, ["lnV1"] + PF + PV + X).round(4).to_string()); out("  ", d)
        # LIML
        lm = fit(s, yv, PF + PV + X, ["lnV1"], Z, method="liml")
        rows += row(f"R1_LIML_{yv}", lm, ["lnV1"])
        out(f"[R1 LIML] {yv}", coef_table(lm, ["lnV1"]).round(4).to_string())
        # OLS FE
        ols = fit(s, yv, ["lnV1"] + PF + PV + X)
        rows += row(f"R1_OLS_{yv}", ols, ["lnV1"] + PF + PV + X)
        out(f"[R1 OLS FE] {yv}", coef_table(ols, ["lnV1"]).round(4).to_string())
        # (R3) 축약형: 가격·수확가치 없음
        r3 = fit(s, yv, Z)
        rows += row(f"R3_{yv}", r3, Z)
        out(f"[R3] {yv}"); out(coef_table(r3, Z).round(4).to_string())
        # 종료 기준 작기의 D, W
        se = s.dropna(subset=["D_end", "W_end"])
        ive = fit(se, yv, PF + PV + X, ["lnV1"], ["D_end", "W_end"])
        de = iv_diag(ive)
        rows += row(f"R1_2SLS_endrule_{yv}", ive, ["lnV1"])
        diags.append(dict(spec=f"R1_2SLS_endrule_{yv}", **de))
        out(f"[R1 2SLS end-rule] {yv}", coef_table(ive, ["lnV1"]).round(4).to_string(), de)

    r2e = fit(s, "lnV1", ["D_end", "W_end"] + PV + X)
    rows += row("R2_first_stage_endrule", r2e, ["D_end", "W_end"])
    out("[R2 end-rule]"); out(coef_table(r2e, ["D_end", "W_end"]).round(4).to_string())

    # Dillon Table 8형 점검: 가격을 D, W에 회귀 (commune-파동, commune·시점 고정효과)
    cm = (s.groupby(["commune_id", "wave"])
            .agg(district=("district", "first"), tinh=("tinh", "first"), D=("D", "mean"), W=("W", "mean"),
                 ln_pr=("ln_pr", "mean"), ln_p_pork=("ln_p_pork", "mean"),
                 ln_p_chicken=("ln_p_chicken", "mean"), ln_p_fish=("ln_p_fish", "mean"),
                 ln_wage=("ln_wage", "mean"))
            .reset_index())
    for pv in PF + ["ln_wage"]:
        t8 = fit(cm, pv, Z, group="commune_id")
        wt8 = t8.wald_test(formula="D = W = 0")
        rows += row(f"T8_{pv}", t8, Z, dict(joint_p=float(wt8.pval)))
        out(f"[Table8] {pv}", coef_table(t8, Z).round(4).to_string(), "joint p", round(float(wt8.pval), 4))

    pd.DataFrame(rows).to_csv(RES / "fit_coefficients.csv", index=False)
    pd.DataFrame(diags).to_csv(RES / "fit_diagnostics.csv", index=False)
    (RES / "fit_summary.txt").write_text("\n".join(LINES), encoding="utf-8")


if __name__ == "__main__":
    main()

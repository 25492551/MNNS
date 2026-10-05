"""자료 검증과 모형 점검.

A. 구축 자료 점검: 병합·대체 비율, 패널 연결, HDDS·ASF, V 구성, 강우·D/W, 작기 배정
B. 모형 점검: 1단계 대안 명세, 위약(면접 뒤 3개월 강우), 관개·지역 이질성, OLS 민감도

입력: data/derived/panel_hh.csv, data/derived/chirps_monthly_units.csv, VARHS commune 2014·2016
출력: data/derived/results/validate_*.csv, data/derived/results/validate_summary.txt
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fe_iv import coef_table, fit, iv_diag  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DER = ROOT / "data" / "derived"
RES = DER / "results"
CLEAN = ROOT / "data" / "VARHS-2008-16" / "VARHS-2008-16Clean" / "2008-16Clean"
EXT = ROOT / "data" / "external"

X = ["a0_14", "a15_65", "a66p"]
PV = ["ln_urea", "ln_wage"]
PF = ["ln_pr", "ln_p_pork", "ln_p_chicken", "ln_p_fish"]
NORTH = {105, 205, 217, 301, 302}
PROV_NAME = {105: "Ha Tay", 205: "Lao Cai", 217: "Phu Tho", 301: "Lai Chau", 302: "Dien Bien",
             403: "Nghe An", 503: "Quang Nam", 511: "Khanh Hoa", 605: "Dak Lak", 606: "Dak Nong",
             607: "Lam Dong", 801: "Long An"}
L: list[str] = []


def out(*a) -> None:
    s = " ".join(str(x) for x in a)
    L.append(s)
    print(s)


def sample(p: pd.DataFrame) -> pd.DataFrame:
    s = p[p.rice_grower == 1].dropna(subset=["hdds", "asf", "lnV1", "D", "W"] + X + PV + PF)
    return s[s.groupby("hhid").hhid.transform("size") > 1].copy()


def joint_first_stage(df, zs, y="lnV1", ctrl=None):
    ctrl = PV + X if ctrl is None else ctrl
    r = fit(df, y, zs + ctrl)
    w = r.wald_test(formula=" = ".join(zs) + " = 0") if len(zs) > 1 else None
    t = coef_table(r, zs)
    stat = float(w.stat) / len(zs) if w is not None else float((t.coef / t.se).iloc[0] ** 2)
    pval = float(w.pval) if w is not None else float(t.p.iloc[0])
    rec = dict(nobs=int(r.nobs), n_hh=r.n_hh, n_cl=r.n_cl, F=stat, F_p=pval)
    for n, rr in t.iterrows():
        rec[f"b_{n}"], rec[f"se_{n}"], rec[f"p_{n}"] = rr.coef, rr.se, rr.p
    return rec


# ---------------------------------------------------------------- A. 자료
def check_data(p: pd.DataFrame, s: pd.DataFrame) -> None:
    rg = p[p.rice_grower == 1]
    out("== A1 병합과 대체")
    a1 = rg.groupby("wave").agg(n=("hhid", "size"), month_imp=("month_imputed", "mean"),
                                wage_imp=("wage_imputed", "mean"), uv_imp=("uv_imputed", "mean"),
                                V_na=("V", lambda v: v.isna().mean()), V0=("V", lambda v: (v == 0).mean()),
                                rain_dist=("rain_level", lambda v: (v == "DIST").mean()))
    a1.round(3).to_csv(RES / "validate_A1_merge.csv")
    out(a1.round(3).to_string())

    out("== A2 패널 연결")
    nw = p.groupby("hhid").wave.nunique()
    out("waves per household (all hh):", nw.value_counts().sort_index().to_dict())
    p2 = p.sort_values(["hhid", "wave"]).copy()
    p2["prev_size"] = p2.groupby("hhid").hhsize.shift()
    p2["prev_wave"] = p2.groupby("hhid").wave.shift()
    p2["prev_tinh"] = p2.groupby("hhid").tinh.shift()
    cons = p2[p2.prev_wave.notna() & (p2.wave - p2.prev_wave == 2)]
    d = (cons.hhsize - cons.prev_size).abs()
    a2 = dict(linked_pairs=len(cons), share_abs_dsize_le2=float((d <= 2).mean()),
              share_abs_dsize_ge5=float((d >= 5).mean()), province_changed=int((cons.tinh != cons.prev_tinh).sum()))
    out(a2)
    pd.Series(a2).to_csv(RES / "validate_A2_panel.csv")

    out("== A3 HDDS·ASF")
    fg = [f"fg{i:02d}" for i in range(1, 12)]
    a3 = s.groupby("wave").agg(hdds_mean=("hdds", "mean"), hdds_sd=("hdds", "std"),
                               asf_mean=("asf", "mean"), cereal=("fg01", "mean"))
    a3["asf_gt_hdds"] = s.groupby("wave").apply(lambda g: int((g.asf > g.hdds).sum()))
    shares = s[fg].mean().rename(lambda c: c.replace("fg", "g"))
    a3.round(3).to_csv(RES / "validate_A3_hdds.csv")
    shares.round(3).to_csv(RES / "validate_A3_food_group_shares.csv")
    out(a3.round(3).to_string()); out("group shares", shares.round(3).to_dict())
    out("hdds distribution", s.hdds.value_counts().sort_index().to_dict())

    out("== A4 V 구성")
    v = rg.dropna(subset=["kg_recent", "kg12"]).copy()
    v = v[(v.kg12 > 0) & (v.kg_recent > 0)]
    v["ratio"] = v.kg_recent / v.kg12
    a4 = v.groupby(["tinh", "season_s"]).ratio.describe(percentiles=[0.25, 0.5, 0.75])[
        ["count", "25%", "50%", "75%"]]
    a4["share_gt_1.05"] = v.groupby(["tinh", "season_s"]).ratio.apply(lambda r: (r > 1.05).mean())
    a4.index = [f"{PROV_NAME[t]}|{sname}" for t, sname in a4.index]
    a4.round(3).to_csv(RES / "validate_A4_recent_share.csv")
    out(a4.round(3).to_string())
    fao = pd.read_csv(EXT / "faostat" / "vnm_rice_producer_price_lcu.csv")
    fao = fao[fao.month == "Annual value"].set_index("year").value / 1e6
    uv = rg[rg.uv_imputed == 0].groupby("wave").uv_hh.median()
    a4b = pd.DataFrame({"varhs_uv_median_kVND_per_kg": uv, "faostat_annual_kVND_per_kg": fao.reindex(uv.index)})
    a4b["ratio"] = a4b.iloc[:, 0] / a4b.iloc[:, 1]
    a4b.round(3).to_csv(RES / "validate_A4_unit_value.csv")
    out(a4b.round(3).to_string())
    lv = s[s.V > 0]
    out("ln V sd (V>0):", round(np.log(lv.V).std(), 3), "within-hh sd:",
        round((np.log(lv.V) - np.log(lv.V).groupby(lv.hhid).transform("mean")).std(), 3))

    out("== A5 강우와 D/W")
    r = pd.read_csv(DER / "chirps_monthly_units.csv")
    pr = r[r.unit.str.startswith("PROV:") & (r.year <= 2007)]
    ann = pr.groupby(["unit", "year"]).precip_mm.sum().groupby("unit").mean().round(0)
    ann.index = [PROV_NAME[int(u.split(":")[1])] for u in ann.index]
    ann.to_csv(RES / "validate_A5_annual_rain_1981_2007.csv")
    out("mean annual rain 1981-2007 (mm)", ann.to_dict())
    zz = s.groupby(["district", "wave"])[["Z", "Z_prov", "Z_end", "Z_post"]].first().reset_index()
    a5 = zz.groupby("wave").agg(Z_mean=("Z", "mean"), Z_sd=("Z", "std"), share_dry=("Z", lambda z: (z < 0).mean()),
                                share_absZ_gt1=("Z", lambda z: (z.abs() > 1).mean()))
    a5.round(3).to_csv(RES / "validate_A5_Z_by_wave.csv")
    out(a5.round(3).to_string())
    zz["Z_dm"] = zz.Z - zz.groupby("wave").Z.transform("mean")
    out("district-wave cells", len(zz), "corr(Z, Z_prov)", round(zz.Z.corr(zz.Z_prov), 3),
        "corr(Z, Z_end)", round(zz.Z.corr(zz.Z_end), 3),
        "share of Z variance within wave", round(zz.Z_dm.var() / zz.Z.var(), 3))
    pz = s.groupby(["tinh", "wave"]).Z.mean().unstack().round(2)
    pz.index = [PROV_NAME[t] for t in pz.index]
    pz.to_csv(RES / "validate_A5_Z_province_wave.csv")
    out(pz.to_string())

    out("== A6 작기 배정(시작 기준) 진단: 최근 작기 쌀 kg / 두 번째 작기 쌀 kg")
    q = rg[(rg.kg_recent > 0) & (rg.kg_second > 0)].copy()
    q["lr"] = np.log(q.kg_recent / q.kg_second)
    a6 = q[q.tinh.isin(NORTH | {403})].groupby(["tinh", "wave", "month"]).lr.agg(
        ["count", "median", lambda x: (x > 0).mean()])
    a6.columns = ["n", "median_log_ratio", "share_recent_larger"]
    a6 = a6[a6.n >= 20]
    a6.index = [f"{PROV_NAME[t]}|{w}|m{m}" for t, w, m in a6.index]
    a6.round(3).to_csv(RES / "validate_A6_season_ratio.csv")
    out(a6.round(3).to_string())


# ---------------------------------------------------------------- B. 모형
def irrigation() -> pd.Series:
    vals = []
    for yy, y in (("14", 2014), ("16", 2016)):
        c = pd.read_stata(CLEAN / "commune_clean" / f"commune_{yy}_clean.dta", convert_categoricals=False,
                          columns=[f"tinh_{y}", f"quan_{y}", f"xa_{y}", "s4q29_1"]).dropna()
        k = c[[f"tinh_{y}", f"quan_{y}", f"xa_{y}"]].astype("int64")
        c["commune_id"] = k.iloc[:, 0] * 10000 + k.iloc[:, 1] * 100 + k.iloc[:, 2]
        vals.append(c[["commune_id", "s4q29_1"]])
    return pd.concat(vals).groupby("commune_id").s4q29_1.mean()


def check_model(s: pd.DataFrame) -> None:
    out("== B1 1단계 대안 명세 (결합 F = D, W 결합 Wald/2, district 군집)")
    s = s.copy()
    s["ln_kg1"] = np.log1p(s.kg_recent)
    s["Zpos"], s["Zneg"] = s.W, s.D
    s["Z2"] = s.Z ** 2
    s["D1"] = (s.Z < -1).astype(float)
    s["W1"] = (s.Z > 1).astype(float)
    specs = {
        "main: lnV1 ~ D,W (district, start)": (s, ["D", "W"], "lnV1"),
        "quantity: ln(1+kg) ~ D,W": (s, ["D", "W"], "ln_kg1"),
        "province rain: lnV1 ~ D_prov,W_prov": (s, ["D_prov", "W_prov"], "lnV1"),
        "end rule: lnV1 ~ D_end,W_end": (s, ["D_end", "W_end"], "lnV1"),
        "linear+square: lnV1 ~ Z,Z^2": (s, ["Z", "Z2"], "lnV1"),
        "extreme: lnV1 ~ 1[Z<-1],1[Z>1]": (s, ["D1", "W1"], "lnV1"),
        "placebo: lnV1 ~ D_post,W_post": (s, ["D_post", "W_post"], "lnV1"),
        "V>0 only: lnV1 ~ D,W": (s[s.V > 0], ["D", "W"], "lnV1"),
        "district-rain only: lnV1 ~ D,W": (s[s.rain_level == "DIST"], ["D", "W"], "lnV1"),
    }
    rows = []
    for k, (df, zs, yv) in specs.items():
        rec = joint_first_stage(df, zs, yv)
        rows.append(dict(spec=k, **rec))
    b1 = pd.DataFrame(rows).set_index("spec")
    b1.round(4).to_csv(RES / "validate_B1_first_stage.csv")
    out(b1[["nobs", "F", "F_p"] + [c for c in b1.columns if c.startswith("b_")]].round(4).to_string())

    out("== B2 위약 축약형: HDDS ~ 면접 뒤 3개월 D,W")
    rows = []
    for yv in ("hdds", "asf"):
        for zs, tag in ((["D", "W"], "R3 main"), (["D_post", "W_post"], "R3 placebo post-interview")):
            r = fit(s, yv, zs)
            for n, rr in coef_table(r, zs).iterrows():
                rows.append(dict(outcome=yv, spec=tag, var=n, coef=rr.coef, se=rr.se, p=rr.p, nobs=int(r.nobs)))
    b2 = pd.DataFrame(rows)
    b2.round(4).to_csv(RES / "validate_B2_placebo.csv", index=False)
    out(b2.round(4).to_string(index=False))

    out("== B3 이질성: 관개 비율, 지역")
    irr = irrigation()
    s["irr"] = s.commune_id.map(irr)
    s["irr_low"] = s.irr < s.irr.median()
    rows = []
    groups = {
        "irrigation below median": s[s.irr_low == True],  # noqa: E712
        "irrigation at/above median": s[s.irr_low == False],  # noqa: E712
        "north (5 provinces)": s[s.tinh.isin(NORTH)],
        "central/highlands/south": s[~s.tinh.isin(NORTH)],
    }
    out("irrigation share median", round(float(s.irr.median()), 1), "coverage", round(float(s.irr.notna().mean()), 3))
    for k, df in groups.items():
        rows.append(dict(group=k, **joint_first_stage(df, ["D", "W"])))
    for t in sorted(s.tinh.unique()):
        rows.append(dict(group=f"drop {PROV_NAME[t]}", **joint_first_stage(s[s.tinh != t], ["D", "W"])))
    b3 = pd.DataFrame(rows).set_index("group")
    b3.round(4).to_csv(RES / "validate_B3_heterogeneity.csv")
    out(b3[["nobs", "F", "F_p", "b_D", "p_D", "b_W", "p_W"]].round(4).to_string())

    out("== B4 OLS FE 민감도 (lnV1 계수)")
    lo, hi = s.V[s.V > 0].quantile([0.01, 0.99])
    bal = s[s.groupby("hhid").wave.transform("nunique") == 5]
    subs = {
        "full": s,
        "no imputed month/wage/unit value": s[(s.month_imputed == 0) & (s.wage_imputed == 0) & (s.uv_imputed == 0)],
        "trim V 1-99% (V>0)": s[(s.V >= lo) & (s.V <= hi)],
        "balanced 5 waves": bal,
        "district rain only": s[s.rain_level == "DIST"],
    }
    subs["V>0 only"] = s[s.V > 0]
    s["V0"] = (s.V == 0).astype(float)
    rows = []
    for k, df in subs.items():
        for yv in ("hdds", "asf"):
            r = fit(df, yv, ["lnV1"] + PF + PV + X)
            t = coef_table(r, ["lnV1"]).iloc[0]
            rows.append(dict(sample=k, outcome=yv, coef=t.coef, se=t.se, p=t.p, nobs=int(r.nobs), n_hh=r.n_hh))
    for yv in ("hdds", "asf"):
        r = fit(s, yv, ["lnV1", "V0"] + PF + PV + X)
        for n, t in coef_table(r, ["lnV1", "V0"]).iterrows():
            rows.append(dict(sample=f"full + 1[V=0] ({n})", outcome=yv, coef=t.coef, se=t.se, p=t.p,
                             nobs=int(r.nobs), n_hh=r.n_hh))
    out("V==0 hh-waves in sample", int((s.V == 0).sum()), "households with any V==0",
        int(s[s.V == 0].hhid.nunique()))
    b4 = pd.DataFrame(rows)
    b4.round(4).to_csv(RES / "validate_B4_ols_sensitivity.csv", index=False)
    out(b4.round(4).to_string(index=False))

    out("== B5 1단계 F가 약할 때 2SLS: just-identified D만, W만")
    rows = []
    for zs in (["D"], ["W"], ["D", "W"]):
        r = fit(s, "hdds", PF + PV + X, ["lnV1"], zs)
        dg = iv_diag(r)
        t = coef_table(r, ["lnV1"]).iloc[0]
        rows.append(dict(instruments="+".join(zs), coef=t.coef, se=t.se, p=t.p, **dg))
    b5 = pd.DataFrame(rows)
    b5.round(4).to_csv(RES / "validate_B5_iv_variants.csv", index=False)
    out(b5.round(4).to_string(index=False))


def main() -> None:
    RES.mkdir(parents=True, exist_ok=True)
    p = pd.read_csv(DER / "panel_hh.csv")
    s = sample(p)
    check_data(p, s)
    check_model(s)
    (RES / "validate_summary.txt").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

"""기본 데이터 특성 통계.

입력: data/derived/panel_hh.csv (03_build_panel.py), data/external/gso/district_codes_2002.csv
출력: data/derived/results/desc_*.csv, data/derived/results/desc_summary.txt

추정 표본은 04_fit.py의 sample()과 같다. 가격·임금은 일반 CPI(2015=100) 면접월 값으로 실질화한 2015년 가격이다.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DER = ROOT / "data" / "derived"
RES = DER / "results"
sample = import_module("04_fit").sample

FG = {"fg01": "곡류", "fg02": "서류", "fg03": "채소", "fg04": "과일", "fg05": "육류",
      "fg06": "계란", "fg07": "어류", "fg08": "두류·견과", "fg09": "유제품", "fg10": "유지",
      "fg11": "당류"}
LINES: list[str] = []


def out(*a) -> None:
    s = " ".join(str(x) for x in a)
    LINES.append(s)
    print(s)


def section(title: str, df: pd.DataFrame, name: str, nd: int = 3) -> None:
    df.round(nd).to_csv(RES / f"desc_{name}.csv", encoding="utf-8-sig")
    out(f"\n## {title}  [desc_{name}.csv]")
    out(df.round(nd).to_string())


def add_real(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    p["pr_real"] = np.exp(p.ln_pr)
    p["pork_real"] = np.exp(p.ln_p_pork)
    p["chicken_real"] = np.exp(p.ln_p_chicken)
    p["fish_real"] = np.exp(p.ln_p_fish)
    p["wage_real"] = np.exp(p.ln_wage)
    p["V0"] = (p.V == 0).astype(float).where(p.V.notna())
    p["Dpos"] = (p.D > 0).astype(float).where(p.D.notna())
    p["Wpos"] = (p.W > 0).astype(float).where(p.W.notna())
    return p


VARS = {
    "hdds": "HDDS (0–11)", "asf": "ASF (0–4)",
    "V": "V 최근 작기 쌀 수확가치 (2015년 천 동)", "lnV1": "ln(1+V)", "V0": "V=0 비율",
    "kg_recent": "최근 작기 쌀 수확량 (kg)", "uv": "쌀 단가 (명목 천 동/kg)",
    "Z": "Z 작기 강우 표준화 편차", "D": "D 건조 강도", "W": "W 과잉 강도",
    "Dpos": "D>0 비율", "Wpos": "W>0 비율",
    "hhsize": "가구원 수", "a0_14": "0–14세", "a15_65": "15–65세", "a66p": "66세 이상",
    "pr_real": "쌀 농가수취가 (2015년 동/kg)", "pork_real": "돼지고기 (2015년 천 동/kg)",
    "chicken_real": "닭고기 (2015년 천 동/kg)", "fish_real": "생선 (2015년 천 동/kg)",
    "urea_usd_per_mt": "요소 국제가 (달러/톤)", "wage_real": "남성 수확 일당 (2015년 천 동)",
}


def main() -> None:
    RES.mkdir(parents=True, exist_ok=True)
    p = add_real(pd.read_csv(DER / "panel_hh.csv"))
    s = add_real(sample(pd.read_csv(DER / "panel_hh.csv")))
    out("# 기본 데이터 특성 통계")
    out("estimation sample hh-waves", len(s), "households", s.hhid.nunique(),
        "communes", s.commune_id.nunique(), "districts", s.district.nunique(), "provinces", s.tinh.nunique())

    # 1. 표본 흐름
    rg = p[p.rice_grower == 1]
    flow = pd.DataFrame({
        "전체 가구": p.groupby("wave").size(),
        "쌀 재배 가구": rg.groupby("wave").size(),
        "V 결측": rg.groupby("wave").V.apply(lambda v: v.isna().sum()),
        "V=0": rg.groupby("wave").V.apply(lambda v: (v == 0).sum()),
        "추정 표본": s.groupby("wave").size(),
    }).T
    flow["합계"] = flow.sum(axis=1)
    section("표본 흐름", flow, "sample_flow", 0)

    # 2. 패널 균형
    nw = s.groupby("hhid").wave.nunique().value_counts().sort_index()
    section("가구당 관측 파동 수 (추정 표본)",
            pd.DataFrame({"가구": nw, "가구 비율": nw / nw.sum()}), "panel_balance")

    # 3. 전체 요약
    cols = list(VARS)
    t = s[cols].describe(percentiles=[0.25, 0.5, 0.75]).T
    t.index = [VARS[c] for c in t.index]
    section("추정 표본 요약 통계", t[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]], "summary")

    q = [0.9, 0.95, 0.99, 0.999, 1.0]
    tail = s[["V", "kg_recent", "uv"]].quantile(q).T
    tail.columns = [f"p{c * 100:g}" for c in q]
    tail["n>p99"] = [(s[c] > s[c].quantile(0.99)).sum() for c in ["V", "kg_recent", "uv"]]
    tail.index = [VARS[c] for c in tail.index]
    section("수확가치·수확량 상위 꼬리", tail, "tail", 1)

    # 4. 파동별 평균(표준편차)
    wcols = ["hdds", "asf", "V", "lnV1", "V0", "kg_recent", "Z", "D", "W", "Dpos", "Wpos", "hhsize",
             "a0_14", "a15_65", "a66p", "pr_real", "pork_real", "chicken_real", "fish_real",
             "urea_usd_per_mt", "wage_real"]
    m = s.groupby("wave")[wcols].mean().T
    sd = s.groupby("wave")[wcols].std().T
    m["전체"] = s[wcols].mean()
    sd["전체"] = s[wcols].std()
    m.index = sd.index = [VARS[c] for c in wcols]
    section("파동별 평균", m, "by_wave_mean")
    section("파동별 표준편차", sd, "by_wave_sd")
    med = s.groupby("wave")[["V", "kg_recent"]].median().T
    med.index = [VARS[c] for c in med.index]
    section("파동별 중앙값", med, "by_wave_median", 1)

    # 5. 가구 간·가구 내 변동
    dec = []
    for c in ["hdds", "asf", "lnV1", "Z", "D", "W", "hhsize", "a0_14", "a15_65", "a66p", "wage_real"]:
        x = s[c]
        hm = s.groupby("hhid")[c].transform("mean")
        wv = s.groupby("wave")[c].transform("mean")
        resid = x - hm - wv + x.mean()
        dec.append(dict(var=VARS[c], overall_sd=x.std(), between_sd=s.groupby("hhid")[c].mean().std(),
                        within_sd=(x - hm).std(), within_net_wave_sd=resid.std(),
                        within_share_var=((x - hm).var() / x.var())))
    section("전체·가구 간·가구 내 표준편차 (가구 내는 가구 평균 제거, 파동 제거는 가구·파동 평균 모두 제거)",
            pd.DataFrame(dec).set_index("var"), "within_between")

    # 6. HDDS, ASF 분포
    hd = pd.crosstab(s.hdds.astype(int), s.wave, normalize="columns")
    hd["전체"] = s.hdds.astype(int).value_counts(normalize=True).sort_index()
    section("HDDS 분포 (파동별 비율)", hd, "hdds_dist")
    ad = pd.crosstab(s.asf.astype(int), s.wave, normalize="columns")
    ad["전체"] = s.asf.astype(int).value_counts(normalize=True).sort_index()
    section("ASF 분포 (파동별 비율)", ad, "asf_dist")

    # 7. 식품군별 섭취 비율
    fg = s.groupby("wave")[list(FG)].mean().T
    fg["전체"] = s[list(FG)].mean()
    fg["비쌀재배 가구"] = p[p.rice_grower == 0][list(FG)].mean()
    fg.index = [f"{k} {v}" for k, v in FG.items()]
    section("식품군별 지난 24시간 섭취 가구 비율", fg, "food_groups")

    # 8. 쌀 재배 여부 비교 (전체 가구)
    cmp_cols = ["hdds", "asf", "hhsize", "a0_14", "a15_65", "a66p"]
    g = p.groupby(["wave", "rice_grower"])[cmp_cols].mean().unstack("rice_grower")
    rows = []
    for c in cmp_cols:
        a, b = p.loc[p.rice_grower == 1, c].dropna(), p.loc[p.rice_grower == 0, c].dropna()
        se = np.sqrt(a.var() / len(a) + b.var() / len(b))
        rows.append(dict(var=VARS[c], rice=a.mean(), nonrice=b.mean(), diff=a.mean() - b.mean(),
                         t=(a.mean() - b.mean()) / se, n_rice=len(a), n_nonrice=len(b)))
    section("쌀 재배 가구와 비재배 가구 (전체 가구-파동, 단순 t)", pd.DataFrame(rows).set_index("var"),
            "rice_vs_nonrice")
    g.columns = [f"{VARS[c]}|{'쌀' if r else '비쌀'}" for c, r in g.columns]
    section("쌀 재배 여부별 파동 평균", g.T, "rice_vs_nonrice_by_wave")

    # 9. 성별
    names = (pd.read_csv(ROOT / "data" / "external" / "gso" / "district_codes_2002.csv")
               .drop_duplicates("tinh").set_index("tinh").prov_name)
    names = names.str.replace("Tỉnh ", "", regex=False)
    names = names.reindex(sorted(set(names.index) | {302, 606}))
    names.loc[302], names.loc[606] = "Lai Châu", "Đắk Nông"
    share_rice = p.groupby("tinh").rice_grower.mean()
    pv = s.groupby("tinh").agg(
        hh_waves=("hhid", "size"), households=("hhid", "nunique"), districts=("district", "nunique"),
        hdds=("hdds", "mean"), asf=("asf", "mean"), V_median=("V", "median"), V0=("V0", "mean"),
        Z_mean=("Z", "mean"), Z_sd=("Z", "std"), wage_real=("wage_real", "mean"),
        month_mode=("month", lambda x: int(x.mode().iloc[0])),
        dist_rain=("rain_level", lambda x: (x == "DIST").mean()),
        summer_season=("season_s", lambda x: (x == "Summer").mean()))
    pv.insert(0, "rice_share_all", share_rice)
    pv.insert(0, "name", names.reindex(pv.index))
    section("성별 (추정 표본; rice_share_all은 전체 가구 중 쌀 재배 비율)", pv, "by_province", 2)

    # 10. 강우와 작기 배정
    rz = s.groupby("wave").agg(
        Z_mean=("Z", "mean"), Z_sd=("Z", "std"), Z_min=("Z", "min"), Z_max=("Z", "max"),
        D_pos=("Dpos", "mean"), W_pos=("Wpos", "mean"),
        abs_gt1=("Z", lambda z: (z.abs() > 1).mean()), abs_gt2=("Z", lambda z: (z.abs() > 2).mean()),
        district_rain=("rain_level", lambda x: (x == "DIST").mean()))
    dz = s.groupby(["wave", "district"]).Z.first().groupby("wave").agg(["count", "std"])
    rz["districts"] = dz["count"]
    rz["Z_sd_across_district"] = dz["std"]
    section("작기 강우 Z (시작 기준)", rz.T, "rain")
    lab = np.where(s.hy_s == s.wave, "당해 ", "전년 ") + s.season_s
    ss = pd.crosstab(lab, s.wave).astype(float)
    ss.loc["시작≠종료 비율"] = ((s.season_s != s.season_e) | (s.hy_s != s.hy_e)).groupby(s.wave).mean()
    section("작기 배정 (시작 기준) 가구 수와 종료 기준과 다른 비율", ss, "season")
    mo = pd.crosstab(s.month, s.wave)
    section("면접월 분포 (가구 수)", mo, "interview_month", 0)

    # 11. 대체·보정 비율
    imp = s.groupby("wave").agg(
        month_imputed=("month_imputed", "mean"), wage_imputed=("wage_imputed", "mean"),
        uv_imputed=("uv_imputed", "mean"), province_rain=("rain_level", lambda x: (x != "DIST").mean()),
        rice_price_annual=("rice_src", lambda x: (x == "annual").mean()))
    imp.loc["전체"] = [s.month_imputed.mean(), s.wage_imputed.mean(), s.uv_imputed.mean(),
                       (s.rain_level != "DIST").mean(), (s.rice_src == "annual").mean()]
    section("대체·보정 값 비율", imp.T, "imputation")

    # 12. 상관
    cc = ["hdds", "asf", "lnV1", "D", "W", "hhsize", "ln_pr", "ln_p_pork", "ln_p_chicken", "ln_p_fish",
          "ln_urea", "ln_wage"]
    section("상관계수 (추정 표본, 수준)", s[cc].corr(), "corr")
    hm = s[cc] - s.groupby("hhid")[cc].transform("mean")
    section("상관계수 (가구 평균 제거 후)", hm.corr(), "corr_within")

    (RES / "desc_summary.txt").write_text("\n".join(LINES), encoding="utf-8")


if __name__ == "__main__":
    main()

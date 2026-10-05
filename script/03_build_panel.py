"""식 (R1)·(R2)·(R3)의 가구-파동 분석 자료를 만든다.

정의는 docs/베트남_쌀농가_식단다양성_제안식.md, 대체 규칙은 docs/미수집_자료.md와
docs/대체생략_오차상한.md를 따른다.

- HDDS: 24시간 회상 11개 식품군 수(0-11). ASF: 육류·계란·어류·유제품(0-4).
- V: Q3A 최근 작기 쌀 수량(kg) x Q3B 12개월 쌀 단가(천 동/kg), 일반 CPI(2015=100)로 실질화.
- 작기 배정: commune 면접월 15일 전에 수확이 시작된 마지막 작기(시작 기준). 종료 기준은 비교용.
- D, W: 그 작기 창(파종 시작 달 ~ 수확 시작 달)의 누적 강우를 1981-2007 기준으로 표준화한 Z의
  음·양 부분. district 강우가 기본이고, 성 평균 강우와 면접 뒤 3개월 강우(위약)도 함께 만든다.

입력: VARHS Clean, data/derived/district_crosswalk.csv, data/derived/chirps_monthly_units.csv,
      data/external/{riceatlas,faostat,worldbank}
출력: data/derived/panel_hh.csv, data/derived/build_log.txt
"""
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "VARHS-2008-16" / "VARHS-2008-16Clean" / "2008-16Clean"
EXT = ROOT / "data" / "external"
DER = ROOT / "data" / "derived"
BASE_END = 2007
LOG: list[str] = []


def log(*a) -> None:
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s)


WAVES = {
    2008: dict(cover="2008_new/Phieu_1_New_08", food=("2008_new/Phieu_1_New_08", "p40q1_"),
               q1=("2008_new/Q1a_New", "p2q4_"),
               q3a=("2008_new/Q3a_New", [("p17q1_", "p17q3_", "p17q4_"), ("p17q6_", "p17q8_", "p17q9_"),
                                          ("p17q10_", "p17q12_", "p17q13_")]),
               q3b=("2008_new/Q3b_New", "p18ma_", "p18q1_", "p18q2_"), q7a="2008_new/Q7a_New",
               wage="s4q25b_12008"),
    2010: dict(cover="2010_new/Phieu_1_New_10", food=("2010_new/Phieu_2_New_10", "p37q1_"),
               q1=("2010_new/Q1_New_10", "p1q4_"),
               q3a=("2010_new/Q3A_New_10", [("p16q1_", "p16q3_", "p16q4_"), ("p16q6_", "p16q8_", "p16q9_"),
                                             ("p16q10_", "p16q12_", "p16q13_")]),
               q3b=("2010_new/Q3B_New_10", "p17ma_", "p17q1_", "p17q2_"), q7a="2010_new/Q7A_New_10",
               wage="s4q25b_1"),
    2012: dict(cover="2012_new/Phieu1_New_12", food=("2012_new/Phieu_2_New_12", "p36q1_"),
               q1=("2012_new/Q1_New_12", "p1q4_"),
               q3a=("2012_new/Q3A_New_12", [("p14q1_", "p14q3a_", "p14q3b_"), ("p14q5_", "p14q7a_", "p14q7b_"),
                                             ("p14q8_", "p14q10a_", "p14q10b_")]),
               q3b=("2012_new/Q3B_New_12", "p15ma_", "p15q1_", "p15q2_"), q7a="2012_new/Q7A_New_12",
               wage="s4q25b_1"),
    2014: dict(cover="2014_new/Phieu1_New_14", food=("2014_new/Phieu2_New_14", "p38q1_"),
               q1=("2014_new/Q1_New_14", "p1q4_"),
               q3a=("2014_new/Q3A_New_14", [("p15q1_", "p15q3a_", "p15q3b_"), ("p15q5_", "p15q7a_", "p15q7b_"),
                                             ("p15q8_", "p15q10a_", "p15q10b_")]),
               q3b=("2014_new/Q3B_New_14", "p16ma_", "p16q1_", "p16q2_"), q7a="2014_new/Q7A_New_14",
               wage="s4q32b_1"),
    2016: dict(cover="2016_new/Phieu1_New_16", food=("2016_new/Phieu2_New_16", "p37q1_"),
               q1=("2016_new/Q1_New_16", "p1q4b_"),
               q3a=("2016_new/Q3A_New_16", [("p15q1_", "p15q3a_", "p15q3b_"), ("p15q5_", "p15q7a_", "p15q7b_"),
                                             ("p15q8_", "p15q10a_", "p15q10b_")]),
               q3b=("2016_new/Q3B_New_16", "p16ma_", "p16q1_", "p16q2_"), q7a="2016_new/Q7A_New_16",
               wage="s4q32b_1"),
}
PREV = {2010: 2008, 2012: 2010, 2014: 2012, 2016: 2014}
FOOD_GROUPS = [f"{i:02d}" for i in range(1, 12)]
ASF_GROUPS = ["05", "06", "07", "09"]
Q7A_ITEMS = {1: "pork", 3: "chicken", 4: "fish"}

RICEATLAS_ROW = {105: "Ha Tay", 205: "Lao Cai", 217: "Phu Tho", 301: "Lai Chau", 302: "Dien Bien",
                 403: "Nghe An", 503: "Quang Nam", 511: "Khanh Hoa", 605: None, 606: None, 607: None,
                 801: "Long An"}


def read(rel: str, cols=None) -> pd.DataFrame:
    return pd.read_stata(CLEAN / f"{rel}.dta", convert_categoricals=False, columns=cols)


def keys(y: int) -> list[str]:
    return [f"tinh_{y}", f"quan_{y}", f"xa_{y}", f"ma_h0_{y}"]


def std_keys(df: pd.DataFrame, y: int) -> pd.DataFrame:
    k = ["tinh", "quan", "xa", "hh"]
    d = df.rename(columns=dict(zip(keys(y), k))).dropna(subset=k).copy()
    d[k] = d[k].astype(int)
    return d


# ---------------------------------------------------------------- 가구 모듈
def food(y: int) -> pd.DataFrame:
    f, pre = WAVES[y]["food"]
    cols = [pre + g for g in FOOD_GROUPS]
    d = std_keys(read(f, keys(y) + cols), y)
    raw = d[cols]
    log(y, "food raw codes", sorted(pd.unique(raw.values.ravel()[~pd.isna(raw.values.ravel())]).tolist()))
    yes = (raw == 1).astype(float).where(raw.notna())
    d["hdds"] = yes.sum(axis=1, min_count=11)
    d["asf"] = yes[[pre + g for g in ASF_GROUPS]].sum(axis=1, min_count=4)
    for g in FOOD_GROUPS:
        d[f"fg{g}"] = yes[pre + g]
    return d[["tinh", "quan", "xa", "hh", "hdds", "asf"] + [f"fg{g}" for g in FOOD_GROUPS]]


def members(y: int) -> pd.DataFrame:
    f, by = WAVES[y]["q1"]
    d = std_keys(read(f, keys(y) + [by]), y)
    age = y - d[by].where((d[by] >= 1900) & (d[by] <= y))
    d["a0_14"] = (age <= 14).astype(int)
    d["a15_65"] = ((age >= 15) & (age <= 65)).astype(int)
    d["a66p"] = (age >= 66).astype(int)
    d["age_na"] = age.isna().astype(int)
    g = d.groupby(["tinh", "quan", "xa", "hh"])[["a0_14", "a15_65", "a66p", "age_na"]].sum().reset_index()
    g["hhsize"] = g[["a0_14", "a15_65", "a66p", "age_na"]].sum(axis=1)
    return g


def rice_recent(y: int) -> pd.DataFrame:
    f, seasons = WAVES[y]["q3a"]
    cols = [c for s in seasons for c in s]
    d = std_keys(read(f, keys(y) + cols), y)
    out = d[["tinh", "quan", "xa", "hh"]].copy()
    for k, (crop, qty, unit) in enumerate(seasons, start=1):
        is_rice = d[crop] == 1
        q = d[qty].where(~d[qty].isin([98, 99]))
        ok = (d[unit] == 1) | ((d[unit].isna()) & (q == 0))
        out[f"rice{k}"] = is_rice.astype(int)
        out[f"kg{k}"] = np.where(is_rice, q.where(ok), 0.0)
        out[f"bad{k}"] = (is_rice & (q.isna() | ~ok)).astype(int)
    g = out.groupby(["tinh", "quan", "xa", "hh"]).agg(
        n_rice_plots1=("rice1", "sum"), kg_recent=("kg1", "sum"), bad_recent=("bad1", "sum"),
        n_rice_plots2=("rice2", "sum"), kg_second=("kg2", "sum"), bad_second=("bad2", "sum"),
        n_rice_plots3=("rice3", "sum"), kg_third=("kg3", "sum"),
    ).reset_index()
    g.loc[g.bad_recent > 0, "kg_recent"] = np.nan
    g.loc[g.bad_second > 0, "kg_second"] = np.nan
    return g


def rice_12m(y: int) -> pd.DataFrame:
    f, crop, kg, val = WAVES[y]["q3b"]
    d = std_keys(read(f, keys(y) + [crop, kg, val]), y)
    d = d[d[crop] == 1].copy()
    d["kg12"] = d[kg].where(~d[kg].isin([98, 999999]))
    d["val12"] = d[val].where(~d[val].isin([98, 999999]))
    return d.groupby(["tinh", "quan", "xa", "hh"])[["kg12", "val12"]].sum(min_count=1).reset_index()


def q7a_prices(y: int) -> pd.DataFrame:
    df = read(WAVES[y]["q7a"])
    pre = next(re.match(r"^(p\d+)ma_$", c).group(1) for c in df.columns if re.match(r"^p\d+ma_$", c))
    d = std_keys(df[keys(y) + [f"{pre}ma_", f"{pre}q1_", f"{pre}q3_"]], y)
    d = d.rename(columns={f"{pre}ma_": "item", f"{pre}q1_": "used", f"{pre}q3_": "price"})
    d = d[(d.used == 1) & d.item.isin(Q7A_ITEMS) & (d.price > 0) & ~d.price.isin([98, 99])]
    d["item"] = d.item.map(Q7A_ITEMS)
    return d[["tinh", "quan", "xa", "item", "price"]]


def commune(y: int) -> pd.DataFrame:
    yy = str(y)[2:]
    d = read(f"commune_clean/commune_{yy}_clean")
    k = [f"tinh_{y}", f"quan_{y}", f"xa_{y}"]
    w = WAVES[y]["wage"]
    d = d[k + ["month", w]].dropna(subset=k).rename(columns=dict(zip(k, ["tinh", "quan", "xa"])))
    d[["tinh", "quan", "xa"]] = d[["tinh", "quan", "xa"]].astype(int)
    d["wage_m"] = d[w].where(d[w] > 0)
    d.loc[d.wage_m > 2000, "wage_m"] = d.wage_m / 1000
    return d.drop(columns=[w]).drop_duplicates(["tinh", "quan", "xa"])


# ---------------------------------------------------------------- 패널 ID
def panel_ids(covers: dict[int, pd.DataFrame]) -> dict[int, pd.Series]:
    parent: dict = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for y, c in covers.items():
        cur = list(zip([y] * len(c), *[c[k] for k in keys(y)]))
        for n in cur:
            find(n)
        if y in PREV:
            p = PREV[y]
            pk = keys(p)
            if all(k in c.columns for k in pk):
                ok = c[pk].notna().all(axis=1) & (c[pk[3]] > 0)
                for n, prev in zip(np.array(cur, dtype=object)[ok.values],
                                   zip(*[c.loc[ok, k] for k in pk])):
                    union(tuple(n), (p, *prev))
    roots, ids = {}, {}
    for y, c in covers.items():
        cur = list(zip([y] * len(c), *[c[k] for k in keys(y)]))
        ids[y] = pd.Series([roots.setdefault(find(n), len(roots)) for n in cur], index=c.index)
    return ids


# ---------------------------------------------------------------- 외부 가격
def cpi_general() -> pd.DataFrame:
    c = pd.read_csv(EXT / "faostat" / "vnm_cpi_monthly.csv")
    c = c[c.item.str.contains("General")]
    c["m"] = pd.to_datetime(c.start_date).dt.month
    return c[["year", "m", "index_2015_eq_100"]].rename(columns={"m": "month", "index_2015_eq_100": "cpi"})


def rice_price() -> pd.DataFrame:
    p = pd.read_csv(EXT / "faostat" / "vnm_rice_producer_price_lcu.csv")
    ann = p[p.month == "Annual value"].set_index("year").value
    mon = p[p.month != "Annual value"].copy()
    mon["m"] = pd.to_datetime(mon.start_date).dt.month
    mon = mon.set_index(["year", "m"]).value
    rows = []
    for y in WAVES:
        for m in range(1, 13):
            v, src = mon.get((y, m), np.nan), "monthly"
            if np.isnan(v):
                v, src = ann.get(y, np.nan), "annual"
            rows.append(dict(year=y, month=m, rice_vnd_t=v, rice_src=src))
    return pd.DataFrame(rows)


def urea() -> pd.DataFrame:
    u = pd.read_csv(EXT / "worldbank" / "fertilizer_and_rice_monthly.csv")
    u["year"] = u.month.str[:4].astype(int)
    u["m"] = u.month.str[5:].astype(int)
    return u[["year", "m", "urea_usd_per_mt"]].rename(columns={"m": "month"})


# ---------------------------------------------------------------- 작기와 강우
def doy_month(doy: int) -> int:
    return (pd.Timestamp(2001, 1, 1) + pd.Timedelta(days=int(doy) - 1)).month


def calendars() -> dict[int, list[dict]]:
    ra = pd.read_csv(EXT / "riceatlas" / "vietnam" / "rice_calendar_vnm.csv")
    out = {}
    for code, name in RICEATLAS_ROW.items():
        r = ra[ra.REGION == "Central Highlands"].iloc[0] if name is None else ra[ra.SUB_REGION == name].iloc[0]
        ss = []
        for k in (1, 2, 3):
            if r[f"HARV_ST{k}"] > 0:
                ss.append(dict(name=r[f"NAME{k}"], plant=int(r[f"PLANT_ST{k}"]),
                               hst=int(r[f"HARV_ST{k}"]), hend=int(r[f"HARV_END{k}"])))
        out[code] = ss
    return out


def assign_season(cal: list[dict], year: int, month: int, rule: str) -> tuple[str, int]:
    ref = pd.Timestamp(2001, month, 15).dayofyear
    best = None
    for hy in (year, year - 1):
        for s in cal:
            ev = s["hst"] if rule == "start" else s["hend"]
            if (hy, ev) <= (year, ref) and (best is None or (hy, ev) > (best[1], best[2])):
                best = (s["name"], hy, ev)
    return best[0], best[1]


def window(cal: list[dict], season: str, hy: int) -> list[tuple[int, int]]:
    s = next(x for x in cal if x["name"] == season)
    m0, m1 = doy_month(s["plant"]), doy_month(s["hst"])
    y0 = hy - 1 if s["plant"] > s["hst"] else hy
    months, (yy, mm) = [], (y0, m0)
    while (yy, mm) <= (hy, m1):
        months.append((yy, mm))
        yy, mm = (yy + 1, 1) if mm == 12 else (yy, mm + 1)
    return months


class Rain:
    def __init__(self) -> None:
        r = pd.read_csv(DER / "chirps_monthly_units.csv")
        self.n = r.groupby("unit").n_cells.first().to_dict()
        self.p = r.set_index(["unit", "year", "month"]).precip_mm
        self.cache: dict = {}

    def series(self, units: tuple[str, ...]) -> pd.Series:
        if units not in self.cache:
            w = np.array([self.n[u] for u in units], dtype=float)
            s = sum(self.p.loc[u] * wi for u, wi in zip(units, w)) / w.sum()
            self.cache[units] = s
        return self.cache[units]

    def z(self, units: tuple[str, ...], months: list[tuple[int, int]]) -> float:
        s = self.series(units)
        hy = months[-1][0]
        offs = [(y - hy, m) for y, m in months]
        def total(h):
            return sum(s.get((h + dy, m), np.nan) for dy, m in offs)
        base = np.array([total(h) for h in range(1982, BASE_END + 1)])
        base = base[~np.isnan(base)]
        return (total(hy) - base.mean()) / base.std(ddof=1)


# ---------------------------------------------------------------- 조립
def main() -> None:
    covers = {}
    for y, spec in WAVES.items():
        c = read(spec["cover"])
        kk = keys(y) + ([k for k in keys(PREV[y]) if k in c.columns] if y in PREV else [])
        covers[y] = c[kk].dropna(subset=keys(y)).reset_index(drop=True)
    ids = panel_ids(covers)

    cw = pd.read_csv(DER / "district_crosswalk.csv")
    cw["units"] = [tuple(g.split(";")) if lv == "DIST" else (f"PROV:{t}",)
                   for g, lv, t in zip(cw.gadm_gids, cw.level, cw.tinh)]
    cw = cw.set_index(["tinh", "quan"])
    cals = calendars()
    rain = Rain()
    cpi = cpi_general()
    rp = rice_price()
    ur = urea()

    frames = []
    for y in WAVES:
        c = std_keys(covers[y][keys(y)].copy(), y)
        c["hhid"] = ids[y].values
        c["wave"] = y
        d = (c.merge(food(y), how="left", on=["tinh", "quan", "xa", "hh"])
              .merge(members(y), how="left", on=["tinh", "quan", "xa", "hh"])
              .merge(rice_recent(y), how="left", on=["tinh", "quan", "xa", "hh"])
              .merge(rice_12m(y), how="left", on=["tinh", "quan", "xa", "hh"]))
        com = commune(y)
        d = d.merge(com, how="left", on=["tinh", "quan", "xa"], indicator="_cm")
        log(y, "households", len(d), "commune matched", int((d._cm == "both").sum()),
            "month missing", int(d.month.isna().sum()))
        pm = d.groupby("tinh").month.agg(lambda s: s.mode().iloc[0] if s.notna().any() else 7)
        d["month_imputed"] = d.month.isna().astype(int)
        d["month"] = d.month.fillna(d.tinh.map(pm)).astype(int)
        d = d.drop(columns="_cm")

        # 식품 가격: commune -> district -> 성 중앙값
        q7 = q7a_prices(y)
        for item in Q7A_ITEMS.values():
            qi = q7[q7.item == item]
            lv = [qi.groupby(["tinh", "quan", "xa"]).price.median(),
                  qi.groupby(["tinh", "quan"]).price.median(),
                  qi.groupby(["tinh"]).price.median()]
            v = d.set_index(["tinh", "quan", "xa"]).index.map(lv[0].to_dict())
            v = pd.Series(v, index=d.index)
            v = v.fillna(pd.Series(d.set_index(["tinh", "quan"]).index.map(lv[1].to_dict()), index=d.index))
            v = v.fillna(d.tinh.map(lv[2]))
            d[f"p_{item}"] = v

        # 임금 결측: district -> 성 중앙값
        wd = d.groupby(["tinh", "quan"]).wage_m.transform("median")
        wp = d.groupby("tinh").wage_m.transform("median")
        d["wage_imputed"] = d.wage_m.isna().astype(int)
        d["wage_m"] = d.wage_m.fillna(wd).fillna(wp)

        # 쌀 단가와 V
        d["uv_hh"] = (d.val12 / d.kg12).where((d.kg12 > 0) & (d.val12 > 0))
        prov_med = d.groupby("tinh").uv_hh.transform("median")
        com_med = d.groupby(["tinh", "quan", "xa"]).uv_hh.transform("median")
        out = (d.uv_hh < prov_med / 3) | (d.uv_hh > prov_med * 3)
        d["uv_imputed"] = (d.uv_hh.isna() | out).astype(int)
        d["uv"] = d.uv_hh.where(~out).fillna(com_med).fillna(prov_med)
        frames.append(d)

    p = pd.concat(frames, ignore_index=True)
    p = p.merge(cpi.rename(columns={"year": "wave"}), how="left", on=["wave", "month"])
    p = p.merge(rp.rename(columns={"year": "wave"}), how="left", on=["wave", "month"])
    p = p.merge(ur.rename(columns={"year": "wave"}), how="left", on=["wave", "month"])
    defl = p.cpi / 100
    p["rice_grower"] = (((p.kg12 > 0) | (p.val12 > 0)) |
                        (p[["n_rice_plots1", "n_rice_plots2", "n_rice_plots3"]].sum(axis=1) > 0)).astype(int)
    p["V"] = p.kg_recent.fillna(np.nan) * p.uv / defl
    p.loc[(p.rice_grower == 1) & (p.n_rice_plots1.fillna(0) == 0), "V"] = 0.0
    p["lnV1"] = np.log1p(p.V)
    p["ln_pr"] = np.log(p.rice_vnd_t / 1000 / defl)
    for item in Q7A_ITEMS.values():
        p[f"ln_p_{item}"] = np.log(p[f"p_{item}"] / defl)
    p["ln_wage"] = np.log(p.wage_m / defl)
    p["ln_urea"] = np.log(p.urea_usd_per_mt)
    p["district"] = p.tinh * 100 + p.quan
    p["commune_id"] = p.tinh * 10000 + p.quan * 100 + p.xa

    # 작기 배정과 D, W
    zs = {k: [] for k in ("season_s", "hy_s", "season_e", "hy_e", "Z", "Z_end", "Z_prov", "Z_post")}
    for t, q, y, m in zip(p.tinh, p.quan, p.wave, p.month):
        cal = cals[t]
        units = cw.loc[(t, q), "units"] if (t, q) in cw.index else (f"PROV:{t}",)
        s_s, hy_s = assign_season(cal, y, m, "start")
        s_e, hy_e = assign_season(cal, y, m, "end")
        w_s, w_e = window(cal, s_s, hy_s), window(cal, s_e, hy_e)
        post = [(y, mm) for mm in range(m + 1, m + 4)]
        zs["season_s"].append(s_s); zs["hy_s"].append(hy_s)
        zs["season_e"].append(s_e); zs["hy_e"].append(hy_e)
        zs["Z"].append(rain.z(units, w_s))
        zs["Z_end"].append(rain.z(units, w_e))
        zs["Z_prov"].append(rain.z((f"PROV:{t}",), w_s))
        zs["Z_post"].append(rain.z(units, post))
    for k, v in zs.items():
        p[k] = v
    for z, suf in (("Z", ""), ("Z_end", "_end"), ("Z_prov", "_prov"), ("Z_post", "_post")):
        p[f"D{suf}"] = np.maximum(-p[z], 0)
        p[f"W{suf}"] = np.maximum(p[z], 0)
    p["rain_level"] = [cw.loc[(t, q), "level"] if (t, q) in cw.index else "PROV" for t, q in zip(p.tinh, p.quan)]

    p.to_csv(DER / "panel_hh.csv", index=False)
    rg = p[p.rice_grower == 1]
    log("all hh-waves", len(p), "rice grower hh-waves", len(rg), "unique hh", rg.hhid.nunique())
    log("rice growers by wave", rg.groupby("wave").size().to_dict())
    log("V missing among rice growers", int(rg.V.isna().sum()), "V==0", int((rg.V == 0).sum()))
    log("season (start) by wave\n", pd.crosstab(rg.season_s + "@" + (rg.wave - rg.hy_s).astype(str), rg.wave).to_string())
    log("start!=end share by wave", rg.assign(diff=(rg.season_s != rg.season_e) | (rg.hy_s != rg.hy_e))
        .groupby("wave")["diff"].mean().round(3).to_dict())
    (DER / "build_log.txt").write_text("\n".join(LOG), encoding="utf-8")


if __name__ == "__main__":
    main()

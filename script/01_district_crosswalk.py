"""VARHS (성, district) 코드를 GADM 4.1 2단계 구역에 대응시킨다.

VARHS 코드는 2002년 GSO 행정코드(성 3자리 + district 2자리, 예: 10501 = Ha Tay의 Ha Dong)이다.
목록 출처: https://diaocthongthai.com/danh-sach-quan-huyen-viet-nam-2002/ (GSO 2002-12-31 기준)
원문 사본: data/external/gso/danh_sach_quan_huyen_2002_raw.txt

2002년 이후 분할된 district는 그 뒤에 생긴 GADM 구역을 합친다.
2004년에 신설·분할된 Dien Bien(302), Dak Nong(606)과 이름을 확정할 수 없는 코드는
성 전체(`PROV`)로 둔다.

출력
- data/external/gso/district_codes_2002.csv
- data/derived/district_crosswalk.csv  (tinh, quan, gso_name, gadm_gids, level)
"""
from pathlib import Path
import re
import unicodedata

import pandas as pd
import shapefile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "external" / "gso" / "danh_sach_quan_huyen_2002_raw.txt"
GADM = ROOT / "data" / "gadm41_VNM_shp-20261004T075122Z-1-001" / "gadm41_VNM_shp" / "gadm41_VNM_2"
CLEAN = ROOT / "data" / "VARHS-2008-16" / "VARHS-2008-16Clean" / "2008-16Clean"
OUT = ROOT / "data" / "derived"

PROV_GADM = {
    105: "Hà Nội", 205: "Lào Cai", 217: "Phú Thọ", 301: "Lai Châu", 302: "Điện Biên",
    403: "Nghệ An", 503: "Quảng Nam", 511: "Khánh Hòa", 605: "Đắk Lắk", 606: "Đắk Nông",
    607: "Lâm Đồng", 801: "Long An",
}
PROV_ONLY = {302, 606}

# 2002 이후 분할·개칭: VARHS 코드 -> GADM 구역 이름(정규화 전)
OVERRIDE = {
    (217, 13): ["Cẩm Khê"],                      # Sông Thao, 개칭
    (217, 19): ["Thanh Sơn", "Tân Sơn"],         # 2007 Tân Sơn 분리
    (217, 20): ["Thanh Sơn", "Tân Sơn"],
    (403, 13): ["Nghĩa Đàn", "Thái Hoà"],        # 2007 Thái Hòa 분리
    (403, 14): ["Nghĩa Đàn", "Thái Hoà"],
    (403, 17): ["Quỳnh Lưu", "Hoàng Mai"],       # 2013 Hoàng Mai 분리
    (503, 1): ["Tam Kỳ", "Phú Ninh"],            # 2005 Phú Ninh 분리
    (503, 5): ["Đông Giang", "Tây Giang"],       # Hiên, 2003 분할
    (503, 17): ["Quế Sơn", "Nông Sơn"],          # 2008 Nông Sơn 분리
    (503, 27): ["Bắc Trà My", "Nam Trà My"],     # 2003 분할
    (605, 9): ["Krông Búk", "Thị Xã Buôn Hồ"],   # 2008 Buôn Hồ 분리
    (605, 23): ["Krông A Na", "Cư Kuin"],        # 2007 Cư Kuin 분리
    (605, 24): ["Krông A Na", "Cư Kuin"],
    (607, 11): ["Lâm Hà", "Đam Rông"],           # 2004 Đam Rông 분리
    (801, 7): ["Mộc Hóa", "Kiến Tường"],         # 2013 Kiến Tường 분리
    (301, 5): ["Mường Tè", "Nậm Nhùn"],          # 2012 Nậm Nhùn 분리
    (301, 8): ["Tam Đường", "Lai Châu"],         # 2004 Lai Châu 시 분리
}


def norm(s: str) -> str:
    s = s.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"^(huyen|thi xa|thanh pho|quan)\s+", "", s.strip())
    return re.sub(r"[^a-z]", "", s)


def gso_2002() -> pd.DataFrame:
    text = RAW.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| ([^|]+?) \| (\d{5}) \| ([^|]+?) \| ([^|]+?) \|", text, re.M)
    df = pd.DataFrame(rows, columns=["prov_new", "prov_name", "code", "type", "name"])
    df["tinh"] = df.code.str[:3].astype(int)
    df["quan"] = df.code.str[3:].astype(int)
    return df


def gadm() -> pd.DataFrame:
    r = shapefile.Reader(str(GADM), encoding="utf-8")
    return pd.DataFrame([rec.as_dict() for rec in r.records()])[["GID_2", "NAME_1", "NAME_2"]]


def varhs_codes() -> pd.DataFrame:
    spec = [("2008_new/Phieu_1_New_08.dta", "2008"), ("2010_new/Phieu_1_New_10.dta", "2010"),
            ("2012_new/Phieu1_New_12.dta", "2012"), ("2014_new/Phieu1_New_14.dta", "2014"),
            ("2016_new/Phieu1_New_16.dta", "2016")]
    out = []
    for f, y in spec:
        d = pd.read_stata(CLEAN / f, convert_categoricals=False, columns=[f"tinh_{y}", f"quan_{y}"])
        out.append(d.set_axis(["tinh", "quan"], axis=1).assign(wave=int(y)))
    o = pd.concat(out).dropna().astype(int)
    return o.groupby(["tinh", "quan"]).wave.agg(lambda s: ",".join(map(str, sorted(s.unique())))).reset_index()


def main() -> None:
    g02 = gso_2002()
    g02.to_csv(RAW.parent / "district_codes_2002.csv", index=False, encoding="utf-8")
    gd = gadm()
    gd["key"] = gd.NAME_2.map(norm)
    codes = varhs_codes()

    rows = []
    for _, r in codes.iterrows():
        t, q = int(r.tinh), int(r.quan)
        prov = gd[gd.NAME_1 == PROV_GADM[t]]
        hit = g02[(g02.tinh == t) & (g02.quan == q)]
        gso_name = hit.name.iloc[0] if len(hit) else ""
        gids, level = [], "PROV"
        if t not in PROV_ONLY:
            names = OVERRIDE.get((t, q))
            if names is None and gso_name:
                names = [gso_name]
            if names:
                m = prov[prov.key.isin([norm(n) for n in names])]
                if len(m) == len(names):
                    gids, level = m.GID_2.tolist(), "DIST"
        if level == "PROV":
            gids = prov.GID_2.tolist()
        rows.append(dict(tinh=t, quan=q, waves=r.wave, gso_name=gso_name,
                         gadm_names=";".join(gd.set_index("GID_2").loc[gids, "NAME_2"]) if level == "DIST" else "",
                         gadm_gids=";".join(gids), level=level))
    cw = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    cw.to_csv(OUT / "district_crosswalk.csv", index=False, encoding="utf-8-sig")
    print(cw.level.value_counts().to_string())
    print(cw[cw.level == "PROV"][["tinh", "quan", "waves", "gso_name"]].to_string())


if __name__ == "__main__":
    main()

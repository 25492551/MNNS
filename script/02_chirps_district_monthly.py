"""CHIRPS v2.0 월강수를 GADM district와 성 단위 평균으로 집계한다(1981-01 ~ 2016-12).

격자 중심점이 구역 안에 있는 셀의 단순 평균이다. 중심점이 하나도 없는 작은 구역은
대표점에서 가장 가까운 셀을 쓴다. 성 평균은 그 성의 모든 district 셀을 합친 평균이다.

출력: data/derived/chirps_monthly_units.csv  (unit, year, month, precip_mm, n_cells)
      unit = GADM GID_2 또는 'PROV:<VARHS 성 코드>'
"""
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import shapefile
import shapely
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
NC = ROOT / "data" / "chirps-v2.0.monthly.nc"
GADM = ROOT / "data" / "gadm41_VNM_shp-20261004T075122Z-1-001" / "gadm41_VNM_shp" / "gadm41_VNM_2"
OUT = ROOT / "data" / "derived" / "chirps_monthly_units.csv"

PROV_GADM = {
    105: "Hà Nội", 205: "Lào Cai", 217: "Phú Thọ", 301: "Lai Châu", 302: "Điện Biên",
    403: "Nghệ An", 503: "Quảng Nam", 511: "Khánh Hòa", 605: "Đắk Lắk", 606: "Đắk Nông",
    607: "Lâm Đồng", 801: "Long An",
}
LON = (101.5, 110.0)
LAT = (8.0, 24.0)
Y0, Y1 = 1981, 2016


def main() -> None:
    ds = netCDF4.Dataset(NC)
    lat = ds.variables["latitude"][:].data
    lon = ds.variables["longitude"][:].data
    tdays = ds.variables["time"][:].data
    dates = pd.Timestamp("1980-01-01") + pd.to_timedelta(tdays, unit="D")
    ti = np.where((dates.year >= Y0) & (dates.year <= Y1))[0]
    yi = np.where((lat >= LAT[0]) & (lat <= LAT[1]))[0]
    xi = np.where((lon >= LON[0]) & (lon <= LON[1]))[0]
    pr = ds.variables["precip"][ti[0]:ti[-1] + 1, yi[0]:yi[-1] + 1, xi[0]:xi[-1] + 1]
    pr = np.ma.filled(pr.astype("float64"), np.nan)
    glat, glon = lat[yi[0]:yi[-1] + 1], lon[xi[0]:xi[-1] + 1]
    LO, LA = np.meshgrid(glon, glat)
    sel_dates = dates[ti]

    r = shapefile.Reader(str(GADM), encoding="utf-8")
    recs = [rec.as_dict() for rec in r.records()]
    geoms = [shape(s.__geo_interface__) for s in r.shapes()]
    wanted = set(PROV_GADM.values())

    unit_masks: dict[str, np.ndarray] = {}
    for rec, g in zip(recs, geoms):
        if rec["NAME_1"] not in wanted:
            continue
        m = shapely.contains_xy(g, LO, LA)
        if not m.any():
            p = g.representative_point()
            j = np.abs(glat - p.y).argmin()
            i = np.abs(glon - p.x).argmin()
            m = np.zeros_like(LO, dtype=bool)
            m[j, i] = True
        unit_masks[rec["GID_2"]] = m
    gid_prov = {rec["GID_2"]: rec["NAME_1"] for rec in recs}
    for code, name in PROV_GADM.items():
        ms = [m for gid, m in unit_masks.items() if gid_prov.get(gid) == name]
        unit_masks[f"PROV:{code}"] = np.logical_or.reduce(ms)

    rows = []
    for unit, m in unit_masks.items():
        vals = np.nanmean(pr[:, m], axis=1)
        rows.append(pd.DataFrame({"unit": unit, "year": sel_dates.year, "month": sel_dates.month,
                                  "precip_mm": vals, "n_cells": int(m.sum())}))
    out = pd.concat(rows, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(out.groupby("unit").n_cells.first().describe().to_string())
    print("rows", len(out), "units", out.unit.nunique(), "nan", int(out.precip_mm.isna().sum()))


if __name__ == "__main__":
    main()

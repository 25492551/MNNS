"""VARHS 모듈의 변수명·라벨·값 라벨을 텍스트로 덤프한다.

출력: data/derived/inspect/<파동>_<파일>.txt
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "VARHS-2008-16" / "VARHS-2008-16Clean" / "2008-16Clean"
OUT = ROOT / "data" / "derived" / "inspect"

FILES = {
    "2008_new": ["Phieu_1_New_08", "Phieu_2_New_08", "Q1a_New", "Q3a_New", "Q3b_New", "Q3c_New"],
    "2010_new": ["Phieu_1_New_10", "Phieu_2_New_10", "Q1_New_10", "Q3A_New_10", "Q3B_New_10", "Q3C_New_10"],
    "2012_new": ["Phieu1_New_12", "Phieu_2_New_12", "Q1_New_12", "Q3A_New_12", "Q3B_New_12", "Q3C_New_12"],
    "2014_new": ["Phieu1_New_14", "Phieu2_New_14", "Q1_New_14", "Q3A_New_14", "Q3B_New_14", "Q3C_New_14"],
    "2016_new": ["Phieu1_New_16", "Phieu2_New_16", "Q1_New_16", "Q3A_New_16", "Q3B_New_16", "Q3C_New_16"],
    "commune_clean": [f"commune_{y}_clean" for y in ("08", "10", "12", "14", "16")],
}
EXTRA = {
    "2008_new": ["Q7a_New"],
    "2010_new": ["Q7A_New_10"],
    "2012_new": ["Q7A_New_12"],
    "2014_new": ["Q7A_New_14"],
    "2016_new": ["Q7A_New_16"],
}


def dump(folder: str, name: str) -> None:
    path = CLEAN / folder / f"{name}.dta"
    it = pd.read_stata(path, iterator=True)
    labels = it.variable_labels()
    vlabels = it.value_labels()
    df = pd.read_stata(path, convert_categoricals=False)
    lines = [f"{path.name}  rows={len(df)}  cols={df.shape[1]}", ""]
    for col, lab in labels.items():
        s = df[col]
        nn = int(s.notna().sum())
        if pd.api.types.is_numeric_dtype(s) and nn:
            desc = f"min={s.min():.4g} max={s.max():.4g} nuniq={s.nunique()}"
        else:
            desc = f"nuniq={s.nunique()} ex={list(s.dropna().astype(str).unique()[:4])}"
        lines.append(f"{col:<14} nn={nn:<6} {desc} | {lab}")
    lines.append("")
    lines.append("VALUE LABELS")
    for k, v in vlabels.items():
        items = list(v.items())
        lines.append(f"[{k}] n={len(items)}: " + "; ".join(f"{a}={b}" for a, b in items[:400]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{folder}_{name}.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    targets = EXTRA if "--extra" in sys.argv else FILES
    for folder, names in targets.items():
        for n in names:
            try:
                dump(folder, n)
            except Exception as e:  # noqa: BLE001
                print("FAIL", folder, n, e, file=sys.stderr)
    print("done")

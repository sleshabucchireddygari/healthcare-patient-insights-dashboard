"""
Clean and validate the raw extracts.

Steps (each one is logged to reports/data_quality_report.md):
  1. Remove exact duplicate rows
  2. Standardize text fields (department, gender)
  3. Parse mixed date formats
  4. Flag / fix invalid values (negative charges, discharge before admission)
  5. Handle missing values
  6. Derive analysis fields: length_of_stay, age_at_admission, age_group,
     readmitted_30d (another admission for the same patient within 30 days of discharge)

Output: data/processed/patients_clean.csv, data/processed/admissions_clean.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT, REPORTS = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "reports"

DEPT_MAP = {
    "cardiology": "Cardiology",
    "orthopedics": "Orthopedics", "orthopaedics": "Orthopedics", "ortho": "Orthopedics",
    "oncology": "Oncology",
    "neurology": "Neurology",
    "general medicine": "General Medicine", "gen med": "General Medicine",
    "pulmonology": "Pulmonology",
    "pediatrics": "Pediatrics",
}
GENDER_MAP = {"f": "Female", "female": "Female", "m": "Male", "male": "Male"}


def parse_mixed_dates(s: pd.Series) -> pd.Series:
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    us = pd.to_datetime(s, format="%m/%d/%Y", errors="coerce")
    return iso.fillna(us)


def clean(log: list[str]):
    pat = pd.read_csv(RAW / "patients.csv")
    adm = pd.read_csv(RAW / "admissions.csv")
    log.append(f"| Raw rows loaded | {len(pat):,} patients / {len(adm):,} admissions |")

    # 1. duplicates
    d_p, d_a = pat.duplicated().sum(), adm.duplicated().sum()
    pat, adm = pat.drop_duplicates(), adm.drop_duplicates()
    log.append(f"| Exact duplicate rows removed | {d_p} patients / {d_a} admissions |")

    # 2. standardize text
    raw_depts = adm["department"].nunique()
    adm["department"] = (adm["department"].str.strip().str.replace(r"\s+", " ", regex=True)
                         .str.lower().map(DEPT_MAP))
    log.append(f"| Department labels standardized | {raw_depts} variants -> {adm['department'].nunique()} departments |")
    bad_gender = (~pat["gender"].isin(["Female", "Male"])).sum()
    pat["gender"] = pat["gender"].str.strip().str.lower().map(GENDER_MAP)
    log.append(f"| Gender values standardized | {bad_gender} rows (F / M / lowercase) |")

    # 3. dates
    us_fmt = adm["admission_date"].astype(str).str.contains("/").sum()
    adm["admission_date"] = parse_mixed_dates(adm["admission_date"])
    adm["discharge_date"] = parse_mixed_dates(adm["discharge_date"])
    pat["date_of_birth"] = pd.to_datetime(pat["date_of_birth"])
    log.append(f"| Dates converted from MM/DD/YYYY | {us_fmt} admission dates |")

    # 4. invalid values
    neg = (adm["total_charges"] < 0).sum()
    adm.loc[adm["total_charges"] < 0, "total_charges"] = adm["total_charges"].abs()
    log.append(f"| Negative charges (sign error) corrected | {neg} |")
    bad_dates = (adm["discharge_date"] < adm["admission_date"]).sum()
    adm.loc[adm["discharge_date"] < adm["admission_date"], "discharge_date"] = pd.NaT
    log.append(f"| Discharge before admission set to missing | {bad_dates} |")

    # 5. missing values
    miss_dis = adm["discharge_date"].isna().sum()
    adm = adm.dropna(subset=["discharge_date"])
    log.append(f"| Admissions dropped: no valid discharge date | {miss_dis} |")
    miss_type = adm["admission_type"].isna().sum()
    adm["admission_type"] = adm["admission_type"].fillna("Unknown")
    log.append(f"| Missing admission type -> 'Unknown' | {miss_type} |")
    miss_chg = adm["total_charges"].isna().sum()
    med = adm.groupby(["department", "diagnosis"])["total_charges"].transform("median")
    adm["total_charges"] = adm["total_charges"].fillna(med).round(2)
    log.append(f"| Missing charges imputed (dept + diagnosis median) | {miss_chg} |")
    miss_ins = pat["insurance_type"].isna().sum()
    pat["insurance_type"] = pat["insurance_type"].fillna("Unknown")
    log.append(f"| Missing insurance -> 'Unknown' | {miss_ins} |")

    # 6. derived fields
    adm = adm.merge(pat[["patient_id", "date_of_birth"]], on="patient_id", how="left")
    adm["length_of_stay"] = (adm["discharge_date"] - adm["admission_date"]).dt.days
    adm["age_at_admission"] = ((adm["admission_date"] - adm["date_of_birth"]).dt.days // 365.25).astype(int)
    adm["age_group"] = pd.cut(adm["age_at_admission"], [-1, 17, 39, 64, 79, 200],
                              labels=["0-17", "18-39", "40-64", "65-79", "80+"]).astype(str)
    adm = adm.drop(columns="date_of_birth").sort_values(["patient_id", "admission_date"])
    next_adm = adm.groupby("patient_id")["admission_date"].shift(-1)
    adm["days_to_next_admission"] = (next_adm - adm["discharge_date"]).dt.days
    adm["readmitted_30d"] = (adm["days_to_next_admission"].between(0, 30)).astype(int)
    adm = adm.sort_values("admission_date").reset_index(drop=True)

    orphan = (~adm["patient_id"].isin(pat["patient_id"])).sum()
    log.append(f"| Validation: admissions without a matching patient | {orphan} |")
    log.append(f"| Clean rows written | {len(pat):,} patients / {len(adm):,} admissions |")
    return pat, adm


def main():
    log = ["| Step | Result |", "|---|---|"]
    pat, adm = clean(log)
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    for c in ("admission_date", "discharge_date"):
        adm[c] = adm[c].dt.strftime("%Y-%m-%d")
    pat["date_of_birth"] = pat["date_of_birth"].dt.strftime("%Y-%m-%d")
    pat.to_csv(OUT / "patients_clean.csv", index=False)
    adm.to_csv(OUT / "admissions_clean.csv", index=False)

    report = "# Data Quality Report\n\nGenerated by `src/clean_data.py`.\n\n" + "\n".join(log) + "\n"
    (REPORTS / "data_quality_report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()

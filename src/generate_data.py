"""
Generate a synthetic hospital dataset (no real patient data / PHI).

The raw files intentionally contain the kinds of problems found in real
operational extracts so the cleaning step has something to fix:
  - duplicate rows
  - missing values
  - inconsistent text (casing, extra spaces, abbreviations)
  - mixed date formats
  - invalid values (negative charges, discharge before admission)

Output: data/raw/patients.csv, data/raw/admissions.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PATIENTS = 4000
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# department -> (share of admissions, mean length of stay in days, mean charge $)
DEPARTMENTS = {
    "Cardiology":       (0.17, 4.6, 32000),
    "Orthopedics":      (0.13, 3.8, 28000),
    "Oncology":         (0.11, 6.2, 41000),
    "Neurology":        (0.10, 5.1, 30000),
    "General Medicine": (0.24, 3.4, 14000),
    "Pulmonology":      (0.12, 4.9, 22000),
    "Pediatrics":       (0.13, 2.7, 11000),
}
DIAGNOSES = {
    "Cardiology": ["Heart Failure", "Myocardial Infarction", "Arrhythmia"],
    "Orthopedics": ["Hip Fracture", "Joint Replacement", "Spinal Disorder"],
    "Oncology": ["Breast Cancer", "Lung Cancer", "Lymphoma"],
    "Neurology": ["Stroke", "Seizure Disorder", "Multiple Sclerosis"],
    "General Medicine": ["Sepsis", "Diabetes Complication", "Kidney Infection"],
    "Pulmonology": ["COPD", "Pneumonia", "Asthma"],
    "Pediatrics": ["Bronchiolitis", "Gastroenteritis", "Pediatric Asthma"],
}
INSURANCE = ["Medicare", "Medicaid", "Commercial", "Self-Pay"]
CITIES = ["Birmingham", "Hoover", "Tuscaloosa", "Huntsville", "Montgomery", "Bessemer"]


def make_patients(rng: np.random.Generator) -> pd.DataFrame:
    ages = rng.integers(0, 95, N_PATIENTS)
    dob = [START - pd.Timedelta(days=int(a * 365.25 + rng.integers(0, 365))) for a in ages]
    ins = []
    for a in ages:
        if a >= 65:
            ins.append(rng.choice(INSURANCE, p=[0.78, 0.07, 0.13, 0.02]))
        elif a < 18:
            ins.append(rng.choice(INSURANCE, p=[0.0, 0.48, 0.48, 0.04]))
        else:
            ins.append(rng.choice(INSURANCE, p=[0.04, 0.22, 0.62, 0.12]))
    return pd.DataFrame({
        "patient_id": [f"P{i:05d}" for i in range(1, N_PATIENTS + 1)],
        "gender": rng.choice(["Female", "Male"], N_PATIENTS, p=[0.52, 0.48]),
        "date_of_birth": pd.to_datetime(dob).strftime("%Y-%m-%d"),
        "insurance_type": ins,
        "city": rng.choice(CITIES, N_PATIENTS, p=[0.38, 0.14, 0.14, 0.12, 0.12, 0.10]),
    })


def make_admissions(rng: np.random.Generator, patients: pd.DataFrame) -> pd.DataFrame:
    depts = list(DEPARTMENTS)
    shares = np.array([DEPARTMENTS[d][0] for d in depts])
    ages = ((START - pd.to_datetime(patients["date_of_birth"])).dt.days / 365.25).to_numpy()
    rows = []
    days_span = (END - START).days

    for idx, pid in enumerate(patients["patient_id"]):
        n = rng.choice([1, 2, 3, 4], p=[0.62, 0.24, 0.10, 0.04])
        age = ages[idx]
        if age < 18:
            dept_p = np.zeros(len(depts)); dept_p[depts.index("Pediatrics")] = 1.0
        else:
            dept_p = shares.copy(); dept_p[depts.index("Pediatrics")] = 0; dept_p /= dept_p.sum()
        dept = rng.choice(depts, p=dept_p)
        # start 6 months before the window so repeat visits are in steady state
        date = START - pd.Timedelta(days=180) + pd.Timedelta(days=int(rng.integers(0, days_span + 180)))

        for k in range(n):
            if k > 0:
                # ~35% of follow-up visits come back within 30 days (a readmission)
                gap = int(rng.integers(3, 30)) if rng.random() < 0.35 else int(rng.integers(31, 240))
                date = discharge + pd.Timedelta(days=gap)
                if date > END:
                    break
                if rng.random() < 0.3:
                    dept = rng.choice(depts, p=dept_p)
            # winter respiratory bump
            seasonal = 1.25 if (dept in ("Pulmonology", "Pediatrics") and date.month in (12, 1, 2)) else 1.0
            mean_los = DEPARTMENTS[dept][1] * seasonal * (1.25 if age >= 75 else 1.0)
            los = max(0, int(round(rng.gamma(2.2, mean_los / 2.2))))
            discharge = date + pd.Timedelta(days=los)
            adm_type = rng.choice(["Emergency", "Urgent", "Elective"], p=[0.52, 0.28, 0.20])
            charge = DEPARTMENTS[dept][2] * (0.6 + 0.12 * los) * rng.lognormal(0, 0.25)

            p_dead = 0.012 + (0.03 if age >= 80 else 0) + (0.02 if dept == "Oncology" else 0)
            outcome = rng.choice(
                ["Recovered", "Improved", "Transferred", "Deceased"], p=_outcome_probs(p_dead)
            )
            rows.append({
                "patient_id": pid,
                "department": dept,
                "diagnosis": rng.choice(DIAGNOSES[dept]),
                "admission_type": adm_type,
                "admission_date": date,
                "discharge_date": discharge,
                "outcome": outcome,
                "total_charges": round(float(charge), 2),
            })
            if outcome == "Deceased":
                break

    df = pd.DataFrame(rows)
    df = df[df["admission_date"] >= START].sort_values("admission_date").reset_index(drop=True)
    df.insert(0, "admission_id", [f"A{i:06d}" for i in range(1, len(df) + 1)])
    return df


def _outcome_probs(p_dead: float) -> list[float]:
    base = np.array([0.58, 0.30, 0.10])
    base = base / base.sum() * (1 - p_dead)
    return list(base) + [p_dead]


def add_data_quality_issues(rng: np.random.Generator, adm: pd.DataFrame, pat: pd.DataFrame):
    adm = adm.copy()
    pat = pat.copy()
    n = len(adm)

    # dates as strings, ~15% in US format
    adm["admission_date"] = adm["admission_date"].dt.strftime("%Y-%m-%d")
    adm["discharge_date"] = adm["discharge_date"].dt.strftime("%Y-%m-%d")
    us = rng.random(n) < 0.15
    adm.loc[us, "admission_date"] = pd.to_datetime(adm.loc[us, "admission_date"]).dt.strftime("%m/%d/%Y")

    # inconsistent department labels
    messy = {"Cardiology": ["cardiology", " Cardiology ", "CARDIOLOGY"],
             "General Medicine": ["Gen Med", "general medicine", "General  Medicine"],
             "Orthopedics": ["Orthopaedics", "ortho"],
             "Pulmonology": ["pulmonology "]}
    for clean, variants in messy.items():
        idx = adm.index[(adm["department"] == clean) & (rng.random(n) < 0.08)]
        adm.loc[idx, "department"] = rng.choice(variants, len(idx))

    # missing values
    adm.loc[rng.random(n) < 0.02, "total_charges"] = np.nan
    adm.loc[rng.random(n) < 0.015, "discharge_date"] = np.nan
    adm.loc[rng.random(n) < 0.01, "admission_type"] = np.nan
    pat.loc[rng.random(len(pat)) < 0.03, "insurance_type"] = np.nan
    pat.loc[rng.random(len(pat)) < 0.02, "gender"] = rng.choice(["F", "M", "female"], 1)[0]

    # invalid values
    neg = adm.sample(15, random_state=1).index
    adm.loc[neg, "total_charges"] = -adm.loc[neg, "total_charges"].abs()
    swap = adm.dropna(subset=["discharge_date"]).sample(12, random_state=2).index
    adm.loc[swap, "discharge_date"] = "2023-12-31"

    # exact duplicate rows (double-loaded records)
    adm = pd.concat([adm, adm.sample(60, random_state=3)]).sample(frac=1, random_state=4)
    pat = pd.concat([pat, pat.sample(25, random_state=5)])
    return adm.reset_index(drop=True), pat.reset_index(drop=True)


def main():
    rng = np.random.default_rng(SEED)
    patients = make_patients(rng)
    admissions = make_admissions(rng, patients)
    admissions, patients = add_data_quality_issues(rng, admissions, patients)
    RAW.mkdir(parents=True, exist_ok=True)
    patients.to_csv(RAW / "patients.csv", index=False)
    admissions.to_csv(RAW / "admissions.csv", index=False)
    print(f"Wrote {len(patients):,} patient rows and {len(admissions):,} admission rows to {RAW}")


if __name__ == "__main__":
    main()

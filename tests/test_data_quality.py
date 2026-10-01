"""Data-quality checks on the processed data. Run: pytest -q"""
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.fixture(scope="module")
def adm():
    return pd.read_csv(PROC / "admissions_clean.csv", parse_dates=["admission_date", "discharge_date"])


@pytest.fixture(scope="module")
def pat():
    return pd.read_csv(PROC / "patients_clean.csv")


def test_no_duplicates(adm, pat):
    assert not adm.duplicated().any()
    assert adm["admission_id"].is_unique
    assert pat["patient_id"].is_unique


def test_no_missing_key_fields(adm):
    cols = ["admission_id", "patient_id", "department", "admission_date",
            "discharge_date", "total_charges", "outcome"]
    assert adm[cols].notna().all().all()


def test_valid_ranges(adm):
    assert (adm["total_charges"] >= 0).all()
    assert (adm["discharge_date"] >= adm["admission_date"]).all()
    assert (adm["length_of_stay"] >= 0).all()
    assert (adm["age_at_admission"] >= 0).all()


def test_standardized_categories(adm, pat):
    assert adm["department"].nunique() == 7
    assert set(pat["gender"].dropna()) <= {"Female", "Male"}


def test_referential_integrity(adm, pat):
    assert adm["patient_id"].isin(pat["patient_id"]).all()


def test_sql_matches_python_readmissions():
    with sqlite3.connect(PROC / "healthcare.db") as conn:
        check = pd.read_csv(PROC / "kpi_readmission_check.csv")
        n = conn.execute("SELECT COUNT(*) FROM fact_admissions").fetchone()[0]
    assert check.loc[0, "mismatches"] == 0
    assert n == len(pd.read_csv(PROC / "admissions_clean.csv"))

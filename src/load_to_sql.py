"""
Load the cleaned CSVs into a SQLite star schema and run the KPI queries.

Output:
  data/processed/healthcare.db   - SQLite database (dim_patients, dim_departments, fact_admissions)
  data/processed/kpi_<name>.csv  - one file per query in sql/kpi_queries.sql
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, SQL = ROOT / "data" / "processed", ROOT / "sql"
DB = PROC / "healthcare.db"


def load(conn: sqlite3.Connection):
    conn.executescript((SQL / "schema.sql").read_text())
    pat = pd.read_csv(PROC / "patients_clean.csv")
    adm = pd.read_csv(PROC / "admissions_clean.csv")

    depts = pd.DataFrame({"department": sorted(adm["department"].unique())})
    depts.insert(0, "department_id", range(1, len(depts) + 1))
    adm = adm.merge(depts, on="department")

    cols = ["admission_id", "patient_id", "department_id", "diagnosis", "admission_type",
            "admission_date", "discharge_date", "length_of_stay", "age_at_admission",
            "age_group", "outcome", "total_charges", "readmitted_30d"]
    pat.to_sql("dim_patients", conn, if_exists="append", index=False)
    depts.to_sql("dim_departments", conn, if_exists="append", index=False)
    adm[cols].to_sql("fact_admissions", conn, if_exists="append", index=False)
    conn.commit()
    print(f"Loaded {len(pat):,} patients, {len(depts)} departments, {len(adm):,} admissions into {DB.name}")


def run_kpis(conn: sqlite3.Connection):
    text = (SQL / "kpi_queries.sql").read_text()
    blocks = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)[1:]
    for name, query in zip(blocks[::2], blocks[1::2]):
        df = pd.read_sql_query(query.strip().rstrip(";"), conn)
        df.to_csv(PROC / f"kpi_{name}.csv", index=False)
        print(f"\n== {name} ==\n{df.head(10).to_string(index=False)}")


def main():
    DB.unlink(missing_ok=True)
    with sqlite3.connect(DB) as conn:
        load(conn)
        run_kpis(conn)


if __name__ == "__main__":
    main()

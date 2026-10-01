# Building the Power BI report

The Python pipeline produces clean, model-ready data. This guide rebuilds the same
dashboard in Power BI Desktop (Windows). Save your finished file as
`powerbi/Healthcare_Patient_Insights.pbix` and commit it with a screenshot.

## 1. Get data

**Option A – CSV (simplest)**
*Home → Get data → Text/CSV* and load:

| File | Table name |
|---|---|
| `data/processed/admissions_clean.csv` | `fact_admissions` |
| `data/processed/patients_clean.csv` | `dim_patients` |

Then create `dim_departments` in Power Query: reference `fact_admissions`, keep the
`department` column, *Remove Duplicates*, add an index column `department_id`.

**Option B – SQLite via ODBC**
Install the SQLite ODBC driver, create a DSN pointing to `data/processed/healthcare.db`,
then *Get data → ODBC* and select `fact_admissions`, `dim_patients`, `dim_departments`.

In Power Query set data types: dates → *Date*, `total_charges` → *Fixed decimal*,
`length_of_stay`, `readmitted_30d` → *Whole number*.

## 2. Model (star schema)

```
dim_patients (1) ──< fact_admissions >── (1) dim_departments
                           │
                        'Date' (1)
```

* `dim_patients[patient_id]` → `fact_admissions[patient_id]`
* `dim_departments[department]` (or `department_id`) → `fact_admissions`
* `'Date'[Date]` → `fact_admissions[admission_date]`

Add the measures from [DAX_measures.md](DAX_measures.md).

## 3. Report pages

**Page 1 – Overview**
* Cards: Total Admissions, Unique Patients, Avg Length of Stay, Readmission Rate %, Avg Charge per Admission
* Line chart: Total Admissions by `'Date'[Year-Month]` (+ 3M rolling average)
* Bar chart: Total Admissions by department
* Bar chart: Avg Length of Stay by department; column chart by `age_group`

**Page 2 – Outcomes & Readmissions**
* 100% stacked bar: Total Admissions by department, legend = `outcome`
* Bar chart: Readmission Rate % by department
* Bar chart: Readmission Rate % by diagnosis (Top N = 8 filter)
* Bar chart: Total Admissions by `insurance_type` (payer mix)

**Slicers (sync across pages):** date range, department, admission type, insurance type.

## 4. Theme

*View → Themes → Browse for themes* → `powerbi/theme.json` (colorblind-safe palette
matching the Streamlit app).

## 5. Validate

Check your card values against `data/processed/kpi_overall_kpis.csv` (produced by the SQL
queries). They should match exactly – this is the reconciliation step between the SQL layer and
the BI layer.

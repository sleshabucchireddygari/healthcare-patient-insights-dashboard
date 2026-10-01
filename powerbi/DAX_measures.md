# Power BI – DAX Measures

Paste these into a `_Measures` table in Power BI Desktop after loading the model
described in [POWERBI_GUIDE.md](POWERBI_GUIDE.md). Table names match the SQLite star schema.

```DAX
Total Admissions = COUNTROWS ( fact_admissions )

Unique Patients = DISTINCTCOUNT ( fact_admissions[patient_id] )

Avg Length of Stay =
AVERAGE ( fact_admissions[length_of_stay] )

Readmissions (30d) =
SUM ( fact_admissions[readmitted_30d] )

Readmission Rate % =
DIVIDE ( [Readmissions (30d)], [Total Admissions] )

Deaths =
CALCULATE ( [Total Admissions], fact_admissions[outcome] = "Deceased" )

Mortality Rate % =
DIVIDE ( [Deaths], [Total Admissions] )

Total Charges = SUM ( fact_admissions[total_charges] )

Avg Charge per Admission =
DIVIDE ( [Total Charges], [Total Admissions] )

Bed Days = SUM ( fact_admissions[length_of_stay] )

-- Time intelligence (requires the Date table below, marked as a date table)
Admissions PY =
CALCULATE ( [Total Admissions], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )

Admissions YoY % =
DIVIDE ( [Total Admissions] - [Admissions PY], [Admissions PY] )

Admissions 3M Rolling Avg =
AVERAGEX (
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -3, MONTH ),
    [Total Admissions]
)

-- Department ranking for a "top departments" visual
Dept Rank by Readmission =
RANKX ( ALL ( dim_departments[department] ), [Readmission Rate %], , DESC )
```

## Date table

```DAX
Date =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2024, 1, 1 ), DATE ( 2025, 12, 31 ) ),
    "Year", YEAR ( [Date] ),
    "Month", FORMAT ( [Date], "MMM" ),
    "Month Number", MONTH ( [Date] ),
    "Year-Month", FORMAT ( [Date], "YYYY-MM" ),
    "Quarter", "Q" & QUARTER ( [Date] )
)
```

Relate `'Date'[Date]` → `fact_admissions[admission_date]` (one-to-many), then
**Mark as date table**. Sort `Month` by `Month Number`.

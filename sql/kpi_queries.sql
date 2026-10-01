-- KPI queries for the Healthcare Patient Insights Dashboard
-- Each query is separated by a "-- name:" header so src/load_to_sql.py can run
-- and export them individually to data/processed/kpi_*.csv.

-- name: overall_kpis
SELECT
    COUNT(*)                                        AS total_admissions,
    COUNT(DISTINCT patient_id)                      AS unique_patients,
    ROUND(AVG(length_of_stay), 2)                   AS avg_length_of_stay,
    ROUND(100.0 * AVG(readmitted_30d), 2)           AS readmission_rate_pct,
    ROUND(100.0 * AVG(outcome = 'Deceased'), 2)     AS mortality_rate_pct,
    ROUND(SUM(total_charges), 0)                    AS total_charges,
    ROUND(AVG(total_charges), 0)                    AS avg_charge_per_admission
FROM fact_admissions;

-- name: monthly_admissions
SELECT
    strftime('%Y-%m', admission_date)               AS month,
    COUNT(*)                                        AS admissions,
    ROUND(AVG(length_of_stay), 2)                   AS avg_length_of_stay,
    ROUND(100.0 * AVG(readmitted_30d), 2)           AS readmission_rate_pct
FROM fact_admissions
GROUP BY month
ORDER BY month;

-- name: department_performance
SELECT
    d.department,
    COUNT(*)                                        AS admissions,
    ROUND(AVG(a.length_of_stay), 2)                 AS avg_length_of_stay,
    ROUND(100.0 * AVG(a.readmitted_30d), 2)         AS readmission_rate_pct,
    ROUND(100.0 * AVG(a.outcome = 'Deceased'), 2)   AS mortality_rate_pct,
    ROUND(AVG(a.total_charges), 0)                  AS avg_charge
FROM fact_admissions a
JOIN dim_departments d USING (department_id)
GROUP BY d.department
ORDER BY admissions DESC;

-- name: outcomes_by_department
SELECT
    d.department,
    a.outcome,
    COUNT(*)                                        AS admissions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY d.department), 2) AS pct_of_department
FROM fact_admissions a
JOIN dim_departments d USING (department_id)
GROUP BY d.department, a.outcome
ORDER BY d.department, admissions DESC;

-- name: los_by_age_group
SELECT
    age_group,
    COUNT(*)                                        AS admissions,
    ROUND(AVG(length_of_stay), 2)                   AS avg_length_of_stay,
    ROUND(100.0 * AVG(readmitted_30d), 2)           AS readmission_rate_pct
FROM fact_admissions
GROUP BY age_group
ORDER BY CASE age_group WHEN '0-17' THEN 1 WHEN '18-39' THEN 2 WHEN '40-64' THEN 3
                        WHEN '65-79' THEN 4 ELSE 5 END;

-- name: payer_mix
SELECT
    p.insurance_type,
    COUNT(*)                                        AS admissions,
    ROUND(SUM(a.total_charges), 0)                  AS total_charges,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_admissions
FROM fact_admissions a
JOIN dim_patients p USING (patient_id)
GROUP BY p.insurance_type
ORDER BY admissions DESC;

-- name: top_diagnoses_by_readmission
SELECT
    diagnosis,
    COUNT(*)                                        AS admissions,
    SUM(readmitted_30d)                             AS readmissions,
    ROUND(100.0 * AVG(readmitted_30d), 2)           AS readmission_rate_pct
FROM fact_admissions
GROUP BY diagnosis
HAVING COUNT(*) >= 100
ORDER BY readmission_rate_pct DESC
LIMIT 10;

-- name: readmission_check
-- Recomputes the 30-day readmission flag in SQL with a window function and
-- compares it with the flag produced by the Python cleaning step.
WITH next_visit AS (
    SELECT
        admission_id,
        readmitted_30d,
        julianday(LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date))
          - julianday(discharge_date) AS days_to_next
    FROM fact_admissions
)
SELECT
    SUM(CASE WHEN days_to_next BETWEEN 0 AND 30 THEN 1 ELSE 0 END) AS sql_readmissions,
    SUM(readmitted_30d)                                            AS python_readmissions,
    SUM(CASE WHEN (days_to_next BETWEEN 0 AND 30) <> readmitted_30d THEN 1 ELSE 0 END) AS mismatches
FROM next_visit;

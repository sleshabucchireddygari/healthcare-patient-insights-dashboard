-- Star schema for the hospital dataset (SQLite; also valid MySQL with minor type changes)

DROP TABLE IF EXISTS fact_admissions;
DROP TABLE IF EXISTS dim_patients;
DROP TABLE IF EXISTS dim_departments;

CREATE TABLE dim_patients (
    patient_id      TEXT PRIMARY KEY,
    gender          TEXT,
    date_of_birth   DATE,
    insurance_type  TEXT,
    city            TEXT
);

CREATE TABLE dim_departments (
    department_id   INTEGER PRIMARY KEY,
    department      TEXT UNIQUE NOT NULL
);

CREATE TABLE fact_admissions (
    admission_id            TEXT PRIMARY KEY,
    patient_id              TEXT NOT NULL REFERENCES dim_patients(patient_id),
    department_id           INTEGER NOT NULL REFERENCES dim_departments(department_id),
    diagnosis               TEXT,
    admission_type          TEXT,
    admission_date          DATE NOT NULL,
    discharge_date          DATE NOT NULL,
    length_of_stay          INTEGER CHECK (length_of_stay >= 0),
    age_at_admission        INTEGER,
    age_group               TEXT,
    outcome                 TEXT,
    total_charges           REAL CHECK (total_charges >= 0),
    readmitted_30d          INTEGER CHECK (readmitted_30d IN (0, 1))
);

CREATE INDEX idx_adm_patient ON fact_admissions(patient_id, admission_date);
CREATE INDEX idx_adm_dept    ON fact_admissions(department_id);
CREATE INDEX idx_adm_date    ON fact_admissions(admission_date);

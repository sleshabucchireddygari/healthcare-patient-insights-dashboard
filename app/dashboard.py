"""
Healthcare Patient Insights Dashboard (Streamlit + Plotly)

Run:  streamlit run app/dashboard.py
Reads data/processed/healthcare.db (build it with `python src/run_pipeline.py`).
"""
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "healthcare.db"

# Validated colorblind-safe categorical palette (fixed order) + text tokens
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
OUTCOME_COLORS = {"Recovered": BLUE, "Improved": ORANGE, "Transferred": AQUA, "Deceased": YELLOW}
AGE_ORDER = ["0-17", "18-39", "40-64", "65-79", "80+"]

st.set_page_config(page_title="Healthcare Patient Insights", page_icon="🏥", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    if not DB.exists():
        st.error("Database not found. Run `python src/run_pipeline.py` first.")
        st.stop()
    query = """
        SELECT a.*, d.department, p.gender, p.insurance_type, p.city
        FROM fact_admissions a
        JOIN dim_departments d USING (department_id)
        JOIN dim_patients   p USING (patient_id)
    """
    with sqlite3.connect(DB) as conn:
        df = pd.read_sql_query(query, conn, parse_dates=["admission_date", "discharge_date"])
    df["month"] = df["admission_date"].dt.to_period("M").dt.to_timestamp()
    return df


def pad_x(fig: go.Figure, max_value: float) -> go.Figure:
    """Leave room on the right so outside bar labels are never clipped."""
    fig.update_xaxes(range=[0, max_value * 1.18])
    return fig


def style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color=TEXT),
        hoverlabel=dict(bgcolor="white", font_size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont_color=MUTED, title_font_color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont_color=MUTED, title_font_color=MUTED)
    return fig


df = load_data()

# ---------------- Header & filters ----------------
st.title("Healthcare Patient Insights Dashboard")
st.caption("Hospital admissions, outcomes, length of stay and readmissions · synthetic data, 2024–2025")

with st.sidebar:
    st.header("Filters")
    min_d, max_d = df["admission_date"].min().date(), df["admission_date"].max().date()
    dates = st.date_input("Admission date range", (min_d, max_d), min_value=min_d, max_value=max_d)
    depts = st.multiselect("Department", sorted(df["department"].unique()))
    adm_types = st.multiselect("Admission type", sorted(df["admission_type"].unique()))
    payers = st.multiselect("Insurance", sorted(df["insurance_type"].unique()))
    st.caption("Leave a filter empty to include everything.")

f = df.copy()
if isinstance(dates, tuple) and len(dates) == 2:
    f = f[(f["admission_date"].dt.date >= dates[0]) & (f["admission_date"].dt.date <= dates[1])]
for col, chosen in (("department", depts), ("admission_type", adm_types), ("insurance_type", payers)):
    if chosen:
        f = f[f[col].isin(chosen)]

if f.empty:
    st.warning("No admissions match these filters.")
    st.stop()

# ---------------- KPI row ----------------
k = st.columns(5)
k[0].metric("Admissions", f"{len(f):,}", help="Inpatient admissions in the selected period")
k[1].metric("Unique patients", f"{f['patient_id'].nunique():,}")
k[2].metric("Avg length of stay", f"{f['length_of_stay'].mean():.1f} days")
k[3].metric("30-day readmission rate", f"{f['readmitted_30d'].mean():.1%}",
            help="Share of admissions followed by another admission within 30 days of discharge")
k[4].metric("Avg charge / admission", f"${f['total_charges'].mean():,.0f}")

tab_overview, tab_quality, tab_data = st.tabs(["Overview", "Outcomes & readmissions", "Data"])

# ---------------- Overview ----------------
with tab_overview:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Monthly admissions")
        m = f.groupby("month").agg(admissions=("admission_id", "count")).reset_index()
        fig = px.line(m, x="month", y="admissions", markers=True,
                      labels={"month": "", "admissions": "Admissions"})
        fig.update_traces(line=dict(color=BLUE, width=2), marker=dict(size=8))
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(style(fig), width="stretch")
    with c2:
        st.subheader("Admissions by department")
        d = f["department"].value_counts().sort_values().reset_index()
        fig = px.bar(d, x="count", y="department", orientation="h",
                     labels={"count": "Admissions", "department": ""}, text="count")
        fig.update_traces(marker_color=BLUE, textposition="outside", cliponaxis=False)
        pad_x(fig, d["count"].max())
        st.plotly_chart(style(fig), width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Average length of stay by department")
        los = f.groupby("department")["length_of_stay"].mean().sort_values().reset_index()
        fig = px.bar(los, x="length_of_stay", y="department", orientation="h",
                     labels={"length_of_stay": "Avg days", "department": ""},
                     text=los["length_of_stay"].round(1))
        fig.update_traces(marker_color=BLUE, textposition="outside", cliponaxis=False)
        pad_x(fig, los["length_of_stay"].max())
        st.plotly_chart(style(fig), width="stretch")
    with c4:
        st.subheader("Average length of stay by age group")
        age = (f.groupby("age_group")["length_of_stay"].mean()
               .reindex(AGE_ORDER).dropna().reset_index())
        fig = px.bar(age, x="age_group", y="length_of_stay",
                     labels={"age_group": "Age group", "length_of_stay": "Avg days"},
                     text=age["length_of_stay"].round(1))
        fig.update_traces(marker_color=BLUE, textposition="outside", cliponaxis=False)
        st.plotly_chart(style(fig), width="stretch")

# ---------------- Outcomes & readmissions ----------------
with tab_quality:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Treatment outcomes by department")
        o = (f.groupby(["department", "outcome"]).size()
             .groupby(level=0).transform(lambda s: s / s.sum()).rename("share").reset_index())
        fig = px.bar(o, x="share", y="department", color="outcome", orientation="h",
                     color_discrete_map=OUTCOME_COLORS,
                     category_orders={"outcome": list(OUTCOME_COLORS)},
                     labels={"share": "Share of admissions", "department": ""})
        fig.update_traces(marker_line_color="white", marker_line_width=2)
        fig.update_layout(barmode="stack", xaxis_tickformat=".0%")
        st.plotly_chart(style(fig, 380), width="stretch")
    with c2:
        st.subheader("30-day readmission rate by department")
        r = f.groupby("department")["readmitted_30d"].mean().sort_values().reset_index()
        fig = px.bar(r, x="readmitted_30d", y="department", orientation="h",
                     labels={"readmitted_30d": "Readmission rate", "department": ""},
                     text=r["readmitted_30d"].map("{:.1%}".format))
        fig.update_traces(marker_color=BLUE, textposition="outside", cliponaxis=False)
        pad_x(fig, r["readmitted_30d"].max())
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(style(fig, 380), width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Highest readmission diagnoses")
        dx = (f.groupby("diagnosis").agg(admissions=("admission_id", "count"),
                                         rate=("readmitted_30d", "mean"))
              .query("admissions >= 30").nlargest(8, "rate").sort_values("rate").reset_index())
        fig = px.bar(dx, x="rate", y="diagnosis", orientation="h",
                     hover_data={"admissions": True},
                     labels={"rate": "Readmission rate", "diagnosis": ""},
                     text=dx["rate"].map("{:.1%}".format))
        fig.update_traces(marker_color=BLUE, textposition="outside", cliponaxis=False)
        pad_x(fig, dx["rate"].max())
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(style(fig), width="stretch")
    with c4:
        st.subheader("Payer mix")
        pm = f["insurance_type"].value_counts(normalize=True).sort_values().reset_index()
        fig = px.bar(pm, x="proportion", y="insurance_type", orientation="h",
                     labels={"proportion": "Share of admissions", "insurance_type": ""},
                     text=pm["proportion"].map("{:.0%}".format))
        fig.update_traces(marker_color=BLUE, textposition="outside", cliponaxis=False)
        pad_x(fig, pm["proportion"].max())
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(style(fig), width="stretch")

# ---------------- Data ----------------
with tab_data:
    st.subheader("Department summary")
    summary = (f.groupby("department")
               .agg(admissions=("admission_id", "count"),
                    avg_los_days=("length_of_stay", "mean"),
                    readmission_rate=("readmitted_30d", "mean"),
                    mortality_rate=("outcome", lambda s: (s == "Deceased").mean()),
                    avg_charge=("total_charges", "mean"))
               .sort_values("admissions", ascending=False))
    st.dataframe(summary.style.format({"avg_los_days": "{:.1f}", "readmission_rate": "{:.1%}",
                                       "mortality_rate": "{:.1%}", "avg_charge": "${:,.0f}"}),
                 width="stretch")
    st.subheader("Filtered admissions")
    show = f.drop(columns=["department_id", "month"])
    st.dataframe(show, width="stretch", height=360)
    st.download_button("Download filtered data (CSV)", show.to_csv(index=False),
                       "admissions_filtered.csv", "text/csv")

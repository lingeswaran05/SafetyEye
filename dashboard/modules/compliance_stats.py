import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

from ..utils.log_reader import read_logs

THEME = "plotly_dark"


def render_compliance_dashboard():
    st.title("📊 Compliance & Safety Analytics")
    st.markdown("Automated insights and historical trends from workplace PPE monitoring logs.")

    df = read_logs()
    if df.empty:
        st.info("ℹ️ No violation logs recorded yet. Run live monitoring or replay sessions to populate data.")
        return

    # Key Performance Indicators (KPIs)
    total_records = len(df)
    total_violations = len(df[df["violation_type"].notnull()])
    
    # Calculate monitored duration if timestamps are present
    if "timestamp" in df.columns and total_records > 1:
        valid_ts = df["timestamp"].dropna()
        if len(valid_ts) > 1:
            time_span_seconds = (valid_ts.max() - valid_ts.min()).total_seconds()
            monitored_hours = max(time_span_seconds / 3600.0, 0.01)
        else:
            monitored_hours = 0.0
    else:
        monitored_hours = 0.0

    avg_conf = df["confidence"].mean() if "confidence" in df.columns else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🚨 Total Violations Logged", total_violations)
    kpi2.metric("⏱️ Monitored Hours", f"{monitored_hours:.2f} hrs" if monitored_hours > 0 else "Active")
    kpi3.metric("🎯 Avg Confidence", f"{avg_conf:.1%}" if avg_conf else "N/A")
    kpi4.metric("📁 Logged Snapshots", total_records)

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)

    # 1. Violation Type Distribution Bar Chart
    with col_chart1:
        st.subheader("Violation Types Distribution")
        if "violation_type" in df.columns:
            type_counts = df["violation_type"].value_counts().reset_index()
            type_counts.columns = ["Violation Type", "Count"]

            fig_bar = px.bar(
                type_counts,
                x="Violation Type",
                y="Count",
                color="Violation Type",
                template=THEME,
                title="Violations by Category",
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

    # 2. Hourly Timeline Trend (Version-agnostic across all Pandas versions)
    with col_chart2:
        st.subheader("Hourly Violation Activity")
        if "timestamp" in df.columns:
            df_valid = df.dropna(subset=["timestamp"]).copy()
            if not df_valid.empty:
                df_valid["Hour"] = df_valid["timestamp"].dt.strftime("%Y-%m-%d %H:00")
                df_hourly = (
                    df_valid.groupby("Hour")
                    .size()
                    .reset_index(name="Alerts Count")
                    .sort_values(by="Hour")
                )

                fig_line = px.line(
                    df_hourly,
                    x="Hour",
                    y="Alerts Count",
                    markers=True,
                    template=THEME,
                    title="Hourly Violation Alerts Timeline",
                )
                st.plotly_chart(fig_line, use_container_width=True)

    # Raw Data Explorer & Export
    st.markdown("---")
    st.subheader("📋 Violation Records Explorer")
    st.dataframe(df.sort_values(by="timestamp", ascending=False).reset_index(drop=True), use_container_width=True)

    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Full Compliance CSV Report",
        data=csv_data,
        file_name="safetyeye_compliance_report.csv",
        mime="text/csv",
    )

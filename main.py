# main.py
import streamlit as st
from streamlit_toggle import theme as st_toggle_theme
from state import initialize_state
from calculations import calculate_databricks_costs_for_tier, calculate_s3_cost_per_zone, calculate_sql_warehouse_cost
from ui_components import render_summary_column, render_databricks_tab, render_s3_tab, render_sql_warehouse_tab, render_configuration_guide, render_export_button
from data import DBU_RATES
from file_exportor import generate_consolidated_excel_export 
import io 

# --- Page Configuration ---
st.set_page_config(
    page_title="Cloud Cost Calculator",
    page_icon="🧮",
    layout="wide"
)

# --- 1. Initialize Session State ---
# This is the most important part. It MUST be called before any calculations.
initialize_state()

# This is for Databricks overall growth, not S3 per-zone growth
if 'monthly_growth_percent' not in st.session_state:
    st.session_state.monthly_growth_percent = 0.0

if 'theme' not in st.session_state:
    st.session_state.theme = 'light'
    

# --- 2. Perform All Calculations ---
# This block can now safely access session_state because it has been initialized.
calculated_dbx_data = {}
for tier in DBU_RATES.keys():
    df_with_costs, dbu_cost, ec2_cost = calculate_databricks_costs_for_tier(st.session_state.dbx_jobs[tier], tier)
    calculated_dbx_data[tier] = {
        "df": df_with_costs,
        "dbu_cost": dbu_cost,
        "ec2_cost": ec2_cost
    }

# This line correctly unpacks the three return values from the function call
s3_costs_per_zone, s3_cost, projected_s3_cost_12_months = calculate_s3_cost_per_zone()
sql_cost = calculate_sql_warehouse_cost()

databricks_total_cost = sum(data['dbu_cost'] + data['ec2_cost'] for data in calculated_dbx_data.values())
total_cost = databricks_total_cost + s3_cost + sql_cost

# --- 3. Render Main Layout ---
title_col, controls_col = st.columns([4, 1])

with title_col:
    st.title("☁️ Cloud Cost Calculator")
    st.caption("Databricks & AWS Cost Estimation")

with controls_col:
    # Arrange theme toggle and export button horizontally
    export_col, theme_col = st.columns(2)

    with export_col:
        # Generate Excel file content
        render_export_button(
            calculated_dbx_data, # Pass the local variable here
            st.session_state.s3_calc_method,
            st.session_state.s3_direct,
            st.session_state.s3_table_based,
            st.session_state.sql_warehouses
        )
    with theme_col:
        # Custom theme toggle using a button
        if st.session_state.theme == 'light':
            button_label = "🌙"
            new_theme = 'dark'
        else:
            button_label = "☀️"
            new_theme = 'light'

        if st.button(button_label):
            st.session_state.theme = new_theme
            # Set Streamlit's internal theme option
            st.config.set_option("theme.base", new_theme)
            st.rerun() # Rerun to apply the theme change immediately

# Apply the current theme setting
st.config.set_option("theme.base", st.session_state.theme)

main_col, summary_col = st.columns([3, 1])

with main_col:
    tab1, tab2, tab3 = st.tabs(["Databricks & Compute", "S3 Storage", "SQL Warehouse"])

    with tab1:
        render_databricks_tab(calculated_dbx_data)
        render_configuration_guide()
    with tab2:
        # Pass the projected_s3_cost_12_months to render_s3_tab
        render_s3_tab(s3_costs_per_zone, s3_cost, projected_s3_cost_12_months)
    with tab3:
        render_sql_warehouse_tab(sql_cost)

with summary_col:
    # Pass the projected_s3_cost_12_months to render_summary_column
    render_summary_column(total_cost, databricks_total_cost, s3_cost, sql_cost, projected_s3_cost_12_months)

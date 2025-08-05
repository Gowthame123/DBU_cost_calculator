# state.py
import streamlit as st
import pandas as pd
from data import INSTANCE_LIST, SQL_WAREHOUSE_SIZES, S3_STORAGE_CLASSES, DBU_RATES, SQL_WAREHOUSE_TYPES

def initialize_state():
    """Initializes session state variables if they don't exist."""
    # Removed the 'initialized' flag check to ensure all keys are checked
    # This makes the initialization more robust against partial state issues

    # Databricks state
    if 'dbx_jobs' not in st.session_state:
        st.session_state.dbx_jobs = {
            tier: pd.DataFrame([{
                "#": 1, "Job Name": f"{tier.split(' / ')[1]} Job 1", "Runtime (hrs)": 0, "Runs/Month": 0,
                "Instance Type": INSTANCE_LIST[0], "Nodes": 1, "Photon": False, "Spot": False
            }]) for tier in DBU_RATES.keys()
        }

    # S3 state
    if 's3_calc_method' not in st.session_state:
        st.session_state.s3_calc_method = "Direct Storage"
    
    if 's3_direct' not in st.session_state:
        st.session_state.s3_direct = {
            "Landing Zone": {"class": "Standard", "amount": 0, "unit": "GB", "put": 0, "get": 0, "monthly_growth_percent": 0.0},
            "L0 / Bronze": {"class": "Standard", "amount": 0, "unit": "GB", "put": 0, "get": 0, "monthly_growth_percent": 0.0},
            "L1 / Silver": {"class": "Infrequent Access", "amount": 0, "unit": "GB", "put": 0, "get": 0, "monthly_growth_percent": 0.0},
            "L2 / Gold": {"class": "Standard", "amount": 0, "unit": "GB", "put": 0, "get": 0, "monthly_growth_percent": 0.0},
        }
    
    # Ensure existing s3_direct entries have 'monthly_growth_percent'
    for zone, config in st.session_state.s3_direct.items():
        if 'monthly_growth_percent' not in config:
            config['monthly_growth_percent'] = 0.0

    if 's3_table_based' not in st.session_state:
        st.session_state.s3_table_based = {
            # Initializing with a list of a single default table entry,
            # which aligns better with how data_editor handles dynamic rows.
            "Landing Zone": [{"Table Name": "Landing_Table_1", "Records": 100000, "Columns": 10}], 
            "L0 / Bronze":  [{"Table Name": "Bronze_Table_1", "Records": 100000, "Columns": 15}], 
            "L1 / Silver":  [{"Table Name": "Silver_Table_1", "Records": 100000, "Columns": 20}], 
            "L2 / Gold":    [{"Table Name": "Gold_Table_1", "Records": 100000, "Columns": 25}], 
        }
    else: # Ensure existing entries also get 'Columns' if they are old format

        from data import DEFAULT_KB_PER_RECORD_PER_COLUMN # Need this here for potential migration
        
        for zone_name, table_configs in st.session_state.s3_table_based.items():
            if isinstance(table_configs, dict) and "records" in table_configs:
                # This handles the old single-dict-per-zone format
                # Convert it to a list containing the new structure
                st.session_state.s3_table_based[zone_name] = [{
                    "Table Name": f"{zone_name.replace(' / ', '_')} Table 1",
                    "Records": table_configs.get("records", 100000),
                    "Columns": 10 # Default new column count
                }]
            elif isinstance(table_configs, list):
                # Ensure each item in the list has 'Columns'
                for i, table_config in enumerate(table_configs):
                    if 'Columns' not in table_config:
                        st.session_state.s3_table_based[zone_name][i]['Columns'] = 10 # Default new column count

    # SQL Warehouse state
    if 'sql_warehouses' not in st.session_state:
        st.session_state.sql_warehouses = [{
            "id": "warehouse_0", "name": "Primary BI Warehouse", "type": SQL_WAREHOUSE_TYPES[0], "size": SQL_WAREHOUSE_SIZES[0], # Default to 2X-Small
            "hours_per_day": 8, "days_per_month": 22, "auto_suspend": True, "suspend_after": 10
        }]
    
    # Ensure existing SQL warehouses have 'type'
    for warehouse in st.session_state.sql_warehouses:
        if 'type' not in warehouse:
            warehouse['type'] = SQL_WAREHOUSE_TYPES[0]

    # Monthly Growth Rate for Databricks (used in overall projection, but no longer an input in summary)
    if 'monthly_growth_percent' not in st.session_state:
        st.session_state.monthly_growth_percent = 0.0

    # Theme state
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'

# calculations.py
import streamlit as st
import pandas as pd
from data import DBU_RATES, FLAT_INSTANCE_LIST, S3_PRICING, SQL_WAREHOUSE_PRICING, PHOTON_PREMIUM_MULTIPLIER, SPOT_DISCOUNT_MULTIPLIER, DEFAULT_KB_PER_RECORD_PER_COLUMN

def calculate_databricks_costs_for_tier(jobs_df, tier):
    """
    Calculates costs for a specific tier's DataFrame.
    Returns a new DataFrame with calculated columns and total costs for the tier.
    """
    if jobs_df.empty:
        return pd.DataFrame(columns=["#", "Job Name", "Runtime (hrs)", "Runs/Month", "Instance Type", "Nodes", "Photon", "Spot", "DBU Cost", "EC2 Cost", "Total Cost"]), 0, 0

    df = jobs_df.copy()
    base_dbu_rate = DBU_RATES[tier]

    # Calculate DBU Rate per job
    df['DBU Units'] = df.apply(
        lambda row: row["Runtime (hrs)"] * row["Runs/Month"] * row["Nodes"],
        axis=1
    )
    df['DBU Cost'] = df.apply(
        lambda row: row['DBU Units'] * base_dbu_rate * (PHOTON_PREMIUM_MULTIPLIER if row['Photon'] else 1.0),
        axis=1
    )


    # Calculate EC2 Cost per job
    def get_ec2_cost(row):
        ec2_rate = FLAT_INSTANCE_LIST.get(row["Instance Type"], 0) * (SPOT_DISCOUNT_MULTIPLIER if row["Spot"] else 1.0)
        return row["Runtime (hrs)"] * row["Runs/Month"] * row["Nodes"] * ec2_rate
    df['EC2 Cost'] = df.apply(get_ec2_cost, axis=1)

    # Calculate total costs for the tier
    total_dbu_cost = df['DBU Cost'].sum()
    total_ec2_cost = df['EC2 Cost'].sum()

    return df, total_dbu_cost, total_ec2_cost

def calculate_s3_cost_per_zone():
    """
    Calculates S3 cost for each individual zone, the total current cost,
    and the total 12-month projected cost.
    """
    current_costs_per_zone = {}
    projected_costs_per_zone = {} # Keep this for S3 tab display if needed, or remove if not displayed individually
    total_s3_cost = 0
    total_projected_s3_cost_12_months = 0

    if st.session_state.s3_calc_method == "Direct Storage":
        for zone, config in st.session_state.s3_direct.items():
            pricing = S3_PRICING.get(config["class"], {"storage_gb": 0, "put_1k": 0, "get_1k": 0})
            storage_gb = config["amount"] * 1024 if config["unit"] == "TB" else config["amount"]
            
            # Current monthly cost for the zone
            storage_cost = storage_gb * pricing["storage_gb"]
            # put_cost = config["put"] * pricing["put_1k"] # Uncomment if PUT/GET operations are added back
            # get_cost = config["get"] * pricing["get_1k"] # Uncomment if PUT/GET operations are added back
            
            zone_current_cost = storage_cost # + put_cost + get_cost
            current_costs_per_zone[zone] = zone_current_cost
            total_s3_cost += zone_current_cost

            # Calculate 12-month projected cost for this zone (per-zone S3 growth is kept)
            monthly_growth_percent = config.get("monthly_growth_percent", 0.0)
            if monthly_growth_percent > 0:
                growth_factor = 1 + (monthly_growth_percent / 100)
                if growth_factor != 1:
                    zone_projected_cost = zone_current_cost * (growth_factor**12 - 1) / (growth_factor - 1)
                else:
                    zone_projected_cost = zone_current_cost * 12
            else:
                zone_projected_cost = zone_current_cost * 12

            projected_costs_per_zone[zone] = zone_projected_cost
            total_projected_s3_cost_12_months += zone_projected_cost
            
    else: # Table-Based
        standard_pricing = S3_PRICING["Standard"]
        for zone, list_of_table_configs in st.session_state.s3_table_based.items():
            zone_estimated_gb = 0
            for table_config in list_of_table_configs:
                if isinstance(table_config, dict):
                    records = float(table_config.get("Records", 0))
                    # Retrieve the number of columns
                    num_columns = float(table_config.get("Columns", 0)) # <--- Changed here

                    # Calculate estimated GB: (records * num_columns * DEFAULT_KB_PER_RECORD_PER_COLUMN) / (1024 * 1024)
                    # Assuming DEFAULT_KB_PER_RECORD_PER_COLUMN is in KB
                    estimated_gb_for_table = (records * num_columns * DEFAULT_KB_PER_RECORD_PER_COLUMN) / (1024 * 1024)
                    zone_estimated_gb += estimated_gb_for_table

            zone_current_cost = zone_estimated_gb * standard_pricing["storage_gb"]
            current_costs_per_zone[zone] = zone_current_cost
            total_s3_cost += zone_current_cost
            
            total_projected_s3_cost_12_months += zone_current_cost * 12
            projected_costs_per_zone[zone] = zone_current_cost * 12


    return current_costs_per_zone, total_s3_cost, total_projected_s3_cost_12_months

def calculate_sql_warehouse_cost():
    """Calculates total SQL Warehouse cost from session state."""
    total_sql_cost = 0
    for warehouse in st.session_state.sql_warehouses:
        if warehouse["hours_per_day"] > 0 and warehouse["days_per_month"] > 0:
            size_key = warehouse["size"].split(" - ")[0]
            hourly_rate = SQL_WAREHOUSE_PRICING.get(size_key, {}).get("cost_per_hr", 0)
            cost = hourly_rate * warehouse["hours_per_day"] * warehouse["days_per_month"]
            total_sql_cost += cost
            
    return total_sql_cost

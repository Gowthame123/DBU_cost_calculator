# excel_exporter.py
import io
import pandas as pd
import xlsxwriter # Ensure xlsxwriter is installed: pip install xlsxwriter

# Import necessary data for calculations within the exporter
from data import SQL_WAREHOUSE_PRICING, DBU_RATES # DBU_RATES for tier names if needed, SQL_WAREHOUSE_PRICING for details


def generate_consolidated_excel_export(calculated_dbx_data, s3_calc_method, s3_direct_config, s3_table_based_config, sql_warehouses_config):
    """
    Generates a consolidated Excel file with multiple sheets for different cost categories.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

        # 1. Databricks Jobs Sheet (All Tiers Combined)
        all_dbx_dfs = []
        for tier, data in calculated_dbx_data.items():
            df_to_export = data['df'].copy()
            # Add a 'Tier' column to identify the original tier for each job
            df_to_export['Tier'] = tier
            all_dbx_dfs.append(df_to_export)

        if all_dbx_dfs:
            combined_dbx_df = pd.concat(all_dbx_dfs, ignore_index=True)

            # Clean and reorder columns for better export for the combined DataFrame
            if 'Total Cost' in combined_dbx_df.columns:
                combined_dbx_df = combined_dbx_df.drop(columns=['Total Cost'], errors='ignore')

            # Rename columns for clarity in Excel
            combined_dbx_df = combined_dbx_df.rename(columns={
                '#': 'Job No',
                'Job Name': 'Name',
                'Runtime (hrs)': 'Runtime Hours',
                'Runs/Month': 'Runs per Month',
                'Instance Type': 'Instance',
                'Nodes': 'Nodes',
                'Photon': 'Photon Enabled',
                'Spot': 'Spot Instance',
                'DBU Units': 'Calculated DBU Units',
                'DBU Cost': 'Calculated DBU Cost ($)',
                'EC2 Cost': 'Calculated EC2 Cost ($)'
            })
            # Ensure 'Tier' is the first column for clarity
            ordered_cols_dbx = [
                'Tier', 'Job No', 'Name', 'Runtime Hours', 'Runs per Month', 'Instance',
                'Nodes', 'Photon Enabled', 'Spot Instance', 'Calculated DBU Units',
                'Calculated DBU Cost ($)', 'Calculated EC2 Cost ($)'
            ]
            # Ensure only relevant columns are kept and in order
            # The 'df' from calculated_dbx_data should only contain the columns from calculations.py
            # plus the new 'Tier' column.
            # If there are extra columns from previous states that are not in ordered_cols_dbx, they will be dropped.
            combined_dbx_df = combined_dbx_df[ordered_cols_dbx]
            combined_dbx_df.to_excel(writer, sheet_name="Databricks_Jobs", index=False)
        else:
            # Create an empty DataFrame with expected columns if no data
            empty_dbx_df = pd.DataFrame(columns=[
                'Tier', 'Job No', 'Name', 'Runtime Hours', 'Runs per Month', 'Instance',
                'Nodes', 'Photon Enabled', 'Spot Instance', 'Calculated DBU Units',
                'Calculated DBU Cost ($)', 'Calculated EC2 Cost ($)'
            ])
            empty_dbx_df.to_excel(writer, sheet_name="Databricks_Jobs", index=False)


        # 2. S3 Storage Sheets (based on active method)
        if s3_calc_method == "Direct Storage":
            direct_data = []
            for zone, config in s3_direct_config.items():
                direct_data.append({
                    "Zone": zone,
                    "Storage Class": config["class"],
                    "Storage Amount": config["amount"],
                    "Unit": config["unit"],
                    "Monthly Growth %": config["monthly_growth_percent"]
                })
            if direct_data:
                df_direct = pd.DataFrame(direct_data)
                df_direct.to_excel(writer, sheet_name='S3_Direct_Storage', index=False)
            else:
                empty_s3_direct_df = pd.DataFrame(columns=["Zone", "Storage Class", "Storage Amount", "Unit", "Monthly Growth %"])
                empty_s3_direct_df.to_excel(writer, sheet_name='S3_Direct_Storage', index=False)

        else: # Table-Based
            # Initialize an empty list to collect all table entries from all zones
            consolidated_table_data_for_export = []
            # Iterate through each zone and its list of table configurations
            for zone, list_of_table_configs in s3_table_based_config.items():
                # Ensure list_of_table_configs is iterable and contains dictionaries
                if not isinstance(list_of_table_configs, list):
                    # Handle case where it might be a single dict from old state, or empty
                    list_of_table_configs = [list_of_table_configs] if isinstance(list_of_table_configs, dict) else []

                # Iterate through each individual table configuration within the zone's list
                for table_config in list_of_table_configs:
                    # Ensure table_config is a dictionary before trying to access keys
                    if isinstance(table_config, dict):
                        row = {
                            "Zone": zone, # Add the zone name to each table's row
                            "Table Name": table_config.get("Table Name", ""),
                            "Records": table_config.get("Records", 0),
                            "Columns": table_config.get("Columns", 0) # <--- Using the new 'Columns' here
                        }
                        consolidated_table_data_for_export.append(row)

            if consolidated_table_data_for_export: # Only create DataFrame if there's data
                df_table = pd.DataFrame(consolidated_table_data_for_export)
                # Define the desired order of columns for the Excel sheet
                ordered_cols_s3_table = ["Zone", "Table Name", "Records", "Columns"] # <--- Updated column order
                df_table = df_table[ordered_cols_s3_table]
                df_table.to_excel(writer, sheet_name='S3_Table_Based_Storage', index=False)
            else:
                empty_s3_table_df = pd.DataFrame(columns=["Zone", "Table Name", "Records", "Columns"])
                empty_s3_table_df.to_excel(writer, sheet_name='S3_Table_Based_Storage', index=False)

        # 3. SQL Warehouses Sheet
        if sql_warehouses_config:
            warehouse_data = []
            for wh in sql_warehouses_config:
                size_key = wh["size"].split(" - ")[0]
                hourly_rate = SQL_WAREHOUSE_PRICING.get(size_key, {}).get("cost_per_hr", 0)
                dbt_per_hr = SQL_WAREHOUSE_PRICING.get(size_key, {}).get("dbt_per_hr", 0)

                warehouse_data.append({
                    "Name": wh["name"],
                    "Type": wh["type"],
                    "Size": size_key,
                    "DBUs per Hour": dbt_per_hr,
                    "Hourly Rate ($)": hourly_rate,
                    "Hours per Day": wh["hours_per_day"],
                    "Days per Month": wh["days_per_month"],
                    "Monthly Cost ($)": hourly_rate * wh["hours_per_day"] * wh["days_per_month"],
                })
            df_sql = pd.DataFrame(warehouse_data)
            ordered_cols_sql = [
                "Name", "Type", "Size", "DBUs per Hour", "Hourly Rate ($)",
                "Hours per Day", "Days per Month", "Monthly Cost ($)"
            ]
            df_sql = df_sql[ordered_cols_sql]
            df_sql.to_excel(writer, sheet_name='SQL_Warehouses', index=False)
        else:
            empty_sql_df = pd.DataFrame(columns=[
                "Name", "Type", "Size", "DBUs per Hour", "Hourly Rate ($)",
                "Hours per Day", "Days per Month", "Monthly Cost ($)"
            ])
            empty_sql_df.to_excel(writer, sheet_name='SQL_Warehouses', index=False)

    output.seek(0)
    return output.getvalue()
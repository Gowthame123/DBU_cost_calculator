# ui_components.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data import DBU_RATES, INSTANCE_LIST, S3_STORAGE_CLASSES, SQL_WAREHOUSE_SIZES, SQL_WAREHOUSE_PRICING, SQL_WAREHOUSE_TYPES
from file_exportor import generate_consolidated_excel_export


def render_summary_column(total_cost, databricks_cost, s3_cost, sql_cost, projected_s3_cost_12_months):
    """Renders the right-hand summary column with the donut chart."""
    st.header("📈 Monthly Total")
    st.metric("Total Cloud Cost", f"${total_cost:,.2f}")
    st.divider()

    # Removed: New: Monthly Growth Input from summary column
    # st.subheader("Growth Projection")
    # st.session_state.monthly_growth_percent = st.number_input(
    #     "Monthly Databricks Growth %",
    #     min_value=0.0,
    #     max_value=100.0,
    #     value=st.session_state.monthly_growth_percent,
    #     step=0.1,
    #     format="%.1f",
    #     help="Anticipated monthly percentage increase in Databricks costs."
    # )

    # Calculate 12-month projected cost (still uses st.session_state.monthly_growth_percent for Databricks)
    projected_cost_12_months = 0
    current_dbx_cost = databricks_cost
    sql_warehouse_cost_fixed = sql_cost # SQL warehouse cost is assumed not to grow with this percentage

    # Re-calculate Databricks 12-month projection using the value from session state
    # (which can be set in state.py or manipulated elsewhere if needed)
    if st.session_state.monthly_growth_percent > 0:
        growth_factor_dbx = 1 + (st.session_state.monthly_growth_percent / 100)
        if growth_factor_dbx != 1:
            projected_dbx_cost_12_months = current_dbx_cost * (growth_factor_dbx**12 - 1) / (growth_factor_dbx - 1)
        else:
            projected_dbx_cost_12_months = current_dbx_cost * 12
    else:
        projected_dbx_cost_12_months = current_dbx_cost * 12

    # Total 12-month projection includes Databricks, SQL, and S3 projections
    #projected_cost_12_months = projected_dbx_cost_12_months + sql_warehouse_cost_fixed * 12 + projected_s3_cost_12_months

    #st.metric("12-Month Projected Total", f"${projected_cost_12_months:,.2f}")
    #st.divider()

    st.header("Cost Distribution")
    cost_data = {
        "Databricks & Compute": databricks_cost,
        "S3 Storage": s3_cost,
        "SQL Warehouse": sql_cost,
    }
    non_zero_costs = {k: v for k, v in cost_data.items() if v > 0}

    if non_zero_costs:
        fig = go.Figure(data=[go.Pie(
            labels=list(non_zero_costs.keys()), values=list(non_zero_costs.values()), hole=.6,
            marker_colors=['#FF8C00', '#3CB371', '#1E90FF'], hoverinfo="label+percent",
            textinfo="percent", textfont_size=14
        )])
        fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",  # Horizontal legend
            yanchor="bottom",
            y=-0.2,  # Adjust this value to move the legend further down
            xanchor="center",
            x=0.5
        ),
        margin=dict(t=0, b=0, l=0, r=0),
        height=250
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No costs configured yet.")

    st.divider()
    st.header("Cost Insights")
    st.info("""
    - Consider **spot instances** for non-critical workloads to save ~70% on EC2.
    - Enable **auto-suspend** for SQL warehouses to avoid paying for idle compute.
    - Use appropriate **S3 storage classes** for data to optimize storage costs.
    """)

def render_databricks_tab(calculated_dbx_data):
    """Renders the detailed Databricks & Compute tab UI."""
    st.header("Databricks & Compute Costs")
    st.markdown("Configure jobs across different tiers. Specify the number of jobs and configure them in the table below.")
    # container for the main content
    total_dbu_cost = sum(data['dbu_cost'] for data in calculated_dbx_data.values())
    total_ec2_cost = sum(data['ec2_cost'] for data in calculated_dbx_data.values())
    total_jobs = sum(len(st.session_state.dbx_jobs[tier]) for tier in DBU_RATES.keys())

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Jobs", f"{total_jobs}")
        c2.metric("DBU Costs", f"${total_dbu_cost:,.2f}")
        c3.metric("EC2 Costs", f"${total_ec2_cost:,.2f}")
        c4.metric("Monthly Total", f"${total_dbu_cost + total_ec2_cost:,.2f}")

    for tier, data in calculated_dbx_data.items():
        with st.container(border=True):
            df_state = st.session_state.dbx_jobs[tier]
            tier_total_cost = data['dbu_cost'] + data['ec2_cost']
            
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"### {tier} <span style='background-color:#E8E8E8; border-radius:5px; padding: 2px 8px; font-size:90%; font-weight:bold; color:black;'>${tier_total_cost:,.2f}</span>", unsafe_allow_html=True)
            
            c2.write(f"{tier}")
            num_jobs = c2.number_input("Number of Jobs", min_value=0, max_value=20, value=len(df_state), key=f"num_jobs_{tier}", label_visibility="collapsed")

            # --- THIS IS THE FIX ---
            # This logic robustly handles adding or removing rows and prevents errors.
            current_len = len(df_state)
            if num_jobs != current_len:
                if num_jobs > current_len:
                    # Add new rows
                    new_rows_count = num_jobs - current_len
                    new_rows = pd.DataFrame([{
                        "Job Name": "New Job", "Runtime (hrs)": 0, "Runs/Month": 0,
                        "Instance Type": INSTANCE_LIST[0], "Nodes": 1, "Photon": False, "Spot": False
                    }] * new_rows_count)
                    updated_df = pd.concat([df_state, new_rows], ignore_index=True)
                else: # num_jobs < current_len
                    # Remove rows from the end
                    updated_df = df_state.head(num_jobs)
                
                # Always re-index the '#' column after any change
                updated_df['#'] = updated_df.index + 1
                st.session_state.dbx_jobs[tier] = updated_df
                st.rerun()


            if not df_state.empty:
                display_df = data['df']
                editable_cols = ["Job Name", "Runtime (hrs)", "Runs/Month", "Instance Type", "Nodes", "Photon", "Spot"]
                
                edited_df = st.data_editor(
                    display_df,
                    column_order=["Job Name", "#", "Runtime (hrs)", "Runs/Month", "Instance Type", "Nodes", "Photon", "Spot", "DBU Units", "EC2 Cost", "DBU Cost" ],
                    column_config={
                        "#": st.column_config.NumberColumn("Job.no", disabled=True, width="small"),
                        "Instance Type": st.column_config.SelectboxColumn("Instance Type", options=INSTANCE_LIST, required=True),
                       # "DBU Rate": st.column_config.NumberColumn("DBU Rate", format="$%.4f", disabled=True),
                        #"Cost": st.column_config.TextColumn("Cost", disabled=True),
                        "DBU Units": st.column_config.NumberColumn("DBU", format="%.2f", disabled=True),
                        "DBU Cost": st.column_config.NumberColumn("DBX", format="$%.2f", disabled=True),
                        "EC2 Cost": st.column_config.NumberColumn("EC2", format="$%.2f", disabled=True),
                    },
                    hide_index=True, key=f"editor_{tier}", use_container_width=True
                )
                
                # if not edited_df[editable_cols].reset_index(drop=True).equals(df_state[editable_cols].reset_index(drop=True)):
                #    st.session_state.dbx_jobs[tier] = edited_df[["#"] + editable_cols]
                #    st.rerun()

                if not edited_df[editable_cols].reset_index(drop=True).equals(df_state[editable_cols].reset_index(drop=True)):
                    st.session_state.dbx_jobs[tier] = edited_df[["#"] + editable_cols ] 
                    st.rerun()

def render_s3_tab(s3_costs_per_zone, total_s3_cost, projected_s3_cost_12_months):
    """Renders the S3 Storage tab UI with a vertical layout and summary."""
    st.header("AWS S3 Storage Costs")
    st.radio("Calculation Method", ["Direct Storage", "Table-Based"], key="s3_calc_method", horizontal=True)
    
    st.divider()

    if st.session_state.s3_calc_method == "Direct Storage":
        for zone, config in st.session_state.s3_direct.items():
            with st.container(border=True):
                st.subheader(zone)
                c1, c2, c3, c4 = st.columns(4)
                config["class"] = c1.selectbox("Storage Class", S3_STORAGE_CLASSES, key=f"s3_class_{zone}", index=S3_STORAGE_CLASSES.index(config["class"]))
                config["amount"] = c2.number_input("Storage Amount", min_value=0, key=f"s3_amount_{zone}", value=config["amount"])
                config["unit"] = c3.selectbox("Unit", ["GB", "TB"], key=f"s3_unit_{zone}", index=["GB", "TB"].index(config["unit"]))
                
                # Keep monthly growth input for each zone in S3 tab
                config["monthly_growth_percent"] = c4.number_input(
                    f"Monthly Growth % for {zone}",
                    min_value=0.0,
                    max_value=100.0,
                    value=config.get("monthly_growth_percent", 0.0),
                    step=0.1,
                    format="%.1f",
                    key=f"s3_growth_{zone}",
                    help=f"Anticipated monthly percentage increase in storage for {zone}."
                )

                # c4, c5, _ = st.columns(3)
                # config["put"] = c4.number_input("PUTs (x1000)", min_value=0, key=f"s3_put_{zone}", value=config["put"])
                # config["get"] = c5.number_input("GETs (x1000)", min_value=0, key=f"s3_get_{zone}", value=config["get"])
 
    else: # Table-Based
        st.markdown("Configure S3 storage based on the number of records and columns per table.")

        for zone_name, zone_config in st.session_state.s3_table_based.items():
            with st.container(border=True):
                st.subheader(zone_name)

                # Ensure current_zone_tables_data is always a list of dicts
                if not isinstance(st.session_state.s3_table_based[zone_name], list):
                    old_config = st.session_state.s3_table_based[zone_name]
                    st.session_state.s3_table_based[zone_name] = [{
                        "Table Name": f"{zone_name.replace(' / ', '_')} Table 1",
                        "Records": old_config.get("records", 100000),
                        "Columns": old_config.get("columns", 10)
                    }]
                current_zone_tables_data = st.session_state.s3_table_based[zone_name]

                # Prepare initial DataFrame for data_editor
                # Apply initial sanitization/normalization for comparison consistency
                normalized_current_data = []
                for row in current_zone_tables_data:
                    normalized_row = row.copy() # Avoid modifying original session state data directly
                    normalized_row["Records"] = float(normalized_row.get("Records") or 0)
                    normalized_row["Columns"] = float(normalized_row.get("Columns") or 0)
                    normalized_row["Table Name"] = normalized_row.get("Table Name") or ""
                    normalized_current_data.append(normalized_row)
                
                df_zone_initial = pd.DataFrame(normalized_current_data)
                
                if df_zone_initial.empty:
                    df_zone_initial = pd.DataFrame(columns=["Table Name", "Records", "Columns"])
                
                # IMPORTANT: Remove 'id' column before passing to data_editor if it's not a user-editable column
                # The data editor can sometimes re-introduce it if it's in the initial df.
                # If 'id' is for internal tracking only, ensure it's not part of the editable set or the comparison.
                display_df = df_zone_initial.copy()
                if 'id' in display_df.columns:
                    display_df = display_df.drop(columns=['id'])

                edited_df_zone = st.data_editor(
                    display_df, # Use the display_df which might exclude 'id'
                    column_config={
                        # "id": st.column_config.Column(label="", width="small", disabled=True,  help="Unique ID for internal tracking"), # Remove if 'id' is dropped
                        "Table Name": st.column_config.TextColumn("Table Name", required=True),
                        "Records": st.column_config.NumberColumn("Records", min_value=0, format="%d"),
                        "Avg Rec Size (KB)": None,
                        "Avg Rec Size (MB)": None,
                        "Columns": st.column_config.NumberColumn("Columns", min_value=0, format="%d"),
                    },
                    hide_index=True,
                    num_rows="dynamic",
                    key=f"s3_table_editor_{zone_name}",
                    use_container_width=True
                )
              
                # Convert the edited DataFrame to a list of dicts for comparison and storage
                sanitized_updated_zone_data = []
                edited_df_zone_processed = edited_df_zone.copy()
                
                # Apply the same sanitization/normalization to the edited data as to the original data
                if "Records" in edited_df_zone_processed.columns:
                    edited_df_zone_processed["Records"] = edited_df_zone_processed["Records"].apply(lambda x: float(x) if x is not None and x != '' else 0.0)
                else: # New column might be added by data_editor if num_rows="dynamic"
                     edited_df_zone_processed["Records"] = 0.0

                if "Columns" in edited_df_zone_processed.columns:
                    edited_df_zone_processed["Columns"] = edited_df_zone_processed["Columns"].apply(lambda x: float(x) if x is not None and x != '' else 0.0)
                else:
                    edited_df_zone_processed["Columns"] = 0.0
                
                if "Table Name" in edited_df_zone_processed.columns:
                    edited_df_zone_processed["Table Name"] = edited_df_zone_processed["Table Name"].apply(lambda x: x or "")
                else:
                    edited_df_zone_processed["Table Name"] = ""

                # Filter out rows that are effectively empty (all primary keys blank)
                # It's important to do this AFTER sanitization
                original_row_count = len(edited_df_zone_processed)
                edited_df_zone_processed = edited_df_zone_processed[
                    (edited_df_zone_processed["Table Name"] != "") |
                    (edited_df_zone_processed["Records"] != 0) |
                    (edited_df_zone_processed["Columns"] != 0)
                ]
                
                # If rows were removed by filtering, we need to ensure unique IDs are regenerated
                # if 'id' was used internally
                if len(edited_df_zone_processed) < original_row_count:
                    # Regenerate IDs to avoid stale ones if rows were deleted
                    edited_df_zone_processed['id'] = [f"{zone_name}_table_{i}" for i in range(len(edited_df_zone_processed))]
                elif 'id' not in edited_df_zone_processed.columns:
                     # For newly added rows, assign a new ID
                    edited_df_zone_processed['id'] = [f"{zone_name}_table_{i}" for i in range(len(edited_df_zone_processed))]


                # Convert to a consistent dictionary format for comparison and storage
                # Ensure the column order for comparison
                cols_for_comparison = ["Table Name", "Records", "Columns"]
                

                # Re-create df_zone_initial but with normalized values and only relevant columns for comparison
                current_df_for_comparison = pd.DataFrame(normalized_current_data)[cols_for_comparison].reset_index(drop=True)
                
                # Also ensure edited_df_zone_processed only contains the columns we care about for comparison
                updated_df_for_comparison = edited_df_zone_processed[cols_for_comparison].reset_index(drop=True)

                # Now, perform the robust comparison using .equals()
                if not updated_df_for_comparison.equals(current_df_for_comparison):
                    # Only update session state if a real change is detected
                    # Store the sanitized_updated_zone_data back as a list of dicts.
                    # Ensure 'id' column is handled for storage if present in edited_df_zone_processed
                    st.session_state.s3_table_based[zone_name] = edited_df_zone_processed.to_dict(orient='records')
                    st.rerun()

    st.divider()

    with st.container(border=True):
        st.subheader("Total S3 Storage Cost")
        st.markdown(f"<h2 style='text-align: center;'>${total_s3_cost:,.2f}/month</h2>", unsafe_allow_html=True)
        #st.caption(f"Calculated using {st.session_state.s3_calc_method} method")
        


def render_sql_warehouse_tab(total_sql_cost):
    """Renders the SQL Warehouse tab UI with a total cost summary."""
    c1, c2 = st.columns([4, 1])
    with c1:
        st.header("Databricks SQL Warehouse Costs")
    with c2: # Explicitly place the button in the second column
        if st.button("＋ Add SQL Warehouse", key="add_sql_warehouse_button_top"):
            new_id = f"warehouse_{len(st.session_state.sql_warehouses)}"
            st.session_state.sql_warehouses.append({
                "id": new_id,
                "name": "New Warehouse",
                "size": SQL_WAREHOUSE_SIZES[0],
                "type": SQL_WAREHOUSE_TYPES[0],
                "hours_per_day": 8,
                "days_per_month": 22,
                "auto_suspend": True,
                "suspend_after": 10
            })
            st.rerun() # Rerun immediately after state change

    st.markdown("---") # Add a separator after the button if desired

    if not st.session_state.sql_warehouses: # Handle case where no warehouses exist after deletion
        st.info("No SQL Warehouses configured. Click 'Add SQL Warehouse' to start.")
        st.divider() # Add a divider if you want it here
        return

    for i, warehouse in enumerate(st.session_state.sql_warehouses):
        with st.container(border=True):
            sql_details_col, actions_col = st.columns([4, 1])

            with sql_details_col:
                st.subheader(warehouse["name"])
                size_key = warehouse["size"].split(" - ")[0]
                dbt_per_hr = SQL_WAREHOUSE_PRICING.get(size_key, {}).get("dbt_per_hr", 0)
                st.caption(f"{dbt_per_hr} DBUs • {warehouse['hours_per_day']}h/day • {warehouse['days_per_month']} days/month")

            with actions_col:
                # Add a delete button for each warehouse
                if st.button("🗑️ Delete", key=f"delete_sql_warehouse_{i}"):
                    st.session_state.sql_warehouses.pop(i)
                    st.rerun()


            st.markdown("---") # Separator within each warehouse container

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                warehouse["name"] = st.text_input("Name", value=warehouse["name"], key=f"sql_name_{i}")
            with c2:
                current_type = warehouse.get("type", SQL_WAREHOUSE_TYPES[0]) # Use .get() for safety
                # Determine the initial index for the selectbox
                try:
                    default_index = SQL_WAREHOUSE_TYPES.index(current_type)
                except ValueError:
                    # If current_type is not in the list (e.g., "Standard" from old session state)
                    # default to the first available type ("Classic")
                    default_index = 0 
                
                warehouse["type"] = st.selectbox("Type", SQL_WAREHOUSE_TYPES, index=default_index, key=f"sql_type_{i}")
            with c3:
                warehouse["size"] = st.selectbox("Size", SQL_WAREHOUSE_SIZES, index=SQL_WAREHOUSE_SIZES.index(warehouse["size"]), key=f"sql_size_{i}")
            with c4:
                warehouse["hours_per_day"] = st.number_input("Hours per Day", min_value=0, max_value=24, value=warehouse["hours_per_day"], key=f"sql_hours_{i}")
            with c5:
                warehouse["days_per_month"] = st.number_input("Days per Month", min_value=0, max_value=31, value=warehouse["days_per_month"], key=f"sql_days_{i}")
            # st.markdown("**Auto-Suspend Configuration**")
            # warehouse["auto_suspend"] = st.checkbox("Enable Auto-Suspend", value=warehouse["auto_suspend"], key=f"sql_suspend_{i}")
            # if warehouse["auto_suspend"]:
            #     warehouse["suspend_after"] = st.number_input("Suspend After (minutes)", min_value=0, value=warehouse["suspend_after"], key=f"sql_suspend_after_{i}")


    with st.container(border=True):
        st.subheader("Total SQL Warehouse Cost")
        warehouse_count = len(st.session_state.sql_warehouses)
        st.markdown(f"<h2 style='text-align: center;'>${total_sql_cost:,.2f}/month</h2>", unsafe_allow_html=True)
        st.caption(f"{warehouse_count} warehouse(s) configured")

def render_configuration_guide():
    """Renders the configuration guide expander at the bottom of a tab."""
    with st.expander("ℹ️ Configuration Guide", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            **Photon Engine** Adds 20% to DBU cost but provides significant performance improvements for analytical workloads.
            """)
            st.markdown("""
            **DBU Rates (Auto-calculated)** Bronze: $0.15, Silver: $0.30, Gold: $0.60 per DBU hour (before Photon premium).
            """)
        with c2:
            st.markdown("""
            **Spot Instances** Provides ~70% cost savings on EC2 compute but instances may be interrupted.
            """)
            st.markdown("""
            **Instance Families** Choose instance types based on workload: General Purpose (`m5`), Compute Optimized (`c5`), Memory Optimized (`r5`/`r5d`).
            """)

def render_export_button(calculated_dbx_data, s3_calc_method, s3_direct_config, s3_table_based_config, sql_warehouses_config):
    """
    Renders the Excel export button. This function is called from main.py.
    It orchestrates the data collection from session state and passes it
    to the excel_exporter for file generation.
    """
    # Generate Excel file content
    excel_file_bytes = generate_consolidated_excel_export(
        calculated_dbx_data,
        s3_calc_method,
        s3_direct_config,
        s3_table_based_config,
        sql_warehouses_config
    )

    # Export Button (visible)
    st.download_button(
        label="📊 Export Excel",
        data=excel_file_bytes,
        file_name="cloud_cost_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="export_consolidated_excel_button"
    )
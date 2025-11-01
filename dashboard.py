import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(
    page_title="AudioPine Advanced Dashboard",
    page_icon="🔊",
    layout="wide"
)

# --- PASSWORD PROTECTION ---
def check_password():
    """Returns `True` if the user entered the correct password."""
    def password_entered():
        if "password" in st.session_state and st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# --- DATA LOADING AND CLEANING ---
@st.cache_data
def load_data_from_gsheet():
    SHEET_ID = "1fW6Mx6pbh7IW0Ix4wK8oG9E8Wc0f1N3f"
    INVENTORY_GID = "436105721"
    SALES_GID = "11827407"
    inventory_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INVENTORY_GID}"
    sales_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SALES_GID}"
    df_inventory = pd.read_csv(inventory_url)
    df_sales = pd.read_csv(sales_url)
    
    REQUIRED_INVENTORY_COLS = ["Item ID", "Category", "Product Name / Model", "Supplier Price (Ksh)", "Selling Price (Ksh)", "Balance Stock"]
    REQUIRED_SALES_COLS = ["Item ID / Product", "Qty Sold", "Date", "Profit", "Payment Method", "Installer/Referral"]
    if not all(col in df_inventory.columns for col in REQUIRED_INVENTORY_COLS):
        raise ValueError("Inventory sheet is missing required columns.")
    if not all(col in df_sales.columns for col in REQUIRED_SALES_COLS):
        raise ValueError("Sales sheet is missing required columns.")

    df_sales.rename(columns={'Item ID / Product': 'Item ID', 'Qty Sold': 'Quantity Sold', 'Date': 'Sale Date'}, inplace=True)
    df_sales['Sale Date'] = pd.to_datetime(df_sales['Sale Date'], errors='coerce')
    df_sales['Profit'] = pd.to_numeric(df_sales['Profit'], errors='coerce').fillna(0)
    df_sales['Quantity Sold'] = pd.to_numeric(df_sales['Quantity Sold'], errors='coerce').fillna(0)
    numeric_inventory_cols = ["Supplier Price (Ksh)", "Selling Price (Ksh)", "Balance Stock"]
    for col in numeric_inventory_cols:
        df_inventory[col] = pd.to_numeric(df_inventory[col], errors='coerce').fillna(0)
    
    df_sales.dropna(subset=['Sale Date', 'Item ID'], inplace=True)
    df_inventory.dropna(subset=['Item ID'], inplace=True)
    
    df_inventory['Item ID'] = df_inventory['Item ID'].astype(str).str.strip()
    df_sales['Item ID'] = df_sales['Item ID'].astype(str).str.strip()
    
    df_merged = pd.merge(df_sales, df_inventory, on="Item ID", how="left")
    df_merged.rename(columns={'Total Sale': 'Revenue'}, inplace=True)
    df_merged['Revenue'] = pd.to_numeric(df_merged['Revenue'], errors='coerce').fillna(0)
    
    df_merged['Category'] = df_merged['Category'].fillna('Unknown').str.strip()
    df_merged['Payment Method'] = df_merged['Payment Method'].str.strip()
    df_merged['Installer/Referral'] = df_merged['Installer/Referral'].str.strip()
    
    return df_inventory, df_merged

# --- MAIN APP LOGIC WRAPPED IN PASSWORD CHECK ---
if check_password():
    try:
        df_inventory, df_sales_merged = load_data_from_gsheet()
    except Exception as e:
        st.error(f"❌ An error occurred during data loading: {e}")
        st.stop()

    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Dashboard Filters")
    min_date = df_sales_merged["Sale Date"].min().date()
    max_date = df_sales_merged["Sale Date"].max().date()
    start_date, end_date = st.sidebar.date_input("Date Range:", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    
    df_date_filtered = df_sales_merged[(df_sales_merged["Sale Date"].dt.date >= start_date) & (df_sales_merged["Sale Date"].dt.date <= end_date)]
    
    # --- THIS IS THE CORRECTED LINE ---
    category = st.sidebar.multiselect("Category:", options=df_date_filtered["Category"].unique(), default=df_date_filtered["Category"].unique())
    df_cat_filtered = df_date_filtered[df_date_filtered["Category"].isin(category)]
    
    # --- THIS IS THE SECOND CORRECTED LINE ---
    product_name = st.sidebar.multiselect("Product Name:", options=df_cat_filtered["Product Name / Model"].unique(), default=df_cat_filtered["Product Name / Model"].unique())
    df_filtered = df_cat_filtered[df_cat_filtered["Product Name / Model"].isin(product_name)]
    
    if df_filtered.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    # --- DASHBOARD UI WITH TABS ---
    st.title("🔊 AudioPine Advanced Sales & Inventory Dashboard")
    st.markdown(f"_Displaying data from **{start_date.strftime('%b %d, %Y')}** to **{end_date.strftime('%b %d, %Y')}**_")
    
    tab1, tab2, tab3 = st.tabs(["📈 Sales Overview", "📦 Product & Customer Insights", "🏭 Inventory Management"])

    with tab1:
        total_revenue = int(df_filtered["Revenue"].sum())
        total_profit = int(df_filtered["Profit"].sum())
        total_items_sold = int(df_filtered["Quantity Sold"].sum())
        avg_profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        st.markdown("### Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Revenue", f"{total_revenue:,.0f} Ksh")
        col2.metric("Total Profit", f"{total_profit:,.0f} Ksh")
        col3.metric("Items Sold", f"{total_items_sold}")
        col4.metric("Avg. Profit Margin", f"{avg_profit_margin:.1f}%")
        st.markdown("---")
        
        st.subheader("Weekly Profit Trend")
        weekly_profit = df_filtered.set_index('Sale Date').resample('W-Mon')['Profit'].sum()
        st.line_chart(weekly_profit)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Profit by Installer/Referral")
            profit_by_installer = df_filtered.groupby("Installer/Referral")["Profit"].sum().sort_values(ascending=True)
            st.bar_chart(profit_by_installer, horizontal=True)
        with col2:
            st.subheader("Profit by Payment Method")
            profit_by_payment = df_filtered.groupby("Payment Method")["Profit"].sum()
            st.bar_chart(profit_by_payment)

    with tab2:
        st.markdown("### Product & Customer Performance")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Top 5 Products by Profit")
            st.dataframe(df_filtered.groupby("Product Name / Model")["Profit"].sum().nlargest(5).sort_values(ascending=False))
        with col2:
            st.subheader("Top 5 Products by Quantity Sold")
            st.dataframe(df_filtered.groupby("Product Name / Model")["Quantity Sold"].sum().nlargest(5).sort_values(ascending=False))
            
        st.markdown("---")
        st.subheader("Top 10 Customers by Profit")
        st.dataframe(df_filtered.groupby("Customer Name")["Profit"].sum().nlargest(10).sort_values(ascending=False))

    with tab3:
        st.markdown("### Inventory Insights")
        total_stock_value_cost = int((df_inventory['Balance Stock'] * df_inventory['Supplier Price (Ksh)']).sum())
        total_stock_value_retail = int((df_inventory['Balance Stock'] * df_inventory['Selling Price (Ksh)']).sum())
        
        col1, col2 = st.columns(2)
        col1.metric("Total Stock Value (at Cost)", f"{total_stock_value_cost:,.0f} Ksh")
        col2.metric("Total Stock Value (at Retail)", f"{total_stock_value_retail:,.0f} Ksh")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Low Stock Items")
            low_stock_threshold = 5
            low_stock_items = df_inventory[df_inventory["Balance Stock"] <= low_stock_threshold]
            st.dataframe(low_stock_items[["Item ID", "Product Name / Model", "Balance Stock"]])
        with col2:
            st.subheader("Slow-Moving Stock")
            last_sale_dates = df_sales_merged.groupby('Item ID')['Sale Date'].max().reset_index()
            last_sale_dates.rename(columns={'Sale Date': 'Last Sale Date'}, inplace=True)
            inventory_analysis = pd.merge(df_inventory, last_sale_dates, on='Item ID', how='left')
            latest_date_in_data = df_sales_merged['Sale Date'].max()
            inventory_analysis['Days Since Last Sale'] = (latest_date_in_data - inventory_analysis['Last Sale Date']).dt.days
            inventory_analysis['Days Since Last Sale'] = inventory_analysis['Days Since Last Sale'].fillna('Never Sold')
            slow_moving = inventory_analysis[
                (pd.to_numeric(inventory_analysis['Days Since Last Sale'], errors='coerce') > 90) |
                (inventory_analysis['Days Since Last Sale'] == 'Never Sold')
            ]
            st.dataframe(slow_moving[['Item ID', 'Product Name / Model', 'Balance Stock', 'Days Since Last Sale']])
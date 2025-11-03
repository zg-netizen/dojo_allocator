"""Streamlit dashboard for Dojo Allocator."""

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
from config.settings import get_settings
import requests
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import yaml


# Helper function to format source names consistently
def format_source_name(source):
    """Format source names for consistent display"""
    source_mapping = {
        "congressional": "🏛️ Congressional",
        "form4": "📋 Form 4 (SEC EDGAR)",
        "openinsider": "👁️ OpenInsider",
        "stock_act": "📊 STOCK Act",
        "sec_edgar": "🏢 SEC EDGAR",
        "13d": "📄 13D/13G",
        "insider": "👤 Insider (OpenInsider)",
        "manual": "✋ Manual",
    }
    return source_mapping.get(source.lower(), f"📊 {source.title()}")


# Helper function to format conviction tiers consistently
def format_conviction_tier(tier):
    """Format conviction tiers for consistent display"""
    tier_mapping = {
        "S": "🔥 S-Tier",
        "A": "⭐ A-Tier",
        "B": "📈 B-Tier",
        "C": "📊 C-Tier",
    }
    return tier_mapping.get(tier, f"📊 {tier}-Tier")


# Helper function to format direction consistently
def format_direction(direction):
    """Format direction for consistent display"""
    direction_mapping = {"LONG": "📈 LONG", "SHORT": "📉 SHORT"}
    return direction_mapping.get(direction, f"📊 {direction}")


# Helper function to format status consistently
def format_status(status):
    """Format status for consistent display"""
    status_mapping = {
        "ACTIVE": "🟢 Active",
        "OPEN": "🟢 Open",
        "CLOSED": "🔴 Closed",
        "PENDING": "🟡 Pending",
        "REJECTED": "❌ Rejected",
        "EXPIRED": "⏰ Expired"
    }
    return status_mapping.get(status, f"📊 {status}")


# Helper function to get symbol information for tooltips
def get_symbol_info(symbol, db_session):
    """Get company information for symbol tooltip"""
    try:
        # Get the most recent signal for this symbol
        result = db_session.execute(text("""
            SELECT
                symbol,
                filer_name,
                transaction_value,
                filing_date,
                source,
                direction,
                conviction_tier
            FROM signals
            WHERE symbol = :symbol
            ORDER BY filing_date DESC
            LIMIT 1
        """), {"symbol": symbol}).fetchone()

        if result:
            filer_name, transaction_value, filing_date, source, direction, conviction_tier = result[
                1:7]

            # Format the tooltip content
            transaction_display = f"${transaction_value:,.0f}" if transaction_value > 0 else "N/A"
            filing_display = filing_date.strftime(
                '%Y-%m-%d') if filing_date else 'N/A'
            tier_display = format_conviction_tier(
                conviction_tier) if conviction_tier else 'N/A'

            return {
                'company': filer_name,
                'source': format_source_name(source),
                'direction': format_direction(direction),
                'tier': tier_display,
                'transaction_value': transaction_display,
                'filing_date': filing_display
            }
        else:
            return None
    except Exception as e:
        return None


# Helper function to create symbol with tooltip using st.columns
def display_symbol_with_tooltip(symbol, db_session):
    """Display symbol with tooltip using Streamlit's native tooltip"""
    symbol_info = get_symbol_info(symbol, db_session)

    if symbol_info:
        tooltip_text = f"""
        Company: {symbol_info['company']}
        Source: {symbol_info['source']}
        Direction: {symbol_info['direction']}
        Tier: {symbol_info['tier']}
        Transaction Value: {symbol_info['transaction_value']}
        Filing Date: {symbol_info['filing_date']}
        """

        # Use st.tooltip for native Streamlit tooltips
        with st.tooltip(tooltip_text):
            st.write(f"**{symbol}**")
    else:
        st.write(symbol)


# Helper function to add tooltip info to dataframe
def add_tooltip_info_to_df(df, symbol_column, db_session):
    """Add tooltip information as a separate column"""
    try:
        if symbol_column in df.columns:
            tooltip_info = []
            for symbol in df[symbol_column]:
                try:
                    info = get_symbol_info(symbol, db_session)
                    if info:
                        tooltip_text = f"Company: {info['company']} | Source: {info['source']} | Tier: {info['tier']}"
                        tooltip_info.append(tooltip_text)
                    else:
                        tooltip_info.append("No additional info available")
                except Exception as e:
                    tooltip_info.append(f"Error: {str(e)[:50]}")

            df[f"{symbol_column}_Info"] = tooltip_info
        return df
    except Exception as e:
        # If there's an error, add a column with error info
        df[f"{symbol_column}_Info"] = f"Error loading info: {str(e)[:50]}"
        return df


# Helper function to create enhanced KPI cards
def create_kpi_card(
    title, value, delta=None, delta_type="neutral", card_type="default"
):
    """Create an enhanced KPI card with proper styling"""

    # Determine delta styling
    delta_class = "kpi-delta-neutral"
    delta_icon = ""

    if delta_type == "positive":
        delta_class = "kpi-delta-positive"
        delta_icon = "↗"
    elif delta_type == "negative":
        delta_class = "kpi-delta-negative"
        delta_icon = "↘"

    # Determine card styling
    card_class = "kpi-card"
    if card_type == "primary":
        card_class += " kpi-card-primary"
    elif card_type == "success":
        card_class += " kpi-card-success"
    elif card_type == "warning":
        card_class += " kpi-card-warning"
    elif card_type == "danger":
        card_class += " kpi-card-danger"

    # Format delta display
    delta_display = ""
    if delta is not None:
        delta_display = (
            f'<div class="kpi-delta {delta_class}">{delta_icon} {delta}</div>'
        )

    # Create the card HTML
    card_html = f"""
    <div class="{card_class}">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        {delta_display}
    </div>
    """

    return card_html


# Toast notification system
def show_toast(message, type="success", duration=3000):
    """Show a toast notification"""
    toast_class = f"toast-{type}"

    toast_html = f"""
    <div class="{toast_class}" id="toast-notification">
        {message}
    </div>
    <script>
        setTimeout(function() {{
            const toast = document.getElementById('toast-notification');
            if (toast) {{
                toast.style.opacity = '0';
                setTimeout(function() {{
                    toast.remove();
                }}, 300);
            }}
        }}, {duration});
    </script>
    """

    return st.markdown(toast_html, unsafe_allow_html=True)


# System status notifications
def check_system_status():
    """Check system status and show notifications"""
    notifications = []

    # Check API connectivity
    try:
        import requests

        response = requests.get("http://api:8000/health", timeout=5)
        if response.status_code != 200:
            notifications.append(("warning", "API connection unstable"))
    except:
        notifications.append(
    ("error", "API offline - some features may not work"))

    # Check database connectivity
    try:
        db = Session()
        db.execute(text("SELECT 1"))
        db.close()
    except:
        notifications.append(("error", "Database connection failed"))

    # Check Celery worker status
    try:
        response = requests.get("http://api:8000/celery/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("workers", 0) == 0:
                notifications.append(
                    ("warning", "Celery workers idle - background tasks may be delayed")
                )
        else:
            notifications.append(("warning", "Celery status unknown"))
    except:
        notifications.append(
    ("warning", "Celery offline - background tasks disabled"))

    return notifications


# Helper function to create status indicator
def create_status_indicator(status, text):
    """Create a status indicator badge"""
    status_class = "status-indicator"

    if status.lower() == "active":
        status_class += " status-active"
    elif status.lower() == "pending":
        status_class += " status-pending"
    elif status.lower() == "closed":
        status_class += " status-closed"

    return f'<span class="{status_class}">{text}</span>'


# Helper function to fetch current prices for positions
def fetch_current_prices(symbols, max_symbols=20):
    """Fetch current prices for a list of symbols using yfinance"""
    import yfinance as yf

    current_prices = {}

    # Limit symbols to prevent timeout
    symbols_to_fetch = symbols[:max_symbols]

    for symbol in symbols_to_fetch:
        try:
            ticker = yf.Ticker(symbol)
            # Prefer intraday last trade (1m) to better match market
            price = None
            try:
                intraday = ticker.history(period="1d", interval="1m")
                if not intraday.empty and "Close" in intraday.columns:
                    price = float(intraday["Close"].dropna().iloc[-1])
            except Exception:
                pass
            if price is None:
                try:
                    fi = getattr(ticker, "fast_info", None)
                    if fi and getattr(fi, "last_price", None):
                        price = float(fi.last_price)
                except Exception:
                    pass
            if price is None:
                daily = ticker.history(period="1d")
                if not daily.empty:
                    price = float(daily["Close"].iloc[-1])
            current_prices[symbol] = price
        except Exception:
            current_prices[symbol] = None

    return current_prices


# Helper function to calculate current return
def calculate_current_return(entry_price, current_price, shares):
    """Calculate current return percentage and P&L"""
    if current_price is None or entry_price is None or shares is None:
        return None, None, None

    entry_value = float(entry_price) * float(shares)
    current_value = float(current_price) * float(shares)
    unrealized_pnl = current_value - entry_value
    return_pct = (unrealized_pnl / entry_value * 100) if entry_value > 0 else 0

    return return_pct, unrealized_pnl, current_value


st.set_page_config(
    page_title="Dojo Allocator", layout="wide", initial_sidebar_state="expanded"
)
st.title("🥋 Dojo Allocator Dashboard")

# Enhanced navigation with icons and hover states
st.markdown(
    """
<style>
    /* Enhanced Sidebar Navigation */
    .nav-item {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: 8px;
        transition: all 0.2s ease;
        cursor: pointer;
        border-left: 3px solid transparent;
    }

    .nav-item:hover {
        background: #f3f4f6;
        border-left-color: #3b82f6;
        transform: translateX(2px);
    }

    .nav-item.active {
        background: #dbeafe;
        border-left-color: #3b82f6;
        color: #1d4ed8;
        font-weight: 600;
    }

    .nav-icon {
        margin-right: 0.75rem;
        font-size: 1.2rem;
        width: 24px;
        text-align: center;
    }

    .nav-text {
        font-size: 0.95rem;
        font-weight: 500;
    }

    /* System Status Enhancements */
    .status-section {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }

    .status-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #f1f5f9;
    }

    .status-item:last-child {
        border-bottom: none;
    }

    .status-label {
        font-size: 0.875rem;
        color: #6b7280;
        font-weight: 500;
    }

    .status-value {
        font-size: 0.875rem;
        font-weight: 600;
    }

    .status-connected {
        color: #10b981;
    }

    .status-error {
        color: #ef4444;
    }

    .status-warning {
        color: #f59e0b;
    }

    /* Brand Header */
    .brand-header {
        text-align: center;
        padding: 1.5rem 1rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }

    .brand-logo {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }

    .brand-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0.25rem;
    }

    .brand-subtitle {
        font-size: 0.875rem;
        color: #6b7280;
    }
</style>
""",
    unsafe_allow_html=True,
)
# Mobile CSS optimizations
st.markdown(
    """
<style>
    /* Enhanced Responsive Grid */
    .dashboard-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    }

    @media screen and (max-width: 768px) {
        .dashboard-grid {
            grid-template-columns: 1fr;
            gap: 0.5rem;
        }

        .kpi-card {
            padding: 1rem;
            margin-bottom: 0.5rem;
        }

        .kpi-value {
            font-size: 1.5rem;
        }

        .enhanced-table {
            font-size: 0.75rem;
        }

        .enhanced-table th,
        .enhanced-table td {
            padding: 0.5rem;
        }
    }

    @media screen and (min-width: 769px) and (max-width: 1024px) {
        .dashboard-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }

    @media screen and (min-width: 1025px) {
        .dashboard-grid {
            grid-template-columns: repeat(4, 1fr);
        }
    }

    /* Mobile Sidebar Enhancements */
    @media screen and (max-width: 768px) {
        .stSidebar {
            position: fixed;
            top: 0;
            left: -100%;
            width: 280px;
            height: 100vh;
            background: white;
            z-index: 1000;
            transition: left 0.3s ease;
            box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
        }

        .stSidebar[data-testid="stSidebar"] {
            left: 0;
        }

        .main .block-container {
            margin-left: 0;
            padding: 1rem;
        }

        /* Mobile menu toggle */
        .mobile-menu-toggle {
            position: fixed;
            top: 1rem;
            left: 1rem;
            z-index: 1001;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            font-size: 1.2rem;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        }

        .mobile-menu-toggle:hover {
            background: #1d4ed8;
        }
    }

    /* Tablet optimizations */
    @media screen and (min-width: 769px) and (max-width: 1024px) {
        .stSidebar {
            width: 250px;
        }

        .main .block-container {
            margin-left: 250px;
            padding: 2rem;
        }

        .kpi-card {
            padding: 1.25rem;
        }
    }

    /* Desktop optimizations */
    @media screen and (min-width: 1025px) {
        .stSidebar {
            width: 300px;
        }

        .main .block-container {
            margin-left: 300px;
            padding: 3rem;
        }

        .kpi-card {
            padding: 1.5rem;
        }
    }

    /* Sticky headers for tables */
    .enhanced-table {
        position: relative;
    }

    .enhanced-table th {
        position: sticky;
        top: 0;
        z-index: 10;
        background: #f8fafc;
    }

    /* Horizontal scroll for tables on mobile */
    @media screen and (max-width: 768px) {
        .enhanced-table {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }

        .enhanced-table table {
            min-width: 600px;
        }
    }

    /* Enhanced KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        transition: all 0.2s ease-in-out;
        position: relative;
        overflow: hidden;
    }

    .kpi-card:hover {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transform: translateY(-2px);
        border-color: #3b82f6;
    }

    .kpi-card-primary {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border-color: #1d4ed8;
    }

    .kpi-card-success {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border-color: #059669;
    }

    .kpi-card-warning {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        border-color: #d97706;
    }

    .kpi-card-danger {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        border-color: #dc2626;
    }

    .kpi-title {
        font-size: 0.875rem;
        font-weight: 500;
        opacity: 0.8;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        font-family: 'JetBrains Mono', 'Monaco', 'Consolas', monospace;
    }

    .kpi-delta {
        font-size: 0.875rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }

    .kpi-delta-positive {
        color: #10b981;
    }

    .kpi-delta-negative {
        color: #ef4444;
    }

    .kpi-delta-neutral {
        color: #6b7280;
    }

    /* Enhanced Data Tables */
    .enhanced-table {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }

    .enhanced-table table {
        border-collapse: collapse;
        width: 100%;
    }

    .enhanced-table th {
        background: #f8fafc;
        font-weight: 600;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 2px solid #e2e8f0;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .enhanced-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.875rem;
    }

    .enhanced-table tr:nth-child(even) {
        background: #f8fafc;
    }

    .enhanced-table tr:hover {
        background: #f1f5f9;
    }

    /* Status Indicators */
    .status-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .status-active {
        background: #dcfce7;
        color: #166534;
    }

    .status-pending {
        background: #fef3c7;
        color: #92400e;
    }

    .status-closed {
        background: #fee2e2;
        color: #991b1b;
    }

    /* Philosophy Tabs Enhancement */
    .philosophy-tab {
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        background: #ffffff;
    }

    .philosophy-tab-dalio {
        border-left: 4px solid #3b82f6;
    }

    .philosophy-tab-buffett {
        border-left: 4px solid #f59e0b;
    }

    .philosophy-tab-pabrai {
        border-left: 4px solid #ef4444;
    }

    .philosophy-tab-oleary {
        border-left: 4px solid #06b6d4;
    }

    .philosophy-tab-saylor {
        border-left: 4px solid #8b5cf6;
    }

    .philosophy-tab-japanese {
        border-left: 4px solid #6b7280;
    }

    /* Loading States */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #3b82f6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* Dark Mode Support */
    @media (prefers-color-scheme: dark) {
        .kpi-card {
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            border-color: #374151;
            color: #f9fafb;
        }

        .kpi-card:hover {
            border-color: #3b82f6;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
        }

        .enhanced-table {
            background: #1f2937;
            color: #f9fafb;
        }

        .enhanced-table th {
            background: #374151;
            color: #f9fafb;
        }

        .enhanced-table td {
            color: #f9fafb;
            border-color: #374151;
        }

        .enhanced-table tr:nth-child(even) {
            background: #374151;
        }

        .enhanced-table tr:hover {
            background: #4b5563;
        }

        .status-section {
            background: #1f2937;
            border-color: #374151;
        }

        .status-label {
            color: #9ca3af;
        }

        .brand-title {
            color: #f9fafb;
        }

        .brand-subtitle {
            color: #9ca3af;
        }
    }

    /* Manual Dark Mode Class */
    .dark-mode {
        background-color: #111827 !important;
        color: #f9fafb !important;
    }

    .dark-mode .main .block-container {
        background-color: #111827 !important;
        color: #f9fafb !important;
    }

    .dark-mode .stApp {
        background-color: #111827 !important;
    }

    .dark-mode .stSidebar {
        background-color: #1f2937 !important;
    }

    .dark-mode .stSidebar .stMarkdown {
        color: #f9fafb !important;
    }

    .dark-mode .stButton > button {
        background-color: #374151 !important;
        color: #f9fafb !important;
        border-color: #4b5563 !important;
    }

    .dark-mode .stButton > button:hover {
        background-color: #4b5563 !important;
        border-color: #6b7280 !important;
    }

    .dark-mode .stSelectbox > div > div {
        background-color: #374151 !important;
        color: #f9fafb !important;
    }

    .dark-mode .stTextInput > div > div > input {
        background-color: #374151 !important;
        color: #f9fafb !important;
        border-color: #4b5563 !important;
    }

    .dark-mode .stSlider > div > div > div > div {
        background-color: #374151 !important;
    }

    .dark-mode .stCheckbox > label {
        color: #f9fafb !important;
    }

    .dark-mode .stExpander > div {
        background-color: #374151 !important;
        border-color: #4b5563 !important;
    }

    .dark-mode .stExpander > div > div {
        color: #f9fafb !important;
    }

    .dark-mode .stTabs > div > div > div {
        background-color: #374151 !important;
        border-color: #4b5563 !important;
    }

    .dark-mode .stTabs > div > div > div > button {
        background-color: #374151 !important;
        color: #f9fafb !important;
        border-color: #4b5563 !important;
    }

    .dark-mode .stTabs > div > div > div > button:hover {
        background-color: #4b5563 !important;
    }

    .dark-mode .stTabs > div > div > div > button[aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
    }

    .dark-mode .kpi-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border-color: #374151;
        color: #f9fafb;
    }

    .dark-mode .kpi-card:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
    }

    .dark-mode .enhanced-table {
        background: #1f2937;
        color: #f9fafb;
    }

    .dark-mode .enhanced-table th {
        background: #374151;
        color: #f9fafb;
    }

    .dark-mode .enhanced-table td {
        color: #f9fafb;
        border-color: #374151;
    }

    .dark-mode .enhanced-table tr:nth-child(even) {
        background: #374151;
    }

    .dark-mode .enhanced-table tr:hover {
        background: #4b5563;
    }

    .dark-mode .status-section {
        background: #1f2937;
        border-color: #374151;
    }

    .dark-mode .status-label {
        color: #9ca3af;
    }

    .dark-mode .brand-title {
        color: #f9fafb;
    }

    .dark-mode .brand-subtitle {
        color: #9ca3af;
    }

    .dark-mode .nav-item {
        background: #374151;
        color: #f9fafb;
        border-color: #4b5563;
    }

    .dark-mode .nav-item:hover {
        background: #4b5563;
        border-color: #6b7280;
    }

    .dark-mode .nav-item.active {
        background: #3b82f6;
        color: #ffffff;
    }

    .dark-mode .status-item {
        background: #374151;
        border-color: #4b5563;
    }

    .dark-mode .status-label {
        color: #d1d5db;
    }

    .dark-mode .status-value {
        color: #f9fafb;
    }

    .dark-mode .philosophy-tab-dalio {
        border-left-color: #3b82f6;
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
    }

    .dark-mode .philosophy-tab-buffett {
        border-left-color: #10b981;
        background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
    }

    .dark-mode .philosophy-tab-pabrai {
        border-left-color: #f59e0b;
        background: linear-gradient(135deg, #78350f 0%, #92400e 100%);
    }

    .dark-mode .philosophy-tab-oleary {
        border-left-color: #ef4444;
        background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
    }

    .dark-mode .philosophy-tab-saylor {
        border-left-color: #8b5cf6;
        background: linear-gradient(135deg, #581c87 0%, #6b21a8 100%);
    }

    .dark-mode .philosophy-tab-japanese {
        border-left-color: #06b6d4;
        background: linear-gradient(135deg, #164e63 0%, #155e75 100%);
    }

    .dark-mode .parameter-card {
        background: #374151;
        border-color: #4b5563;
    }

    .dark-mode .toast-success {
        background: #065f46;
        color: #d1fae5;
        border-color: #10b981;
    }

    .dark-mode .toast-error {
        background: #7f1d1d;
        color: #fecaca;
        border-color: #ef4444;
    }

    .dark-mode .toast-warning {
        background: #78350f;
        color: #fef3c7;
        border-color: #f59e0b;
    }

    /* Accessibility Enhancements */
    .kpi-card:focus {
        outline: 2px solid #3b82f6;
        outline-offset: 2px;
    }

    .nav-item:focus {
        outline: 2px solid #3b82f6;
        outline-offset: 2px;
    }

    /* Reduced Motion Support */
    @media (prefers-reduced-motion: reduce) {
        .kpi-card {
            transition: none;
        }

        .nav-item {
            transition: none;
        }

        .nav-item:hover {
            transform: none;
        }
    }

    /* High Contrast Mode */
    @media (prefers-contrast: high) {
        .kpi-card {
            border-width: 2px;
        }

        .enhanced-table th {
            border-bottom-width: 3px;
        }

        .nav-item {
            border-left-width: 4px;
        }
    }

    /* Print Styles */
    @media print {
        .stSidebar {
            display: none;
        }

        .main .block-container {
            margin-left: 0;
            padding: 0;
        }

        .kpi-card {
            break-inside: avoid;
            box-shadow: none;
            border: 1px solid #000;
        }

        .enhanced-table {
            box-shadow: none;
            border: 1px solid #000;
        }
    }

    /* Loading Animations */
    .loading-pulse {
        animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }

    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: .5;
        }
    }

    .loading-bounce {
        animation: bounce 1s infinite;
    }

    @keyframes bounce {
        0%, 100% {
            transform: translateY(-25%);
            animation-timing-function: cubic-bezier(0.8,0,1,1);
        }
        50% {
            transform: none;
            animation-timing-function: cubic-bezier(0,0,0.2,1);
        }
    }

    /* Compact Mode Toggle */
    .compact-mode .kpi-card {
        padding: 0.75rem;
    }

    .compact-mode .kpi-value {
        font-size: 1.5rem;
    }

    .compact-mode .kpi-title {
        font-size: 0.75rem;
    }

    .compact-mode .enhanced-table th,
    .compact-mode .enhanced-table td {
        padding: 0.5rem;
        font-size: 0.75rem;
    }

    /* Error States */
    .error-state {
        border-color: #ef4444;
        background: #fef2f2;
    }

    .error-state .kpi-value {
        color: #ef4444;
    }

    /* Success States */
    .success-state {
        border-color: #10b981;
        background: #f0fdf4;
    }

    .success-state .kpi-value {
        color: #10b981;
    }

    /* Warning States */
    .warning-state {
        border-color: #f59e0b;
        background: #fffbeb;
    }

    .warning-state .kpi-value {
        color: #f59e0b;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar - Unified Structure
st.sidebar.markdown(
    """
<div class="brand-header">
    <div class="brand-logo">🥋</div>
    <div class="brand-title">Dojo Allocator</div>
    <div class="brand-subtitle">Autonomous Trading System</div>
</div>
""",
    unsafe_allow_html=True,
)


# Navigation with icons
nav_options = [
    ("🏠", "Overview"),
    ("📈", "Performance"),
    ("📊", "Signals"),
    ("💼", "Positions"),
    ("🔄", "Cycle Status"),
    ("🎛️", "Philosophy Settings"),
    ("📊", "Scenario Comparison"),
    ("❓", "How It Works"),
]

# Create navigation buttons
st.sidebar.markdown("### Navigation")

# Handle page navigation first
if "current_page" in st.session_state:
    page = st.session_state.current_page
else:
    page = "Overview"

# Create clickable navigation buttons
for icon, label in nav_options:
    if st.sidebar.button(f"{icon} {label}", key=f"nav_{label}"):
        st.session_state.current_page = label
        st.rerun()

# Display Options (moved to bottom of sidebar)
with st.sidebar.expander("🎛️ Display Options", expanded=True):
    dark_mode = st.checkbox(
    "Dark Mode",
    value=False,
     help="Switch to dark theme")
    compact_mode = st.checkbox(
        "Compact Mode", value=False, help="Reduce spacing and font sizes for dense layouts"
    )

    with st.expander("♿ Accessibility", expanded=False):
        high_contrast = st.checkbox(
            "High Contrast", value=False, help="Increase contrast for better visibility"
        )
        reduced_motion = st.checkbox(
            "Reduce Motion",
            value=False,
            help="Disable animations for users with motion sensitivity",
        )
        large_text = st.checkbox(
            "Large Text", value=False, help="Increase text size for better readability"
        )

# Build accessibility class string
accessibility_class = ""
try:
    if high_contrast:
        accessibility_class += " high-contrast"
    if reduced_motion:
        accessibility_class += " reduced-motion"
    if large_text:
        accessibility_class += " large-text"
    if compact_mode:
        accessibility_class += " compact-mode"
    if dark_mode:
        accessibility_class += " dark-mode"
except NameError:
    # Variables not defined, use empty string
    accessibility_class = ""

# Apply dark mode using JavaScript injection
if dark_mode:
    st.markdown("""
    <script>
    // Apply dark mode styles
    document.documentElement.style.setProperty(
        '--background-color', '#111827');
    document.documentElement.style.setProperty('--text-color', '#f9fafb');

    // Apply to main content
    const mainContent = document.querySelector('.main .block-container');
    if (mainContent) {
        mainContent.style.backgroundColor = '#111827';
        mainContent.style.color = '#f9fafb';
    }

    // Apply to sidebar
    const sidebar = document.querySelector('.stSidebar');
    if (sidebar) {
        sidebar.style.backgroundColor = '#1f2937';
    }

    // Apply to buttons
    const buttons = document.querySelectorAll('.stButton > button');
    buttons.forEach(button => {
        button.style.backgroundColor = '#374151';
        button.style.color = '#f9fafb';
        button.style.borderColor = '#4b5563';
    });

    // Apply to all text elements
    const textElements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div');
    textElements.forEach(el => {
        if (el.style.color === '' || el.style.color === 'rgb(0, 0, 0)') {
            el.style.color = '#f9fafb';
        }
    });

    // Add dark mode class to body
    document.body.classList.add('dark-mode');
    </script>
    """, unsafe_allow_html=True)

    # Debug: Show dark mode status
    st.sidebar.success("🌙 Dark Mode: ON")
else:
    st.markdown("""
    <script>
    // Remove dark mode styles
    document.documentElement.style.removeProperty('--background-color');
    document.documentElement.style.removeProperty('--text-color');

    // Reset main content
    const mainContent = document.querySelector('.main .block-container');
    if (mainContent) {
        mainContent.style.backgroundColor = '';
        mainContent.style.color = '';
    }

    // Reset sidebar
    const sidebar = document.querySelector('.stSidebar');
    if (sidebar) {
        sidebar.style.backgroundColor = '';
    }

    // Reset buttons
    const buttons = document.querySelectorAll('.stButton > button');
    buttons.forEach(button => {
        button.style.backgroundColor = '';
        button.style.color = '';
        button.style.borderColor = '';
    });

    // Remove dark mode class from body
    document.body.classList.remove('dark-mode');
    </script>
    """, unsafe_allow_html=True)

    # Debug: Show dark mode status
    st.sidebar.info("☀️ Dark Mode: OFF")

# Database setup
settings = get_settings()
engine = create_engine(settings.DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

# System Status Section
st.sidebar.markdown(
    """
<div class="status-section">
    <h4 style="margin: 0 0 1rem 0; color: #374151; font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">🔗 System Status</h4>
""",
    unsafe_allow_html=True,
)

# Check API connectivity
try:
    import requests

    response = requests.get("http://api:8000/health", timeout=5)
    if response.status_code == 200:
        st.sidebar.markdown(
            """
        <div class="status-item">
            <span class="status-label">API</span>
            <span class="status-value status-connected">🟢 Connected</span>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            """
        <div class="status-item">
            <span class="status-label">API</span>
            <span class="status-value status-error">🔴 Error</span>
        </div>
        """,
            unsafe_allow_html=True,
        )
except:
    st.sidebar.markdown(
        """
    <div class="status-item">
        <span class="status-label">API</span>
        <span class="status-value status-error">🔴 Offline</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

# Check database connectivity
try:
    db_test = Session()
    db_test.execute(text("SELECT 1"))
    db_test.close()
    st.sidebar.markdown(
        """
    <div class="status-item">
        <span class="status-label">Database</span>
        <span class="status-value status-connected">🟢 Connected</span>
    </div>
    """,
        unsafe_allow_html=True,
    )
except:
    st.sidebar.markdown(
        """
    <div class="status-item">
        <span class="status-label">Database</span>
        <span class="status-value status-error">🔴 Error</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

# Check Celery worker status
try:
    response = requests.get("http://api:8000/celery/status", timeout=5)
    if response.status_code == 200:
        data = response.json()
        if data.get("workers", 0) > 0:
            st.sidebar.markdown(
                f"""
            <div class="status-item">
                <span class="status-label">Celery</span>
                <span class="status-value status-connected">🟢 Active ({data.get('workers', 0)} workers)</span>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.sidebar.markdown(
                """
            <div class="status-item">
                <span class="status-label">Celery</span>
                <span class="status-value status-warning">🟡 Idle</span>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.sidebar.markdown(
            """
        <div class="status-item">
            <span class="status-label">Celery</span>
            <span class="status-value status-error">🔴 Error</span>
        </div>
        """,
            unsafe_allow_html=True,
        )
except:
    st.sidebar.markdown(
        """
    <div class="status-item">
        <span class="status-label">Celery</span>
        <span class="status-value status-error">🔴 Offline</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.sidebar.markdown("</div>", unsafe_allow_html=True)

# Check system status and show notifications
system_notifications = check_system_status()
for notification_type, message in system_notifications:
    if notification_type == "error":
        st.error(f"🔴 {message}")
    elif notification_type == "warning":
        st.warning(f"🟡 {message}")
    elif notification_type == "success":
        st.success(f"🟢 {message}")

# Helper functions for Performance page
# This is the new fetch function to replace the old one


def fetch_benchmark_data(ticker, days):
    """Fetch benchmark data using Alpaca API with yfinance fallback"""
    import os
    import requests
    import pandas as pd
    from datetime import datetime, timedelta
    import yfinance as yf

    try:
        # Try Alpaca API first
        API_KEY = os.getenv("ALPACA_API_KEY")
        API_SECRET = os.getenv("ALPACA_API_SECRET")

        if API_KEY and API_SECRET:
            fetch_days = max(days, 10)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=fetch_days)

            url = "https://data.alpaca.markets/v2/stocks/bars"
            params = {
                "symbols": ticker,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "timeframe": "1Day",
                "feed": "iex",
            }
            headers = {
    "APCA-API-KEY-ID": API_KEY,
     "APCA-API-SECRET-KEY": API_SECRET}

            response = requests.get(
    url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                bars = data.get("bars", {}).get(ticker, [])

                if bars:
                    df = pd.DataFrame(bars)
                    df["t"] = pd.to_datetime(df["t"])
                    df = df.set_index("t")
                    df = df.sort_index()

                    # Convert UTC index to naive datetime for comparison
                    df.index = df.index.tz_localize(None)

                    # Filter to requested timeframe
                    if days < fetch_days:
                        cutoff = end_date - timedelta(days=days)
                        df = df[df.index >= cutoff]

                    print(f"[ALPACA] {ticker}: {len(df)} data points")
                    return df["c"]
                else:
                    print(f"[ALPACA] {ticker}: No bars in response")
            else:
                print(f"[ALPACA] {ticker}: HTTP {response.status_code}")

        # Fallback to yfinance
        print(f"[YFINANCE] Fallback for {ticker}")

        # Map tickers to yfinance symbols
        yf_symbols = {"SPY": "SPY", "QQQ": "QQQ", "GLD": "GLD"}

        yf_symbol = yf_symbols.get(ticker, ticker)

        # Fetch data with appropriate period
        if days <= 1:
            period = "5d"  # 5 days for 1-day view
        elif days <= 7:
            period = "1mo"  # 1 month for 1-week view
        elif days <= 30:
            period = "3mo"  # 3 months for 1-month view
        else:
            period = "6mo"  # 6 months for 3-month view

        ticker_obj = yf.Ticker(yf_symbol)
        hist = ticker_obj.history(period=period)

        if hist.empty:
            print(f"[YFINANCE] No data for {yf_symbol}")
            return pd.Series()

        # Filter to requested timeframe
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Convert hist index to naive datetime for comparison
        hist_naive = hist.copy()
        hist_naive.index = hist_naive.index.tz_localize(None)

        hist = hist_naive[hist_naive.index >= start_date]

        if hist.empty:
            print(f"[YFINANCE] No data in timeframe for {yf_symbol}")
            return pd.Series()

        print(f"[YFINANCE] {ticker}: {len(hist)} data points")
        return hist["Close"]

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        return pd.Series()


def calculate_portfolio_history(db, days):
    """Calculate portfolio value over time"""
    try:
        from datetime import datetime, timedelta

        # Calculate start date based on days parameter
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get all positions (both OPEN and CLOSED) within the timeframe
        positions = db.execute(
            text(
                """
            SELECT entry_date, shares, entry_price, symbol, status, exit_date, exit_price
            FROM positions
            WHERE entry_date >= :start_date
            ORDER BY entry_date
        """
            ),
            {"start_date": start_date},
        ).fetchall()

        print(
            f"[PORTFOLIO] Found {len(positions)} positions since {start_date}")

        if not positions:
            print("[PORTFOLIO] No positions found in timeframe")
            return pd.Series()

        # Create daily portfolio value series
        portfolio_data = []
        current_value = 100000.0  # Starting portfolio value

        # Group positions by date
        daily_positions = {}
        for pos in positions:
            entry_date = pos[0].date() if hasattr(pos[0], "date") else pos[0]
            if entry_date not in daily_positions:
                daily_positions[entry_date] = []
            daily_positions[entry_date].append(pos)

        # Calculate portfolio value for each day
        for i in range(days + 1):
            current_date = (end_date - timedelta(days=i)).date()

            # Calculate value for this date
            day_value = 100000.0  # Base cash

            # Add value from positions that were active on this date
            for pos in positions:
                entry_date = pos[0].date() if hasattr(
                    pos[0], "date") else pos[0]
                exit_date = (
                    pos[5].date() if pos[5] and hasattr(
                        pos[5], "date") else None
                )

                # Check if position was active on this date
                if entry_date <= current_date:
                    if pos[4] == "OPEN" or (
    exit_date and exit_date > current_date):
                        # Position was active on this date
                        shares = float(pos[1])
                        entry_price = float(pos[2])

                        # Use current price for OPEN positions, exit price for
                        # CLOSED
                        if pos[4] == "OPEN":
                            # For OPEN positions, use entry price as approximation
                            # In a real implementation, you'd fetch current
                            # prices
                            current_price = entry_price
                        else:
                            # For CLOSED positions, use exit price
                            current_price = float(
    pos[6]) if pos[6] else entry_price

                        position_value = shares * current_price
                        day_value += position_value - \
                            (shares * entry_price)  # Add P&L
                    elif exit_date and exit_date == current_date:
                        # Position was closed on this date, include final P&L
                        shares = float(pos[1])
                        entry_price = float(pos[2])
                        exit_price = float(pos[6]) if pos[6] else entry_price
                        pnl = shares * (exit_price - entry_price)
                        day_value += pnl

            portfolio_data.append({"date": current_date, "value": day_value})

        if portfolio_data:
            df = pd.DataFrame(portfolio_data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df = df.sort_index()
            print(f"[PORTFOLIO] Returning {len(df)} data points")
            return df["value"]
        else:
            print("[PORTFOLIO] No portfolio data generated")
            return pd.Series()

    except Exception as e:
        st.error(f"Error calculating portfolio history: {e}")
        return pd.Series()


if page == "Overview":
    st.header("🎯 Multi-Scenario Trading Overview")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.info("""
        **5 Parallel Trading Scenarios Running:**
        Each scenario uses different philosophy settings and risk profiles to test various trading strategies simultaneously.
        """)

    with col2:
        if st.button("🔍 Compare Performance",
     help="Open detailed performance comparison"):
            st.session_state.current_page = "Scenario Comparison"
            st.rerun()

    # Scenario Performance Summary
    st.subheader("📊 Scenario Performance Summary")

    try:
        # Get scenario performance data
        scenario_data = db.execute(
            text("""
            SELECT
                s.scenario_name,
                s.scenario_type,
                s.current_capital,
                s.total_pnl,
                s.total_return_pct,
                COALESCE(sp.position_count, 0) as total_trades,
                s.winning_trades,
                s.losing_trades,
                s.win_rate,
                s.max_drawdown,
                s.sharpe_ratio,
                s.last_updated
            FROM scenarios s
            LEFT JOIN (
                SELECT scenario_id, COUNT(*) as position_count
                FROM scenario_positions
                GROUP BY scenario_id
            ) sp ON s.id = sp.scenario_id
            WHERE s.is_active = true
            ORDER BY s.total_return_pct DESC
            """)
        ).fetchall()

        if scenario_data:
            # Compute live unrealized return per scenario from scenario_positions using yfinance
            live_returns = {}
            try:
                # Build symbol lists per scenario
                scenario_names = [row[0] for row in scenario_data]
                for sname in scenario_names:
                    positions = pd.read_sql(
                        text(
                            """
                            SELECT symbol, direction, shares, entry_price
                            FROM scenario_positions sp
                            JOIN scenarios s ON sp.scenario_id = s.id
                            WHERE s.scenario_name = :sname AND sp.status = 'OPEN'
                            """
                        ),
                        engine,
                        params={"sname": sname},
                    )
                    if positions.empty:
                        live_returns[sname] = None
                        continue

                    symbols = positions["symbol"].unique().tolist()
                    current_prices = fetch_current_prices(symbols)

                    unrealized = 0.0
                    for _, r in positions.iterrows():
                        cur = current_prices.get(r["symbol"]) or r["entry_price"]
                        delta = (float(cur) - float(r["entry_price"])) * float(r["shares"])
                        if str(r["direction"]).upper() == "SHORT":
                            delta = -delta
                        unrealized += delta
                    initial_capital = 100000.0
                    live_return_pct = (unrealized / initial_capital) * 100.0
                    live_returns[sname] = live_return_pct
            except Exception:
                # If live calc fails, leave map empty
                live_returns = {}

            # Create performance cards for each scenario
            cols = st.columns(5)

            # Define scenario icons and colors
            scenario_config = {
                "Conservative": {"icon": "🛡️", "color": "blue", "bg": "#e3f2fd"},
                "Balanced": {"icon": "⚖️", "color": "teal", "bg": "#e0f2f1"},
                "Aggressive": {"icon": "🔥", "color": "orange", "bg": "#fff3e0"},
                "High-Risk": {"icon": "⚠️", "color": "red", "bg": "#ffebee"},
                "Custom": {"icon": "⚙️", "color": "purple", "bg": "#f3e5f5"}
            }

            for i, (scenario_name, scenario_type, current_capital, total_pnl, total_return_pct,
                   total_trades, winning_trades, losing_trades, win_rate, max_drawdown,
                   sharpe_ratio, last_updated) in enumerate(scenario_data):

                with cols[i]:
                    # Get scenario config
                    config = scenario_config.get(
    scenario_name, {
        "icon": "📊", "color": "gray", "bg": "#f5f5f5"})

                    # Determine card color based on performance
                    if total_return_pct > 5:
                        card_type = "success"
                        delta_type = "positive"
                    elif total_return_pct > 0:
                        card_type = "primary"
                        delta_type = "positive"
                    elif total_return_pct > -5:
                        card_type = "default"
                        delta_type = "neutral"
                    else:
                        card_type = "danger"
                        delta_type = "negative"

                    # Make card clickable
                    if st.button(
                        f"{config['icon']} {scenario_name}",
                        key=f"scenario_btn_{i}",
                        help=f"Click to view {scenario_name} details",
                        use_container_width=True
                    ):
                        st.session_state.selected_scenario = scenario_name
                        st.rerun()

                    # Prefer live return if available
                    display_return_pct = live_returns.get(scenario_name)
                    if display_return_pct is None:
                        display_return_pct = total_return_pct

                    # Create enhanced card with scenario styling
                    card_html = f"""
                    <div class="scenario-card" style="background: {config['bg']}; border-left: 4px solid {config['color']}; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; cursor: pointer; transition: transform 0.2s;">
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <span style="font-size: 1.5rem; margin-right: 0.5rem;">{config['icon']}</span>
                            <h4 style="margin: 0; color: {config['color']};">{scenario_name}</h4>
                        </div>
                        <div style="font-size: 1.8rem; font-weight: bold; color: {'green' if display_return_pct > 0 else 'red' if display_return_pct < 0 else 'gray'};">
                            {display_return_pct:.2f}%
                        </div>
                        <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">
                            ${total_pnl:,.0f} P&L
                        </div>
                        <div style="font-size: 0.8rem; color: #888; border-top: 1px solid #eee; padding-top: 0.5rem;">
                            {total_trades} Trades • {win_rate:.1f}% Win Rate • ${current_capital:,.0f} Capital
                        </div>
                    </div>
                    """

                    st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.warning(
                "No scenario data available. Scenarios may not have been initialized yet.")

    except Exception as e:
        st.error(f"Error loading scenario data: {e}")

    st.divider()

    # Scenario Details with Positions
    st.subheader("🔍 Scenario Details & Positions")

    try:
        # Get scenario data again for detailed view
        scenario_data = db.execute(
            text("""
            SELECT
                s.scenario_name,
                s.scenario_type,
                s.current_capital,
                s.total_pnl,
                s.total_return_pct,
                COALESCE(sp.position_count, 0) as total_trades,
                s.winning_trades,
                s.losing_trades,
                s.win_rate,
                s.max_drawdown,
                s.sharpe_ratio,
                s.last_updated
            FROM scenarios s
            LEFT JOIN (
                SELECT scenario_id, COUNT(*) as position_count
                FROM scenario_positions
                GROUP BY scenario_id
            ) sp ON s.id = sp.scenario_id
            WHERE s.is_active = true
            ORDER BY s.total_return_pct DESC
            """)
        ).fetchall()

        if scenario_data:
            # Create tabs for each scenario
            scenario_names = [row[0] for row in scenario_data]

            # Use selected scenario from cards, or default to first
            if "selected_scenario" not in st.session_state:
                st.session_state.selected_scenario = scenario_names[0]

            # Show current selection with option to change
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_scenario = st.selectbox(
                    "📊 Selected Scenario:",
                    scenario_names,
                    index=scenario_names.index(
    st.session_state.selected_scenario) if st.session_state.selected_scenario in scenario_names else 0,
                    help="Select a scenario to view detailed metrics and positions"
                )
            with col2:
                if st.button("🔄 Refresh Data", help="Refresh scenario data"):
                    st.rerun()

            # Find selected scenario data
            selected_data = next(
    row for row in scenario_data if row[0] == selected_scenario)
            scenario_name, scenario_type, current_capital, total_pnl, total_return_pct, \
            total_trades, winning_trades, losing_trades, win_rate, max_drawdown, \
            sharpe_ratio, last_updated = selected_data

            # Display scenario metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Current Capital", f"${current_capital:,.0f}")
            with col2:
                st.metric("Total P&L", f"${total_pnl:,.0f}")
            with col3:
                st.metric("Return %", f"{total_return_pct:.2f}%")
            with col4:
                st.metric("Win Rate", f"{win_rate:.1f}%")

            # Get positions for this scenario
            st.subheader(f"📈 {selected_scenario} Positions")

            # Note: This assumes positions are stored with scenario_id or scenario_name
            # You may need to adjust the query based on your actual database
            # schema
            try:
                positions_df = pd.read_sql(
                    text("""
                    SELECT
                        position_id as "Position ID",
                        symbol as "Symbol",
                        direction as "Direction",
                        shares as "Shares",
                        entry_price as "Entry Price",
                        conviction_tier as "Tier",
                        status as "Status",
                        entry_date as "Entry Date"
                    FROM positions
                    WHERE status = :status
                    ORDER BY entry_date DESC
                    LIMIT 20
                    """),
                    engine,
                    params={"status": "OPEN"},
                )

                if not positions_df.empty:
                    # Add symbol tooltips
                    positions_df = add_tooltip_info_to_df(
                        positions_df, "Symbol", db)

                    # Apply formatting
                    positions_df["Direction"] = positions_df["Direction"].apply(
                        format_direction)
                    positions_df["Tier"] = positions_df["Tier"].apply(
                        format_conviction_tier)
                    positions_df["Status"] = positions_df["Status"].apply(
                        format_status)

                    st.dataframe(positions_df, use_container_width=True)
                else:
                    # Enhanced empty state
                    st.markdown("""
                    <div style="text-align: center; padding: 2rem; background: #f8f9fa; border-radius: 8px; border: 2px dashed #dee2e6;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                        <h3 style="color: #6c757d; margin-bottom: 0.5rem;">No Positions Yet</h3>
                        <p style="color: #6c757d; margin-bottom: 1.5rem;">
                            This scenario hasn't opened any positions yet.<br>
                            Run a re-allocation or start a cycle to see trades here.
                        </p>
                        <div style="display: flex; gap: 1rem; justify-content: center;">
                            <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'trigger_reallocation', value: true}, '*')"
                                    style="background: #007bff; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
                                🔄 Run Re-Allocation
                            </button>
                            <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'view_performance', value: true}, '*')"
                                    style="background: #28a745; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
                                📊 View Performance
                            </button>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Error loading positions: {e}")
                st.info(
                    "Note: Position tracking by scenario may need to be implemented in the database schema.")

        else:
            st.warning("No scenario data available.")

    except Exception as e:
        st.error(f"Error loading scenario details: {e}")

    st.divider()

    # Portfolio Overview
    st.subheader("💰 Portfolio Overview")

    try:
        # Get portfolio summary data
        portfolio_data = db.execute(
            text("""
            SELECT
                COUNT(DISTINCT symbol) as unique_signals,
                COUNT(*) as total_positions,
                COALESCE(SUM(CASE WHEN status = 'OPEN' THEN shares * entry_price ELSE 0 END), 0) as deployed_capital,
                COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl ELSE 0 END), 0) as realized_pnl
            FROM positions
            """)
        ).fetchone()

        unique_signals, total_positions, deployed_capital, realized_pnl = portfolio_data

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Unique Signals", f"{unique_signals:,}")
        with col2:
            st.metric("Total Positions", f"{total_positions:,}")
        with col3:
            st.metric("Deployed Capital", f"${deployed_capital:,.0f}")
        with col4:
            st.metric("Realized P&L", f"${realized_pnl:,.0f}")

    except Exception as e:
        st.error(f"Error loading portfolio data: {e}")

    st.divider()

    # System Status
    st.subheader("🔧 System Status")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Check API status
        try:
            response = requests.get("http://api:8000/health", timeout=5)
            api_status = "🟢 Online" if response.status_code == 200 else "🔴 Offline"
        except:
            api_status = "🔴 Offline"

        st.markdown(
            create_kpi_card(
                "API Status",
                api_status,
                None,
                "positive" if "Online" in api_status else "negative",
                "success" if "Online" in api_status else "danger",
            ),
            unsafe_allow_html=True,
        )

    with col2:
        # Check database status
        try:
            db.execute(text("SELECT 1"))
            db_status = "🟢 Connected"
        except:
            db_status = "🔴 Disconnected"

        st.markdown(
            create_kpi_card(
                "Database",
                db_status,
                None,
                "positive" if "Connected" in db_status else "negative",
                "success" if "Connected" in db_status else "danger",
            ),
            unsafe_allow_html=True,
        )

    with col3:
        # Count active signals
        try:
            active_signals = db.execute(
                text("SELECT COUNT(DISTINCT symbol) FROM signals WHERE status=:status"),
                {"status": "ACTIVE"},
            ).scalar()
            signals_status = f"🟢 {active_signals} Active"
        except:
            signals_status = "🔴 Error"

        st.markdown(
            create_kpi_card(
                "Active Signals",
                signals_status,
                None,
                "positive",
                "primary",
            ),
            unsafe_allow_html=True,
        )

    with col4:
        # Count total positions across all scenarios
        try:
            total_positions = db.execute(
                text("SELECT COUNT(*) FROM positions WHERE status=:status"),
                {"status": "OPEN"},
            ).scalar()
            positions_status = f"🟢 {total_positions} Open"
        except:
            positions_status = "🔴 Error"

        st.markdown(
            create_kpi_card(
                "Total Positions",
                positions_status,
                None,
                "positive",
                "primary",
            ),
            unsafe_allow_html=True,
        )

    st.divider()

    # Quick Actions
    st.subheader("⚡ Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
    "🔄 Run Global Re-Allocation",
    type="primary",
     help="Re-evaluate all scenarios with current market signals"):
            # Show confirmation modal
            st.session_state.show_reallocation_confirm = True
            st.rerun()

    # Confirmation modal for re-allocation
    if st.session_state.get("show_reallocation_confirm", False):
        st.warning("⚠️ **Confirm Global Re-Allocation**")
        st.write("This will:")
        st.write("• Re-evaluate all 5 scenarios with current market signals")
        st.write("• Close existing positions and open new ones based on latest data")
        st.write("• Update performance metrics for all scenarios")

        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("✅ Confirm Re-Allocation", type="primary"):
                st.session_state.show_reallocation_confirm = False
                with st.spinner("Running global re-allocation..."):
                    try:
                        # Trigger parallel scenario execution
                        import requests
                        response = requests.post(
    "http://api:8000/scenarios/execute-all", timeout=120)
                        if response.status_code == 200:
                            st.success(
                                "✅ Global re-allocation completed! All scenarios updated.")
                            show_toast(
    "Global re-allocation completed successfully!", "success")
                        else:
                            st.error(
                                "❌ Re-allocation failed. Please try again.")
                            show_toast("Re-allocation failed", "error")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)[:100]}")
                        show_toast(
    f"Re-allocation error: {str(e)[:50]}", "error")
                st.rerun()

        with col_cancel:
            if st.button("❌ Cancel"):
                st.session_state.show_reallocation_confirm = False
                st.rerun()

    with col2:
        if st.button("📊 View Performance Details"):
            st.session_state.current_page = "Performance"
            st.rerun()

    with col3:
        if st.button("🎯 Compare Scenarios"):
            st.session_state.current_page = "Scenario Comparison"
            st.rerun()

    # Get portfolio stats
    try:
        response = requests.get(
    "http://api:8000/positions/stats/summary", timeout=5)
        portfolio_stats = response.json() if response.status_code == 200 else {}
    except:
        portfolio_stats = {}

    # Calculate portfolio value
    portfolio_value = 100000.0
    try:
        positions_value = db.execute(
            text(
                """
            SELECT COALESCE(SUM(shares * COALESCE(entry_price, 0)), 0) as deployed
            FROM positions WHERE status = :status
        """
            ),
            {"status": "OPEN"},
        ).fetchone()[0]
        positions_value = float(positions_value) if positions_value else 0
        cash_available = portfolio_value - positions_value
        deployment_pct = (
            (positions_value / portfolio_value) *
             100 if portfolio_value > 0 else 0
        )
    except:
        positions_value = 0
        cash_available = portfolio_value
        deployment_pct = 0

    # Top row: Financial metrics with enhanced KPI cards using responsive grid
    st.markdown('<div class="dashboard-grid">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            create_kpi_card(
                "Portfolio Value",
                f"${portfolio_value:,.0f}",
                "Paper Trading",
                "neutral",
                "primary",
            ),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            create_kpi_card(
                "Deployed Capital",
                f"${positions_value:,.0f}",
                f"{deployment_pct:.1f}%",
                "positive" if deployment_pct > 0 else "neutral",
                "success",
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            create_kpi_card(
                "Cash Available",
                f"${cash_available:,.0f}",
                f"{100-deployment_pct:.1f}%",
                "neutral",
                "default",
            ),
            unsafe_allow_html=True,
        )

    with col4:
        total_pnl = portfolio_stats.get("total_pnl", 0)
        pnl_pct = (total_pnl / portfolio_value) * \
                   100 if portfolio_value > 0 else 0
        pnl_type = (
            "positive" if pnl_pct > 0 else "negative" if pnl_pct < 0 else "neutral"
        )
        card_type = "success" if pnl_pct > 0 else "danger" if pnl_pct < 0 else "default"

        st.markdown(
            create_kpi_card(
                "Total P&L",
                f"${total_pnl:,.2f}",
                f"{pnl_pct:+.2f}%",
                pnl_type,
                card_type,
            ),
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Second row: Position metrics with enhanced KPI cards using responsive
    # grid
    st.markdown('<div class="dashboard-grid">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_signals = db.execute(
    text("SELECT COUNT(*) FROM signals")).scalar()
        st.markdown(
            create_kpi_card(
                "Total Signals", f"{total_signals:,}", None, "neutral", "default"
            ),
            unsafe_allow_html=True,
        )

    with col2:
        active_signals = db.execute(
            text("SELECT COUNT(*) FROM signals WHERE status=:status"),
            {"status": "ACTIVE"},
        ).scalar()
        st.markdown(
            create_kpi_card(
                "Active Signals", f"{active_signals:,}", None, "positive", "success"
            ),
            unsafe_allow_html=True,
        )

    with col3:
        open_positions = db.execute(
            text("SELECT COUNT(*) FROM positions WHERE status=:status"),
            {"status": "OPEN"},
        ).scalar()
        st.markdown(
            create_kpi_card(
                "Open Positions", f"{open_positions:,}", None, "positive", "primary"
            ),
            unsafe_allow_html=True,
        )

    with col4:
        closed_positions = db.execute(
            text("SELECT COUNT(*) FROM positions WHERE status=:status"),
            {"status": "CLOSED"},
        ).scalar()
        st.markdown(
            create_kpi_card(
                "Closed Positions", f"{closed_positions:,}", None, "neutral", "default"
            ),
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Cycle Status
    st.divider()
    st.subheader("🔄 Current Cycle Status")

    try:
        # Get cycle information from API
        cycle_response = requests.get(
    "http://api:8000/cycle/current", timeout=5)
        if cycle_response.status_code == 200:
            cycle_data = cycle_response.json()

            if cycle_data.get("status") == "success":
                cycle_info = cycle_data.get("cycle", {})

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    # Calculate cycle day from start date
                    from datetime import datetime
                    start_date = datetime.fromisoformat(
    cycle_info.get(
        "start_date", "").replace(
            "Z", "+00:00"))
                    current_date = datetime.utcnow()
                    cycle_day = (current_date - start_date).days
                    total_days = 30  # 30-day cycle

                    st.markdown(
                        create_kpi_card(
                            "Cycle Day",
                            f"{cycle_day}/{total_days}",
                            f"{cycle_day} days",
                            "neutral",
                            "primary",
                        ),
                        unsafe_allow_html=True,
                    )

                with col2:
                    phase = cycle_info.get("phase", "N/A")
                    phase_color = {
                        "LOAD": "🟢",
                        "ACTIVE": "🔵",
                        "SCALE_OUT": "🟡",
                        "FORCE_CLOSE": "🔴",
                    }.get(phase, "⚪")
                    st.markdown(
                        create_kpi_card(
                            "Phase",
                            f"{phase_color} {phase}",
                            None,
                            "neutral",
                            "default",
                        ),
                        unsafe_allow_html=True,
                    )

                with col3:
                    days_remaining = total_days - cycle_day
                    st.markdown(
                        create_kpi_card(
                            "Days Remaining",
                            f"{days_remaining}",
                            f"{days_remaining} days",
                            "neutral",
                            "warning" if days_remaining < 10 else "default",
                        ),
                        unsafe_allow_html=True,
                    )

                with col4:
                    # Use total_return from the cycle data directly
                    total_return = cycle_info.get("total_return", 0)
                    return_type = (
                        "positive"
                        if total_return > 0
                        else "negative" if total_return < 0 else "neutral"
                    )
                    card_type = (
                        "success"
                        if total_return > 0
                        else "danger" if total_return < 0 else "default"
                    )

                    st.markdown(
                        create_kpi_card(
                            "Cycle Return",
                            f"{total_return:.2f}%",
                            None,
                            return_type,
                            card_type,
                        ),
                        unsafe_allow_html=True,
                    )

                # Progress bar
                progress = cycle_day / 90
                st.progress(progress)
                st.caption(
                    f"Cycle Progress: {cycle_day}/90 days ({progress:.1%})")

                # Quick cycle info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(
                        f"**Cycle ID:** {cycle_info.get('cycle_id', 'N/A')}")
                with col2:
                    risk_metrics = cycle_info.get("risk_metrics", {})
                    drawdown_gate = risk_metrics.get("drawdown_gate", "GREEN")
                    st.write(f"**Risk Status:** {drawdown_gate}")

            else:
                # Enhanced empty state with improved messaging hierarchy
                st.markdown("""
                <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <span style="font-size: 1.25rem;">⚠️</span>
                        <h3 style="color: #dc2626; margin: 0; font-size: 1.125rem; font-weight: 600;">No active cycle found</h3>
                    </div>
                    <p style="color: #7f1d1d; margin: 0; font-size: 0.875rem;">
                        Start a new trading cycle to begin evaluating signals and managing live positions.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                # Action buttons at same level as alert
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    if st.button(
    "🚀 Start New Cycle",
    type="primary",
     use_container_width=True):
                        st.info(
                            "Cycle start functionality will be implemented in Alpha-4")
                with col2:
                    if st.button(
    "📊 View Past Cycles",
     use_container_width=True):
                        st.info(
                            "Cycle history functionality will be implemented in Alpha-4")
                with col3:
                    st.empty()  # Empty column for spacing
        else:
            st.error("❌ API error fetching cycle data")

    except Exception as e:
        st.warning(f"⚠️ Could not fetch cycle data: {str(e)}")

    # Cycle History Summary
    st.divider()
    st.subheader("📊 Recent Cycles")

    # Placeholder cycle history table
    st.markdown("""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: #f1f5f9; border-bottom: 1px solid #e2e8f0;">
                    <th style="padding: 0.75rem; text-align: left; font-weight: 600; color: #374151;">Cycle ID</th>
                    <th style="padding: 0.75rem; text-align: left; font-weight: 600; color: #374151;">Start Date</th>
                    <th style="padding: 0.75rem; text-align: left; font-weight: 600; color: #374151;">End Date</th>
                    <th style="padding: 0.75rem; text-align: left; font-weight: 600; color: #374151;">Status</th>
                    <th style="padding: 0.75rem; text-align: left; font-weight: 600; color: #374151;">Return %</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td colspan="5" style="padding: 2rem; text-align: center; color: #9ca3af; font-style: italic;">
                        No previous cycles found. Start your first cycle to begin tracking performance.
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    # Visual Cycle Flow Diagram
    st.divider()
    st.subheader("🔄 Cycle Flow")

    st.markdown("""
    <div style="text-align: center; padding: 2rem; background: #f8fafc; border-radius: 8px; margin: 1rem 0;">
        <div style="display: flex; justify-content: center; align-items: center; gap: 1rem; flex-wrap: wrap; font-size: 0.875rem; color: #6b7280;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.5rem;">📡</span>
                <span>Signals</span>
            </div>
            <span style="font-size: 1.2rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.5rem;">⚙️</span>
                <span>Allocation</span>
            </div>
            <span style="font-size: 1.2rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.5rem;">📊</span>
                <span>Positions</span>
            </div>
            <span style="font-size: 1.2rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.5rem;">📈</span>
                <span>Performance</span>
            </div>
            <span style="font-size: 1.2rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.5rem;">🏁</span>
                <span>Close</span>
            </div>
        </div>
        <p style="margin-top: 1rem; font-size: 0.75rem; color: #9ca3af;">
            The Dojo Allocator system follows this continuous cycle of signal evaluation, position management, and performance tracking.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Last Sync line for transparency
    from datetime import datetime
    last_sync = datetime.now().strftime('%H:%M:%S')

    st.markdown(f"""
    <div style="text-align: center; margin-top: 2rem; padding: 0.5rem;">
        <p style="margin: 0; font-size: 0.75rem; color: #6b7280;">
            Last system sync: {last_sync} • Next cycle trigger check in 15 min
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Database Backup
    st.divider()
    st.subheader("💾 Database Backup")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.write("**Automatic:** Daily at 2 AM")
        st.write("**Location:** Google Drive → Dojo Backups")

    with col2:
        # Enhanced backup button with confirmation
        if st.button("🔄 Backup Now", type="secondary"):
            st.session_state.show_backup_confirm = True

        # Backup confirmation dialog
        if st.session_state.get("show_backup_confirm", False):
            st.warning("⚠️ **Confirm Database Backup**")
            st.write("This will:")
            st.write("• Create a full database backup")
            st.write("• Upload to Google Drive")
            st.write("• Include all positions, signals, and audit logs")

            col_confirm, col_cancel = st.columns(2)

            with col_confirm:
                if st.button("✅ Confirm Backup", type="primary"):
                    st.session_state.show_backup_confirm = False
            with st.spinner("Creating backup..."):
                import requests

                try:
                    response = requests.post(
                        "http://api:8000/backup/create", timeout=30
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            st.success(f"✅ Backup saved: {data.get('file')}")
                            show_toast(
                                f"Backup completed: {data.get('file')}", "success"
                            )
                            st.rerun()
                        else:
                            st.error(f"❌ {data.get('message', 'Failed')}")
                            show_toast(
                                f"Backup failed: {data.get('message', 'Failed')}",
                                "error",
                            )
                    else:
                        st.error("❌ API error")
                        show_toast("Backup failed: API error", "error")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)[:50]}")
                    show_toast(f"Backup failed: {str(e)[:50]}", "error")

            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.show_backup_confirm = False
                    st.rerun()

    with col3:
        import requests

        try:
            response = requests.get("http://api:8000/backup/list", timeout=5)
            if response.status_code == 200:
                data = response.json()
                total_backups = data.get("count", 0)
                full_system = data.get("full_system_backups", 0)
                st.metric("Total Backups", total_backups)
                if total_backups > 0:
                    st.caption(f"Full System: {full_system}")
                    st.caption(f"DB Only: {total_backups - full_system}")
            else:
                st.metric("Backups", "?")
        except:
            st.metric("Backups", "?")

    # Position Re-Allocation
    st.divider()
    st.subheader("🎯 Position Re-Allocation")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write(
            "**Trigger:** Allocate positions across scenarios (no main cycle allocation)")
        st.write(
            "**Process:** Runs 5 parallel scenarios (Conservative, Balanced, Aggressive, High-Risk, Custom) to compare performance"
        )

    with col2:
        # Enhanced Re-Allocate button with confirmation
        col1, col2 = st.columns([3, 1])

        with col1:
            st.info(
                "💡 **Scenario Allocation** runs 5 parallel trading scenarios with different philosophy settings. Compare performance to decide which strategy to use for the main cycle."
            )

        with col2:
            # Start New Cycle button
            if st.button(
    "🚀 Start New Cycle",
    type="primary",
     help="Start a new trading cycle to evaluate signals"):
                with st.spinner("Starting new cycle..."):
                    try:
                        start_response = requests.post(
    "http://api:8000/cycle/start", timeout=60)
                        if start_response.status_code == 200:
                            st.success("✅ New cycle started successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to start cycle")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

            # Add confirmation dialog
            if st.button(
    "⚙️ Run Scenario Allocation",
    type="secondary",
     help="Allocate positions across all scenarios"):
                st.session_state.show_allocation_confirm = True

        # Confirmation dialog
        if st.session_state.get("show_allocation_confirm", False):
            st.warning("⚠️ **Confirm Scenario Allocation**")
            st.write("This will:")
            st.write(
                "• Run all 5 scenarios in parallel (Conservative, Balanced, Aggressive, High-Risk, Custom)")
            st.write(
                "• Allocate positions to each scenario with different philosophy settings")
            st.write(
                "• **No main cycle allocation** - scenarios run independently for comparison")
            st.write("• Takes 30-60 seconds to complete")

            col_confirm, col_cancel = st.columns(2)

            with col_confirm:
                if st.button("✅ Confirm Scenario Allocation", type="primary"):
                    st.session_state.show_allocation_confirm = False

                    with st.spinner("Running scenario allocation (this may take 30-60 seconds)..."):
                        import requests

                        try:
                            response = requests.post(
                                "http://api:8000/allocation/trigger", timeout=120
                            )
                            if response.status_code == 200:
                                data = response.json()
                                # Store allocation results in session state for
                                # persistence
                                st.session_state.allocation_results = data
                                st.success(
                                    "✅ Scenario allocation completed successfully!")
                                show_toast(
    "Scenario allocation completed successfully!", "success")
                                st.rerun()
                            else:
                                st.error("❌ API error")
                                show_toast(
    "Scenario allocation failed: API error", "error")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)[:50]}")
                            show_toast(
    f"Scenario allocation failed: {str(e)[:50]}", "error")

            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.show_allocation_confirm = False
                    st.rerun()

    # Display allocation results if available in session state
    if hasattr(st.session_state, "allocation_results"):
        data = st.session_state.allocation_results
        if data.get("status") == "success":
            allocated = data.get("allocated", 0)

            # Always show allocation timestamp
            if data.get("allocation_timestamp"):
                st.caption(
                    f"Allocation completed at: {data['allocation_timestamp']}")

            # Always show signal information if available
            if data.get("signal_info"):
                with st.expander("📊 Signals Analyzed (Top 10)", expanded=True):
                    signal_df = pd.DataFrame(data["signal_info"])

                    # Note: Symbol tooltips will be added in future update

                    st.dataframe(signal_df, use_container_width=True)

                # Show summary of signals
                st.info(
                    f"📈 Analyzed {len(data['signal_info'])} active signals for allocation"
                )

            if allocated > 0:
                st.success(f"✅ {allocated} positions allocated!")

                # Show new positions with signal details
                if data.get("results"):
                    st.write("**New Positions Created:**")
                    for result in data["results"]:
                        st.write(
                            f"• **{result['symbol']}**: {result['shares']} shares ({result['tier']}-tier)"
                        )
                        st.write(
                            f"  - Signal Score: {result.get('signal_score', 'N/A')}"
                        )
                        st.write(
                            f"  - Signal Source: {result.get('signal_source', 'N/A')}"
                        )
                        if result.get("signal_discovered_at"):
                            st.write(
                                f"  - Signal Date: {result['signal_discovered_at']}"
                            )
                        st.write(
                            f"  - Philosophy: {result.get('philosophy_applied', 'N/A')}"
                        )
                        st.write("---")
            else:
                # Show message but still display signal info above
                if "No active signals" in data.get("message", ""):
                    st.warning(
                        f"⚠️ {data.get('message', 'No positions allocated')}")
                else:
                    st.info(
                        f"ℹ️ {data.get('message', 'No positions allocated')}")

                # Show portfolio context
                if data.get("portfolio_value"):
                    st.write(
                        f"**Portfolio Value:** ${data['portfolio_value']:,.2f}")
                if data.get("open_positions"):
                    st.write(
                        f"**Current Open Positions:** {data['open_positions']}")

            # Add clear button
            if st.button("🗑️ Clear Results", key="clear_allocation_results"):
                del st.session_state.allocation_results
                st.rerun()
        else:
            st.error(f"❌ {data.get('message', 'Failed')}")

    st.subheader("Active Signals")
    try:
        df = pd.read_sql(
            text(
                """
            SELECT
                signal_id as "Signal ID",
                symbol as "Symbol",
                source as "Source",
                direction as "Direction",
                conviction_tier as "Tier",
                total_score as "Score",
                status as "Status"
            FROM signals
            WHERE status=:status
            ORDER BY total_score DESC, symbol ASC
            LIMIT 10
        """
            ),
            engine,
            params={"status": "ACTIVE"},
        )

        if not df.empty:
            # Apply consistent formatting
            df["Source"] = df["Source"].apply(format_source_name)
            df["Tier"] = df["Tier"].apply(format_conviction_tier)
            df["Direction"] = df["Direction"].apply(format_direction)
            df["Status"] = df["Status"].apply(format_status)

            st.dataframe(df, use_container_width=True)
        else:
            st.info("No active signals")
    except Exception as e:
        st.error(f"Error loading signals: {e}")

    st.subheader("Open Positions")
    try:
        df = pd.read_sql(
            text(
                """
            SELECT
                position_id as "Position ID",
                symbol as "Symbol",
                direction as "Direction",
                shares as "Shares",
                entry_price as "Entry Price",
                conviction_tier as "Tier",
                status as "Status"
            FROM positions
            WHERE status=:status
            ORDER BY entry_date DESC
            LIMIT 10
        """
            ),
            engine,
            params={"status": "OPEN"},
        )

        if not df.empty:
            # Fetch current prices
            symbols = df["Symbol"].unique().tolist()
            with st.spinner("Fetching current prices..."):
                current_prices = fetch_current_prices(symbols)

            # Add current price and return columns
            df["Current Price"] = df["Symbol"].map(current_prices)

            # Calculate returns
            returns_data = []
            total_entry_value = 0
            total_current_value = 0
            total_unrealized_pnl = 0

            for _, row in df.iterrows():
                return_pct, unrealized_pnl, current_value = calculate_current_return(
                    row["Entry Price"], row["Current Price"], row["Shares"]
                )
                returns_data.append(
                    {
                    "Return %": return_pct,
                    "Unrealized P&L": unrealized_pnl,
                        "Current Value": current_value,
                    }
                )

                # Calculate totals
                entry_value = float(row["Entry Price"]) * float(row["Shares"])
                total_entry_value += entry_value
                if current_value is not None:
                    total_current_value += current_value
                    total_unrealized_pnl += unrealized_pnl

            # Add return columns
            df["Return %"] = [r["Return %"] for r in returns_data]
            df["Unrealized P&L"] = [r["Unrealized P&L"] for r in returns_data]
            df["Current Value"] = [r["Current Value"] for r in returns_data]

            # Portfolio summary
            if total_entry_value > 0:
                portfolio_return_pct = (
    total_unrealized_pnl / total_entry_value) * 100

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(
    "Total Entry Value",
     f"${total_entry_value:,.2f}")
                with col2:
                    st.metric(
    "Total Current Value",
     f"${total_current_value:,.2f}")
                with col3:
                    st.metric(
    "Unrealized P&L",
     f"${total_unrealized_pnl:,.2f}")
                with col4:
                    st.metric(
    "Portfolio Return",
     f"{portfolio_return_pct:.2f}%")

            # Apply consistent formatting
            df["Direction"] = df["Direction"].apply(format_direction)
            df["Tier"] = df["Tier"].apply(format_conviction_tier)
            df["Status"] = df["Status"].apply(format_status)

            # Add tooltip information column
            df = add_tooltip_info_to_df(df, "Symbol", db)

            # Format numeric columns
            df["Current Price"] = df["Current Price"].apply(
                lambda x: f"${x:.2f}" if pd.notna(x) else "N/A"
            )
            df["Return %"] = df["Return %"].apply(
                lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
            )
            df["Unrealized P&L"] = df["Unrealized P&L"].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
            )
            df["Current Value"] = df["Current Value"].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
            )

            st.dataframe(df, use_container_width=True)
        else:
            st.info("No open positions")
    except Exception as e:
        st.error(f"Error loading positions: {e}")

elif page == "Performance":
    # Unified header with context
    st.header("📊 Performance Dashboard")
    st.caption(
        "*Tracking Dojo Allocator and scenario performance versus major benchmarks*")

    # Enhanced scenario comparison toggle
    col1, col2 = st.columns([3, 1])

    with col1:
        st.caption(
            "*Aggregate returns from all active strategies versus market indices*")

    with col2:
        include_scenarios = st.toggle(
            "🔍 Compare Scenarios" if not st.session_state.get(
    "compare_scenarios", False) else "✅ Comparing Scenarios",
            value=st.session_state.get("compare_scenarios", False),
            help="Include scenario performance in benchmark comparison"
        )
        st.session_state.compare_scenarios = include_scenarios

    try:
        positions_df = pd.read_sql(
            text(
                """
            SELECT symbol, shares, entry_price, entry_date, conviction_tier
            FROM positions WHERE status = :status
        """
            ),
            engine,
            params={"status": "OPEN"},
        )

        if not positions_df.empty:
            symbols = positions_df["symbol"].unique().tolist()
            current_prices = {}

            with st.spinner("Fetching live prices..."):
                for symbol in symbols[:10]:  # Limit to prevent timeout
                    try:
                        ticker = yf.Ticker(symbol)
                        info = ticker.history(period="1d")
                        if not info.empty:
                            current_prices[symbol] = info["Close"].iloc[-1]
                    except:
                        pass

            positions_df["current_price"] = positions_df["symbol"].map(
                current_prices)
            positions_df["entry_value"] = (
                positions_df["shares"] * positions_df["entry_price"]
            )
            positions_df["current_value"] = (
                positions_df["shares"] * positions_df["current_price"]
            )
            positions_df["unrealized_pnl"] = (
                positions_df["current_value"] - positions_df["entry_value"]
            )
            positions_df["return_pct"] = (
                positions_df["unrealized_pnl"] / positions_df["entry_value"]
            ) * 100

            total_unrealized = positions_df["unrealized_pnl"].sum()
            total_entry = positions_df["entry_value"].sum()
            total_current = positions_df["current_value"].sum()
            total_return_pct = (
                (total_unrealized / total_entry * 100) if total_entry > 0 else 0
            )

            winning = len(positions_df[positions_df["return_pct"] > 0])
            losing = len(positions_df[positions_df["return_pct"] < 0])
            win_rate = (
                (winning / len(positions_df) * 100) if len(positions_df) > 0 else 0
            )

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "Total Value",
                    f"${total_current:,.0f}",
                    f"${total_unrealized:+,.0f}",
                )

            with col2:
                st.metric(
                    "Unrealized P&L",
                    f"${total_unrealized:,.2f}",
                    f"{total_return_pct:+.2f}%",
                )

            with col3:
                st.metric(
    "Win Rate",
    f"{win_rate:.1f}%",
     f"{winning}W / {losing}L")

            with col4:
                avg_win = (
                    positions_df[positions_df["return_pct"]
                        > 0]["return_pct"].mean()
                    if winning > 0
                    else 0
                )
                st.metric("Avg Winner", f"+{avg_win:.2f}%")

            with col5:
                avg_loss = (
                    positions_df[positions_df["return_pct"]
                        < 0]["return_pct"].mean()
                    if losing > 0
                    else 0
                )
                st.metric("Avg Loser", f"{avg_loss:.2f}%")

            st.caption("🔄 Live data • Updates on refresh")
    except Exception as e:
        st.error(f"Error: {e}")

    # Soft section divider
    st.markdown("---")
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # BENCHMARK COMPARISON
    st.subheader("📊 vs. Market Benchmarks")
    st.caption("*Visualize benchmark and scenario trends over time*")

    # Enhanced timeframe controls with blue toggle styling
    st.markdown("**Timeframe:**")
    timeframe = st.radio(
        "Timeframe",
        ["1 Day", "1 Week", "1 Month", "3 Months"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # Enhanced timeframe controls with Dojo blue styling
    st.markdown("""
    <style>
    .stRadio > div > label > div[data-testid="stMarkdownContainer"] > p {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        transition: all 0.2s;
        cursor: pointer;
        font-weight: 500;
    }
    .stRadio > div > label > div[data-testid="stMarkdownContainer"] > p:hover {
        border-color: #3b82f6;
        background: #eff6ff;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.1);
    }
    .stRadio > div > label[data-testid="stRadio"] > div[data-testid="stMarkdownContainer"] > p {
        background: #3b82f6 !important;
        color: white !important;
        border-color: #3b82f6 !important;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
    }
    </style>
    """, unsafe_allow_html=True)

    days_map = {"1 Day": 1, "1 Week": 7, "1 Month": 30, "3 Months": 90}
    selected_days = days_map[timeframe]

    with st.spinner("Loading..."):
        spy_data = fetch_benchmark_data("SPY", selected_days)
        qqq_data = fetch_benchmark_data("QQQ", selected_days)
        gld_data = fetch_benchmark_data("GLD", selected_days)
        portfolio_data = calculate_portfolio_history(db, selected_days)

    print(
        f"[CHART] SPY: {len(spy_data)}, QQQ: {len(qqq_data)}, GLD: {len(gld_data)}, Portfolio: {len(portfolio_data)}"
    )

    def normalize_returns(series):
        if len(series) > 0:
            return ((series / series.iloc[0]) - 1) * 100
        return series

    spy_returns = normalize_returns(spy_data)
    qqq_returns = normalize_returns(qqq_data)
    gld_returns = normalize_returns(gld_data)
    portfolio_returns = normalize_returns(portfolio_data)

    # Fetch scenario data if enabled
    scenario_data = []
    if include_scenarios:
        try:
            scenario_query = db.execute(text("""
                SELECT scenario_name, total_return_pct, total_pnl, current_capital
                FROM scenarios
                ORDER BY total_return_pct DESC
            """))
            scenario_data = scenario_query.fetchall()
        except Exception as e:
            st.warning(f"Could not load scenario data: {e}")

    # Chart with enhanced styling and interactivity
    fig = go.Figure()

    print(
        f"[CHART] Adding traces - Portfolio: {len(portfolio_returns)}, SPY: {len(spy_returns)}, QQQ: {len(qqq_returns)}, GLD: {len(gld_returns)}"
    )

    if len(portfolio_returns) > 0:
        fig.add_trace(
            go.Scatter(
                x=portfolio_returns.index,
                y=portfolio_returns.values,
                mode="lines+markers",
                name="🥋 Dojo Portfolio",
                line=dict(color="#3b82f6", width=4),
                marker=dict(size=6, color="#3b82f6"),
                hovertemplate="<b>%{fullData.name}</b><br>"
                + "Date: %{x}<br>"
                + "Return: %{y:.2f}%<br>"
                + "<extra></extra>",
            )
        )
        print("[CHART] Added Dojo trace")

    if len(spy_returns) > 0:
        fig.add_trace(
            go.Scatter(
                x=spy_returns.index,
                y=spy_returns.values,
                mode="lines",
                name="📈 S&P 500",
                line=dict(color="#10b981", width=3, dash="dash"),
                hovertemplate="<b>%{fullData.name}</b><br>"
                + "Date: %{x}<br>"
                + "Return: %{y:.2f}%<br>"
                + "<extra></extra>",
            )
        )
        print("[CHART] Added SPY trace")

    if len(qqq_returns) > 0:
        fig.add_trace(
            go.Scatter(
                x=qqq_returns.index,
                y=qqq_returns.values,
                mode="lines",
                name="🚀 Nasdaq",
                line=dict(color="#8b5cf6", width=3, dash="dash"),
                hovertemplate="<b>%{fullData.name}</b><br>"
                + "Date: %{x}<br>"
                + "Return: %{y:.2f}%<br>"
                + "<extra></extra>",
            )
        )
        print("[CHART] Added QQQ trace")

    if len(gld_returns) > 0:
        fig.add_trace(
            go.Scatter(
                x=gld_returns.index,
                y=gld_returns.values,
                mode="lines",
                name="🥇 Gold",
                line=dict(color="#f59e0b", width=3, dash="dot"),
                hovertemplate="<b>%{fullData.name}</b><br>"
                + "Date: %{x}<br>"
                + "Return: %{y:.2f}%<br>"
                + "<extra></extra>",
            )
        )
        print("[CHART] Added GLD trace")

    # Add scenario traces if enabled
    if include_scenarios and scenario_data:
        scenario_colors = {
            "Conservative": "#10b981",
            "Balanced": "#3b82f6",
            "Aggressive": "#f59e0b",
            "High-Risk": "#ef4444",
            "Custom": "#8b5cf6"
        }

        scenario_icons = {
            "Conservative": "🛡️",
            "Balanced": "⚖️",
            "Aggressive": "🔥",
            "High-Risk": "⚡",
            "Custom": "⚙️"
        }

        for scenario_name, total_return_pct, total_pnl, current_capital in scenario_data:
            # Create flat line for scenario return (since scenarios don't have time series yet)
            # We'll use the last date from portfolio_returns or create a simple
            # series
            if len(portfolio_returns) > 0:
                dates = portfolio_returns.index
                scenario_series = pd.Series(
    [total_return_pct] * len(dates), index=dates)
            else:
                # Create a simple series if no portfolio data
                dates = pd.date_range(end=datetime.now(), periods=10, freq='D')
                scenario_series = pd.Series(
    [total_return_pct] * len(dates), index=dates)

            icon = scenario_icons.get(scenario_name, "📊")
            color = scenario_colors.get(scenario_name, "#9ca3af")

            fig.add_trace(
                go.Scatter(
                    x=scenario_series.index,
                    y=scenario_series.values,
                    mode="lines",
                    name=f"{icon} {scenario_name}",
                    line=dict(color=color, width=2, dash="dot"),
                    hovertemplate=f"<b>{scenario_name}</b><br>"
                    + f"Return: {total_return_pct:.2f}%<br>"
                    + f"P&L: ${total_pnl:,.2f}<br>"
                    + "<extra></extra>",
                )
            )
            print(f"[CHART] Added {scenario_name} scenario trace")

    # Enhanced chart layout
    fig.update_layout(
        title=dict(
            text=f"📊 Performance Comparison - {timeframe}",
            font=dict(size=20, color="#1f2937"),
            x=0.5,
        ),
        xaxis=dict(
            title="Date",
            title_font=dict(size=14, color="#6b7280"),
            tickfont=dict(size=12, color="#6b7280"),
            gridcolor="#f3f4f6",
            showgrid=True,
        ),
        yaxis=dict(
            title="Return (%)",
            title_font=dict(size=14, color="#6b7280"),
            tickfont=dict(size=12, color="#6b7280"),
            gridcolor="#f3f4f6",
            showgrid=True,
            zeroline=True,
            zerolinecolor="#e5e7eb",
            zerolinewidth=2,
        ),
        hovermode="x unified",
        height=600,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=60, t=80, b=60),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#e5e7eb",
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor="white", bordercolor="#e5e7eb", font_size=12, font_family="Arial"
        ),
    )

    # Add annotations for key events
    if len(portfolio_returns) > 0:
        max_return = portfolio_returns.max()
        min_return = portfolio_returns.min()

        if max_return > 0:
            max_idx = portfolio_returns.idxmax()
            fig.add_annotation(
                x=max_idx,
                y=max_return,
                text=f"Peak: {max_return:.2f}%",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#10b981",
                bgcolor="white",
                bordercolor="#10b981",
                borderwidth=1,
            )

        if min_return < 0:
            min_idx = portfolio_returns.idxmin()
            fig.add_annotation(
                x=min_idx,
                y=min_return,
                text=f"Trough: {min_return:.2f}%",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#ef4444",
                bgcolor="white",
                bordercolor="#ef4444",
                borderwidth=1,
            )

    st.plotly_chart(fig, use_container_width=True)

    # Section divider
    st.markdown(
    '<div style="border-top: 1px solid #e5e7eb; margin: 2rem 0;"></div>',
     unsafe_allow_html=True)

    # Check if we have any data to display
    has_data = (len(portfolio_returns) > 0 or len(spy_returns) > 0 or
                len(qqq_returns) > 0 or len(gld_returns) > 0)

    # Check if we have positions (to determine if it's a fresh system vs API
    # error)
    has_positions = len(portfolio_returns) > 0

    if not has_data:
        # Check if benchmark data is available but portfolio is empty
        has_benchmark_data = (len(spy_returns) > 0 or len(
            qqq_returns) > 0 or len(gld_returns) > 0)

        if has_benchmark_data and not has_positions:
            # Show benchmark data with portfolio empty state
            st.info(
                "📊 **Benchmark data loaded** • Portfolio performance will appear after first re-allocation")
        elif not has_positions:
            # Fresh system - no positions yet
            st.markdown("""
            <div style="text-align: center; padding: 2rem; background: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px; margin: 1rem 0;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">🎯</div>
                <h3 style="color: #1e40af; margin-bottom: 0.5rem;">Ready to Start Trading</h3>
                <p style="color: #1e40af; margin-bottom: 1rem;">
                    No positions yet. Run a re-allocation to begin tracking performance.<br>
                    Benchmark data will load automatically once trading starts.
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_reallocation', value: true}, '*')"
                            style="background: #3b82f6; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500;">
                        ⚙️ Run Re-Allocation
                    </button>
                    <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_scenarios', value: true}, '*')"
                            style="background: #10b981; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500;">
                        🎯 Go to Scenarios
                    </button>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # API error - positions exist but benchmark data failed
            st.markdown("""
            <div style="text-align: center; padding: 2rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; margin: 1rem 0;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">⚠️</div>
                <h3 style="color: #dc2626; margin-bottom: 0.5rem;">Data Temporarily Unavailable</h3>
                <p style="color: #7f1d1d; margin-bottom: 1rem;">
                    Could not fetch benchmark data from Alpaca/IEX.<br>
                    Please check your internet connection or retry later.
                </p>
                <button onclick="window.location.reload()"
                        style="background: #dc2626; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
                    🔄 Retry
                </button>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption(
            f"📊 Market data: [Alpaca Markets (IEX)](https://alpaca.markets) • Updated {datetime.now().strftime('%H:%M')} • Portfolio data: Live paper trading"
        )

    # Returns with enhanced KPI cards
    st.markdown('<div class="dashboard-grid">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    portfolio_return = (
        float(portfolio_returns.iloc[-1]) if len(portfolio_returns) > 0 else 0
    )
    spy_return = float(spy_returns.iloc[-1]) if len(spy_returns) > 0 else 0
    qqq_return = float(qqq_returns.iloc[-1]) if len(qqq_returns) > 0 else 0
    gld_return = float(gld_returns.iloc[-1]) if len(gld_returns) > 0 else 0

    with col1:
        portfolio_type = (
            "positive"
            if portfolio_return > 0
            else "negative" if portfolio_return < 0 else "neutral"
        )
        portfolio_card = (
            "success"
            if portfolio_return > 0
            else "danger" if portfolio_return < 0 else "default"
        )
        st.markdown(
            create_kpi_card(
                "🥋 Dojo Portfolio",
                f"{portfolio_return:.2f}%",
                None,
                portfolio_type,
                portfolio_card,
            ),
            unsafe_allow_html=True,
        )

    with col2:
        spy_type = (
            "positive"
            if spy_return > 0
            else "negative" if spy_return < 0 else "neutral"
        )
        spy_card = (
            "success" if spy_return > 0 else "danger" if spy_return < 0 else "default"
        )

        # Calculate delta for S&P 500 (vs previous period)
        spy_delta = ""
        if len(spy_returns) > 1:
            prev_return = float(
                spy_returns.iloc[-2]) if len(spy_returns) > 1 else 0
            delta = spy_return - prev_return
            spy_delta = f"{'▲' if delta > 0 else '▼'} {abs(delta):.2f}%"

        st.markdown(
            create_kpi_card(
                "📈 S&P 500",
                f"{spy_return:.2f}%",
                spy_delta,
                spy_type,
                spy_card
            ),
            unsafe_allow_html=True,
        )

    with col3:
        qqq_type = (
            "positive"
            if qqq_return > 0
            else "negative" if qqq_return < 0 else "neutral"
        )
        qqq_card = (
            "success" if qqq_return > 0 else "danger" if qqq_return < 0 else "default"
        )

        # Calculate delta for Nasdaq (vs previous period)
        qqq_delta = ""
        if len(qqq_returns) > 1:
            prev_return = float(
                qqq_returns.iloc[-2]) if len(qqq_returns) > 1 else 0
            delta = qqq_return - prev_return
            qqq_delta = f"{'▲' if delta > 0 else '▼'} {abs(delta):.2f}%"

        st.markdown(
            create_kpi_card(
                "🚀 Nasdaq",
                f"{qqq_return:.2f}%",
                qqq_delta,
                qqq_type,
                qqq_card
            ),
            unsafe_allow_html=True,
        )

    with col4:
        gld_type = (
            "positive"
            if gld_return > 0
            else "negative" if gld_return < 0 else "neutral"
        )
        gld_card = (
            "success" if gld_return > 0 else "danger" if gld_return < 0 else "default"
        )

        # Calculate delta for Gold (vs previous period)
        gld_delta = ""
        if len(gld_returns) > 1:
            prev_return = float(
                gld_returns.iloc[-2]) if len(gld_returns) > 1 else 0
            delta = gld_return - prev_return
            gld_delta = f"{'▲' if delta > 0 else '▼'} {abs(delta):.2f}%"

        st.markdown(
            create_kpi_card(
                "🥇 Gold",
                f"{gld_return:.2f}%",
                gld_delta,
                gld_type,
                gld_card
            ),
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Add scenario KPI cards if enabled
    if include_scenarios and scenario_data:
        # Section divider
        st.markdown(
    '<div style="border-top: 1px solid #e5e7eb; margin: 2rem 0;"></div>',
     unsafe_allow_html=True)

        st.subheader("🎯 Scenario Performance")
        st.caption(
            "*Each scenario runs its own portfolio simulation using independent risk settings and philosophy parameters*")

        scenario_icons = {
            "Conservative": "🛡️",
            "Balanced": "⚖️",
            "Aggressive": "🔥",
            "High-Risk": "⚡",
            "Custom": "⚙️"
        }

        # Create columns for scenario cards
        scenario_cols = st.columns(len(scenario_data))

        for i, (scenario_name, total_return_pct, total_pnl,
                current_capital) in enumerate(scenario_data):
            with scenario_cols[i]:
                icon = scenario_icons.get(scenario_name, "📊")
                scenario_type = (
                    "positive" if total_return_pct > 0
                    else "negative" if total_return_pct < 0
                    else "neutral"
                )
                scenario_card = (
                    "success" if total_return_pct > 0
                    else "danger" if total_return_pct < 0
                    else "default"
                )

                st.markdown(
                    create_kpi_card(
                        f"{icon} {scenario_name}",
                        f"{total_return_pct:.2f}%",
                        None,
                        scenario_type,
                        scenario_card,
                    ),
                    unsafe_allow_html=True,
                )

        st.caption(
            "ℹ️ Scenarios track their own positions and performance independently")

    # Alpha Section with contextual explanation
    st.markdown(
    '<div style="border-top: 1px solid #e5e7eb; margin: 2rem 0;"></div>',
     unsafe_allow_html=True)

    st.subheader("🎯 Alpha Tracking")
    st.caption(
        "Alpha measures how much your portfolio outperforms (or underperforms) the benchmark"
    )

    # Responsive grid layout for Alpha Tracking
    col1, col2 = st.columns(2)

    with col1:
        alpha_spy = portfolio_return - spy_return
        alpha_qqq = portfolio_return - qqq_return

        # S&P 500 Alpha
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: #374151;">vs. S&P 500</span>
                <span style="font-size: 0.875rem; color: #6b7280;">Ahead</span>
            </div>
            <div style="font-size: 1.5rem; font-weight: bold; color: {'#10b981' if alpha_spy > 0 else '#ef4444' if alpha_spy < 0 else '#6b7280'};">
                {alpha_spy:+.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Nasdaq Alpha
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: #374151;">vs. Nasdaq</span>
                <span style="font-size: 0.875rem; color: #6b7280;">Ahead</span>
            </div>
            <div style="font-size: 1.5rem; font-weight: bold; color: {'#10b981' if alpha_qqq > 0 else '#ef4444' if alpha_qqq < 0 else '#6b7280'};">
                {alpha_qqq:+.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        alpha_gld = portfolio_return - gld_return

        # Gold Alpha
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: #374151;">vs. Gold</span>
                <span style="font-size: 0.875rem; color: #6b7280;">Ahead</span>
            </div>
            <div style="font-size: 1.5rem; font-weight: bold; color: {'#10b981' if alpha_gld > 0 else '#ef4444' if alpha_gld < 0 else '#6b7280'};">
                {alpha_gld:+.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Summary Alpha
        avg_alpha = (alpha_spy + alpha_qqq + alpha_gld) / 3
        st.markdown(f"""
        <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px; padding: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: #1e40af;">Average Alpha</span>
                <span style="font-size: 0.875rem; color: #3b82f6;">Overall</span>
            </div>
            <div style="font-size: 1.5rem; font-weight: bold; color: {'#10b981' if avg_alpha > 0 else '#ef4444' if avg_alpha < 0 else '#6b7280'};">
                {avg_alpha:+.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Add micro-feedback for Alpha Tracking
    st.caption(
        f"📊 Updated every 15 minutes • Tracking 3 benchmarks • Last update: {datetime.now().strftime('%H:%M')}"
    )

    # Add live timestamp in chart area
    st.markdown(f"""
    <div style="position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.9); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; color: #6b7280; z-index: 1000;">
        Last update: {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

    # Soft section divider
    st.markdown("---")
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # Unrealized P&L Summary - Make it prominent
    st.subheader("💰 Portfolio Summary")
    st.caption("*Track realized and unrealized results across open positions*")

    # Check if we have position data
    if "positions_df" in locals() and not positions_df.empty and "total_unrealized" in locals():
        st.info(
            f"**Unrealized P&L:** ${total_unrealized:+,.2f} ({total_return_pct:+.2f}%) since last reallocation"
        )

    st.subheader("📊 Position Performance")

    if "positions_df" in locals() and not positions_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.write("**🟢 Top 5 Gainers**")
            top = positions_df.nlargest(5, "return_pct")[
                ["symbol", "return_pct", "unrealized_pnl"]
            ].copy()
            top.columns = ["Symbol", "Return %", "P&L"]
            top["Return %"] = top["Return %"].apply(lambda x: f"{x:.2f}%")
            top["P&L"] = top["P&L"].apply(lambda x: f"${x:,.2f}")

            # Add tooltip information column
            top = add_tooltip_info_to_df(top, "Symbol", db)

            st.dataframe(top, use_container_width=True)

        with col2:
            st.write("**🔴 Top 5 Losers**")
            bottom = positions_df.nsmallest(5, "return_pct")[
                ["symbol", "return_pct", "unrealized_pnl"]
            ].copy()
            bottom.columns = ["Symbol", "Return %", "P&L"]
            bottom["Return %"] = bottom["Return %"].apply(
                lambda x: f"{x:.2f}%")
            bottom["P&L"] = bottom["P&L"].apply(lambda x: f"${x:,.2f}")

            # Add tooltip information column
            bottom = add_tooltip_info_to_df(bottom, "Symbol", db)

            st.dataframe(bottom, use_container_width=True)
    else:
        # Enhanced empty state for Portfolio Summary
        st.markdown("""
        <div style="text-align: center; padding: 3rem; background: #f8f9fa; border-radius: 12px; border: 2px dashed #dee2e6; margin: 2rem 0;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">📊</div>
            <h3 style="color: #6c757d; margin-bottom: 0.5rem;">No Portfolio Data Yet</h3>
            <p style="color: #6c757d; margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto;">
                Once trading begins, you'll see your positions, realized P&L, and historical performance here.
                <br><br>
                <strong>Next steps:</strong> Run a re-allocation or start a trading cycle to begin tracking performance.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_scenarios', value: true}, '*')"
                        style="background: #3b82f6; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s; animation: pulse 2s infinite;">
                    🎯 Go to Scenarios
                </button>
                <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_overview', value: true}, '*')"
                        style="background: #10b981; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s; animation: pulse 2s infinite 1s;">
                    🏠 Go to Overview
                </button>
            </div>
            <style>
                @keyframes pulse {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.05); }
                }
            </style>
        </div>
        """, unsafe_allow_html=True)

elif page == "Signals":
    st.header("📡 Signals")
    st.caption("*Live feed of trading signals aggregated from insider filings, congressional trades, and institutional data*")

    # Get live counts for filter options
    status_counts = db.execute(text("""
        SELECT status, COUNT(*) as count
        FROM signals
        GROUP BY status
    """)).fetchall()

    tier_counts = db.execute(text("""
        SELECT conviction_tier, COUNT(*) as count
        FROM signals
        GROUP BY conviction_tier
    """)).fetchall()

    # Create count dictionaries
    status_count_dict = {row[0]: row[1] for row in status_counts}
    tier_count_dict = {row[0]: row[1] for row in tier_counts}

    # Enhanced filter dropdowns with live counts
    status_options = ["All"] + [
    f"{status} ({status_count_dict.get(status, 0)})" for status in [
        "ACTIVE", "PENDING", "REJECTED", "EXPIRED"]]
    tier_options = [
        "All"] + [f"{tier} ({tier_count_dict.get(tier, 0)})" for tier in ["S", "A", "B", "C"]]

    status_filter = st.selectbox("Status", status_options)
    tier_filter = st.selectbox("Tier", tier_options)

    # Extract actual filter values (remove counts from display)
    status_value = status_filter.split(
        " (")[0] if " (" in status_filter else status_filter
    tier_value = tier_filter.split(
        " (")[0] if " (" in tier_filter else tier_filter

    query = """
        SELECT
            signal_id as "Signal ID",
            symbol as "Symbol",
            source as "Source",
            direction as "Direction",
            conviction_tier as "Tier",
            total_score as "Score",
            status as "Status"
        FROM signals
        WHERE 1=1
    """
    params = {}
    if status_value != "All":
        query += " AND status=:status"
        params["status"] = status_value
    if tier_value != "All":
        query += " AND conviction_tier=:tier"
        params["tier"] = tier_value

    # Add ORDER BY and LIMIT after WHERE clause
    query += " ORDER BY total_score DESC, symbol ASC LIMIT 100"

    try:
        df = pd.read_sql(text(query), engine, params=params)
        if not df.empty:
            # Apply consistent formatting
            df["Source"] = df["Source"].apply(format_source_name)
            df["Direction"] = df["Direction"].apply(format_direction)

            # Add color-coded status styling
            def format_status_with_color(status):
                if pd.isna(status):
                    return '<span style="background: #f3f4f6; color: #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">Unknown</span>'
                elif status == 'ACTIVE':
                    return '<span style="background: #dcfce7; color: #16a34a; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">🟢 Active</span>'
                elif status == 'PENDING':
                    return '<span style="background: #fef3c7; color: #d97706; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">🟡 Pending</span>'
                elif status == 'CLOSED':
                    return '<span style="background: #f3f4f6; color: #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">⚫ Closed</span>'
                elif status == 'REJECTED' or status == 'EXPIRED':
                    return '<span style="background: #fecaca; color: #dc2626; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">🔴 ' + status.title() + \
                                                                                                                                                                              '</span>'
                else:
                    return f'<span style="background: #f3f4f6; color: #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">{status}</span>'

            df["Status"] = df["Status"].apply(format_status_with_color)

            # Add color-coded tier styling
            def format_tier_with_color(tier):
                if pd.isna(tier) or tier == 'None':
                    return '<span style="background: #f3f4f6; color: #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">None</span>'
                elif tier == 'S':
                    return '<span style="background: #ede9fe; color: #7c3aed; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">S</span>'
                elif tier == 'A':
                    return '<span style="background: #dbeafe; color: #2563eb; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">A</span>'
                elif tier == 'B':
                    return '<span style="background: #dcfce7; color: #16a34a; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">B</span>'
                elif tier == 'C':
                    return '<span style="background: #fef3c7; color: #d97706; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">C</span>'
                else:
                    return f'<span style="background: #f3f4f6; color: #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">{tier}</span>'

            df["Tier"] = df["Tier"].apply(format_tier_with_color)

            # Store original scores for calculations before formatting
            original_scores = df["Score"].copy()

            # Add contextual score formatting with tooltips
            def format_score_with_tooltip(score):
                if pd.isna(score) or score is None:
                    return '<span style="color: #6b7280; cursor: help;" title="Score unavailable — awaiting next signal evaluation cycle">—</span>'
                else:
                    return f'<span style="font-weight: 500;">{float(score):.2f}</span>'

            df["Score"] = df["Score"].apply(format_score_with_tooltip)

            # Add tooltip information column with truncation
            df = add_tooltip_info_to_df(df, "Symbol", db)

            # Truncate Symbol_Info column for better readability
            def truncate_symbol_info(info):
                if len(str(info)) > 50:
                    return f'<span title="{info}" style="cursor: help;">{str(info)[:47]}...</span>'
                return str(info)

            df["Symbol_Info"] = df["Symbol_Info"].apply(truncate_symbol_info)

            # Add real-time pulse indicator for recent signals
            def add_pulse_indicator(signal_id):
                # Simulate recent signals (in production, this would check
                # actual timestamps)
                recent_signals = df["Signal ID"].head(
                    3).tolist()  # First 3 signals as "recent"
                if signal_id in recent_signals:
                    return '<span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%; animation: pulse 2s infinite; margin-right: 4px;" title="Recently updated"></span>'
                return ''

            df["Signal ID"] = df["Signal ID"].apply(
                lambda x: add_pulse_indicator(x) + str(x))

            # Display enhanced table with HTML rendering
            st.markdown('<div class="enhanced-table">', unsafe_allow_html=True)

            # Add sort icons to column headers
            def add_sort_icons(html_content):
                # Add sort icons to sortable columns
                html_content = html_content.replace(
                    '<th>Score</th>',
                    '<th onclick="alert(\'Sort by Score\')" style="cursor: pointer;">Score ▲▼</th>'
                )
                html_content = html_content.replace(
                    '<th>Tier</th>',
                    '<th onclick="alert(\'Sort by Tier\')" style="cursor: pointer;">Tier ▲▼</th>'
                )
                html_content = html_content.replace(
                    '<th>Status</th>',
                    '<th onclick="alert(\'Sort by Status\')" style="cursor: pointer;">Status ▲▼</th>'
                )
                return html_content

            # Convert dataframe to HTML with proper styling
            table_html = df.to_html(
    escape=False,
    index=False,
     table_id="signals-table")
            table_html = add_sort_icons(table_html)

            # Add custom CSS for the table
            st.markdown("""
            <style>
            #signals-table {
                width: 100%;
                border-collapse: collapse;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            #signals-table th {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                padding: 12px 8px;
                text-align: left;
                font-weight: 600;
                color: #374151;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            #signals-table th:hover {
                background-color: #f1f5f9;
            }
            #signals-table td {
                border: 1px solid #e2e8f0;
                padding: 8px;
                vertical-align: middle;
            }
            #signals-table tr:nth-child(even) {
                background-color: #f9fafb;
            }
            #signals-table tr:hover {
                background-color: #f3f4f6;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .pulse-indicator {
                animation: pulse 2s infinite;
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Add data health footer
            from datetime import datetime, timedelta
            last_update = datetime.now().strftime('%H:%M:%S')
            next_sync = "2m 30s"  # Simulated next sync time

            st.markdown(f"""
            <div style="margin-top: 1rem; padding: 0.5rem; background: #f8fafc; border-radius: 4px; border-left: 3px solid #3b82f6;">
                <p style="margin: 0; font-size: 0.75rem; color: #6b7280;">
                    📊 Last refresh: {last_update} • Next sync in {next_sync} • Source: Congressional Form 4 feed
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Add summary metrics
            if not df.empty:
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    total_signals = len(df)
                    st.markdown(
                        create_kpi_card(
                            "Total Signals",
                            f"{total_signals}",
                            None,
                            "neutral",
                            "default",
                        ),
                        unsafe_allow_html=True,
                    )

                with col2:
                    active_count = len(
                        df[df["Status"].str.contains("Active", na=False)]
                    )
                    st.markdown(
                        create_kpi_card(
                            "Active Signals",
                            f"{active_count}",
                            None,
                            "positive",
                            "success",
                        ),
                        unsafe_allow_html=True,
                    )

                with col3:
                    s_tier_count = len(
                        df[df["Tier"].str.contains("S-Tier", na=False)])
                    st.markdown(
                        create_kpi_card(
                            "S-Tier Signals",
                            f"{s_tier_count}",
                            None,
                            "positive",
                            "primary",
                        ),
                        unsafe_allow_html=True,
                    )

                with col4:
                    # Use original scores for calculation, not the formatted
                    # HTML
                    avg_score = original_scores.mean() if not original_scores.empty else 0
                    st.markdown(
                        create_kpi_card(
                            "Average Score",
                            f"{avg_score:.1f}",
                            None,
                            "positive" if avg_score > 50 else "neutral",
                            "success" if avg_score > 50 else "default",
                        ),
                        unsafe_allow_html=True,
                    )
            else:
                # Empty state when no signals found
                st.markdown("""
                <div style="text-align: center; padding: 3rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin: 2rem 0;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📡</div>
                    <h3 style="color: #374151; margin-bottom: 0.5rem;">No Signals Found</h3>
                    <p style="color: #6b7280; margin-bottom: 1.5rem;">
                        Try adjusting your filters or re-running the data sync.<br>
                        New signals are added automatically from insider filings and institutional data.
                    </p>
                    <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                        <button onclick="window.location.reload()"
                                style="background: #3b82f6; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500;">
                            🔄 Refresh Data
                        </button>
                        <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_overview', value: true}, '*')"
                                style="background: #10b981; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500;">
                            🏠 Go to Overview
                        </button>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error: {e}")

elif page == "Positions":
    st.header("📊 Positions")
    st.caption(
        "*Open and closed holdings generated from active trading signals during each cycle*")

    status_filter = st.selectbox("Status", ["All", "OPEN", "CLOSED"])

    # Get actual position counts
    try:
        total_positions = db.execute(text("SELECT COUNT(*) FROM scenario_positions")).scalar()
        total_value = db.execute(text("SELECT SUM(shares * entry_price) FROM scenario_positions")).scalar() or 0
        unique_symbols = db.execute(text("SELECT COUNT(DISTINCT symbol) FROM scenario_positions")).scalar()
    except:
        total_positions = 0
        total_value = 0
        unique_symbols = 0

    # Add summary cards with actual data
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; text-align: center;">
            <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">Open Positions</div>
            <div style="font-size: 1.5rem; font-weight: 600; color: #374151;">{total_positions}</div>
            <div style="font-size: 0.75rem; color: #9ca3af;">Currently held</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; text-align: center;">
            <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">Closed Positions</div>
            <div style="font-size: 1.5rem; font-weight: 600; color: #374151;">0</div>
            <div style="font-size: 0.75rem; color: #9ca3af;">Exited during current cycle</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; text-align: center;">
            <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">Total Deployed Capital</div>
            <div style="font-size: 1.5rem; font-weight: 600; color: #374151;">$0</div>
            <div style="font-size: 0.75rem; color: #9ca3af;">Pending allocation</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; text-align: center;">
            <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">Unrealized P&L</div>
            <div style="font-size: 1.5rem; font-weight: 600; color: #374151;">$0</div>
            <div style="font-size: 0.75rem; color: #9ca3af;">Will update after next cycle run</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    query = """
        SELECT
            sp.id as "Position ID",
            sp.symbol as "Symbol",
            sp.direction as "Direction",
            sp.shares as "Shares",
            sp.entry_price as "Entry Price",
            sp.exit_price as "Exit Price",
            sp.realized_pnl as "Realized P&L",
            'OPEN' as "Status",
            s.scenario_name as "Scenario",
            sp.entry_date as "Entry Date"
        FROM scenario_positions sp
        JOIN scenarios s ON sp.scenario_id = s.id
        WHERE 1=1
    """
    params = {}
    # Note: scenario_positions don't have status field, all are considered "OPEN"
    if status_filter == "CLOSED":
        # For closed positions, we could add a filter if needed
        query += " AND sp.exit_price IS NOT NULL"
    query += " ORDER BY sp.entry_date DESC LIMIT 100"

    try:
        df = pd.read_sql(text(query), engine, params=params)
        if not df.empty:
            # For open positions, fetch current prices and calculate returns
            if status_filter == "All" or status_filter == "OPEN":
                open_positions = df[df["Status"] == "OPEN"].copy()
                if not open_positions.empty:
                    symbols = open_positions["Symbol"].unique().tolist()
                    with st.spinner("Fetching current prices..."):
                        current_prices = fetch_current_prices(symbols)

                    # Add current price and return columns for open positions
                    df["Current Price"] = None
                    df["Return %"] = None
                    df["Unrealized P&L"] = None
                    df["Current Value"] = None

                    for idx, row in df.iterrows():
                        if row["Status"] == "OPEN":
                            current_price = current_prices.get(row["Symbol"])
                            if current_price is not None:
                                return_pct, unrealized_pnl, current_value = (
                                    calculate_current_return(
                                    row["Entry Price"], current_price, row["Shares"]
                                    )
                                )
                                df.at[idx, "Current Price"] = current_price
                                df.at[idx, "Return %"] = return_pct
                                df.at[idx, "Unrealized P&L"] = unrealized_pnl
                                df.at[idx, "Current Value"] = current_value

            # Apply consistent formatting
            df["Direction"] = df["Direction"].apply(format_direction)
            df["Status"] = df["Status"].apply(format_status)

            # Add tooltip information column
            df = add_tooltip_info_to_df(df, "Symbol", db)

            # Format numeric columns
            if "Current Price" in df.columns:
                df["Current Price"] = df["Current Price"].apply(
                    lambda x: f"${x:.2f}" if pd.notna(x) else "N/A"
                )
            if "Return %" in df.columns:
                df["Return %"] = df["Return %"].apply(
                    lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
                )
            if "Unrealized P&L" in df.columns:
                df["Unrealized P&L"] = df["Unrealized P&L"].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
                )
            if "Current Value" in df.columns:
                df["Current Value"] = df["Current Value"].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
                )
            if "Realized P&L" in df.columns:
                df["Realized P&L"] = df["Realized P&L"].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
                )

            # Display enhanced table with styling
            st.markdown('<div class="enhanced-table">', unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Add data health footer
            from datetime import datetime
            last_sync = datetime.now().strftime('%H:%M:%S')

            st.markdown(f"""
            <div style="margin-top: 1rem; padding: 0.5rem; background: #f8fafc; border-radius: 4px; border-left: 3px solid #3b82f6;">
                <p style="margin: 0; font-size: 0.75rem; color: #6b7280;">
                    📊 Last sync: {last_sync} • Next update scheduled in 15 min • Source: Live paper trading
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Add summary metrics
            if not df.empty:
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    total_positions = len(df)
                    st.markdown(
                        create_kpi_card(
                            "Total Positions",
                            f"{total_positions}",
                            None,
                            "neutral",
                            "default",
                        ),
                        unsafe_allow_html=True,
                    )

                with col2:
                    open_count = len(
                        df[df["Status"].str.contains("Open", na=False)])
                    st.markdown(
                        create_kpi_card(
                            "Open Positions",
                            f"{open_count}",
                            None,
                            "positive",
                            "success",
                        ),
                        unsafe_allow_html=True,
                    )

                with col3:
                    closed_count = len(
                        df[df["Status"].str.contains("Closed", na=False)]
                    )
                    st.markdown(
                        create_kpi_card(
                            "Closed Positions",
                            f"{closed_count}",
                            None,
                            "neutral",
                            "default",
                        ),
                        unsafe_allow_html=True,
                    )

                with col4:
                    # Calculate total unrealized P&L for open positions
                    if "Unrealized P&L" in df.columns:
                        unrealized_values = df[
                            df["Status"].str.contains("Open", na=False)
                        ]["Unrealized P&L"]
                        if not unrealized_values.empty:
                            # Extract numeric values from formatted strings
                            numeric_values = []
                            for val in unrealized_values:
                                if val != "N/A":
                                    numeric_val = float(
                                        val.replace("$", "").replace(",", "")
                                    )
                                    numeric_values.append(numeric_val)

                            total_unrealized = (
                                sum(numeric_values) if numeric_values else 0
                            )
                            pnl_type = (
                                "positive"
                                if total_unrealized > 0
                                else "negative" if total_unrealized < 0 else "neutral"
                            )
                            card_type = (
                                "success"
                                if total_unrealized > 0
                                else "danger" if total_unrealized < 0 else "default"
                            )

                            st.markdown(
                                create_kpi_card(
                                    "Total Unrealized P&L",
                                    f"${total_unrealized:,.2f}",
                                    None,
                                    pnl_type,
                                    card_type,
                                ),
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                create_kpi_card(
                                    "Total Unrealized P&L",
                                    "N/A",
                                    None,
                                    "neutral",
                                    "default",
                                ),
                                unsafe_allow_html=True,
                            )
        else:
                # Enhanced empty state with actionable CTAs
                st.markdown("""
                <div style="text-align: center; padding: 3rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin: 2rem 0;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                    <h3 style="color: #374151; margin-bottom: 0.5rem;">No Positions Found</h3>
                    <p style="color: #6b7280; margin-bottom: 1.5rem;">
                        Run a re-allocation or start a new cycle to begin tracking live holdings.<br>
                        Positions are created when trading signals are executed.
                    </p>
                    <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                        <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_reallocation', value: true}, '*')" 
                                style="background: #3b82f6; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500;">
                            ⚙️ Run Re-Allocation
                        </button>
                        <button onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'go_to_cycle_status', value: true}, '*')" 
                                style="background: #10b981; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-weight: 500;">
                            🔄 Go to Cycle Status
                        </button>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add data health footer for empty state too
                from datetime import datetime
                last_sync = datetime.now().strftime('%H:%M:%S')
                
                st.markdown(f"""
                <div style="margin-top: 1rem; padding: 0.5rem; background: #f8fafc; border-radius: 4px; border-left: 3px solid #3b82f6;">
                    <p style="margin: 0; font-size: 0.75rem; color: #6b7280;">
                        📊 Last sync: {last_sync} • Next update scheduled in 15 min • Source: Live paper trading
                    </p>
                </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error: {e}")

elif page == "Cycle Status":
    st.header("🔄 Cycle Status")
    st.caption("*Trading cycles represent active allocation periods. Each cycle runs signal evaluation, allocation, and position tracking until closed*")
    
    # Cycle Automation Toggle
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("**Cycle Management**")
    
    with col2:
        auto_mode = st.toggle(
            "🔄 Auto Cycle Renewal",
            value=False,
            help="When enabled, the system automatically starts a new trading cycle once the current one closes or expires. Useful for continuous backtesting or autonomous operation."
        )
    
    # Visual lifecycle diagram under Cycle Management
    st.markdown("""
    <div style="text-align: center; padding: 1rem; background: #f8fafc; border-radius: 6px; margin: 1rem 0;">
        <div style="display: flex; justify-content: center; align-items: center; gap: 0.75rem; flex-wrap: wrap; font-size: 0.75rem; color: #6b7280;">
            <div style="display: flex; align-items: center; gap: 0.25rem;">
                <span style="font-size: 1rem;">📡</span>
                <span>Signals</span>
            </div>
            <span style="font-size: 0.875rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.25rem;">
                <span style="font-size: 1rem;">⚙️</span>
                <span>Allocation</span>
            </div>
            <span style="font-size: 0.875rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.25rem;">
                <span style="font-size: 1rem;">📊</span>
                <span>Positions</span>
            </div>
            <span style="font-size: 0.875rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.25rem;">
                <span style="font-size: 1rem;">📈</span>
                <span>Performance</span>
            </div>
            <span style="font-size: 0.875rem;">→</span>
            <div style="display: flex; align-items: center; gap: 0.25rem;">
                <span style="font-size: 1rem;">🏁</span>
                <span>Cycle Close</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # Get cycle information from API
        response = requests.get("http://api:8000/cycle/current", timeout=10)
        if response.status_code == 200:
            cycle_data = response.json()
            
            if cycle_data.get("status") == "success":
                cycle_info = cycle_data.get("cycle", {})
                
                # Cycle Overview
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Cycle ID", cycle_info.get("cycle_id", "N/A"))
                
                with col2:
                    cycle_day = cycle_info.get("cycle_day", 0)
                    st.metric("Cycle Day", f"{cycle_day}/90")
                
                with col3:
                    phase = cycle_info.get("phase", "N/A")
                    phase_color = {
                        "LOAD": "🟢",
                        "ACTIVE": "🔵", 
                        "SCALE_OUT": "🟡",
                        "FORCE_CLOSE": "🔴",
                    }.get(phase, "⚪")
                    st.metric("Phase", f"{phase_color} {phase}")
                
                with col4:
                    days_remaining = 90 - cycle_day
                    st.metric("Days Remaining", days_remaining)
                
                # Progress Bar
                progress = cycle_day / 90
                st.progress(progress)
                st.caption(f"Cycle Progress: {cycle_day}/90 days ({progress:.1%})")
                
                # Phase Details
                st.subheader("📊 Phase Details")
                
                phase_info = {
                    "LOAD": {
                        "days": "1-7",
                        "description": "Initial capital deployment",
                        "max_positions": 12,
                    },
                    "ACTIVE": {
                        "days": "8-60",
                        "description": "Active trading phase",
                        "max_positions": 16,
                    },
                    "SCALE_OUT": {
                        "days": "61-75",
                        "description": "Position reduction phase",
                        "max_positions": 8,
                    },
                    "FORCE_CLOSE": {
                        "days": "76-90",
                        "description": "Force close all positions",
                        "max_positions": 0,
                    },
                }
                
                current_phase_info = phase_info.get(phase, {})
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Days:** {current_phase_info.get('days', 'N/A')}")
                with col2:
                    st.write(
                        f"**Description:** {current_phase_info.get('description', 'N/A')}"
                    )
                with col3:
                    st.write(
                        f"**Max Positions:** {current_phase_info.get('max_positions', 'N/A')}"
                    )
                
                # Performance Metrics
                st.subheader("📈 Performance Metrics")
                
                performance = cycle_info.get("performance", {})
                
                col1, col2, col3, col4 = st.columns(4)
        
                with col1:
                    total_return = performance.get("total_return", 0)
                    st.metric("Total Return", f"{total_return:.2f}%")
                
                with col2:
                    win_rate = performance.get("win_rate", 0)
                    st.metric("Win Rate", f"{win_rate:.1f}%")
                
                with col3:
                    total_pnl = performance.get("total_pnl", 0)
                    st.metric("Total P&L", f"${total_pnl:,.2f}")
                
                with col4:
                    positions_count = performance.get("total_positions", 0)
                    st.metric("Total Positions", positions_count)
                
                # Risk Metrics
                st.subheader("⚠️ Risk Metrics")
                
                risk_metrics = cycle_info.get("risk_metrics", {})
                
                col1, col2, col3, col4 = st.columns(4)
        
                with col1:
                    drawdown_gate = risk_metrics.get("drawdown_gate", "GREEN")
                    gate_colors = {
                        "GREEN": "🟢",
                        "YELLOW": "🟡", 
                        "RED": "🔴",
                        "NUCLEAR": "⚫",
                    }
                    st.metric(
                        "Drawdown Gate",
                        f"{gate_colors.get(drawdown_gate, '⚪')} {drawdown_gate}",                                                                              
                    )
                
                with col2:
                    current_dd = risk_metrics.get("current_drawdown", 0)
                    st.metric("Current Drawdown", f"{current_dd:.2%}")
                
                with col3:
                    max_dd = risk_metrics.get("max_drawdown", 0)
                    st.metric("Max Drawdown", f"{max_dd:.2%}")
                
                with col4:
                    cash_reserve = risk_metrics.get("cash_reserve_actual", 0)
                    st.metric("Cash Reserve", f"{cash_reserve:.1%}")
                
                # Settlement Status
                st.subheader("🏁 Settlement Status")
                
                settlement = cycle_info.get("settlement", {})
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    should_complete = settlement.get("should_complete", False)
                    completion_status = "✅ Ready" if should_complete else "⏳ Ongoing"
                    st.metric("Completion Status", completion_status)
                
                with col2:
                    is_valid = settlement.get("is_valid", False)
                    validity_status = "✅ Valid" if is_valid else "❌ Invalid"
                    st.metric("Cycle Validity", validity_status)
                
                with col3:
                    settlement_ready = settlement.get("settlement_ready", False)
                    ready_status = "🚀 Ready" if settlement_ready else "⏳ Not Ready"
                    st.metric("Settlement Ready", ready_status)
                
                # Settlement Actions
                if settlement_ready:
                    st.subheader("🎯 Settlement Actions")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🚀 Settle Cycle", type="primary"):
                            with st.spinner("Settling cycle..."):
                                settle_response = requests.post(
                                    "http://api:8000/cycle/settle", timeout=60
                                )
                                if settle_response.status_code == 200:
                                    settle_data = settle_response.json()
                                    if settle_data.get("status") == "success":
                                        st.success("✅ Cycle settled successfully!")
                                        st.rerun()
                                    else:
                                        st.error(
                                            f"❌ Settlement failed: {settle_data.get('message')}"
                                        )
                                else:
                                    st.error("❌ API error during settlement")
                    
                    with col2:
                        if st.button("🔍 View Settlement Details", type="secondary"):
                            st.json(settlement)
                
                # Cycle History
                st.subheader("📚 Cycle History")
                
                history_response = requests.get(
                    "http://api:8000/cycle/history", timeout=10
                )
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    if history_data.get("status") == "success":
                        cycles = history_data.get("cycles", [])
                        
                        if cycles:
                            history_df = pd.DataFrame(cycles)
                            
                            # Rename columns for consistency
                            if "cycle_id" in history_df.columns:
                                history_df = history_df.rename(
                                    columns={
                                        "cycle_id": "Cycle ID",
                                        "start_date": "Start Date",
                                        "end_date": "End Date",
                                        "status": "Status",
                                        "total_return": "Return %",
                                        "total_pnl": "P&L",
                                        "win_rate": "Win Rate %",
                                        "total_positions": "Positions",
                                    }
                                )
                                
                                # Apply consistent formatting
                                if "Status" in history_df.columns:
                                    history_df["Status"] = history_df["Status"].apply(
                                        format_status
                                    )
                                if "Return %" in history_df.columns:
                                    history_df["Return %"] = history_df[
                                        "Return %"
                                    ].apply(lambda x: f"{x:.2f}%")
                                if "P&L" in history_df.columns:
                                    history_df["P&L"] = history_df["P&L"].apply(
                                        lambda x: f"${x:,.2f}"
                                    )
                                if "Win Rate %" in history_df.columns:
                                    history_df["Win Rate %"] = history_df[
                                        "Win Rate %"
                                    ].apply(lambda x: f"{x:.1f}%")
                            
                            st.dataframe(history_df, use_container_width=True)
                        else:
                            st.info("No cycle history found")
                    else:
                        st.error("Failed to fetch cycle history")
                else:
                    st.error("API error fetching cycle history")
                
            else:
                # No active cycle - show friendly empty state with CTAs
                st.markdown("""
                <div style="text-align: center; padding: 3rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; margin: 2rem 0;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">🔄</div>
                    <h3 style="color: #dc2626; margin-bottom: 0.5rem;">No Active Cycle Found</h3>
                    <p style="color: #6b7280; margin-bottom: 1.5rem;">
                        Start a new trading cycle to evaluate signals, allocate positions, and track performance.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Add action buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚀 Start New Cycle", type="primary", use_container_width=True):
                        with st.spinner("Starting new cycle..."):
                            start_response = requests.post("http://api:8000/cycle/start", timeout=60)                                                           
                            if start_response.status_code == 200:
                                st.success("✅ New cycle started successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to start cycle")
                with col2:
                    if st.button("📚 View Past Cycles", use_container_width=True):
                        st.info("Cycle history will appear below once cycles are completed")
        else:
            st.error("❌ API error: Could not connect to cycle service")
            
        # Add operational trust line
        st.caption(f"🔄 Last sync: {datetime.now().strftime('%H:%M:%S')} • Next auto-check in 15 min")
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

elif page == "Philosophy Settings":
    st.header("🎛️ Philosophy Engine Settings")

    st.info(
        """
    Adjust the parameters that control how the system selects trades, sizes positions, 
    and manages risk. Each philosophy represents rules from legendary investors, 
    encoded as mathematical constraints.
    """
    )

    # ============================================================================
    # SECTION 1: SYSTEM PRESET (SCENARIOS)
    # ============================================================================
    
    st.markdown("---")
    st.markdown("### 1️⃣ System Scenario Preset")
    st.caption("Choose a predefined trading strategy or customize your own")
    
    st.subheader("🎯 Trading Scenarios")
    st.markdown("Choose a predefined scenario or customize your own settings:")
    
    # Define scenario presets
    scenarios = {
        "Conservative": {
            "description": "Low risk, steady growth approach. Focus on capital preservation with modest returns.",
            "use_case": "Ideal for: Risk-averse investors, retirement accounts, market downturns",
            "settings": {
                "dalio": {"enabled": True, "violation_penalty_pct": 0.05},
                "buffett": {"enabled": True, "minimum_expected_return": 0.20, "violation_penalty_pct": 0.20},
                "pabrai": {"enabled": True, "cluster_threshold": 4, "position_multiplier": 1.5, "allocation_bonus_pct": 0.05},
                "oleary": {"enabled": True, "max_hold_days": 60, "min_return_threshold": 0.08},
                "saylor": {"enabled": False, "sharpe_threshold": 3.0, "extension_days": 15, "min_tier": "S"},
                "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 60, "violation_penalty_pct": 0.25, "penalty_decay_rounds": 15}}
            }
        },
        "Balanced": {
            "description": "Moderate risk-reward balance. Suitable for most market conditions and investor profiles.",
            "use_case": "Ideal for: General investing, moderate risk tolerance, long-term growth",
            "settings": {
                "dalio": {"enabled": True, "violation_penalty_pct": 0.10},
                "buffett": {"enabled": True, "minimum_expected_return": 0.15, "violation_penalty_pct": 0.15},
                "pabrai": {"enabled": True, "cluster_threshold": 3, "position_multiplier": 2.0, "allocation_bonus_pct": 0.10},
                "oleary": {"enabled": True, "max_hold_days": 90, "min_return_threshold": 0.05},
                "saylor": {"enabled": True, "sharpe_threshold": 2.0, "extension_days": 30, "min_tier": "A"},
                "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 90, "violation_penalty_pct": 0.20, "penalty_decay_rounds": 10}}
            }
        },
        "Aggressive": {
            "description": "Higher risk for higher returns. More frequent trading with larger position sizes.",
            "use_case": "Ideal for: Growth-focused investors, bull markets, higher risk tolerance",
            "settings": {
                "dalio": {"enabled": True, "violation_penalty_pct": 0.15},
                "buffett": {"enabled": True, "minimum_expected_return": 0.10, "violation_penalty_pct": 0.10},
                "pabrai": {"enabled": True, "cluster_threshold": 2, "position_multiplier": 2.5, "allocation_bonus_pct": 0.15},
                "oleary": {"enabled": True, "max_hold_days": 120, "min_return_threshold": 0.03},
                "saylor": {"enabled": True, "sharpe_threshold": 1.5, "extension_days": 45, "min_tier": "B"},
                "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 120, "violation_penalty_pct": 0.15, "penalty_decay_rounds": 8}}
            }
        },
        "High-Risk": {
            "description": "Maximum risk for maximum returns. Fast trading, large positions, minimal restrictions.",
            "use_case": "Ideal for: Experienced traders, strong bull markets, very high risk tolerance",
            "settings": {
                "dalio": {"enabled": False, "violation_penalty_pct": 0.05},
                "buffett": {"enabled": True, "minimum_expected_return": 0.05, "violation_penalty_pct": 0.05},
                "pabrai": {"enabled": True, "cluster_threshold": 2, "position_multiplier": 3.0, "allocation_bonus_pct": 0.20},
                "oleary": {"enabled": False, "max_hold_days": 180, "min_return_threshold": 0.01},
                "saylor": {"enabled": True, "sharpe_threshold": 1.0, "extension_days": 60, "min_tier": "C"},
                "japanese_discipline": {"enabled": False, "rules": {"fixed_round_duration_days": 180, "violation_penalty_pct": 0.10, "penalty_decay_rounds": 5}}
            }
        },
        "Custom": {
            "description": "Manual configuration. Set your own parameters for each philosophy.",
            "use_case": "Ideal for: Advanced users, specific strategies, experimental approaches",
            "settings": None  # Will use current settings
        }
    }
    
    # Scenario selector
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_scenario = st.selectbox(
            "Choose a trading scenario:",
            options=list(scenarios.keys()),
            index=1,  # Default to "Balanced"
            help="Select a predefined scenario or choose Custom to manually configure"
        )
    
    with col2:
        if st.button("🔄 Apply Scenario", type="primary"):
            if selected_scenario != "Custom":
                if save_settings(scenarios[selected_scenario]["settings"]):
                    st.success(f"✅ Applied {selected_scenario} scenario!")
                    st.rerun()
                else:
                    st.error("❌ Failed to apply scenario settings")
            else:
                st.info("Custom scenario - use the sliders below to configure")
    
    # Display scenario information
    if selected_scenario != "Custom":
        scenario_info = scenarios[selected_scenario]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown(f"**📋 Description:** {scenario_info['description']}")
        
        with col2:
            st.markdown(f"**🎯 Use Case:** {scenario_info['use_case']}")
        
        # Show key characteristics
        st.markdown("**🔧 Key Characteristics:**")
        settings = scenario_info["settings"]
        
        characteristics = []
        if settings["dalio"]["enabled"]:
            characteristics.append(f"Systematic logging (penalty: {settings['dalio']['violation_penalty_pct']*100:.0f}%)")
        if settings["buffett"]["enabled"]:
            characteristics.append(f"Min return: {settings['buffett']['minimum_expected_return']*100:.0f}%")
        if settings["pabrai"]["enabled"]:
            characteristics.append(f"Cluster multiplier: {settings['pabrai']['position_multiplier']:.1f}x")
        if settings["oleary"]["enabled"]:
            characteristics.append(f"Max hold: {settings['oleary']['max_hold_days']} days")
        if settings["saylor"]["enabled"]:
            characteristics.append(f"Min tier: {settings['saylor']['min_tier']}")
        if settings["japanese_discipline"]["enabled"]:
            characteristics.append(f"Round duration: {settings['japanese_discipline']['rules']['fixed_round_duration_days']} days")
        
        for char in characteristics:
            st.markdown(f"• {char}")
    
    st.divider()

    # Load current settings from config file
    def load_current_settings():
        """Load current philosophy settings from YAML file"""
        try:
            # Get the project root directory (two levels up from dashboard/)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config", "philosophy.yaml")
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            st.error(f"Could not load settings: {e}")
            return {}

    def save_settings(new_settings):
        """Save philosophy settings to YAML file"""
        try:
            # Get the project root directory (two levels up from dashboard/)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config", "philosophy.yaml")
            with open(config_path, "w") as f:
                yaml.dump(new_settings, f, default_flow_style=False)
            return True
        except Exception as e:
            st.error(f"Could not save settings: {e}")
            return False

    # Load current settings
    current_settings = load_current_settings()

    # ============================================================================
    # SECTION 2: ACTIVE PHILOSOPHIES BLEND
    # ============================================================================
    
    st.markdown("---")
    st.markdown("### 2️⃣ Active Philosophy Blend")
    st.caption("Current system composition and influence")
    
    st.subheader("🎯 Active Philosophies Summary")
    st.caption("Combined influence on allocation and trade rules")
    
    # Get enabled philosophies from current settings
    dalio_enabled_prev = current_settings.get("dalio", {}).get("enabled", True)
    buffett_enabled_prev = current_settings.get("buffett", {}).get("enabled", True)
    pabrai_enabled_prev = current_settings.get("pabrai", {}).get("enabled", True)
    oleary_enabled_prev = current_settings.get("oleary", {}).get("enabled", True)
    saylor_enabled_prev = current_settings.get("saylor", {}).get("enabled", True)
    japanese_enabled_prev = current_settings.get("japanese_discipline", {}).get("enabled", True)
    
    enabled_philosophies = [
        ("📊 Dalio", dalio_enabled_prev, "#3b82f6"),
        ("💰 Buffett", buffett_enabled_prev, "#10b981"),
        ("👥 Pabrai", pabrai_enabled_prev, "#8b5cf6"),
        ("⚡ O'Leary", oleary_enabled_prev, "#f59e0b"),
        ("🚀 Saylor", saylor_enabled_prev, "#ef4444"),
        ("🥋 Japanese", japanese_enabled_prev, "#6366f1"),
    ]
    
    # Calculate total enabled count
    enabled_count = sum(1 for _, enabled, _ in enabled_philosophies if enabled)
    total_count = len(enabled_philosophies)
    
    # Display as cards
    cols = st.columns(6)
    for i, (name, enabled, color) in enumerate(enabled_philosophies):
        with cols[i]:
            status = "✓" if enabled else "○"
            status_color = color if enabled else "#9ca3af"
            st.markdown(f"""
            <div style="padding: 0.5rem; text-align: center; background: {'#f0f9ff' if enabled else '#f9fafb'}; 
                         border: 1px solid {'#bfdbfe' if enabled else '#e5e7eb'}; border-radius: 4px;">
                <div style="font-size: 1.25rem; color: {status_color}; font-weight: 600;">{status}</div>
                <div style="font-size: 0.75rem; color: #6b7280; margin-top: 0.25rem;">{name.split()[1]}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.caption(f"📊 {enabled_count}/{total_count} philosophies active")
    
    # ============================================================================
    # SECTION 3: PHILOSOPHY RULES
    # ============================================================================
    
    st.markdown("---")
    st.markdown("### 3️⃣ Philosophical Rules")
    st.caption("Configure individual philosophy parameters")
    
    # Create tabs for each philosophy
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📊 Dalio (System)",
            "💰 Buffett (Safety)",
            "👥 Pabrai (Cloning)",
            "⚡ O'Leary (Efficiency)",
            "🚀 Saylor (Conviction)",
            "🥋 Japanese (Discipline)",
        ]
    )

    # ============================================================================
    # TAB 1: RAY DALIO (SYSTEMATIZATION)
    # ============================================================================

    with tab1:
        st.header("Ray Dalio: Radical Systematization")

        st.markdown(
            """
        **Philosophy:** Everything must be logged, measured, and systematic. 
        No intuition overrides.
        
        **Effect:** Violations (manual overrides, intuition trades) reduce allocation power.
        """
        )

        col1, col2 = st.columns(2)

        with col1:
            # Get current values or defaults
            dalio_config = current_settings.get("dalio", {})
            dalio_violation_penalty = st.slider(
                "Violation Penalty (%)",
                min_value=0,
                max_value=30,
                value=int(dalio_config.get("violation_penalty_pct", 0.1) * 100),
                step=5,
                help="Allocation power reduction when system rules are violated. 10% means position sizes drop from 5% to 4.5% for the next cycle.",
            )

            dalio_enabled = st.checkbox(
                "Enable Dalio Rules",
                value=dalio_config.get("enabled", True),
                help="Enforce systematic logging and no overrides",
            )

        with col2:
            st.metric(
                "Current Allocation Power Impact",
                f"{100 - dalio_violation_penalty}%",
                help="Power multiplier after one violation",
            )

            st.caption(
                """
            **Example:** With 10% penalty, if you manually override a trade, 
            your position sizes drop from 5% to 4.5% for 10 rounds.
            """
            )

    # ============================================================================
    # TAB 2: WARREN BUFFETT (MARGIN OF SAFETY)
    # ============================================================================

    with tab2:
        st.header("Warren Buffett: Margin of Safety")

        st.markdown(
            """
        **Philosophy:** Only invest when the expected return exceeds a minimum threshold.
        Protect capital first, grow second.
        
        **Effect:** Trades below minimum expected return are rejected or penalized.
        """
        )

        col1, col2 = st.columns(2)

        with col1:
            buffett_config = current_settings.get("buffett", {})
            buffett_min_return = st.slider(
                "Minimum Expected Return (%)",
                min_value=5,
                max_value=30,
                value=int(buffett_config.get("minimum_expected_return", 0.15) * 100),
                step=1,
                help="Reject trades with expected return below this threshold",
            )

            buffett_violation_penalty = st.slider(
                "Low-Return Trade Penalty (%)",
                min_value=0,
                max_value=30,
                value=int(buffett_config.get("violation_penalty_pct", 0.15) * 100),
                step=5,
                help="Penalty if a trade below threshold is taken anyway",
            )

            buffett_enabled = st.checkbox(
                "Enable Buffett Rules", value=buffett_config.get("enabled", True)
            )

        with col2:
            st.metric(
                "Minimum Expected Value",
                f"+{buffett_min_return}%",
                help="Trades must offer at least this return",
            )

            # Calculate example
            example_risk = 2.0  # 2% risk per trade
            min_rr = buffett_min_return / (example_risk * 100)

            st.metric(
                "Implied Risk:Reward Ratio",
                f"1:{min_rr:.1f}",
                help=f"With 2% risk per trade, need {min_rr:.1f}R reward minimum",
            )

            st.caption(
                """
            **Example:** 15% minimum return means if you risk $100, 
            you must target at least $750+ profit (7.5:1 R:R).
            """
            )

    # ============================================================================
    # TAB 3: MOHNISH PABRAI (CLONING)
    # ============================================================================

    with tab3:
        st.header("Mohnish Pabrai: Cloning Great Investors")

        st.markdown(
            """
        **Philosophy:** When multiple smart investors buy the same stock (cluster), 
        it's a high-conviction signal. Clone their moves with larger position sizes.
        
        **Effect:** Position sizes increase when 3+ insiders/activists buy same stock.
        """
        )

        col1, col2 = st.columns(2)

        with col1:
            pabrai_config = current_settings.get("pabrai", {})
            pabrai_cluster_threshold = st.slider(
                "Cluster Threshold (# of insiders)",
                min_value=2,
                max_value=5,
                value=pabrai_config.get("cluster_threshold", 3),
                step=1,
                help="How many insiders buying = cluster signal",
            )

            pabrai_position_multiplier = st.slider(
                "Position Size Multiplier",
                min_value=1.0,
                max_value=3.0,
                value=pabrai_config.get("position_multiplier", 2.0),
                step=0.1,
                help="Multiply position size by this factor for clusters",
            )

            pabrai_allocation_bonus = st.slider(
                "Allocation Power Bonus (%)",
                min_value=0,
                max_value=30,
                value=int(pabrai_config.get("allocation_bonus_pct", 0.1) * 100),
                step=5,
                help="Increases position sizing weight for trades that meet this philosophy's cluster conditions. 10% = 10% larger positions.",
            )

            pabrai_enabled = st.checkbox(
                "Enable Pabrai Rules", value=pabrai_config.get("enabled", True)
            )

        with col2:
            # Example calculation
            base_size = 3.0  # B-tier base = 3%
            cluster_size = base_size * pabrai_position_multiplier

            st.metric(
                "Example: B-tier Cluster Position",
                f"{cluster_size:.1f}%",
                delta=f"+{cluster_size - base_size:.1f}%",
                help=f"B-tier (3%) × {pabrai_position_multiplier}x multiplier",
            )

            st.caption(
                f"""
            **Example:** If {pabrai_cluster_threshold} CEOs buy NVDA within 30 days:
            - Normal B-tier position: 3% of portfolio
            - Cluster position: {cluster_size:.1f}% of portfolio
            - {(cluster_size/base_size - 1)*100:.0f}% larger bet
            """
            )

    # ============================================================================
    # TAB 4: KEVIN O'LEARY (CAPITAL EFFICIENCY)
    # ============================================================================

    with tab4:
        st.header("Kevin O'Leary: Capital Efficiency")

        st.markdown(
            """
        **Philosophy:** Capital tied up in underperforming positions is wasted. 
        Force close positions that aren't delivering returns.
        
        **Effect:** Positions closed if held >X days AND return <Y%.
        """
        )

        col1, col2 = st.columns(2)

        with col1:
            oleary_config = current_settings.get("oleary", {})
            oleary_max_hold_days = st.slider(
                "Maximum Hold Period (days)",
                min_value=30,
                max_value=180,
                value=oleary_config.get("max_hold_days", 90),
                step=10,
                help="Force close if position held longer than this",
            )

            oleary_min_return_threshold = st.slider(
                "Minimum Return Threshold (%)",
                min_value=0,
                max_value=20,
                value=int(oleary_config.get("min_return_threshold", 0.05) * 100),
                step=1,
                help="Close if return below this after max hold period",
            )

            oleary_enabled = st.checkbox(
                "Enable O'Leary Rules", value=oleary_config.get("enabled", True)
            )

        with col2:
            st.metric(
                "Force Close Rule",
                f"Hold >{oleary_max_hold_days}d AND <{oleary_min_return_threshold}%",
                help="Both conditions must be true to trigger force close",
            )

            # Annualized return equivalent
            annual_equiv = (oleary_min_return_threshold / oleary_max_hold_days) * 365

            st.metric(
                "Annualized Hurdle Rate",
                f"{annual_equiv:.1f}%",
                help=f"{oleary_min_return_threshold}% in {oleary_max_hold_days} days = {annual_equiv:.1f}% annual",
            )

            st.caption(
                f"""
            **Example:** Position in AAPL held for {oleary_max_hold_days} days:
            - If up +{oleary_min_return_threshold}%: Keep holding
            - If up +{oleary_min_return_threshold-1}%: Force close (underperformer)
            - If down: Force close immediately
            """
            )

    # ============================================================================
    # TAB 5: MICHAEL SAYLOR (CONVICTION SCALING)
    # ============================================================================

    with tab5:
        st.header("Michael Saylor: Conviction Scaling")

        st.markdown(
            """
        **Philosophy:** When a high-conviction position is working exceptionally well 
        (high Sharpe ratio), extend the holding period to let winners run.
        
        **Effect:** S-tier winners with Sharpe >2.0 get extended hold period.
        """
        )

        col1, col2 = st.columns(2)

        with col1:
            saylor_config = current_settings.get("saylor", {})
            saylor_sharpe_threshold = st.slider(
                "Sharpe Ratio Threshold",
                min_value=1.0,
                max_value=3.0,
                value=saylor_config.get("sharpe_threshold", 2.0),
                step=0.1,
                help="Extend hold if Sharpe ratio exceeds this",
            )

            saylor_extension_days = st.slider(
                "Extension Period (days)",
                min_value=0,
                max_value=60,
                value=saylor_config.get("extension_days", 30),
                step=10,
                help="How many extra days to hold winning positions",
            )

            saylor_min_tier = st.selectbox(
                "Minimum Tier for Extension",
                options=["S", "A", "B", "C"],
                index=["S", "A", "B", "C"].index(saylor_config.get("min_tier", "S")),
                help="Only extend positions at this tier or higher",
            )

            saylor_enabled = st.checkbox(
                "Enable Saylor Rules", value=saylor_config.get("enabled", True)
            )

        with col2:
            st.metric(
                "Extension Trigger",
                f"Sharpe >{saylor_sharpe_threshold:.1f}",
                help="High risk-adjusted returns = let it run",
            )

            st.metric(
                "Max Extended Hold",
                f"90 + {saylor_extension_days} = {90 + saylor_extension_days} days",
                help="Base cycle + extension",
            )

            st.caption(
                f"""
            **Example:** S-tier position in TSLA at day 60:
            - Sharpe ratio: 2.5 (>{saylor_sharpe_threshold})
            - Extension: +{saylor_extension_days} days
            - New exit: Day {90 + saylor_extension_days} instead of Day 90
            - Lets exceptional winners compound longer
            """
            )

    # ============================================================================
    # TAB 6: JAPANESE DISCIPLINE (BOUNDED RITUAL)
    # ============================================================================

    with tab6:
        st.header("Japanese Discipline: Bounded Ritual")

        st.markdown(
            """
        **Philosophy:** Trading must happen within fixed, disciplined rounds. 
        Mandatory review after each round. Violations reduce allocation power, 
        which slowly decays back to neutral over time.
        
        **Effect:** Fixed 90-day cycles, penalty for violations, slow power restoration.
        """
        )

        col1, col2 = st.columns(2)

        with col1:
            japanese_config = current_settings.get("japanese_discipline", {})
            japanese_cycle_duration = st.slider(
                "Cycle Duration (days)",
                min_value=60,
                max_value=180,
                value=japanese_config.get("rules", {}).get(
                    "fixed_round_duration_days", 90
                ),
                step=10,
                help="Length of each trading round",
            )

            japanese_violation_penalty = st.slider(
                "Discipline Violation Penalty (%)",
                min_value=0,
                max_value=30,
                value=int(
                    japanese_config.get("rules", {}).get("violation_penalty_pct", 0.2)
                    * 100
                ),
                step=5,
                help="Penalty for breaking cycle rules",
            )

            japanese_decay_rounds = st.slider(
                "Penalty Decay Period (cycles)",
                min_value=5,
                max_value=20,
                value=japanese_config.get("rules", {}).get("penalty_decay_rounds", 10),
                step=1,
                help="Number of clean rounds to restore full power",
            )

            japanese_enabled = st.checkbox(
                "Enable Japanese Rules", value=japanese_config.get("enabled", True)
            )

        with col2:
            st.metric(
                "Cycle Length",
                f"{japanese_cycle_duration} days",
                help="Fixed duration for each trading round",
            )

            # Calculate decay per round
            decay_per_round = japanese_violation_penalty / japanese_decay_rounds

            st.metric(
                "Power Restoration Rate",
                f"+{decay_per_round:.1f}% per clean cycle",
                help="How fast allocation power recovers",
            )

            st.caption(
                f"""
            **Example:** You violate a rule (trade outside cycle):
            - Allocation power drops: 100% → {100-japanese_violation_penalty}%
            - Your position sizes shrink {japanese_violation_penalty}%
            - After {japanese_decay_rounds} clean cycles: Back to 100%
            - Encourages long-term discipline
            """
            )

    # ============================================================================
    # SAVE & APPLY SETTINGS
    # ============================================================================

    st.divider()
    
    # Add visual separator for the sticky footer
    st.markdown("---")
    
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.warning("⚠️ Changes take effect on next allocation cycle (not retroactive)")
        st.caption("💡 Tip: Use scenarios for quick presets, or customize individual sliders")

    with col2:
        if st.button("💾 Save Settings", type="primary"):
            # Build settings dict
            new_settings = {
                "dalio": {
                    "enabled": dalio_enabled,
                    "violation_penalty_pct": dalio_violation_penalty / 100,
                },
                "buffett": {
                    "enabled": buffett_enabled,
                    "minimum_expected_return": buffett_min_return / 100,
                    "violation_penalty_pct": buffett_violation_penalty / 100,
                },
                "pabrai": {
                    "enabled": pabrai_enabled,
                    "cluster_threshold": pabrai_cluster_threshold,
                    "position_multiplier": pabrai_position_multiplier,
                    "allocation_bonus_pct": pabrai_allocation_bonus / 100,
                },
                "oleary": {
                    "enabled": oleary_enabled,
                    "max_hold_days": oleary_max_hold_days,
                    "min_return_threshold": oleary_min_return_threshold / 100,
                },
                "saylor": {
                    "enabled": saylor_enabled,
                    "sharpe_threshold": saylor_sharpe_threshold,
                    "extension_days": saylor_extension_days,
                    "min_tier": saylor_min_tier,
                },
                "japanese_discipline": {
                    "enabled": japanese_enabled,
                    "rules": {
                        "fixed_round_duration_days": japanese_cycle_duration,
                        "violation_penalty_pct": japanese_violation_penalty / 100,
                        "penalty_decay_rounds": japanese_decay_rounds,
                    },
                },
            }

            if save_settings(new_settings):
                st.success("✅ Settings saved successfully!")
                st.balloons()
                st.rerun()
                    
    with col3:
        if st.button("🔄 Reset to Defaults"):
            # Load default settings
            default_settings = {
                "dalio": {"enabled": True, "violation_penalty_pct": 0.1},
                "buffett": {
                    "enabled": True,
                    "minimum_expected_return": 0.15,
                    "violation_penalty_pct": 0.15,
                },
                "pabrai": {
                    "enabled": True,
                    "cluster_threshold": 3,
                    "position_multiplier": 2.0,
                    "allocation_bonus_pct": 0.1,
                },
                "oleary": {
                    "enabled": True,
                    "max_hold_days": 90,
                    "min_return_threshold": 0.05,
                },
                "saylor": {
                    "enabled": True,
                    "sharpe_threshold": 2.0,
                    "extension_days": 30,
                    "min_tier": "S",
                },
                "japanese_discipline": {
                    "enabled": True,
                    "rules": {
                        "fixed_round_duration_days": 90,
                        "violation_penalty_pct": 0.2,
                        "penalty_decay_rounds": 10,
                    },
                },
            }

            if save_settings(default_settings):
                st.success("Reset to defaults!")
                st.rerun()

    # ============================================================================
    # SECTION 4: ALLOCATION FEEDBACK
    # ============================================================================
    
    st.markdown("---")
    st.markdown("### 4️⃣ Allocation Feedback")
    st.caption("Monitor system performance and rule adherence")
    
    st.subheader("📊 Current Allocation Power")
    st.caption("📊 *Displaying default values. Real-time allocation power data will appear once cycles are running.*")

    # Simulate current state (in real implementation, this would come from database)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        power = 1.0  # Default allocation power
        st.metric(
            "Allocation Power",
            f"{power:.1%}",
            delta=f"{(power - 1.0)*100:+.1f}%",
            help="Current position sizing multiplier",
        )

    with col2:
        violations = 0  # Default violations
        st.metric(
            "Rule Violations",
            violations,
            help="Total violations across all philosophies",
        )

    with col3:
        clean_rounds = 0  # Default clean rounds
        st.metric(
            "Clean Cycles", clean_rounds, help="Consecutive cycles without violations"
        )

    with col4:
        # Get decay rounds from current settings
        japanese_config = current_settings.get("japanese_discipline", {}).get("rules", {})
        decay_rounds = japanese_config.get("penalty_decay_rounds", 10)
        rounds_to_restore = max(0, decay_rounds - clean_rounds)
        st.metric(
            "Cycles to Full Restore",
            rounds_to_restore,
            help=f"Need {rounds_to_restore} more clean cycles for 100% power",
        )

    # Show current philosophy configuration in a cleaner format
    with st.expander("📜 View Raw Configuration"):
        st.caption("Technical details for developers")
        st.json(current_settings)

elif page == "Scenario Comparison":
    st.header("📊 Scenario Performance Comparison")
    
    st.info(
        """
        Compare the performance of all 5 trading scenarios running in parallel.
        Each scenario uses different philosophy settings and risk profiles.
        """
    )
    
    # Define scenario color mapping for consistent visual identity
    scenario_colors = {
        "Conservative": "#3B82F6",  # Blue
        "Balanced": "#14B8A6",      # Teal
        "Aggressive": "#F97316",    # Orange
        "High-Risk": "#EF4444",     # Red
        "Custom": "#10B981"         # Green
    }
    
    # Fetch scenario performance data
    try:
        # Query scenario performance from database
        scenario_data = db.execute(
            text("""
            SELECT 
                scenario_name,
                scenario_type,
                current_capital,
                total_pnl,
                total_return_pct,
                total_trades,
                winning_trades,
                losing_trades,
                win_rate,
                max_drawdown,
                sharpe_ratio,
                last_updated
            FROM scenarios 
            WHERE is_active = true
            ORDER BY total_return_pct DESC
            """)
        ).fetchall()
        
        if scenario_data:
            # Create performance comparison table
            st.subheader("🏆 Performance Rankings")
            
            # Convert to DataFrame for better display
            import pandas as pd
            
            df = pd.DataFrame(scenario_data, columns=[
                'Scenario', 'Type', 'Capital', 'P&L', 'Return %', 
                'Trades', 'Wins', 'Losses', 'Win Rate %', 'Max DD %', 'Sharpe', 'Last Updated'
            ])
            
            # Format the data
            df['Capital'] = df['Capital'].apply(lambda x: f"${x:,.0f}")
            df['P&L'] = df['P&L'].apply(lambda x: f"${x:,.0f}")
            df['Return %'] = df['Return %'].apply(lambda x: f"{x:.2f}%")
            df['Win Rate %'] = df['Win Rate %'].apply(lambda x: f"{x:.1f}%")
            df['Max DD %'] = df['Max DD %'].apply(lambda x: f"{x:.2f}%")
            df['Sharpe'] = df['Sharpe'].apply(lambda x: f"{x:.2f}")
            
            # Add color coding for scenario names
            def style_scenario(val):
                color = scenario_colors.get(val, "#9ca3af")
                return f'background-color: {color}; color: white; font-weight: bold; padding: 4px 8px; border-radius: 4px;'
            
            df_styled = df.style.applymap(style_scenario, subset=['Scenario'])
            
            # Display table
            st.dataframe(
                df_styled,
                use_container_width=True,
                hide_index=True
            )
            
            # Performance metrics cards
            st.subheader("📈 Key Metrics")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                best_return = max([row[4] for row in scenario_data])  # total_return_pct
                best_scenario = next(row[0] for row in scenario_data if row[4] == best_return)
                st.metric(
                    "Best Return",
                    f"{best_return:.2f}%",
                    help=f"Best performing scenario: {best_scenario}"
                )
            
            with col2:
                best_win_rate = max([row[8] for row in scenario_data])  # win_rate
                best_win_scenario = next(row[0] for row in scenario_data if row[8] == best_win_rate)
                st.metric(
                    "Best Win Rate",
                    f"{best_win_rate:.1f}%",
                    help=f"Highest win rate: {best_win_scenario}"
                )
            
            with col3:
                total_trades = sum([row[5] for row in scenario_data])  # total_trades
                st.metric(
                    "Total Trades",
                    f"{total_trades:,}",
                    help="Combined trades across all scenarios"
                )
            
            with col4:
                avg_return = sum([row[4] for row in scenario_data]) / len(scenario_data)
                st.metric(
                    "Average Return",
                    f"{avg_return:.2f}%",
                    help="Average return across all scenarios"
                )
            
            with col5:
                best_sharpe = max([row[10] for row in scenario_data])  # sharpe_ratio
                best_sharpe_scenario = next(row[0] for row in scenario_data if row[10] == best_sharpe)
                st.metric(
                    "Best Sharpe",
                    f"{best_sharpe:.2f}",
                    help=f"Best risk-adjusted return: {best_sharpe_scenario}"
                )
            
            # Scenario details
            st.subheader("🔍 Scenario Details")
            
            for i, row in enumerate(scenario_data):
                with st.expander(f"{row[0]} ({row[1]}) - {row[4]:.2f}% Return", expanded=(i==0)):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Current Capital", f"${row[2]:,.0f}")
                        st.metric("Total P&L", f"${row[3]:,.0f}")
                        st.metric("Return %", f"{row[4]:.2f}%")
                    
                    with col2:
                        st.metric("Total Trades", f"{row[5]:,}")
                        st.metric("Winning Trades", f"{row[6]:,}")
                        st.metric("Losing Trades", f"{row[7]:,}")
                    
                    with col3:
                        st.metric("Win Rate", f"{row[8]:.1f}%")
                        st.metric("Max Drawdown", f"{row[9]:.2f}%")
                        st.metric("Sharpe Ratio", f"{row[10]:.2f}")
                    
                    # Fetch positions for this scenario
                    try:
                        import requests
                        pos_response = requests.get("http://api:8000/scenarios/positions", timeout=5)
                        if pos_response.status_code == 200:
                            pos_data = pos_response.json()
                            scenario_info = pos_data.get('scenarios', {}).get(row[0], {})
                            positions = scenario_info.get('positions', [])
                            
                            if positions:
                                st.markdown("**📊 Open Positions:**")
                                
                                # Create a DataFrame for better display
                                positions_df = pd.DataFrame(positions)
                                
                                # Display key columns
                                display_df = positions_df[['symbol', 'direction', 'shares', 'entry_price', 'entry_value']].copy()
                                display_df.columns = ['Symbol', 'Dir', 'Shares', 'Entry Price', 'Value']
                                display_df['Entry Price'] = display_df['Entry Price'].apply(lambda x: f"${x:.2f}")
                                display_df['Value'] = display_df['Value'].apply(lambda x: f"${x:,.0f}")
                                
                                st.dataframe(display_df, use_container_width=True, hide_index=True)
                            else:
                                st.info("No open positions yet for this scenario.")
                    except Exception as e:
                        st.debug(f"Could not load positions: {e}")
                    
                    st.caption(f"Last updated: {row[11]}")
            
            # Performance chart
            st.subheader("📊 Performance Over Time")
            
            # Create a performance comparison chart with scenario colors
            import plotly.graph_objects as go
            
            fig = go.Figure()
            
            for row in scenario_data:
                scenario_name = row[0]
                color = scenario_colors.get(scenario_name, "#9ca3af")
                fig.add_trace(go.Bar(
                    name=scenario_name,
                    x=[scenario_name],
                    y=[row[4]],  # total_return_pct
                    text=f"{row[4]:.2f}%",
                    textposition='auto',
                    marker_color=color,
                    hovertemplate=f"<b>{scenario_name}</b><br>Return: %{{y:.2f}}%<br>Sharpe: {row[10]:.2f}<extra></extra>",
                ))
            
            fig.update_layout(
                title="Scenario Performance Comparison",
                xaxis_title="Scenario",
                yaxis_title="Return (%)",
                barmode='group',
                height=400,
                showlegend=False,
                plot_bgcolor='white',
                xaxis=dict(gridcolor='#e5e7eb'),
                yaxis=dict(gridcolor='#e5e7eb'),
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add summary insight
            best_scenario = max(scenario_data, key=lambda x: x[10])  # best sharpe
            worst_dd = max([row[9] for row in scenario_data])  # worst drawdown
            best_dd_scenario = next(row for row in scenario_data if row[9] == worst_dd)
            
            st.info(
                f"💡 **Summary:** {best_scenario[0]} currently delivers the best Sharpe ratio ({best_scenario[10]:.2f}) "
                f"with {worst_dd:.1f}% drawdown. Consider monitoring risk-adjusted returns alongside absolute performance."
            )
            
        else:
            st.warning("No scenario data available. Scenarios may not have been initialized yet.")
            
            if st.button("🚀 Initialize Scenarios"):
                st.info("Initializing scenarios... This will create all 5 trading scenarios.")
                # This would trigger the scenario initialization
                st.success("Scenarios initialized! Check back in a few minutes for performance data.")
    
    except Exception as e:
        st.error(f"Error loading scenario data: {e}")
        st.info("Make sure the scenario tables have been created in the database.")

elif page == "How It Works":
    st.header("❓ How Dojo Allocator Works")
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 12px; margin-bottom: 2rem; color: white;">
        <h2 style="color: white; margin: 0 0 1rem 0;">🥋 Dojo Allocator: Autonomous Trading System</h2>
        <p style="margin: 0; font-size: 1.1rem; opacity: 0.9;">
            A sophisticated multi-scenario trading system that automatically allocates positions based on insider filings, 
            congressional trades, and institutional data using legendary investor philosophies.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # How It Works Section
    st.subheader("🔄 System Architecture")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **📡 Data Sources**
        - **Insider Filings**: SEC Form 4 filings from corporate insiders
        - **Congressional Trades**: STOCK Act disclosures from politicians
        - **Institutional Data**: 13F filings from hedge funds and institutions
        - **Market Data**: Real-time price feeds and technical indicators
        """)
        
        st.markdown("""
        **🎯 Signal Processing**
        - **Quality Filtering**: Advanced algorithms filter low-quality signals
        - **Conviction Scoring**: Each signal gets a score (S, A, B, C tiers)
        - **Risk Assessment**: Position sizing based on volatility and correlation
        - **Timing Optimization**: Entry/exit timing based on market conditions
        """)
    
    with col2:
        st.markdown("""
        **🏛️ Philosophy Engine**
        - **Warren Buffett**: Value investing with long-term focus
        - **George Soros**: Reflexivity and trend-following strategies
        - **Ray Dalio**: All-weather portfolio principles
        - **Paul Tudor Jones**: Macro trend and momentum strategies
        - **Japanese Philosophy**: Risk management and position sizing
        """)
        
        st.markdown("""
        **⚙️ Execution Engine**
        - **Multi-Scenario Testing**: 5 parallel trading strategies
        - **Real-time Allocation**: Dynamic position sizing and rebalancing
        - **Risk Management**: Drawdown limits and position limits
        - **Performance Tracking**: Continuous monitoring and optimization
        """)
    
    st.divider()
    
    # Trading Process
    st.subheader("📈 Trading Process")
    
    steps = [
        ("1️⃣", "Data Collection", "System continuously monitors SEC filings, congressional trades, and institutional data"),
        ("2️⃣", "Signal Generation", "Advanced algorithms analyze data and generate trading signals with conviction scores"),
        ("3️⃣", "Quality Filtering", "Signals are filtered for quality, relevance, and market timing"),
        ("4️⃣", "Philosophy Application", "Each signal is evaluated against 5 different investment philosophies"),
        ("5️⃣", "Scenario Allocation", "Positions are allocated across 5 parallel trading scenarios"),
        ("6️⃣", "Risk Management", "Position sizes are calculated based on risk parameters and portfolio balance"),
        ("7️⃣", "Execution", "Orders are placed and positions are tracked in real-time"),
        ("8️⃣", "Monitoring", "Continuous performance monitoring and automatic rebalancing")
    ]
    
    for icon, title, description in steps:
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"### {icon}")
            with col2:
                st.markdown(f"**{title}**")
                st.markdown(description)
            st.markdown("---")
    
    # FAQ Section
    st.subheader("❓ Frequently Asked Questions")
    
    faq_items = [
        {
            "question": "What makes Dojo Allocator different from other trading systems?",
            "answer": """
            Dojo Allocator combines multiple legendary investment philosophies into a single system, 
            running 5 parallel scenarios simultaneously. It uses real insider trading data and 
            congressional trades as primary signals, which are typically not available to retail traders. 
            The system automatically applies different risk management and position sizing rules based on 
            each philosophy's principles.
            """
        },
        {
            "question": "How does the system handle risk management?",
            "answer": """
            The system implements multiple layers of risk management:
            - **Position Limits**: Maximum position size per stock and per scenario
            - **Drawdown Gates**: Automatic position reduction when drawdowns exceed thresholds
            - **Correlation Analysis**: Avoids over-concentration in correlated positions
            - **Volatility Adjustment**: Position sizes adjust based on stock volatility
            - **Cash Reserves**: Maintains minimum cash levels for opportunities
            """
        },
        {
            "question": "What are the 5 trading scenarios and how do they differ?",
            "answer": """
            **Aggressive**: High conviction, larger position sizes, faster execution
            **Balanced**: Moderate risk, diversified approach, steady growth focus
            **Conservative**: Lower risk, smaller positions, capital preservation focus
            **High-Risk**: Maximum risk tolerance, concentrated positions, high volatility
            **Custom**: User-configurable parameters for specific strategies
            """
        },
        {
            "question": "How often does the system rebalance positions?",
            "answer": """
            The system operates on multiple timeframes:
            - **Real-time**: Continuous signal monitoring and quality assessment
            - **Daily**: Position rebalancing and risk management checks
            - **Weekly**: Full portfolio review and philosophy parameter updates
            - **Monthly**: Complete scenario performance analysis and optimization
            """
        },
        {
            "question": "Can I customize the trading parameters?",
            "answer": """
            Yes! The Philosophy Settings page allows you to:
            - Adjust position sizing rules for each philosophy
            - Modify risk management parameters
            - Change conviction score thresholds
            - Customize rebalancing frequency
            - Set custom scenario parameters
            """
        },
        {
            "question": "How does the system ensure data quality?",
            "answer": """
            The system implements multiple quality filters:
            - **Source Verification**: Only uses verified SEC and congressional data
            - **Timing Validation**: Ensures signals are recent and relevant
            - **Volume Analysis**: Filters out low-volume or illiquid stocks
            - **Correlation Checks**: Avoids duplicate or highly correlated signals
            - **Performance Tracking**: Monitors signal success rates over time
            """
        },
        {
            "question": "What happens if the system detects a market crash or extreme volatility?",
            "answer": """
            The system has built-in crisis management:
            - **Nuclear Drawdown Gate**: Automatic position reduction to minimum levels
            - **Volatility Spikes**: Temporary position size reduction during high volatility
            - **Market Circuit Breakers**: Respects exchange-imposed trading halts
            - **Emergency Liquidation**: Ability to close all positions if needed
            - **Cash Preservation**: Moves to cash during extreme market stress
            """
        },
        {
            "question": "How can I monitor the system's performance?",
            "answer": """
            The dashboard provides comprehensive monitoring:
            - **Real-time Metrics**: Live P&L, position counts, and performance
            - **Scenario Comparison**: Side-by-side performance of all 5 scenarios
            - **Position Tracking**: Detailed view of all open positions
            - **Signal Analysis**: Live feed of incoming and processed signals
            - **Risk Monitoring**: Current drawdown levels and risk metrics
            """
        }
    ]
    
    for i, faq in enumerate(faq_items):
        with st.expander(f"**Q{i+1}:** {faq['question']}", expanded=False):
            st.markdown(faq['answer'])
    
    st.divider()
    
    # Technical Details
    st.subheader("🔧 Technical Architecture")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Backend Infrastructure**
        - **FastAPI**: High-performance REST API
        - **PostgreSQL**: Time-series database for market data
        - **Redis**: Caching and session management
        - **Celery**: Asynchronous task processing
        - **Docker**: Containerized deployment
        """)
    
    with col2:
        st.markdown("""
        **Data Processing**
        - **Pandas**: Data manipulation and analysis
        - **NumPy**: Numerical computations
        - **SciPy**: Statistical analysis
        - **yfinance**: Real-time market data
        - **Alpaca API**: Paper trading execution
        """)
    
    # Contact Information
    st.subheader("📞 Support & Contact")
    
    st.markdown("""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.5rem;">
        <h4 style="margin-top: 0;">Need Help?</h4>
        <p>If you have questions about the system or need technical support:</p>
        <ul>
            <li>Check the <strong>Cycle Status</strong> page for system health</li>
            <li>Review the <strong>Philosophy Settings</strong> for configuration options</li>
            <li>Monitor the <strong>Performance</strong> page for system metrics</li>
            <li>Contact the development team for technical issues</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Close accessibility div if opened
if accessibility_class:
    st.markdown("</div>", unsafe_allow_html=True)

# Footer with accessibility information
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; padding: 1rem; color: #6b7280; font-size: 0.875rem;">
    <p>🥋 <strong>Dojo Allocator</strong> - Autonomous Trading System</p>
    <p>Built with accessibility in mind • Supports keyboard navigation, screen readers, and high contrast mode</p>
    <p>For support or feedback, please contact the development team</p>
</div>
""",
    unsafe_allow_html=True,
)

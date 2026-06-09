import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import json
import urllib.parse
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from st_aggrid.shared import GridUpdateMode
import streamlit.components.v1 as components
import re
import io
import google.generativeai as genai

# ==========================================
# ⚙️ PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Top 250 NSE Stock-Volume Breakout Dashboard", layout="wide", page_icon="📊")

# ==========================================
# 🤖 CONFIGURE AI (GEMINI + GROQ)
# ==========================================
gemini_enabled = False
groq_enabled   = False

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    gemini_enabled = True

if "GROQ_API_KEY" in st.secrets:
    try:
        from groq import Groq as GroqClient
        _groq_client = GroqClient(api_key=st.secrets["GROQ_API_KEY"])
        groq_enabled = True
    except ImportError:
        groq_enabled = False

ai_enabled = gemini_enabled or groq_enabled

# ── helper: unified AI call ────────────────────────────────────────────────
def call_ai(prompt: str, model_choice: str) -> str:
    """Call Gemini or Groq and return text response."""
    if model_choice == "⚡ Groq (Fast)" and groq_enabled:
        resp = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return resp.choices[0].message.content
    elif gemini_enabled:
        mdl = genai.GenerativeModel("gemini-2.5-flash")
        return mdl.generate_content(prompt).text
    else:
        raise RuntimeError("No AI model is configured. Add GEMINI_API_KEY or GROQ_API_KEY to secrets.")

# ── AI model selector widget (shown inside AI tabs) ───────────────────────
def ai_model_selector(key_suffix: str = "") -> str:
    options, default = [], 0
    if groq_enabled:   options.append("⚡ Groq (Fast)")
    if gemini_enabled: options.append("🧠 Gemini")
    if not options:    options = ["⚡ Groq (Fast)", "🧠 Gemini"]
    return st.radio("🤖 AI Model:", options, index=0,
                    horizontal=True, key=f"ai_model_sel_{key_suffix}")

# ==========================================
# 💡 AI PROMPT LIBRARY
# ==========================================
SUGGESTED_AI_PROMPTS = [
    "Based on the current data provided, give me a quick summary of the technical performance and trend for {sym}. Also give me all other details and calculate if this company is profitable or not.",
    "Analyze the 52-week high and low data for {sym}. Is the stock closer to its peak or bottom? What does this imply for entry or exit timing? Identify the ideal buy zone.",
    "Examine the 50 DMA, 100 DMA, and 200 DMA data for {sym}. Is the stock in a bullish crossover, bearish zone, or consolidation phase? Explain the trend strength and momentum.",
    "Using the volume data for {sym}, identify if there is unusual volume activity. Does the current volume indicate institutional buying, selling, or accumulation? What does it signal?",
    "Evaluate the full fundamentals of {sym} — EPS, RONW%, D/E ratio, Net Profit (Cr.), Book Value, and Market Cap. Is this company financially healthy and worth long-term investment?",
    "What is the risk profile of {sym} based on its Pledged %, Promoters Holding %, Institutional Holding %, and Debt-to-Equity ratio? Should a retail investor be cautious right now?",
    "Compare {sym}'s current CMP vs its 200 DMA. Is the stock overbought, oversold, or fairly valued based on the Difference from 200 DMA metric? What is the ideal risk-reward entry zone?",
    "Give a complete Buy / Hold / Sell recommendation for {sym} using all available technical and fundamental data. Include specific price targets, support levels, and a stop-loss level.",
    "Based on the CAR Rating and Output signal for {sym}, what is the system suggesting? Does the historical price action and current data support this signal? How reliable is it?",
    "Summarize {sym}'s sector positioning, market cap, enterprise value, book value, and promoter holding. How does this stock compare to typical benchmarks in its sector in the Indian market?",
]

# ==========================================
# 🌲 PINE SCRIPT CUSTOM RULES LIBRARY
# ==========================================
PINE_CUSTOM_RULES = """Strategy 1 — Volume Breakout with Dynamic Stop Loss
  Rule 1: Enter long when today's volume > 2× the 20-day average volume AND price closes above the prior day's high; set stop loss at 1.5× ATR below entry price.
  Rule 2: Add a false breakout filter — price must hold above the breakout level for 2 consecutive candles before confirming entry; trail stop at the lowest low of the last 3 bars.
  Rule 3: Set profit target at 2:1 risk-reward ratio; plot a volume histogram overlay to identify surge bars visually; include an alert condition for live breakout detection.

Strategy 2 — Moving Average Crossover (50/100/200 DMA)
  Rule 4: Buy when 50 DMA crosses above 100 DMA with price trading above the 200 DMA; exit when 50 DMA crosses back below 100 DMA; use 200 DMA as the hard stop-loss floor.
  Rule 5: Add RSI confirmation — only enter when RSI is between 50–70 at the crossover candle; plot all three DMAs on the chart with distinct colours for visual clarity.
  Rule 6: Allow a re-entry if 50 DMA pulls back to 100 DMA without breaking below 200 DMA; set stop loss 2% below the 50 DMA value at the time of entry.

Strategy 3 — Trend Following with Trailing Stop
  Rule 7: Enter long when price breaks a 20-day high with above-average volume and ADX > 25; apply a Chandelier Exit trailing stop set at 3× ATR from the highest close after entry.
  Rule 8: Use 200 DMA direction as the trend filter — only take long trades when price is above 200 DMA; tighten trailing stop to 2× ATR once profit exceeds 10% from entry.
  Rule 9: Add a re-entry condition: if stopped out but price remains above 200 DMA, re-enter on the next pullback to the 50 DMA; limit to a maximum of 2 re-entries per trend leg.

Strategy 4 — Mean Reversion from 52W High/Low
  Rule 10: Buy when price is within 15% of the 52-week low AND RSI < 35; set profit target at the 52-week midpoint; place hard stop loss 5% below the 52-week low level.
  Rule 11: Exit/short signal when price is within 5% of the 52-week high with RSI > 70; use Bollinger Band upper band touch as secondary confirmation; target the middle Bollinger Band as exit.
  Rule 12: Apply a volume reversal filter — only enter when the reversal candle's volume is ≥ 1.5× the 20-day average; plot the 52-week high and low as horizontal reference lines on the chart."""

import streamlit as st

# ==========================================
# 🛡️ HIDE STREAMLIT MENU
# ==========================================
hide_streamlit_ui = """
<style>
    #MainMenu {visibility: show;}
    header {visibility: show;}
    [data-testid="stToolbar"] {visibility: show;}
    footer {visibility: show;}
</style>
"""
st.markdown(hide_streamlit_ui, unsafe_allow_html=True)

import streamlit as st

# ==========================================
# 🛡️ HIDE GITHUB ICON ONLY
# ==========================================
hide_github_icon = """
<style>
    [data-testid="stToolbar"] {
        right: 2rem;
    }
    [data-testid="stToolbar"]::before {
        content: "";
    }
    button[kind="header"] {display: none;}
</style>
"""
st.markdown(hide_github_icon, unsafe_allow_html=True)

# ==========================================
# 🔐 ADMIN LOGIN SYSTEM
# ==========================================
ADMIN_PASSWORD = "kano"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ── Watchlist session state init ──────────────────────────────────────────
if "watchlist" not in st.session_state:
    # {symbol: {"note": str, "added": str, "cmp": str}}
    st.session_state.watchlist = {}

# ── AI result history for Excel export ───────────────────────────────────
if "ai_history" not in st.session_state:
    # list of dicts: {symbol, model, query, result, timestamp}
    st.session_state.ai_history = []

if not st.session_state.logged_in:
    # Top hint
    st.markdown("<p style='text-align: center; margin-top: 100px; color: Green; font-size: 18px;'>250-V Dashboard</p>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; margin-top: 0px; font-size: 20px;'>🔐 Admin Login</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            pwd = st.text_input("Enter Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            if submit:
                if pwd == ADMIN_PASSWORD:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    import random
                    password_errors = [
                        "Password इल्ले! 😅 इल्ले!, खम्मा घणी भाईसा, सॉरी। तुमसे सब कुछ हो पाएगा! यहां बहुत 🤪 दिमाग मत लगाओ, इस वेबसाइट को नहीं, 😂 इस गलत पासवर्ड को छोड़ दो!",
                        "❌ Password इल्ले भाईसा! 😅 इल्ले! खम्मा घणी, सॉरी। तुम बाहुबली हो, तुमसे सब कुछ हो पाएगा! पर यहाँ फालतू 🤪 दिमाग मत लगाओ। अपनी सुंदर वेबसाइट को नहीं, 😂 इस सड़े हुए गलत पासवर्ड को छोड़ दो!",
                        "❌ खम्मा घणी भाईसा, Password इल्ले! 😅 sorry! तुम तो मंगल ग्रह पर पानी खोज सकते हो, तुमसे सब कुछ हो पाएगा! पर यहाँ ज़्यादा 🤪 दिमाग मत लगाओ। इस सीधे-सादे वेबसाइट को नहीं, 😂 इस जाली पासवर्ड को छोड़ दो!",
                        "❌ Password इल्ले! 😅 इल्ले! खम्मा घणी भाईसा, सॉरी। लोड मत लो, तुमसे सब कुछ हो पाएगा! पर यहाँ फालतू 🤪 दिमाग मत लगाओ। दुनिया छोड़ दो, मोक्ष पकड़ लो, पर पहले 😂 इस गलत पासवर्ड को छोड़ दो!",
                        "❌ अरे भाईसा! Password इल्ले! 😅 खम्मा घणी, सॉरी। तुम चाहो तो सिस्टम हिला सकते हो, तुमसे सब कुछ हो पाएगा! पर यहाँ ज़्यादा 🤪 दिमाग मत लगाओ। इस निर्दोष वेबसाइट को नहीं, 😂 इस भूतिया गलत पासवर्ड को छोड़ दो!"
                    ]
                    st.error(random.choice(password_errors))
    
    # Your dynamic bottom hint
    dynamic_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    st.markdown(f"<p style='text-align: center; color: gray; font-size: 14px; margin-top: 20px;'>Data refreshed: {dynamic_time}</p>", unsafe_allow_html=True)

    st.stop()

# ==========================================
# YOUR EXISTING CSS (keep this)
# ==========================================
st.markdown("""
<style>
    /* Reduce ALL headings to 90% smaller size */
    h1, h2, h3, h4, h5, h6, .stSubheader, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-size: 0.85rem !important;
        font-weight: bold !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌍 GLOBAL MARKET TICKER (LIVE DATA GRID)
# ==========================================
import yfinance as yf
import streamlit as st
from datetime import datetime

st.markdown("<p style='font-size:0.85rem; font-weight:bold; margin:0; padding:0;'>📊 Top 250 NSE Stock-Volume Breakout Dashboard</p>", unsafe_allow_html=True)
st.caption(f"Data refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

@st.cache_data(ttl=60)
def get_live_index_data():
    symbols = {
        "NIFTY 50": "^NSEI",
        "NIFTY NEXT 50": "^NN50",
        "NIFTY MIDCAP 50": "^NSEMDCP50",
        "NIFTY MIDCAP 100": "^CRSLMID",
        "NIFTY MIDCAP 150": "UNSUPPORTED", 
        "NIFTY SMLCAP 50": "UNSUPPORTED",
        "NIFTY SMLCAP 100": "UNSUPPORTED",
        "NIFTY SMLCAP 250": "UNSUPPORTED",
        "NIFTY MIDSML 400": "UNSUPPORTED",
        "NIFTY 100": "^CNX100",
        "NIFTY 200": "^CNX200",
        "NIFTY500 MULTI...": "UNSUPPORTED",
        "NIFTY LARGEMID...": "UNSUPPORTED",
        "NIFTY MID SELE...": "UNSUPPORTED",
        "NIFTY TOTAL MK...": "UNSUPPORTED",
        "NIFTY MICROCAP...": "UNSUPPORTED",
        "NIFTY 500": "^CRSLDX",
        "NIFTY FPI 150": "UNSUPPORTED",
        "NIFTY500 LMS E...": "UNSUPPORTED",
        "NIFTY MIDSMALL...": "UNSUPPORTED",
        "NIFTY SMALLCAP...": "UNSUPPORTED"
    }
    
    data_grid = {}
    for name, ticker_code in symbols.items():
        if ticker_code == "UNSUPPORTED":
            data_grid[name] = {"price": "No Data", "change": 0.0}
            continue
            
        try:
            ticker = yf.Ticker(ticker_code)
            hist = ticker.history(period="5d")
            
            if not hist.empty and len(hist) >= 2:
                live_price = float(hist['Close'].iloc[-1])
                prev_close = float(hist['Close'].iloc[-2])
                pct_change = ((live_price - prev_close) / prev_close) * 100
                data_grid[name] = {"price": f"{live_price:,.2f}", "change": pct_change}
            else:
                data_grid[name] = {"price": "Loading...", "change": 0.0}
        except Exception:
            data_grid[name] = {"price": "Error", "change": 0.0}
            
    return data_grid

live_data = get_live_index_data()

cards_html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; font-family: system-ui, -apple-system, sans-serif;'>"

# Keep track of how many cards we actually printed
valid_cards_count = 0 

for name, info in live_data.items():
    
    # 👇 NEW LOGIC: If the data is bad, skip this block completely!
    if info["price"] in ["No Data", "Loading...", "Error"]:
        continue
        
    valid_cards_count += 1
    bg_color = "#66bb6a" if info["change"] >= 0 else "#ef5350"
    change_sign = "+" if info["change"] >= 0 else ""
    index_nse_url = "https://www.nseindia.com/market-data/live-market-indices"

    cards_html += f"<a href='{index_nse_url}' target='_blank' style='text-decoration:none;'>"
    cards_html += f"<div style='background-color: {bg_color}; color: white; padding: 12px 16px; border-radius: 8px; flex: 1 1 calc(16.66% - 10px); min-width: 140px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>"
    cards_html += f"<div style='font-size: 11px; font-weight: 700; letter-spacing: 0.5px; opacity: 0.95; margin-bottom: 6px; text-transform: uppercase;'>{name}</div>"
    cards_html += f"<div style='display: flex; justify-content: space-between; align-items: baseline;'>"
    cards_html += f"<span style='font-size: 15px; font-weight: 700;'>{info['price']}</span>"
    cards_html += f"<span style='font-size: 11px; font-weight: 600; background: rgba(255,255,255,0.2); padding: 1px 6px; border-radius: 4px;'>{change_sign}{info['change']:.2f}%</span>"
    cards_html += f"</div></div></a>"

cards_html += "</div>"

with st.expander("📈 Click to view Live Market Indices", expanded=False):
    # Failsafe: If Yahoo Finance is completely down and NO cards rendered, show a friendly message
    if valid_cards_count == 0:
        st.info("Market data is currently unavailable. Please check back later.")
    else:
        st.markdown(cards_html, unsafe_allow_html=True)

st.write("---")

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================
def rgb_to_hex(color_dict):
    if not color_dict: return "#ffffff"
    r, g, b = int(color_dict.get('red', 0) * 255), int(color_dict.get('green', 0) * 255), int(color_dict.get('blue', 0) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"

@st.cache_data(ttl=300)
def load_sheet_data_with_colors(sheet_name):
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Missing 'gcp_service_account' in secrets.")
            return pd.DataFrame()

        service_account_info = st.secrets["gcp_service_account"]
        if isinstance(service_account_info, str):
            service_account_info = json.loads(service_account_info)

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
        client = gspread.authorize(creds)

        spreadsheet_id = "1SFhuZbLLlwwFsNo1k2RRx_Zp6bAkRR20W0F_zTwgdwU"
        encoded_sheet = urllib.parse.quote(sheet_name)

        authed_session = AuthorizedSession(creds)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}?includeGridData=true&ranges={encoded_sheet}"
        response = authed_session.get(url)
        data = response.json()

        if 'error' in data: return pd.DataFrame()
        if 'sheets' not in data or not data['sheets']: return pd.DataFrame()

        sheet_data = data['sheets'][0]['data'][0]
        row_data = sheet_data.get('rowData', [])
        if not row_data: return pd.DataFrame()

        values_list, bg_colors_list, txt_colors_list = [], [], []

        for row in row_data:
            cells = row.get('values', [])
            row_vals, row_bgs, row_txts = [], [], []
            for cell in cells:
                row_vals.append(cell.get('formattedValue', ''))
                fmt = cell.get('effectiveFormat', {})
                row_bgs.append(rgb_to_hex(fmt.get('backgroundColor', {})))
                row_txts.append(rgb_to_hex(fmt.get('textFormat', {}).get('foregroundColor', {})))

            values_list.append(row_vals)
            bg_colors_list.append(row_bgs)
            txt_colors_list.append(row_txts)

        raw_headers = values_list[0]
        clean_headers = []
        seen = {}
        for h in raw_headers:
            h = str(h).strip()
            if h == "": h = "empty_column"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else: seen[h] = 0
            clean_headers.append(h)

        df = pd.DataFrame(values_list[1:], columns=clean_headers)
        for i, col in enumerate(clean_headers):
            df[f"_bg_{col}"] = [row[i] if i < len(row) else "#ffffff" for row in bg_colors_list[1:]]
            df[f"_txt_{col}"] = [row[i] if i < len(row) else "#000000" for row in txt_colors_list[1:]]

        return df
    except Exception as e:
        return pd.DataFrame()

def process_hyperlinks(df, symbol_col):
    df_proc = df.copy()
    df_proc['_raw_symbol_'] = df_proc[symbol_col]

    for idx, row in df_proc.iterrows():
        sym = str(row['_raw_symbol_']).strip()
        if not sym or sym == "nan": continue

        for col in df_proc.columns:
            if col.startswith("_bg_") or col.startswith("_txt_") or col == "_raw_symbol_": continue

            c_lower = col.lower()
            url, label = None, "🔗 Link"

            if "trading view" in c_lower: url, label = f"https://www.tradingview.com/symbols/{sym}/", f"Tre {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "history data" in c_lower: url, label = f"https://www.equitypandit.com/historical-data/{sym}", f"History {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "screener" in c_lower: url, label = f"https://www.screener.in/company/{sym}", f"Scr {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "zerodha" in c_lower: url, label = f"https://zerodha.com/markets/stocks/NSE/{sym}", f"🪁 {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "chartlink" in c_lower: url, label = f"https://chartink.com/stocks-new?load-snapshot=exponential-moving-average-simple-moving-average-simple-moving-average-moving-average-convergence-divergence-chart-snapshot-175&symbol={sym}", f"CL {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "market smith" in c_lower: url, label = f"https://marketsmithindia.com/mstool/eval/{sym}/evaluation.jsp", f"ms {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "official nse" in c_lower: url, label = f"https://www.nseindia.com/get-quotes/equity?symbol={sym}", f"nse📰 {sym}" if not c_lower.endswith("1") else "🔗 Link"
            elif "nse" in c_lower: url, label = f"https://charting.nseindia.com/?symbol={sym}-EQ", f"nse {sym}" if not c_lower.endswith("1") else "🔗 Link"

            if url: df_proc.at[idx, col] = f'<a href="{url}" target="_blank" style="text-decoration:none; color:#000000;">{label}</a>'

    return df_proc

def apply_numeric_slider(df, col_name, st_container, display_label=None):
    if col_name in df.columns:
        num_series = df[col_name].astype(str).str.replace(r'[%,]', '', regex=True)
        num_series = pd.to_numeric(num_series, errors='coerce').replace([np.inf, -np.inf], np.nan)

        valid_nums = num_series.dropna()
        if not valid_nums.empty:
            min_val, max_val = round(float(valid_nums.min()), 2), round(float(valid_nums.max()), 2)
            if min_val < max_val:
                label = display_label if display_label else f"{col_name} Range:"
                selected_range = st_container.slider(label, min_value=min_val, max_value=max_val, value=(min_val, max_val), key=f"filter_num_{col_name}")
                return df[(num_series >= selected_range[0]) & (num_series <= selected_range[1])]
    return df

def apply_date_filter(df, col_name, st_container):
    if col_name in df.columns:
        options = ["All Time", "Past 5 Days", "Past 10 Days", "Past 15 Days", "Past 20 Days",
                   "Past 25 Days", "Past 30 Days", "Past 1 Month", "Past 2 Months", "Past 6 Months", "Past 1 Year"]
        selection = st_container.selectbox(f"{col_name}:", options, key=f"filter_date_{col_name}")

        if selection != "All Time":
            date_series = pd.to_datetime(df[col_name], errors='coerce', dayfirst=True)
            today = pd.Timestamp.now()

            if selection == "Past 5 Days": threshold = today - pd.Timedelta(days=5)
            elif selection == "Past 10 Days": threshold = today - pd.Timedelta(days=10)
            elif selection == "Past 15 Days": threshold = today - pd.Timedelta(days=15)
            elif selection == "Past 20 Days": threshold = today - pd.Timedelta(days=20)
            elif selection == "Past 25 Days": threshold = today - pd.Timedelta(days=25)
            elif selection == "Past 30 Days": threshold = today - pd.Timedelta(days=30)
            elif selection == "Past 1 Month": threshold = today - pd.DateOffset(months=1)
            elif selection == "Past 2 Months": threshold = today - pd.DateOffset(months=2)
            elif selection == "Past 6 Months": threshold = today - pd.DateOffset(months=6)
            elif selection == "Past 1 Year": threshold = today - pd.DateOffset(years=1)

            return df[date_series >= threshold]
    return df

def get_clean_text_length(val):
    if pd.isna(val): return 0
    clean_text = re.sub(r'<[^>]*>', '', str(val))
    return len(clean_text)

def clean_for_export(df):
    export_df = df.copy()
    cols_to_drop = [c for c in export_df.columns if c.startswith("_bg_") or c.startswith("_txt_") or c == "_raw_symbol_"]
    export_df = export_df.drop(columns=cols_to_drop, errors='ignore')
    for col in export_df.select_dtypes(include=['object']).columns:
        export_df[col] = export_df[col].apply(lambda x: re.sub(r'<[^>]*>', '', str(x)) if pd.notnull(x) else x)
    return export_df

import streamlit.components.v1 as components

# ==========================================
# 🌍 NATIONAL EXCHANGE SCANNER (ALL NSE/BSE)
# ==========================================
st.markdown("<p style='font-size:0.85rem; font-weight:bold; margin:0; padding:0;'>🌍 National Exchange Scanner (All NSE/BSE Stocks)</p>", unsafe_allow_html=True)
st.caption("Live market data covering 2,000+ equities. Powered by TradingView.")

with st.expander("🏆 Click to view Full-Market India Rankings", expanded=False):
    
    # Create the tabs based on your requested list
    nse_tab1, nse_tab2, nse_tab3, nse_tab4, nse_tab5 = st.tabs([
        "🚀 Gainers & Losers", 
        "📦 Volume & Active", 
        "⭐ 52W High / Low", 
        "🔄 52W Reversals",
        "📊 Top 100 Traded"
    ])

    # Helper function to generate clean TradingView iframes dynamically
    def render_tv_widget(screen_type):
        return f"""
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-screener.js" async>
          {{
          "width": "100%",
          "height": "500",
          "defaultColumn": "overview",
          "defaultScreen": "{screen_type}",
          "market": "india",
          "showToolbar": true,
          "colorTheme": "light",
          "locale": "en"
        }}
          </script>
        </div>
        """

    # 1st Tab: Gainers / Losers
    with nse_tab1:
        colA, colB = st.columns(2)
        with colA:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>🚀 Top Gainers</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("top_gainers"), height=520)
        with colB:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>🔻 Top Losers</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("top_losers"), height=520)
            
    # 2nd & 3rd Tabs Combined: Volume Leaders & Most Active (Turnover/Value)
    with nse_tab2:
        colA, colB = st.columns(2)
        with colA:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>📦 Volume Leaders</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("volume_leaders"), height=520)
        with colB:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>🔥 Most Active (Volume & Value)</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("most_active"), height=520)
            
    # 7th Tab: 52 Week High / Low
    with nse_tab3:
        colA, colB = st.columns(2)
        with colA:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>⭐ New 52-Week Highs</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("new_52wk_high"), height=520)
        with colB:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>⭐ New 52-Week Lows</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("new_52wk_low"), height=520)
            
    # 8th Tab: Reversals from 52W High/Low
    with nse_tab4:
        colA, colB = st.columns(2)
        with colA:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>📈 Outperforming 52W High (Reversal Up)</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("outperforming_52wk_high"), height=520)
        with colB:
            st.markdown("<p style='font-size:14px; font-weight:bold;'>📉 Underperforming 52W Low (Reversal Down)</p>", unsafe_allow_html=True)
            components.html(render_tv_widget("underperforming_52wk_low"), height=520)
            
    # 9th Tab: Top 100 Traded (Full Screener)
    with nse_tab5:
        st.markdown("<p style='font-size:14px; font-weight:bold;'>📊 Top 100+ Stocks Traded (Full India Screener)</p>", unsafe_allow_html=True)
        # Using the general screen so users can sort by turnover, volume, or rating manually
        components.html(render_tv_widget("general"), height=520)

st.write("---")

# ==========================================
# 🏢 TOP 250 STOCKS TICKER (SHEET DATA GRID)
# ==========================================
@st.cache_data(ttl=300)
def get_sheet_stocks_data():
    # Fetching strictly from the requested tab
    df = load_sheet_data_with_colors("Top 250 Stocks")
    data_grid = {}
    
    if df.empty:
        return data_grid
        
    actual_cols = [c for c in df.columns if not c.startswith("_bg_") and not c.startswith("_txt_")]
    
    # Dynamically find the symbol, cmp, and % change columns
    sym_col = next((c for c in actual_cols if c.lower() in ["nse code", "symbol", "ticker", "stock symbol", "id", "stock"]), None)
    cmp_col = next((c for c in actual_cols if "cmp" in c.lower()), None)
    pct_col = next((c for c in actual_cols if "price %" in c.lower() or "change" in c.lower()), None)
    
    if not sym_col or not cmp_col:
        return data_grid
        
    for _, row in df.iterrows():
        sym = str(row.get(sym_col, "")).strip()
        if not sym or sym == "nan":
            continue
            
        raw_cmp = str(row.get(cmp_col, "")).replace(",", "").strip()
        raw_pct = str(row.get(pct_col, "0")).replace("%", "").replace(",", "").strip() if pct_col else "0"
        
        # Validate Price
        try:
            price_val = float(raw_cmp)
            price_str = f"{price_val:,.2f}"
        except ValueError:
            price_str = "No Data"
            
        # Validate % Change
        try:
            pct_val = float(raw_pct)
        except ValueError:
            pct_val = 0.0
            
        data_grid[sym] = {"price": price_str, "change": pct_val}
        
    return data_grid

sheet_live_data = get_sheet_stocks_data()

sheet_cards_html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; font-family: system-ui, -apple-system, sans-serif;'>"

# Keep track of valid cards
sheet_valid_cards_count = 0 

for name, info in sheet_live_data.items():
    
    # 👇 LOGIC: Hide HTML box entirely if the price is bad
    if info["price"] in ["No Data", "Loading...", "Error"]:
        continue
        
    sheet_valid_cards_count += 1
    bg_color = "#66bb6a" if info["change"] >= 0 else "#ef5350"
    change_sign = "+" if info["change"] >= 0 else ""
    nse_url = f"https://www.nseindia.com/get-quotes/equity?symbol={name}"
    
    sheet_cards_html += f"<a href='{nse_url}' target='_blank' style='text-decoration:none;'>"
    sheet_cards_html += f"<div style='background-color: {bg_color}; color: white; padding: 12px 16px; border-radius: 8px; flex: 1 1 calc(16.66% - 10px); min-width: 140px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>"
    sheet_cards_html += f"<div style='font-size: 11px; font-weight: 700; letter-spacing: 0.5px; opacity: 0.95; margin-bottom: 6px; text-transform: uppercase;'>{name}</div>"
    sheet_cards_html += f"<div style='display: flex; justify-content: space-between; align-items: baseline;'>"
    sheet_cards_html += f"<span style='font-size: 15px; font-weight: 700;'>{info['price']}</span>"
    sheet_cards_html += f"<span style='font-size: 11px; font-weight: 600; background: rgba(255,255,255,0.2); padding: 1px 6px; border-radius: 4px;'>{change_sign}{info['change']:.2f}%</span>"
    sheet_cards_html += f"</div></div></a>"

sheet_cards_html += "</div>"

with st.expander("📈 Click to view Top 250 Stocks Matrix", expanded=False):
    # Failsafe if the sheet is completely empty or all rows returned "No Data"
    if sheet_valid_cards_count == 0:
        st.info("Stock matrix data is currently unavailable. Please check the 'Top 250 Stocks' sheet.")
    else:
        st.markdown(sheet_cards_html, unsafe_allow_html=True)

st.write("---")

# ==========================================
# 🏆 TOP 250 STOCKS RANKING DASHBOARDS
# ==========================================
@st.cache_data(ttl=300)
def get_ranked_sheet_data():
    df = load_sheet_data_with_colors("Top 250 Stocks")
    if df.empty:
        return pd.DataFrame()
        
    actual_cols = [c for c in df.columns if not c.startswith("_bg_") and not c.startswith("_txt_")]
    
    sym_col = next((c for c in actual_cols if c.lower() in ["nse code", "symbol", "ticker", "stock symbol", "id", "stock"]), None)
    cmp_col = next((c for c in actual_cols if "cmp" in c.lower()), None)
    pct_col = next((c for c in actual_cols if "price %" in c.lower() or "change" in c.lower()), None)
    vol_col = next((c for c in actual_cols if "volume" in c.lower()), None)
    
    # Look for specific Value and Turnover columns
    value_col = next((c for c in actual_cols if "value" in c.lower() and "face" not in c.lower() and "enterprise" not in c.lower()), None)
    turnover_col = next((c for c in actual_cols if "turnover" in c.lower()), None)
    
    if not sym_col:
        return pd.DataFrame()
        
    # Extract and clean only the necessary columns for sorting
    rank_df = pd.DataFrame()
    rank_df['Symbol'] = df[sym_col].astype(str).str.strip()
    
    rank_df['CMP'] = pd.to_numeric(df[cmp_col].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce') if cmp_col else 0.0
    rank_df['Pct_Change'] = pd.to_numeric(df[pct_col].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce') if pct_col else 0.0
    rank_df['Volume'] = pd.to_numeric(df[vol_col].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce') if vol_col else 0.0

    # Handle Value and Turnover (Use exact columns if they exist, otherwise calculate CMP * Volume)
    fallback_calc = rank_df['CMP'] * rank_df['Volume']
    
    if value_col:
        rank_df['Value'] = pd.to_numeric(df[value_col].astype(str).str.replace(r'[a-zA-Z%, ]', '', regex=True), errors='coerce')
    else:
        rank_df['Value'] = fallback_calc
        
    if turnover_col:
        rank_df['Turnover'] = pd.to_numeric(df[turnover_col].astype(str).str.replace(r'[a-zA-Z%, ]', '', regex=True), errors='coerce')
    else:
        rank_df['Turnover'] = fallback_calc
    
    # Drop rows that don't have valid symbols or prices
    rank_df = rank_df.dropna(subset=['Symbol', 'CMP']).reset_index(drop=True)
    rank_df = rank_df[(rank_df['Symbol'] != 'nan') & (rank_df['Symbol'] != '')]
    
    return rank_df

def build_ranking_cards_html(dataframe, metric_label="change"):
    cards_html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; font-family: system-ui, -apple-system, sans-serif;'>"
    
    if dataframe.empty:
        return "<p style='color: gray; font-size: 14px;'>No data available for this ranking.</p>"
        
    for _, row in dataframe.iterrows():
        sym = row['Symbol']
        price = row['CMP']
        pct = row['Pct_Change']
        
        bg_color = "#66bb6a" if pct >= 0 else "#ef5350"
        change_sign = "+" if pct >= 0 else ""
        
        # Decide what the pill displays based on the metric_label
        if metric_label == "volume":
            vol = row.get('Volume', 0)
            pill_text = f"Vol: {vol/1000000:.1f}M" if vol >= 1000000 else f"Vol: {vol:,.0f}"
            
        elif metric_label == "value":
            val = row.get('Value', 0)
            pill_text = f"Val: ₹{val/10000000:,.1f}Cr" if val >= 10000000 else f"Val: ₹{val:,.0f}"
            
        elif metric_label == "turnover":
            to = row.get('Turnover', 0)
            pill_text = f"T.O: ₹{to/10000000:,.1f}Cr" if to >= 10000000 else f"T.O: ₹{to:,.0f}"
            
        elif metric_label == "vol_val":
            # Custom dual-metric pill for "Most Active by Volume & Value"
            vol = row.get('Volume', 0)
            val = row.get('Value', 0)
            v_str = f"{vol/1000000:.1f}M" if vol >= 1000000 else f"{vol/1000:.1f}k"
            val_str = f"₹{val/10000000:,.1f}Cr" if val >= 10000000 else f"₹{val:,.0f}"
            pill_text = f"📦 {v_str} | 💰 {val_str}"
            
        else:
            pill_text = f"{change_sign}{pct:.2f}%"

        nse_url = f"https://www.nseindia.com/get-quotes/equity?symbol={sym}"
        cards_html += f"<a href='{nse_url}' target='_blank' style='text-decoration:none;'>"
        cards_html += f"<div style='background-color: {bg_color}; color: white; padding: 12px 16px; border-radius: 8px; flex: 1 1 calc(16.66% - 10px); min-width: 140px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>"
        cards_html += f"<div style='font-size: 11px; font-weight: 700; letter-spacing: 0.5px; opacity: 0.95; margin-bottom: 6px; text-transform: uppercase;'>{sym}</div>"
        cards_html += f"<div style='display: flex; justify-content: space-between; align-items: baseline;'>"
        cards_html += f"<span style='font-size: 15px; font-weight: 700;'>{price:,.2f}</span>"
        cards_html += f"<span style='font-size: 11px; font-weight: 600; background: rgba(255,255,255,0.2); padding: 1px 6px; border-radius: 4px; white-space: nowrap;'>{pill_text}</span>"
        cards_html += f"</div></div></a>"
        
    cards_html += "</div>"
    return cards_html

# Fetch Data
rank_data = get_ranked_sheet_data()

with st.expander("🏆 Click to view Advanced Ranking Dashboards (Top 250 Stocks)", expanded=False):
    if rank_data.empty:
        st.info("Ranking data is currently unavailable. Please check the 'Top 250 Stocks' sheet.")
    else:
        # 1. Top 20 Gainers/Losers
        df_gainers = rank_data.nlargest(20, 'Pct_Change')
        df_losers = rank_data.nsmallest(20, 'Pct_Change')
        
        # 2. Top 20 Volume Gainers/Losers
        df_vol_gainers = rank_data.nlargest(20, 'Volume')
        df_vol_losers = rank_data[rank_data['Volume'] > 0].nsmallest(20, 'Volume')
        
        # 3. Most Active by Volume & Value (Sorted by Volume, displaying both)
        df_active_vol_val = rank_data.nlargest(20, 'Volume') 
        
        # 4. Most Active by Value
        df_top_value = rank_data.nlargest(20, 'Value')
        
        # 5. Top by Turnover
        df_top_turnover = rank_data.nlargest(20, 'Turnover')
        
        # 6. Recreating the Most Active variable from Dashboard-1 logic
        df_most_active = rank_data.nlargest(20, 'Value')
        
        # Create Tabs for the 6 categories
        rank_tab1, rank_tab2, rank_tab3, rank_tab4, rank_tab5, rank_tab6 = st.tabs([
            "📈 Gainers/Losers", 
            "📦 Volume Leaders", 
            "🔥 Active (Vol & Val)", 
            "💰 Top by Value", 
            "💎 Top by Turnover",
            "💰 Most Active"
        ])
        
        with rank_tab1:
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>🚀 Top 20 Gainers</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_gainers, "change"), unsafe_allow_html=True)
            
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>🔻 Top 20 Losers</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_losers, "change"), unsafe_allow_html=True)
            
        with rank_tab2:
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>📦 Top 20 by Volume</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_vol_gainers, "volume"), unsafe_allow_html=True)
            
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>💤 Bottom 20 by Volume</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_vol_losers, "volume"), unsafe_allow_html=True)
            
        with rank_tab3:
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>🔥 Most Active Stocks (Volume & Traded Value)</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_active_vol_val, "vol_val"), unsafe_allow_html=True)
            
        with rank_tab4:
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>💰 Most Active by Traded Value</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_top_value, "value"), unsafe_allow_html=True)
            
        with rank_tab5:
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>💎 Highest Market Turnover</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_top_turnover, "turnover"), unsafe_allow_html=True)

        with rank_tab6:
            st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:10px;'>💰 Most Active (Highest Traded Value)</p>", unsafe_allow_html=True)
            st.markdown(build_ranking_cards_html(df_most_active, "value"), unsafe_allow_html=True)

st.write("---")

# ==========================================
# 🔬 BOTTOM FISHING SCANNER — helper
# ==========================================
def compute_bottom_fishing_score(row, actual_cols):
    """
    Score 0–100 based on fundamentals + technical proximity to 52W Low.
    Higher = better bottom-fishing candidate.
    """
    score = 0
    reasons = []

    def get_num(col_keywords, negate=False):
        for kw in col_keywords:
            col = next((c for c in actual_cols if kw.lower() in c.lower()), None)
            if col and col in row:
                try:
                    val = float(str(row[col]).replace('%','').replace(',','').strip())
                    return -val if negate else val
                except: pass
        return None

    # 1. CMP within 8-15% of 52W Low (max 30 pts)
    cmp = get_num(["cmp"])
    low_52 = get_num(["52w low", "52 week low", "52wlow"])
    if cmp and low_52 and low_52 > 0:
        pct_from_low = ((cmp - low_52) / low_52) * 100
        if 8 <= pct_from_low <= 15:
            score += 30
            reasons.append(f"✅ CMP +{pct_from_low:.1f}% from 52W Low (sweet zone)")
        elif pct_from_low < 8:
            score += 15
            reasons.append(f"⚠️ CMP +{pct_from_low:.1f}% from 52W Low (still bottoming)")
        elif pct_from_low <= 25:
            score += 10
            reasons.append(f"🟡 CMP +{pct_from_low:.1f}% from 52W Low (extended)")
        else:
            reasons.append(f"❌ CMP +{pct_from_low:.1f}% from 52W Low (too far)")

    # 2. Uptrend: CMP > 200 DMA (max 15 pts)
    dma200 = get_num(["200 dma"])
    if cmp and dma200 and dma200 > 0:
        if cmp > dma200:
            score += 15
            reasons.append("✅ CMP above 200 DMA (uptrend confirmed)")
        else:
            diff_pct = ((cmp - dma200) / dma200) * 100
            if diff_pct > -10:
                score += 7
                reasons.append(f"🟡 CMP {diff_pct:.1f}% below 200 DMA (near support)")
            else:
                reasons.append(f"❌ CMP {diff_pct:.1f}% below 200 DMA (downtrend)")

    # 3. Volume/Activity (max 10 pts)
    vol = get_num(["volume"])
    if vol and vol > 0:
        if vol >= 10_000_000:
            score += 10
            reasons.append(f"✅ High volume: {vol:,.0f}")
        elif vol >= 1_000_000:
            score += 6
            reasons.append(f"🟡 Moderate volume: {vol:,.0f}")
        else:
            score += 2
            reasons.append(f"⚠️ Low volume: {vol:,.0f}")

    # 4. Zero or Low Debt (max 10 pts)
    de = get_num(["d/e ratio", "debt", "d/e"])
    if de is not None:
        if de <= 0.1:
            score += 10
            reasons.append(f"✅ Debt-Free / Zero Debt (D/E={de:.2f})")
        elif de <= 0.5:
            score += 7
            reasons.append(f"✅ Very Low Debt (D/E={de:.2f})")
        elif de <= 1.0:
            score += 4
            reasons.append(f"🟡 Manageable Debt (D/E={de:.2f})")
        else:
            reasons.append(f"❌ High Debt (D/E={de:.2f})")

    # 5. Positive Net Profit (max 10 pts)
    np_val = get_num(["net profit"])
    if np_val is not None:
        if np_val > 0:
            score += 10
            reasons.append(f"✅ Profitable: Net Profit ₹{np_val:.1f} Cr")
        else:
            reasons.append(f"❌ Loss Making: Net Profit ₹{np_val:.1f} Cr")

    # 6. Good RONW% (max 10 pts)
    ronw = get_num(["ronw"])
    if ronw is not None:
        if ronw >= 15:
            score += 10
            reasons.append(f"✅ Strong RONW: {ronw:.1f}%")
        elif ronw >= 8:
            score += 6
            reasons.append(f"🟡 Moderate RONW: {ronw:.1f}%")
        elif ronw > 0:
            score += 2
            reasons.append(f"⚠️ Low RONW: {ronw:.1f}%")
        else:
            reasons.append(f"❌ Negative RONW: {ronw:.1f}%")

    # 7. Strong Promoter Holding (max 8 pts)
    promo = get_num(["promoters %", "promoter"])
    if promo is not None:
        if promo >= 50:
            score += 8
            reasons.append(f"✅ Promoter Holding: {promo:.1f}%")
        elif promo >= 35:
            score += 5
            reasons.append(f"🟡 Promoter Holding: {promo:.1f}%")
        else:
            reasons.append(f"⚠️ Low Promoter: {promo:.1f}%")

    # 8. Low Pledge (max 7 pts)
    pledge = get_num(["pledged %", "pledged"])
    if pledge is not None:
        if pledge == 0:
            score += 7
            reasons.append("✅ Zero Pledged Shares")
        elif pledge <= 5:
            score += 4
            reasons.append(f"🟡 Low Pledge: {pledge:.1f}%")
        else:
            reasons.append(f"❌ High Pledge: {pledge:.1f}%")

    # 9. Good Revenue / Net Sales (max 0 pts — qualitative flag)
    sales = get_num(["net sales", "net sale"])
    if sales and sales > 0:
        reasons.append(f"📊 Net Sales: ₹{sales:.1f} Cr")

    # Grade
    if score >= 75:
        grade = "🟢 STRONG BUY"
    elif score >= 55:
        grade = "🟡 WATCHLIST"
    elif score >= 35:
        grade = "🟠 CAUTION"
    else:
        grade = "🔴 AVOID"

    return score, grade, reasons


# ==========================================
# 📊 WATCHLIST MANAGER HELPERS
# ==========================================
WATCHLIST_SHEET_NAME = "Watchlist"

def get_gspread_client():
    """Return an authorised gspread client (uncached — for writes)."""
    if "gcp_service_account" not in st.secrets:
        return None
    info = st.secrets["gcp_service_account"]
    if isinstance(info, str):
        info = json.loads(info)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(info, scopes=scope)
    return gspread.authorize(creds)

SPREADSHEET_ID = "1SFhuZbLLlwwFsNo1k2RRx_Zp6bAkRR20W0F_zTwgdwU"

def ensure_watchlist_sheet(client):
    """Create Watchlist sheet if it doesn't exist; return worksheet."""
    try:
        ss = client.open_by_key(SPREADSHEET_ID)
        try:
            return ss.worksheet(WATCHLIST_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=WATCHLIST_SHEET_NAME, rows=500, cols=6)
            ws.append_row(["Symbol", "CMP", "Note", "BF Score", "BF Grade", "Added On"])
            return ws
    except Exception:
        return None

def load_watchlist_from_sheet():
    """Load watchlist dict from Google Sheet into session state."""
    client = get_gspread_client()
    if not client:
        return
    ws = ensure_watchlist_sheet(client)
    if not ws:
        return
    try:
        records = ws.get_all_records()
        loaded = {}
        for r in records:
            sym = str(r.get("Symbol", "")).strip()
            if sym:
                loaded[sym] = {
                    "note":  str(r.get("Note", "")),
                    "cmp":   str(r.get("CMP", "")),
                    "bf_score": str(r.get("BF Score", "")),
                    "bf_grade": str(r.get("BF Grade", "")),
                    "added": str(r.get("Added On", "")),
                }
        st.session_state.watchlist = loaded
    except Exception:
        pass

def save_watchlist_to_sheet():
    """Overwrite watchlist sheet with current session_state.watchlist."""
    client = get_gspread_client()
    if not client:
        st.warning("⚠️ Google Sheet write failed — check secrets.")
        return False
    ws = ensure_watchlist_sheet(client)
    if not ws:
        return False
    try:
        ws.clear()
        ws.append_row(["Symbol", "CMP", "Note", "BF Score", "BF Grade", "Added On"])
        for sym, info in st.session_state.watchlist.items():
            ws.append_row([
                sym,
                info.get("cmp", ""),
                info.get("note", ""),
                info.get("bf_score", ""),
                info.get("bf_grade", ""),
                info.get("added", ""),
            ])
        return True
    except Exception as e:
        st.warning(f"⚠️ Sheet write error: {e}")
        return False

def watchlist_add(sym, cmp="", note="", bf_score="", bf_grade=""):
    st.session_state.watchlist[sym] = {
        "cmp": cmp, "note": note,
        "bf_score": bf_score, "bf_grade": bf_grade,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

def watchlist_remove(sym):
    st.session_state.watchlist.pop(sym, None)

# ── Load watchlist once per session ──────────────────────────────────────
if "watchlist_loaded" not in st.session_state:
    load_watchlist_from_sheet()
    st.session_state.watchlist_loaded = True


# ==========================================
# 🎯 GTT ORDER CALCULATOR HELPER
# ==========================================
def compute_gtt(row_data: dict, cols: list) -> dict:
    """
    Auto-calculate Stop-Loss, Targets & ATR-based GTT levels from row data.
    Returns a dict with all computed values.
    """
    def _num(keys):
        for k in keys:
            for c in cols:
                if k in c.lower():
                    try:
                        v = str(row_data.get(c, "")).replace(",", "").replace("%", "").strip()
                        return float(v)
                    except (ValueError, TypeError):
                        pass
        return None

    cmp   = _num(["cmp"])
    high  = _num(["52w high", "52 week high", "52wk high"])
    low   = _num(["52w low",  "52 week low",  "52wk low"])
    dma50 = _num(["50 dma", "50dma"])
    dma200= _num(["200 dma","200dma"])

    result = {"cmp": cmp, "52w_high": high, "52w_low": low, "dma50": dma50, "dma200": dma200}

    if cmp and high and low:
        # Approximate ATR from 52W range (simplified)
        atr_approx = (high - low) / 52          # weekly range → ~1 week ATR
        result["atr_approx"] = round(atr_approx, 2)

        # Stop-loss levels
        result["sl_tight"]    = round(cmp - 1.0 * atr_approx, 2)   # 1× ATR
        result["sl_standard"] = round(cmp - 1.5 * atr_approx, 2)   # 1.5× ATR
        result["sl_wide"]     = round(cmp - 2.0 * atr_approx, 2)   # 2× ATR (swing)

        # Target levels (2:1 RR default)
        rr = 2.0
        sl_gap = cmp - result["sl_standard"]
        result["target_1r"]  = round(cmp + sl_gap * 1.0, 2)
        result["target_2r"]  = round(cmp + sl_gap * rr,  2)
        result["target_3r"]  = round(cmp + sl_gap * 3.0, 2)

        # Trailing SL at 50 DMA
        result["trail_sl_50dma"]  = round(dma50,  2) if dma50  else None
        result["trail_sl_200dma"] = round(dma200, 2) if dma200 else None

        # % risk
        result["risk_pct"] = round((sl_gap / cmp) * 100, 2) if cmp else None

    return result


# ==========================================
# 📊 AI RESULT → EXCEL EXPORT HELPER
# ==========================================
def ai_results_to_excel(history: list) -> bytes:
    """Convert ai_history list → Excel bytes for download."""
    if not history:
        return b""
    df = pd.DataFrame(history, columns=["Symbol", "Model", "Query", "AI Result", "Timestamp"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="AI Analysis")
        ws = writer.sheets["AI Analysis"]
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 40
        ws.column_dimensions["D"].width = 80
        ws.column_dimensions["E"].width = 20
    return buf.getvalue()


# ==========================================
# 📑 SIDEBAR CONTROLS
# ==========================================
if st.sidebar.button("🧹 Clear All Filters", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key.startswith("filter_") or key == "search_query": del st.session_state[key]
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔍 Global Search")
search_query = st.sidebar.text_input("Search by Symbol, Name, etc...", key="search_query")

st.sidebar.markdown("---")
st.sidebar.header("📑 Select a Tab")
sheet_names = ["Top 250 Stocks", "Final List", "Final List 2", "Diff @ 200 DMA", "+%", "-%"]
selected_sheet = st.sidebar.selectbox("Choose sheet", sheet_names, key="filter_sheet")

# ---------- Main Execution ----------
st.markdown(f"<p style='font-size:0.85rem; font-weight:bold; margin:0; padding:0;'>📄 {selected_sheet}</p>", unsafe_allow_html=True)

with st.spinner("Downloading data from Google API..."):
    raw_df = load_sheet_data_with_colors(selected_sheet)

if not raw_df.empty:

    guess_idx = 0
    actual_cols = [c for c in raw_df.columns if not c.startswith("_bg_") and not c.startswith("_txt_")]

    for i, col_name in enumerate(actual_cols):
        if col_name.lower() in ["nse code", "symbol", "ticker", "stock symbol", "id", "stock"]:
            guess_idx = i
            break

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Settings")
    selected_symbol_col = st.sidebar.selectbox("Symbol Column:", actual_cols, index=guess_idx, key="filter_symbol_col")

    final_df = process_hyperlinks(raw_df, selected_symbol_col)
    filtered_df = final_df.copy()

    if search_query:
        mask = filtered_df[actual_cols].astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        filtered_df = filtered_df[mask]

    # ==========================================
    # 🎨 COLOR FILTERS
    # ==========================================
    st.sidebar.markdown("---")
    st.sidebar.header("🎨 Color Filters")
    color_filter_col = st.sidebar.selectbox("Select Column to Filter by Color:", ["None"] + actual_cols, key="filter_color_col")

    if color_filter_col != "None":
        bg_col_reference = f"_bg_{color_filter_col}"
        if bg_col_reference in filtered_df.columns:
            unique_hexes = filtered_df[bg_col_reference].unique()

            color_dictionary = {
                "#ffffff": "⚪ White (Default)",
                "#0f9d58": "🟢 Green",
                "#ea4335": "🔴 Red",
                "#f4b400": "🟡 Yellow",
                "#4285f4": "🔵 Blue",
                "#ff9900": "🟠 Orange",
                "#b6d7a8": "🟩 Light Green",
                "#f4cccc": "🟥 Light Red",
                "#d9d2e9": "🟪 Light Purple"
            }

            ui_color_options = []
            for hx in unique_hexes:
                hx_lower = str(hx).lower()
                if hx_lower in color_dictionary:
                    ui_color_options.append(color_dictionary[hx_lower])
                else:
                    ui_color_options.append(f"🎨 Custom Hex: {hx_lower}")

            selected_ui_colors = st.sidebar.multiselect(f"Select Colors in '{color_filter_col}':", sorted(ui_color_options), key="filter_color_selections")

            if selected_ui_colors:
                valid_hexes_to_keep = []
                for ui_choice in selected_ui_colors:
                    for hex_key, name in color_dictionary.items():
                        if name == ui_choice:
                            valid_hexes_to_keep.append(hex_key)
                    if ui_choice.startswith("🎨 Custom Hex: "):
                        valid_hexes_to_keep.append(ui_choice.replace("🎨 Custom Hex: ", ""))
                filtered_df = filtered_df[filtered_df[bg_col_reference].str.lower().isin(valid_hexes_to_keep)]

    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Categorical Filters")
    active_filters = [c for c in actual_cols if any(key in c.lower() for key in ["cumulative average", "industry", "sector", "output", "start gtt order"])]
    for col_to_filter in active_filters:
        unique_options = sorted([val for val in final_df[col_to_filter].unique() if str(val).strip() != ""])
        selected_options = st.sidebar.multiselect(f"Filter by {col_to_filter}:", options=unique_options, key=f"filter_cat_{col_to_filter}")
        if selected_options:
            filtered_df = filtered_df[filtered_df[col_to_filter].isin(selected_options)]

    st.sidebar.markdown("---")
    st.sidebar.header("📈 DMA Trend Filter")
    dma_choice = st.sidebar.selectbox("Select DMA Condition:", [
        "All (No Filter)", "50 DMA < 100 DMA < 200 DMA", "50 DMA > 100 DMA > 200 DMA",
        "50 DMA > 200 DMA", "50 DMA < 200 DMA"], key="filter_dma_trend")

    if dma_choice != "All (No Filter)":
        dma50_col = next((c for c in actual_cols if "50 dma" in c.lower()), None)
        dma100_col = next((c for c in actual_cols if "100 dma" in c.lower()), None)
        dma200_col = next((c for c in actual_cols if "200 dma" in c.lower()), None)

        if dma50_col and dma200_col:
            s50 = pd.to_numeric(filtered_df[dma50_col].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce')
            s200 = pd.to_numeric(filtered_df[dma200_col].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce')

            if dma_choice == "50 DMA > 200 DMA": filtered_df = filtered_df[s50 > s200]
            elif dma_choice == "50 DMA < 200 DMA": filtered_df = filtered_df[s50 < s200]
            elif dma100_col:
                s100 = pd.to_numeric(filtered_df[dma100_col].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce')
                if dma_choice == "50 DMA < 100 DMA < 200 DMA": filtered_df = filtered_df[(s50 < s100) & (s100 < s200)]
                elif dma_choice == "50 DMA > 100 DMA > 200 DMA": filtered_df = filtered_df[(s50 > s100) & (s100 > s200)]

    st.sidebar.markdown("---")
    st.sidebar.header("📊 Numeric Range Filters")

    diff_200_col = next((c for c in actual_cols if "diff" in c.lower() and "200" in c.lower()), None)
    if diff_200_col: filtered_df = apply_numeric_slider(filtered_df, diff_200_col, st.sidebar, "Diff. from 200 DMA Range:")

    low_pct_col = next((c for c in actual_cols if "52" in c.lower() and "low" in c.lower() and ("%" in c.lower() or "per" in c.lower())), None)
    if low_pct_col: filtered_df = apply_numeric_slider(filtered_df, low_pct_col, st.sidebar, "From 52W Low Range:")

    high_pct_col = next((c for c in actual_cols if "52" in c.lower() and "high" in c.lower() and ("%" in c.lower() or "per" in c.lower())), None)
    if high_pct_col: filtered_df = apply_numeric_slider(filtered_df, high_pct_col, st.sidebar, "From 52W High Range:")

    numeric_targets = ["Volume", "CMP", "Price %", "Promoters %", "Institutional %", "Face Value", "Net Profit", "EPS", "RONW %", "Market Cap", "Enterprise Value"]
    processed_cols = {diff_200_col, low_pct_col, high_pct_col}
    for target in numeric_targets:
        col_match = next((c for c in actual_cols if target.lower() in c.lower() and c not in processed_cols), None)
        if col_match:
            filtered_df = apply_numeric_slider(filtered_df, col_match, st.sidebar)
            processed_cols.add(col_match)

    st.sidebar.markdown("---")
    st.sidebar.header("📅 Date Filters")
    high_date_col = next((c for c in actual_cols if "52w high date" in c.lower()), None)
    low_date_col = next((c for c in actual_cols if "52w low date" in c.lower()), None)
    if high_date_col: filtered_df = apply_date_filter(filtered_df, high_date_col, st.sidebar)
    if low_date_col: filtered_df = apply_date_filter(filtered_df, low_date_col, st.sidebar)

    # ==========================================
    # 📊 SIDEBAR — WATCHLIST MANAGER
    # ==========================================
    st.sidebar.markdown("---")
    st.sidebar.header("📊 My Watchlist")

    if st.session_state.watchlist:
        wl_count = len(st.session_state.watchlist)
        st.sidebar.caption(f"🔖 {wl_count} stock{'s' if wl_count > 1 else ''} saved")
        for _ws, _wi in list(st.session_state.watchlist.items()):
            _col1, _col2 = st.sidebar.columns([3, 1])
            _col1.markdown(
                f"**{_ws}** {'`' + _wi['cmp'] + '`' if _wi['cmp'] else ''}<br>"
                f"<small style='color:gray'>{_wi.get('note','')[:35]}</small>",
                unsafe_allow_html=True,
            )
            if _col2.button("❌", key=f"wl_rm_{_ws}", help=f"Remove {_ws}"):
                watchlist_remove(_ws)
                save_watchlist_to_sheet()
                st.rerun()
        st.sidebar.markdown("")
        # Download watchlist as Excel
        _wl_df = pd.DataFrame([
            {"Symbol": s, "CMP": d["cmp"], "Note": d["note"],
             "BF Score": d.get("bf_score",""), "BF Grade": d.get("bf_grade",""),
             "Added On": d["added"]}
            for s, d in st.session_state.watchlist.items()
        ])
        _wl_buf = io.BytesIO()
        with pd.ExcelWriter(_wl_buf, engine="openpyxl") as _w:
            _wl_df.to_excel(_w, index=False, sheet_name="Watchlist")
        st.sidebar.download_button(
            "📥 Download Watchlist Excel",
            data=_wl_buf.getvalue(),
            file_name=f"Watchlist_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.sidebar.info("No stocks in watchlist yet.\nAdd from the workspace panel below.")

    # ==========================================
    # 📤 SIDEBAR — AI ANALYSIS EXCEL EXPORT
    # ==========================================
    if st.session_state.ai_history:
        st.sidebar.markdown("---")
        st.sidebar.header("🤖 AI History Export")
        st.sidebar.caption(f"{len(st.session_state.ai_history)} analyses saved this session")
        _ai_xl = ai_results_to_excel(st.session_state.ai_history)
        st.sidebar.download_button(
            "📥 Download All AI Results (Excel)",
            data=_ai_xl,
            file_name=f"AI_Analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        if st.sidebar.button("🗑️ Clear AI History", use_container_width=True):
            st.session_state.ai_history = []
            st.rerun()

    # ==========================================
    # 🎨 DYNAMIC COLUMN REORDERING LOGIC
    # ==========================================
    core_sequence = []

    if selected_symbol_col in filtered_df.columns:
        core_sequence.append(selected_symbol_col)

    vol_target = next((c for c in actual_cols if "volume" in c.lower()), None)
    if vol_target and vol_target not in core_sequence: core_sequence.append(vol_target)

    close_target = next((c for c in actual_cols if "close price" in c.lower() or "prev" in c.lower()), None)
    if close_target and close_target not in core_sequence: core_sequence.append(close_target)

    cmp_target = next((c for c in actual_cols if "cmp" in c.lower()), None)
    if cmp_target and cmp_target not in core_sequence: core_sequence.append(cmp_target)

    pct_target = next((c for c in actual_cols if "price %" in c.lower()), None)
    if pct_target and pct_target not in core_sequence: core_sequence.append(pct_target)

    high_target = next((c for c in actual_cols if "52" in c.lower() and "high" in c.lower() and "date" not in c.lower() and "%" not in c.lower()), None)
    if high_target and high_target not in core_sequence: core_sequence.append(high_target)

    low_target = next((c for c in actual_cols if "52" in c.lower() and "low" in c.lower() and "date" not in c.lower() and "%" not in c.lower()), None)
    if low_target and low_target not in core_sequence: core_sequence.append(low_target)

    all_other_fields = [c for c in filtered_df.columns if c not in core_sequence and not c.startswith("_bg_") and not c.startswith("_txt_") and c != "_raw_symbol_"]
    hidden_meta_attributes = [c for c in filtered_df.columns if c.startswith("_bg_") or c.startswith("_txt_") or c == "_raw_symbol_"]

    enforced_column_layout = core_sequence + all_other_fields + hidden_meta_attributes
    filtered_df = filtered_df[enforced_column_layout]

    # ==========================================
    # 📌 TOP UI: ROWS COUNT, COLUMN WIDTH ADJUSTER & EXCEL DOWNLOAD
    # ==========================================
    st.markdown("---")

    export_df = clean_for_export(filtered_df)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        safe_sheet_name = selected_sheet[:31].replace(":", "").replace("/", "")
        export_df.to_excel(writer, index=False, sheet_name=safe_sheet_name)

    top_col1, top_col2 = st.columns([4, 1])

    with top_col1:
        sizing_mode = st.radio(
            "📏 Column Width Adjustment:",
            ["Default", "✅ Fit to Row 1", "✅✅ Fit to Row 2"],
            horizontal=True,
            help="Automatically adjust the column widths based on the text length of the selected row."
        )

    with top_col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📥 Download as Excel",
            data=buffer.getvalue(),
            file_name=f"{selected_sheet}_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=False
        )

    bot_col1, bot_col2 = st.columns([1, 4])
    with bot_col1:
        st.write(f"**Rows:** {filtered_df.shape[0]} | **Columns:** {len(actual_cols)}")

    with bot_col2:
        url_placeholder = st.empty()

    # ==========================================
    # 🎨 AG GRID INITIALIZATION WITH SELECTION ENGINE
    # ==========================================
    html_renderer = JsCode("""
    class HtmlRenderer {
        init(params) {
            this.eGui = document.createElement('span');
            this.eGui.innerHTML = params.value ? String(params.value) : '';
        }
        getGui() {
            return this.eGui;
        }
    }
    """)

    exact_mirror_style = JsCode("""
    function(params) {
        let colName = params.colDef.field;
        let c_low = colName.toLowerCase();

        let bgCol = "_bg_" + colName;
        let txtCol = "_txt_" + colName;

        let bgColor = params.data[bgCol];
        let txtColor = params.data[txtCol];

        let isTargetCol = c_low.includes("cmp") || c_low.includes("close price") || c_low.includes("prev");

        if (isTargetCol) {
            if (!bgColor || bgColor.toLowerCase() === '#ffffff') return null;
            return {
                'backgroundColor': bgColor,
                'color': txtColor || '#000000',
                'fontWeight': (txtColor === '#ffffff' || bgColor === '#0f9d58' || bgColor === '#ea4335') ? 'bold' : 'normal'
            };
        }

        if (!bgColor || bgColor.toLowerCase() === '#ffffff') {
            return { 'color': '#000000' };
        }

        return {
            'backgroundColor': bgColor,
            'color': '#000000',
            'fontWeight': (bgColor === '#0f9d58' || bgColor === '#ea4335') ? 'bold' : 'normal'
        };
    }
    """)

    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_selection(selection_mode="single", use_checkbox=True)
    gb.configure_side_bar(filters_panel=False, columns_panel=True)

    priority_columns_lower = ["nse code", "id", "company name", "stock name", "symbol", "industry", "sector"]
    is_first_visible_column = True

    for col in filtered_df.columns:
        if col.startswith("_bg_") or col.startswith("_txt_") or col == "_raw_symbol_":
            gb.configure_column(col, hide=True)
            continue

        if sizing_mode == "✅ Fit to Row 1" and len(filtered_df) > 0:
            char_count = get_clean_text_length(filtered_df.iloc[0][col])
            header_count = len(str(col))
            base_calc = int(max(char_count, header_count) * 7 + 22)
            if is_first_visible_column: base_calc += 30
            width, min_width = (base_calc, 40)

        elif sizing_mode == "✅✅ Fit to Row 2" and len(filtered_df) > 1:
            char_count = get_clean_text_length(filtered_df.iloc[1][col])
            header_count = len(str(col))
            base_calc = int(max(char_count, header_count) * 7 + 22)
            if is_first_visible_column: base_calc += 30
            width, min_width = (base_calc, 40)

        else:
            width, min_width = (220, 150) if col.lower() in priority_columns_lower else (120, 80)

        pinned_value = "left" if is_first_visible_column else None
        if is_first_visible_column: is_first_visible_column = False

        c_low = col.lower()
        if any(k in c_low for k in ["trading view", "history data", "screener", "zerodha", "chartlink", "market smith", "official nse", "nse"]):
            gb.configure_column(col, width=width, minWidth=min_width, sortable=True, filter=True, resizable=True,
                editable=False, pinned=pinned_value, cellRenderer=html_renderer, cellStyle=exact_mirror_style)
        else:
            gb.configure_column(col, width=width, minWidth=min_width, sortable=True, filter=True, resizable=True,
                editable=False, pinned=pinned_value, cellStyle=exact_mirror_style)

    gb.configure_grid_options(domLayout="normal", rowHeight=35, headerHeight=45, enableCellTextSelection=True, ensureDomOrder=True, alwaysShowHorizontalScroll=True)
    grid_options = gb.build()

    grid_response = AgGrid(
        filtered_df, gridOptions=grid_options, theme="streamlit", update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True, fit_columns_on_grid_load=False, enable_enterprise_modules=False, height=400, width='100%',
        key="primary_stock_table_grid"
    )

    # ==========================================
    # 🎯 SELECTION WORKSPACE (LINKS + EMBED PANELS)
    # ==========================================
    selected_rows = grid_response.get("selected_rows", [])
    if selected_rows is not None and len(selected_rows) > 0:
        sel_row = selected_rows.iloc[0] if isinstance(selected_rows, pd.DataFrame) else selected_rows[0]
        sym = str(sel_row.get("_raw_symbol_", "")).strip()

        if sym:
            with url_placeholder.container():
                st.markdown(
                    f"**⚡ {sym} Links:** "
                    f"[Trading View (🔗)](https://www.tradingview.com/symbols/{sym}/) &nbsp;|&nbsp; "
                    f"[History Data (🔗)](https://www.equitypandit.com/historical-data/{sym}) &nbsp;|&nbsp; "
                    f"[Screener (🔗)](https://www.screener.in/company/{sym}) &nbsp;|&nbsp; "
                    f"[Zerodha (🔗)](https://zerodha.com/markets/stocks/NSE/{sym}) &nbsp;|&nbsp; "
                    f"[Chartlink (🔗)](https://chartink.com/stocks-new?load-snapshot=exponential-moving-average-simple-moving-average-simple-moving-average-moving-average-convergence-divergence-chart-snapshot-175&symbol={sym}) &nbsp;|&nbsp; "
                    f"[Market Smith (🔗)](https://marketsmithindia.com/mstool/eval/{sym}/evaluation.jsp) &nbsp;|&nbsp; "
                    f"[NSE URL (🔗)](https://www.nseindia.com/get-quotes/equity?symbol={sym})"
                )

            st.markdown(f"---")
            st.subheader(f"🛠️ Live Workspace Panel: {sym}")
            box_height = st.slider("📏 Adjust Panel Box Height (px):", min_value=300, max_value=1000, value=500, step=50, key="panel_height_slider")

            ws_tabs = st.tabs([
                "📈 Chart & Trade Info (NSE Component)", "📋 History Data (EquityPandit)",
                "🎯 Bullish/Bearish Zone", "📁 Screener Documents",
                "🪁 Zerodha Portal", "📊 MarketSmith India", "📉 TradingView Symbol Profile",
                "🤖 AI Stock Analysis", "💻 AI Pine Script Builder",
                "🔬 Bottom Fishing Score",
                "🎯 GTT Order Calculator", "📊 Watchlist Manager"
            ])

            with ws_tabs[0]:
                _url0 = f"https://charting.nseindia.com/?symbol={sym}-EQ"
                st.markdown(f"**NSE Interactive Chart Frame** &nbsp;|&nbsp; [🌐 Open in Browser]({_url0})", unsafe_allow_html=False)
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url0}" width="100%" height="{box_height}" style="border:none; border-radius:5px;"></iframe>', height=box_height+20)

            with ws_tabs[1]:
                _url1 = f"https://www.equitypandit.com/historical-data/{sym.lower()}"
                st.markdown(f"**EquityPandit Historical Matrix Data** &nbsp;|&nbsp; [🌐 Open in Browser]({_url1})")
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url1}" width="100%" height="{box_height}" style="border:none; border-radius:5px; background-color:white;"></iframe>', height=box_height+20)

            with ws_tabs[2]:
                _url2 = f"https://www.equitypandit.com/share-price/{sym.lower()}#chart"
                st.markdown(f"**Bullish / Bearish Zone Indicator** &nbsp;|&nbsp; [🌐 Open in Browser]({_url2})")
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url2}" width="100%" height="{box_height}" style="border:none; border-radius:5px; background-color:white;"></iframe>', height=box_height+20)

            with ws_tabs[3]:
                _url3 = f"https://www.screener.in/company/{sym}/consolidated/"
                st.markdown(f"**Screener Corporate Filings** &nbsp;|&nbsp; [🌐 Open in Browser]({_url3})")
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url3}" width="100%" height="{box_height}" style="border:none; border-radius:5px; background-color:white;"></iframe>', height=box_height+20)

            with ws_tabs[4]:
                _url4 = f"https://zerodha.com/markets/stocks/NSE/{sym}/"
                st.markdown(f"**Zerodha Markets Financial Performance Metrics** &nbsp;|&nbsp; [🌐 Open in Browser]({_url4})")
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url4}" width="100%" height="{box_height}" style="border:none; border-radius:5px; background-color:white;"></iframe>', height=box_height+20)

            with ws_tabs[5]:
                _url5 = f"https://marketsmithindia.com/mstool/eval/{sym.lower()}/evaluation.jsp"
                st.markdown(f"**MarketSmith India Institutional Trading Evaluation Engine** &nbsp;|&nbsp; [🌐 Open in Browser]({_url5})")
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url5}" width="100%" height="{box_height}" style="border:none; border-radius:5px; background-color:white;"></iframe>', height=box_height+20)

            with ws_tabs[6]:
                _url6 = f"https://www.tradingview.com/symbols/{sym}/"
                st.markdown(f"**TradingView Comprehensive Asset Market Registry Summary Profile** &nbsp;|&nbsp; [🌐 Open in Browser]({_url6})")
                st.caption("📱 If frame is blank on mobile, tap the link above to open directly.")
                components.html(f'<iframe src="{_url6}" width="100%" height="{box_height}" style="border:none; border-radius:5px; background-color:white;"></iframe>', height=box_height+20)

            with ws_tabs[7]:
                st.markdown(f"### 🤖 Ask AI About **{sym}**")

                if not ai_enabled:
                    st.warning("⚠️ No AI configured. Add `GEMINI_API_KEY` or `GROQ_API_KEY` to Streamlit secrets.")
                else:
                    # ── Model selector ──────────────────────────────────────
                    chosen_model = ai_model_selector("analysis")
                    st.caption(
                        "⚡ Groq = llama-3.3-70b (free, fast) &nbsp;|&nbsp; 🧠 Gemini = gemini-2.5-flash"
                        if groq_enabled and gemini_enabled
                        else ("⚡ Groq connected" if groq_enabled else "🧠 Gemini connected")
                    )
                    st.write("Using the live data pulled from your dashboard, the AI can analyze technicals, ranges, and context.")

                    ai_query = st.text_area(
                        "Your Query:",
                        value=f"Based on the current data provided, give me a quick summary of the technical performance and trend for {sym}.",
                        height=80,
                        key="ai_query_analysis"
                    )

                    if st.button("✨ Generate AI Analysis", use_container_width=True, key="btn_ai_analysis"):
                        with st.spinner(f"Analyzing {sym} with {chosen_model}..."):
                            try:
                                clean_row_context = {k: v for k, v in sel_row.items() if not str(k).startswith('_')}
                                prompt = f"""
You are a professional stock market analyst evaluating Indian NSE stocks.
The user is asking about the stock: {sym}.

Here is the live data extracted directly from the user's dashboard for this stock:
{clean_row_context}

User Query: {ai_query}

Please provide a clear, concise, and professional response.
"""
                                ai_result = call_ai(prompt, chosen_model)
                                st.session_state["last_ai_result"] = {"sym": sym, "model": chosen_model, "query": ai_query, "result": ai_result}
                                # Save to history
                                st.session_state.ai_history.append([
                                    sym, chosen_model, ai_query, ai_result,
                                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ])
                                st.info(ai_result)
                            except Exception as e:
                                st.error(f"AI error: {e}")

                    # ── Show export & share buttons if result exists ────────
                    if st.session_state.get("last_ai_result", {}).get("sym") == sym:
                        _last = st.session_state["last_ai_result"]
                        _res_text = _last["result"]

                        st.markdown("---")
                        _ec1, _ec2, _ec3 = st.columns(3)

                        # Excel download (single result)
                        with _ec1:
                            _single_xl = ai_results_to_excel([[
                                sym, _last["model"], _last["query"], _res_text,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ]])
                            st.download_button(
                                "📥 Save as Excel",
                                data=_single_xl,
                                file_name=f"AI_{sym}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key="dl_ai_excel_analysis"
                            )

                        # WhatsApp share
                        with _ec2:
                            _wa_text = urllib.parse.quote(
                                f"📊 *{sym} AI Analysis* ({_last['model']})\n\n{_res_text[:800]}"
                                + ("\n\n_(truncated)_" if len(_res_text) > 800 else "")
                            )
                            st.markdown(
                                f"<a href='https://wa.me/?text={_wa_text}' target='_blank'>"
                                f"<button style='width:100%;padding:8px;background:#25D366;color:white;"
                                f"border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:bold;'>"
                                f"📱 Share on WhatsApp</button></a>",
                                unsafe_allow_html=True
                            )

                        # Telegram share
                        with _ec3:
                            _tg_text = urllib.parse.quote(
                                f"📊 {sym} AI Analysis ({_last['model']})\n\n{_res_text[:800]}"
                            )
                            st.markdown(
                                f"<a href='https://t.me/share/url?url=NSEDashboard&text={_tg_text}' target='_blank'>"
                                f"<button style='width:100%;padding:8px;background:#229ED9;color:white;"
                                f"border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:bold;'>"
                                f"✈️ Share on Telegram</button></a>",
                                unsafe_allow_html=True
                            )

                    st.markdown("---")
                    st.markdown("**💡 Suggested Prompts** — copy any prompt below and paste it into the query box above:")
                    prompt_lines = "\n".join(
                        [f"{i+1}. {p.replace('{sym}', sym)}" for i, p in enumerate(SUGGESTED_AI_PROMPTS)]
                    )
                    st.text(prompt_lines)

            with ws_tabs[8]:
                st.markdown(f"### 💻 AI Pine Script Generator for **{sym}**")

                if not ai_enabled:
                    st.warning("⚠️ No AI configured. Add `GEMINI_API_KEY` or `GROQ_API_KEY` to Streamlit secrets.")
                else:
                    chosen_model_pine = ai_model_selector("pine")
                    st.write("Generate a custom TradingView Pine Script v5 strategy tailored to this stock's current metrics.")

                    strategy_focus = st.selectbox("Select Strategy Focus:", [
                        "Volume Breakout with Dynamic Stop Loss",
                        "Moving Average Crossover (50/100/200 DMA)",
                        "Trend Following with Trailing Stop",
                        "Mean Reversion from 52W High/Low"
                    ], key="pine_strategy_focus")

                    pine_query = st.text_area("Additional Custom Rules (Optional):", value=f"Include risk management parameters and plot signals on the chart.", height=60, key="pine_query")

                    if st.button("⚙️ Generate TradingView Pine Script", use_container_width=True, key="btn_pine"):
                        with st.spinner(f"Writing Pine Script v5 code for {sym}..."):
                            try:
                                clean_row_context = {k: v for k, v in sel_row.items() if not str(k).startswith('_')}
                                prompt = f"""
You are an expert quantitative developer specializing in TradingView Pine Script v5.

Write a complete, ready-to-copy Pine Script v5 strategy for the stock: {sym}.

Strategy Focus: {strategy_focus}
Custom Rules: {pine_query}

Here is the live fundamental and technical data for {sym} to incorporate as baseline context or threshold values if relevant:
{clean_row_context}

Formatting Requirements:
1. Start with `//@version=5` and `strategy("{sym} Custom Script", overlay=true)`
2. Include clear comments explaining the logic.
3. Provide ONLY the Pine Script code inside a markdown code block, no other conversational text.
"""
                                pine_result = call_ai(prompt, chosen_model_pine)
                                st.session_state["last_pine_result"] = {"sym": sym, "result": pine_result}
                                st.markdown("### 📋 Your Custom Strategy Code:")
                                st.write("Copy the code below and paste it into the TradingView Pine Editor.")
                                st.markdown(pine_result)
                            except Exception as e:
                                st.error(f"AI error: {e}")

                    # Excel download for pine script
                    if st.session_state.get("last_pine_result", {}).get("sym") == sym:
                        _pine_res = st.session_state["last_pine_result"]["result"]
                        _pine_xl = ai_results_to_excel([[
                            sym, "Pine Script", strategy_focus, _pine_res,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ]])
                        st.download_button(
                            "📥 Save Pine Script as Excel",
                            data=_pine_xl,
                            file_name=f"PineScript_{sym}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_pine_excel"
                        )

                    st.markdown("---")
                    st.markdown("**📋 Custom Rules Reference** — copy any rule and paste it into the Additional Custom Rules box above:")
                    st.text(PINE_CUSTOM_RULES)

            # ==========================================
            # 🔬 BOTTOM FISHING SCORE TAB (NEW!)
            # ==========================================
            with ws_tabs[9]:
                st.markdown(f"### 🔬 Bottom Fishing Analysis: **{sym}**")
                st.caption("Scores this stock on 8 key criteria for buying from the bottom. Based entirely on your live sheet data.")

                clean_sel = {k: v for k, v in sel_row.items() if not str(k).startswith('_')}
                bf_score, bf_grade, bf_reasons = compute_bottom_fishing_score(clean_sel, actual_cols)

                # Score gauge
                score_color = "#16e37f" if bf_score >= 75 else ("#f4b400" if bf_score >= 55 else ("#ff9900" if bf_score >= 35 else "#ea4335"))
                st.markdown(f"""
                <div style="background:{score_color}22; border-left:6px solid {score_color}; padding:16px 20px; border-radius:8px; margin-bottom:16px;">
                    <div style="font-size:2rem; font-weight:bold; color:{score_color};">{bf_score}/100</div>
                    <div style="font-size:1.3rem; font-weight:bold;">{bf_grade}</div>
                    <div style="font-size:0.85rem; color:#555; margin-top:4px;">Bottom Fishing Composite Score for {sym}</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("#### 📋 Detailed Scoring Breakdown")
                for reason in bf_reasons:
                    st.markdown(f"- {reason}")

                st.markdown("---")
                st.markdown("#### 📖 Scoring Criteria")
                criteria_md = """
| # | Criteria | Max Points | Description |
|---|----------|-----------|-------------|
| 1 | **52W Low Proximity** | 30 | CMP is 8–15% above 52W Low (ideal entry zone) |
| 2 | **Uptrend (200 DMA)** | 15 | CMP above 200 DMA = confirmed uptrend |
| 3 | **Volume Activity** | 10 | High trading volume = institutional interest |
| 4 | **Low/Zero Debt** | 10 | D/E ratio ≤ 0.1 is ideal (no loan burden) |
| 5 | **Net Profitability** | 10 | Positive net profit confirms fundamental health |
| 6 | **RONW %** | 10 | Return on Net Worth ≥ 15% = strong business |
| 7 | **Promoter Holding** | 8 | ≥ 50% shows management confidence |
| 8 | **Zero Pledge** | 7 | No pledged shares = no financial stress |
"""
                st.markdown(criteria_md)

                st.info("💡 **Buy Strategy:** Look for scores ≥ 55 (Watchlist) or ≥ 75 (Strong Buy). "
                        "The sweet zone is CMP at 8–15% above 52W Low with uptrend confirmed (CMP > 200 DMA), "
                        "backed by positive profits, low debt, and high promoter holding. "
                        "This combination maximizes probability of a bull run from the bottom.")

                # AI-enhanced bottom analysis
                if ai_enabled:
                    st.markdown("---")
                    chosen_model_bf = ai_model_selector("bf")
                    if st.button("🤖 Get AI Deep Analysis for Bottom Buy", use_container_width=True, key="bf_ai_btn"):
                        with st.spinner(f"Running deep bottom-fishing analysis for {sym} with {chosen_model_bf}..."):
                            try:
                                prompt = f"""
You are an expert Indian stock market analyst specializing in bottom-fishing and value investing.

Stock: {sym}
Live Data from Dashboard: {clean_sel}
Bottom Fishing Score: {bf_score}/100
Grade: {bf_grade}
Scoring Breakdown: {chr(10).join(bf_reasons)}

Please provide a comprehensive bottom-fishing analysis covering:
1. Is this stock in or near the 52-week low zone? What does this mean?
2. Is the stock entering an uptrend? Evidence from DMA data.
3. Volume analysis — is there accumulation visible?
4. Fundamental health — debt, profitability, revenue growth signals.
5. Bull run potential — sector tailwinds, promoter activity, institutional interest.
6. Specific entry price zone recommendation with stop loss and target.
7. Risk factors that could delay recovery.
8. Overall verdict: Strong Buy / Watchlist / Avoid for bottom-fishing strategy.

Be specific, data-driven, and actionable for a retail investor.
"""
                                bf_ai_result = call_ai(prompt, chosen_model_bf)
                                st.session_state["last_bf_ai_result"] = {"sym": sym, "result": bf_ai_result}
                                st.session_state.ai_history.append([
                                    sym, chosen_model_bf, "Bottom Fishing Deep Analysis", bf_ai_result,
                                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ])
                                st.success("✅ AI Analysis Complete")
                                st.markdown(bf_ai_result)
                            except Exception as e:
                                st.error(f"AI error: {e}")

                    # Share buttons for BF score
                    st.markdown("---")
                    st.markdown("#### 📤 Share BF Score Card")
                    _bf_card_text = (
                        f"🔬 *Bottom Fishing Score: {sym}*\n\n"
                        f"📊 Score: *{bf_score}/100*\n"
                        f"📈 Grade: {bf_grade}\n\n"
                        + "\n".join(bf_reasons[:5])
                        + f"\n\n🕒 {datetime.now().strftime('%d %b %Y %H:%M')}\n📌 NSE Stock Dashboard"
                    )
                    _bf_wa  = urllib.parse.quote(_bf_card_text)
                    _bf_tg  = urllib.parse.quote(_bf_card_text)
                    _sh1, _sh2 = st.columns(2)
                    with _sh1:
                        st.markdown(
                            f"<a href='https://wa.me/?text={_bf_wa}' target='_blank'>"
                            f"<button style='width:100%;padding:8px;background:#25D366;color:white;"
                            f"border:none;border-radius:6px;cursor:pointer;font-weight:bold;'>"
                            f"📱 Share on WhatsApp</button></a>",
                            unsafe_allow_html=True
                        )
                    with _sh2:
                        st.markdown(
                            f"<a href='https://t.me/share/url?url=Dashboard&text={_bf_tg}' target='_blank'>"
                            f"<button style='width:100%;padding:8px;background:#229ED9;color:white;"
                            f"border:none;border-radius:6px;cursor:pointer;font-weight:bold;'>"
                            f"✈️ Share on Telegram</button></a>",
                            unsafe_allow_html=True
                        )

            # ==========================================
            # 🎯 GTT ORDER CALCULATOR TAB (NEW - ws_tabs[10])
            # ==========================================
            with ws_tabs[10]:
                st.markdown(f"### 🎯 GTT Order Calculator: **{sym}**")
                st.caption("Auto-suggest Stop-Loss, Targets & ATR-based GTT levels from your live sheet data.")

                clean_sel_gtt = {k: v for k, v in sel_row.items() if not str(k).startswith('_')}
                gtt = compute_gtt(clean_sel_gtt, actual_cols)

                if not gtt.get("cmp"):
                    st.warning("⚠️ CMP column not found in sheet data. Cannot compute GTT levels.")
                else:
                    cmp_v = gtt["cmp"]

                    # ── Summary cards row ──────────────────────────────────
                    gc1, gc2, gc3, gc4 = st.columns(4)
                    gc1.metric("📍 CMP", f"₹{cmp_v:,.2f}")
                    if gtt.get("52w_high"): gc2.metric("⬆️ 52W High", f"₹{gtt['52w_high']:,.2f}")
                    if gtt.get("52w_low"):  gc3.metric("⬇️ 52W Low",  f"₹{gtt['52w_low']:,.2f}")
                    if gtt.get("atr_approx"): gc4.metric("📊 ATR (approx)", f"₹{gtt['atr_approx']:,.2f}")

                    st.markdown("---")

                    # ── Manual ATR override ───────────────────────────────
                    st.markdown("#### ⚙️ Customize ATR Multiplier")
                    col_atr1, col_atr2 = st.columns(2)
                    manual_atr = col_atr1.number_input(
                        "Manual ATR Override (₹) — leave 0 to use auto",
                        min_value=0.0, value=0.0, step=0.5, key="gtt_manual_atr"
                    )
                    rr_ratio = col_atr2.selectbox(
                        "Risk-Reward Ratio:", ["1:1", "1:1.5", "1:2", "1:2.5", "1:3"],
                        index=2, key="gtt_rr_ratio"
                    )
                    rr_val = float(rr_ratio.split(":")[1])

                    # Recalculate with manual inputs if provided
                    effective_atr = manual_atr if manual_atr > 0 else gtt.get("atr_approx", 0)
                    if effective_atr and effective_atr > 0:
                        sl_tight    = round(cmp_v - 1.0 * effective_atr, 2)
                        sl_standard = round(cmp_v - 1.5 * effective_atr, 2)
                        sl_wide     = round(cmp_v - 2.0 * effective_atr, 2)
                        sl_gap      = cmp_v - sl_standard
                        t1 = round(cmp_v + sl_gap * 1.0,   2)
                        t2 = round(cmp_v + sl_gap * rr_val, 2)
                        t3 = round(cmp_v + sl_gap * 3.0,   2)
                        risk_pct = round((sl_gap / cmp_v) * 100, 2)

                        # ── Stop-Loss table ───────────────────────────────
                        st.markdown("#### 🛡️ Stop-Loss Levels")
                        sl_df = pd.DataFrame([
                            {"Type": "Tight SL (1× ATR)",    "Price (₹)": sl_tight,    "% Risk": round((cmp_v-sl_tight)/cmp_v*100,2),    "Use Case": "Intraday / Scalp"},
                            {"Type": "Standard SL (1.5× ATR)","Price (₹)": sl_standard,"% Risk": round((cmp_v-sl_standard)/cmp_v*100,2),"Use Case": "Swing / BTST"},
                            {"Type": "Wide SL (2× ATR)",     "Price (₹)": sl_wide,     "% Risk": round((cmp_v-sl_wide)/cmp_v*100,2),     "Use Case": "Positional"},
                        ])
                        if gtt.get("trail_sl_50dma"):
                            sl_df = pd.concat([sl_df, pd.DataFrame([{
                                "Type": "Trail SL @ 50 DMA", "Price (₹)": gtt["trail_sl_50dma"],
                                "% Risk": round((cmp_v-gtt["trail_sl_50dma"])/cmp_v*100,2) if gtt["trail_sl_50dma"] < cmp_v else 0,
                                "Use Case": "Trailing Stop"
                            }])], ignore_index=True)
                        st.dataframe(sl_df, use_container_width=True, hide_index=True)

                        # ── Target levels ─────────────────────────────────
                        st.markdown(f"#### 🎯 Target Levels (based on {rr_ratio} R:R)")
                        tgt_df = pd.DataFrame([
                            {"Target": "T1 (1R)",            "Price (₹)": t1, "% Gain": round((t1-cmp_v)/cmp_v*100,2), "Strategy": "Book 30–40%"},
                            {"Target": f"T2 ({rr_ratio} R:R)","Price (₹)": t2, "% Gain": round((t2-cmp_v)/cmp_v*100,2), "Strategy": "Book 40–50%"},
                            {"Target": "T3 (3R — runner)",   "Price (₹)": t3, "% Gain": round((t3-cmp_v)/cmp_v*100,2), "Strategy": "Hold remainder"},
                        ])
                        st.dataframe(tgt_df, use_container_width=True, hide_index=True)

                        # ── Position sizing helper ────────────────────────
                        st.markdown("#### 💰 Position Sizing Helper")
                        ps_col1, ps_col2 = st.columns(2)
                        capital = ps_col1.number_input("Capital (₹):", min_value=1000, value=100000, step=5000, key="gtt_capital")
                        risk_pct_inp = ps_col2.number_input("Max Risk % of Capital:", min_value=0.5, max_value=10.0, value=2.0, step=0.5, key="gtt_risk_pct")
                        max_loss_rs = capital * risk_pct_inp / 100
                        qty = int(max_loss_rs / (cmp_v - sl_standard)) if (cmp_v - sl_standard) > 0 else 0
                        invest_val = qty * cmp_v
                        st.success(
                            f"📦 Suggested Qty: **{qty} shares** &nbsp;|&nbsp; "
                            f"Investment: **₹{invest_val:,.0f}** &nbsp;|&nbsp; "
                            f"Max Loss: **₹{max_loss_rs:,.0f}** ({risk_pct_inp}%)"
                        )

                        # ── GTT Order summary card ────────────────────────
                        st.markdown("---")
                        st.markdown("#### 📋 GTT Order Summary (Copy-Ready)")
                        gtt_summary = (
                            f"🎯 *GTT Order: {sym}*\n\n"
                            f"📍 Entry CMP: ₹{cmp_v:,.2f}\n"
                            f"🛡️ Stop-Loss: ₹{sl_standard:,.2f} ({risk_pct:.1f}% risk)\n"
                            f"🎯 Target 1:  ₹{t1:,.2f} (+{round((t1-cmp_v)/cmp_v*100,1)}%)\n"
                            f"🎯 Target 2:  ₹{t2:,.2f} (+{round((t2-cmp_v)/cmp_v*100,1)}%)\n"
                            f"🎯 Target 3:  ₹{t3:,.2f} (+{round((t3-cmp_v)/cmp_v*100,1)}%)\n"
                            f"📦 Qty: {qty} shares | ₹{invest_val:,.0f}\n"
                            f"📊 ATR: ₹{effective_atr:.2f} | R:R {rr_ratio}\n"
                            f"🕒 {datetime.now().strftime('%d %b %Y %H:%M')}"
                        )
                        st.code(gtt_summary, language="")

                        # Share GTT summary
                        _gtt_wa = urllib.parse.quote(gtt_summary)
                        _gtt_tg = urllib.parse.quote(gtt_summary)
                        _gc1, _gc2 = st.columns(2)
                        with _gc1:
                            st.markdown(
                                f"<a href='https://wa.me/?text={_gtt_wa}' target='_blank'>"
                                f"<button style='width:100%;padding:8px;background:#25D366;color:white;"
                                f"border:none;border-radius:6px;cursor:pointer;font-weight:bold;'>"
                                f"📱 Share GTT on WhatsApp</button></a>",
                                unsafe_allow_html=True
                            )
                        with _gc2:
                            st.markdown(
                                f"<a href='https://t.me/share/url?url=Dashboard&text={_gtt_tg}' target='_blank'>"
                                f"<button style='width:100%;padding:8px;background:#229ED9;color:white;"
                                f"border:none;border-radius:6px;cursor:pointer;font-weight:bold;'>"
                                f"✈️ Share GTT on Telegram</button></a>",
                                unsafe_allow_html=True
                            )

                    else:
                        st.warning("⚠️ Could not compute ATR — 52W High/Low columns not found in sheet. Please enter ATR manually above.")

            # ==========================================
            # 📊 WATCHLIST MANAGER TAB (NEW - ws_tabs[11])
            # ==========================================
            with ws_tabs[11]:
                st.markdown(f"### 📊 Watchlist Manager")
                clean_sel_wl = {k: v for k, v in sel_row.items() if not str(k).startswith('_')}
                bf_score_wl, bf_grade_wl, _ = compute_bottom_fishing_score(clean_sel_wl, actual_cols)
                cmp_wl = str(clean_sel_wl.get(cmp_target, "")) if cmp_target else ""

                # ── Add current stock ──────────────────────────────────────
                already_in = sym in st.session_state.watchlist
                st.markdown(f"**Current Stock: {sym}** {'✅ Already in Watchlist' if already_in else ''}")
                wl_note = st.text_input(
                    "📝 Note (optional):",
                    value=st.session_state.watchlist.get(sym, {}).get("note", ""),
                    placeholder="e.g. Near 52W low, watching for breakout",
                    key=f"wl_note_{sym}"
                )
                wl_col1, wl_col2 = st.columns(2)
                with wl_col1:
                    if st.button(
                        f"{'🔄 Update' if already_in else '➕ Add'} {sym} to Watchlist",
                        use_container_width=True, key="wl_add_btn"
                    ):
                        watchlist_add(sym, cmp=cmp_wl, note=wl_note,
                                      bf_score=str(bf_score_wl), bf_grade=bf_grade_wl)
                        saved = save_watchlist_to_sheet()
                        if saved:
                            st.success(f"✅ {sym} saved to Watchlist (Google Sheet updated!)")
                        else:
                            st.info(f"✅ {sym} added to session Watchlist (Sheet write failed — check secrets).")
                        st.rerun()
                with wl_col2:
                    if already_in:
                        if st.button(f"❌ Remove {sym} from Watchlist", use_container_width=True, key="wl_rm_btn"):
                            watchlist_remove(sym)
                            save_watchlist_to_sheet()
                            st.rerun()

                st.markdown("---")

                # ── Full watchlist table ───────────────────────────────────
                st.markdown("#### 🗂️ Your Full Watchlist")
                if st.session_state.watchlist:
                    wl_data = [
                        {
                            "Symbol":   s,
                            "CMP (₹)":  d["cmp"],
                            "BF Score": d.get("bf_score",""),
                            "Grade":    d.get("bf_grade",""),
                            "Note":     d.get("note",""),
                            "Added":    d.get("added",""),
                        }
                        for s, d in st.session_state.watchlist.items()
                    ]
                    wl_df = pd.DataFrame(wl_data)
                    st.dataframe(wl_df, use_container_width=True, hide_index=True)

                    # Download watchlist Excel
                    _wl2_buf = io.BytesIO()
                    with pd.ExcelWriter(_wl2_buf, engine="openpyxl") as _w2:
                        wl_df.to_excel(_w2, index=False, sheet_name="Watchlist")
                    st.download_button(
                        "📥 Download Watchlist as Excel",
                        data=_wl2_buf.getvalue(),
                        file_name=f"Watchlist_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_wl_excel_tab"
                    )

                    # Share watchlist summary via WhatsApp / Telegram
                    _wl_share_lines = "\n".join(
                        [f"• {s} — Score:{d.get('bf_score','')} {d.get('bf_grade','').split()[0] if d.get('bf_grade') else ''} — {d.get('note','')[:30]}"
                         for s, d in list(st.session_state.watchlist.items())[:15]]
                    )
                    _wl_share_text = f"📊 *My NSE Watchlist*\n\n{_wl_share_lines}\n\n🕒 {datetime.now().strftime('%d %b %Y')}"
                    _wl_wa = urllib.parse.quote(_wl_share_text)
                    _wl_tg = urllib.parse.quote(_wl_share_text)

                    st.markdown("")
                    _ws1, _ws2 = st.columns(2)
                    with _ws1:
                        st.markdown(
                            f"<a href='https://wa.me/?text={_wl_wa}' target='_blank'>"
                            f"<button style='width:100%;padding:8px;background:#25D366;color:white;"
                            f"border:none;border-radius:6px;cursor:pointer;font-weight:bold;'>"
                            f"📱 Share Watchlist on WhatsApp</button></a>",
                            unsafe_allow_html=True
                        )
                    with _ws2:
                        st.markdown(
                            f"<a href='https://t.me/share/url?url=Dashboard&text={_wl_tg}' target='_blank'>"
                            f"<button style='width:100%;padding:8px;background:#229ED9;color:white;"
                            f"border:none;border-radius:6px;cursor:pointer;font-weight:bold;'>"
                            f"✈️ Share Watchlist on Telegram</button></a>",
                            unsafe_allow_html=True
                        )
                else:
                    st.info("Your watchlist is empty. Add stocks using the button above!")

    # ==========================================
    # 🌍 NATIONAL ANALYTICS PORTAL WORKSPACE
    # ==========================================
    st.markdown("---")
    st.subheader("📊 National Live Market Analytics Portal Framework")

    st.markdown("""
    <style>
        div[data-baseweb="tab-list"] {
            flex-wrap: wrap !important;
            row-gap: 3px !important;
            column-gap: 8px !important;
        }
        div[data-baseweb="tab-list"] button {
            margin-top: 1px !important;
            margin-bottom: 1px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            height: auto !important;
        }
        div[data-baseweb="tab-highlight"] {
            display: none !important;
        }
        div[data-baseweb="tab"][aria-selected="true"] {
            background-color: rgba(31, 119, 180, 0.1) !important;
            border-radius: 5px !important;
            border-bottom: 2px solid #1f77b4 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    mkt_tabs = st.tabs([
        "🔥 Most Active", "🚀 Volume Gainers", "🏆 Top Gainers/Losers", "⭐ 52W Boundaries", "📦 Stocks Traded", "⚖️ Advances/Declines",
        "🕒 Pre-Open Market", "⚡ Price Band Hitters", "🗺️ Index Ticker Heatmap", "🎫 IPO Tracker", "⚠️ Volume Shockers",
        "📂 Document Reports", "🖋️ TV Script Engine", "🔮 MunafaSutra Tickers", "🎯 Dhan Asset Registry", "💎 Weekly Activity Metrics",
        "🔧 ScanX Core Screener", "🚦 ScanX Live Engine", "🎨 Screener Exploration", "📈 IPO Chittorgarh", "🏷️ IPO Watch Panel", "💓 NSE Pulse",
        "📊 Chartink Screeners", "📋 Chartink Dashboard", "🗾 Chartink Atlas", "📚 Mahesh Kaushik", "💰 EFTI Wealth"
    ])

    # Reusable helper to render a styled "Open in Browser" button above each portal iframe
    def _portal_btn(url, label="Open in Browser"):
        return (
            f"<div style='margin-bottom:8px;'>"
            f"<a href='{url}' target='_blank' style='"
            f"display:inline-block; background:#1976d2; color:#fff; font-size:14px; font-weight:600;"
            f"padding:8px 18px; border-radius:6px; text-decoration:none;'>"
            f"🌐 {label}</a>"
            f"<span style='font-size:12px; color:#888; margin-left:12px;'>📱 Mobile: tap button if frame is blank</span>"
            f"</div>"
        )

    with mkt_tabs[0]:
        _u = "https://www.nseindia.com/market-data/most-active-equities"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[1]:
        _u = "https://www.nseindia.com/market-data/volume-gainers-spurts"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[2]:
        _u = "https://www.nseindia.com/market-data/top-gainers-losers"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[3]:
        _u = "https://www.nseindia.com/market-data/52-week-high-equity-market"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[4]:
        _u = "https://www.nseindia.com/market-data/stocks-traded"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[5]:
        _u = "https://www.nseindia.com/market-data/advance"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[6]:
        _u = "https://www.nseindia.com/market-data/pre-open-market-cm-and-emerge-market"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[7]:
        _u = "https://www.nseindia.com/market-data/upper-band-hitters"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[8]:
        _u = "https://www.nseindia.com/index-tracker/NIFTY%2050"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[9]:
        _u = "https://www.nseindia.com/market-data/all-upcoming-issues-ipo"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[10]:
        _u = "https://www.moneycontrol.com/stocks/market-stats/volume-shockers-nse/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[11]:
        _u = "https://www.nseindia.com/all-reports/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[12]:
        _u = "https://www.tradingview.com/scripts/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none;"></iframe>', height=520)
    with mkt_tabs[13]:
        _u = "https://munafasutra.com/nse/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[14]:
        _u = "https://dhan.co/all-stocks-list/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[15]:
        _u = "https://dhan.co/stocks/market/most-active-stocks-this-week/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[16]:
        _u = "https://scanx.trade/create-custom-screener"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[17]:
        _u = "https://scanx.trade/stock-screener/live-market-screener"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[18]:
        _u = "https://www.screener.in/explore/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[19]:
        _u = "https://www.chittorgarh.com/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[20]:
        _u = "https://ipowatch.in/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[21]:
        _u = "https://nsepulse.streamlit.app/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[22]:
        _u = "https://chartink.com/screeners"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[23]:
        _u = "https://chartink.com/scan_dashboard"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[24]:
        _u = "https://chartink.com/atlas"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[25]:
        _u = "https://www.maheshkaushik.com/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)
    with mkt_tabs[26]:
        _u = "https://eftiwealth.com/"
        st.markdown(_portal_btn(_u), unsafe_allow_html=True)
        components.html(f'<iframe src="{_u}" width="100%" height="500" style="border:none; background-color:white;"></iframe>', height=520)

    # ==========================================
    # 🏆 MULTI-HORIZON PERFORMANCE SUMMARY MATRIX
    # ==========================================
    st.markdown("---")
    st.markdown("### 📈 Multi-Horizon Performance Summary Matrix")

    perf_width_col1, perf_width_col2 = st.columns([4, 1])
    with perf_width_col1:
        perf_sizing_mode = st.radio(
            "📏 Column Width Adjustment:",
            ["Default", "✅ Fit to Row 1", "✅✅ Fit to Row 2"],
            horizontal=True,
            help="Automatically adjust column widths based on text length of the selected row.",
            key="perf_matrix_sizing_mode"
        )

    horizons = [
        "1 Day", "2 Day", "3 Day", "5 Day", "7 Day", "10 Day", "12 Day", "15 Days", "20 Days", "25 Days", "30 Days",
        "2 Months", "3 Months", "4 Months", "5 Months", "6 Months", "7 Months", "8 Months", "9 Months", "10 Months", "11 Months",
        "1 Year", "18 Months", "1.5 Years", "2 Years", "2.5 Years", "3 Years", "Volume"
    ]

    col_tools1, col_tools2, col_tools3 = st.columns([2, 2, 3])
    with col_tools1:
        sort_basis = st.selectbox("🎯 Base Horizon for Performance Ranking:", horizons, index=0)
    with col_tools2:
        sort_direction = st.radio("排序 Sorting Order Type:", ["Best -> Worst", "Worst -> Best"], index=0, horizontal=True)
    with col_tools3:
        summary_search = st.text_input("🔍 Filter stocks inside this matrix...", placeholder="Type symbol name...", key="perf_matrix_search")

    detected_metric_map = {}

    for h in horizons:
        if h == "Volume":
            if vol_target: detected_metric_map[h] = vol_target
            continue
        keywords = [h.lower(), h.lower().replace(" ", ""), h.lower().replace("s", "")]
        if h == "1 Day": keywords.append("price %")
        for c in actual_cols:
            if any(k in c.lower() for k in keywords) and "%" in c.lower():
                detected_metric_map[h] = c
                break

    if detected_metric_map:
        reporting_data = []
        for idx, row in filtered_df.iterrows():
            clean_ticker = str(row.get('_raw_symbol_', '')).strip()
            price_val = row.get(cmp_target, "") if cmp_target else ""

            url = f"https://charting.nseindia.com/?symbol={clean_ticker}-EQ"
            hyperlinked_name = f'<a href="{url}" target="_blank" style="text-decoration:none; color:#000000; font-weight:bold;">{clean_ticker}</a>'

            entry = {
                "STOCK NAME": hyperlinked_name,
                "CURRENT PRICE": price_val
            }

            for h, actual_col in detected_metric_map.items():
                raw_val = str(row.get(actual_col, "0")).replace("%", "").replace(",", "").strip()
                try:
                    entry[h] = float(raw_val) if raw_val not in ["", "nan", "None"] else 0.0
                except ValueError:
                    entry[h] = 0.0

            # ── NEW: Bottom Fishing Score column ──────────────────
            clean_r = {k: v for k, v in row.items() if not str(k).startswith('_')}
            bf_s, bf_g, _ = compute_bottom_fishing_score(clean_r, actual_cols)
            entry["🔬 BF Score"] = bf_s
            entry["📊 BF Grade"] = bf_g

            reporting_data.append(entry)

        perf_df = pd.DataFrame(reporting_data)

        if summary_search:
            perf_df = perf_df[perf_df["STOCK NAME"].str.replace(r'<[^>]*>', '', regex=True).str.contains(summary_search, case=False, na=False)]

        target_sort_col = sort_basis if sort_basis in perf_df.columns else perf_df.columns[2]
        ascending_flag = (sort_direction == "Worst -> Best")
        perf_df = perf_df.sort_values(by=target_sort_col, ascending=ascending_flag).reset_index(drop=True)
        perf_df.insert(0, "RANK", perf_df.index + 1)

        display_perf_df = perf_df.copy()
        for h in detected_metric_map.keys():
            if h in display_perf_df.columns:
                if h == "Volume":
                    display_perf_df[h] = display_perf_df[h].apply(lambda x: f"{int(x):,}" if pd.notnull(x) else "-")
                else:
                    display_perf_df[h] = display_perf_df[h].apply(lambda x: f"+{x:.2f}%" if x > 0 else (f"{x:.2f}%" if x < 0 else "0.00%"))

        perf_gb = GridOptionsBuilder.from_dataframe(display_perf_df)
        perf_gb.configure_column("RANK", width=70, pinned="left")
        perf_gb.configure_column("STOCK NAME", width=140, pinned="left", cellRenderer=html_renderer)

        color_code_js = JsCode("""
        function(params) {
            if (params.value === undefined || params.value === null || params.colDef.field === "Volume") return null;
            let val = parseFloat(String(params.value).replace(/[+%,]/g, ''));
            if (val > 0) return { 'color': '#000000', 'backgroundColor': '#e6f4ea', 'fontWeight': 'bold' };
            if (val < 0) return { 'color': '#000000', 'backgroundColor': '#fce8e6', 'fontWeight': 'bold' };
            return null;
        }
        """)

        bf_score_js = JsCode("""
        function(params) {
            let val = parseFloat(params.value);
            if (val >= 75) return { 'backgroundColor': '#16e37f33', 'color': '#000', 'fontWeight': 'bold' };
            if (val >= 55) return { 'backgroundColor': '#f4b40033', 'color': '#000', 'fontWeight': 'bold' };
            if (val >= 35) return { 'backgroundColor': '#ff990033', 'color': '#000' };
            return { 'backgroundColor': '#ea433533', 'color': '#000' };
        }
        """)

        bf_grade_js = JsCode("""
        function(params) {
            let v = String(params.value);
            if (v.includes('STRONG BUY')) return { 'backgroundColor': '#16e37f44', 'fontWeight': 'bold' };
            if (v.includes('WATCHLIST')) return { 'backgroundColor': '#f4b40044', 'fontWeight': 'bold' };
            if (v.includes('CAUTION')) return { 'backgroundColor': '#ff990044' };
            return { 'backgroundColor': '#ea433544' };
        }
        """)

        for col in display_perf_df.columns:
            if col in ("RANK",):
                continue  # already configured above
            if perf_sizing_mode == "✅ Fit to Row 1" and len(display_perf_df) > 0:
                char_count = get_clean_text_length(display_perf_df.iloc[0][col])
                header_count = len(str(col))
                dyn_width = int(max(char_count, header_count) * 7 + 22)
            elif perf_sizing_mode == "✅✅ Fit to Row 2" and len(display_perf_df) > 1:
                char_count = get_clean_text_length(display_perf_df.iloc[1][col])
                header_count = len(str(col))
                dyn_width = int(max(char_count, header_count) * 7 + 22)
            else:
                # Default fixed widths
                default_widths = {"STOCK NAME": 140, "CURRENT PRICE": 130, "🔬 BF Score": 110, "📊 BF Grade": 160}
                dyn_width = default_widths.get(col, 130)

            if col == "STOCK NAME":
                perf_gb.configure_column(col, width=dyn_width, pinned="left", cellRenderer=html_renderer)
            elif col == "CURRENT PRICE":
                perf_gb.configure_column(col, width=dyn_width)
            elif col == "🔬 BF Score":
                perf_gb.configure_column(col, width=dyn_width, cellStyle=bf_score_js)
            elif col == "📊 BF Grade":
                perf_gb.configure_column(col, width=dyn_width, cellStyle=bf_grade_js)
            elif col in detected_metric_map:
                perf_gb.configure_column(col, width=dyn_width, cellStyle=color_code_js)
            else:
                perf_gb.configure_column(col, width=dyn_width)

        perf_gb.configure_grid_options(domLayout="normal", rowHeight=38, headerHeight=45, enableCellTextSelection=True)
        perf_grid_ops = perf_gb.build()

        AgGrid(display_perf_df, gridOptions=perf_grid_ops, theme="streamlit", allow_unsafe_jscode=True, fit_columns_on_grid_load=False, height=450, width='100%', key="horizon_perf_grid")

    # ==========================================
    # 🔬 STANDALONE BOTTOM FISHING SCANNER
    # ==========================================
    st.markdown("---")
    st.markdown("### 🔬 Bottom Fishing Scanner — Buy from Bottom Candidates")
    st.caption("Stocks that are 8–15% above 52W Low, in uptrend, with high volume + strong fundamentals")

    bf_width_col1, bf_width_col2 = st.columns([4, 1])
    with bf_width_col1:
        bf_sizing_mode = st.radio(
            "📏 Column Width Adjustment:",
            ["Default", "✅ Fit to Row 1", "✅✅ Fit to Row 2"],
            horizontal=True,
            help="Automatically adjust column widths based on text length of the selected row.",
            key="bf_scanner_sizing_mode"
        )

    bf_col1, bf_col2, bf_col3 = st.columns([2, 2, 2])
    with bf_col1:
        min_bf_score = st.slider("Minimum BF Score:", min_value=0, max_value=100, value=55, step=5, key="bf_min_score")
    with bf_col2:
        bf_sort = st.radio("Sort by:", ["Score (High→Low)", "Score (Low→High)"], horizontal=True, key="bf_sort")
    with bf_col3:
        bf_search = st.text_input("Search symbol:", placeholder="e.g. WIPRO", key="bf_search")

    bf_results = []
    for idx, row in filtered_df.iterrows():
        clean_r = {k: v for k, v in row.items() if not str(k).startswith('_')}
        bf_s, bf_g, bf_rsns = compute_bottom_fishing_score(clean_r, actual_cols)
        if bf_s >= min_bf_score:
            ticker = str(row.get('_raw_symbol_', '')).strip()
            cmp_v = clean_r.get(cmp_target, "") if cmp_target else ""
            sector_col = next((c for c in actual_cols if "sector" in c.lower()), None)
            sector_v = clean_r.get(sector_col, "") if sector_col else ""
            bf_results.append({
                "Symbol": ticker,
                "Score": bf_s,
                "Grade": bf_g,
                "CMP": cmp_v,
                "Sector": str(sector_v)[:30],
                "Key Reasons": " | ".join(bf_rsns[:3])
            })

    if bf_search:
        bf_results = [r for r in bf_results if bf_search.upper() in r["Symbol"].upper()]

    bf_results.sort(key=lambda x: x["Score"], reverse=(bf_sort == "Score (High→Low)"))

    if bf_results:
        st.success(f"✅ Found **{len(bf_results)}** stocks matching your bottom-fishing criteria (score ≥ {min_bf_score})")
        bf_scan_df = pd.DataFrame(bf_results)

        bf_gb = GridOptionsBuilder.from_dataframe(bf_scan_df)

        bf_score_style = JsCode("""
        function(params) {
            let val = parseFloat(params.value);
            if (val >= 75) return { 'backgroundColor': '#16e37f33', 'color': '#000', 'fontWeight': 'bold' };
            if (val >= 55) return { 'backgroundColor': '#f4b40033', 'color': '#000', 'fontWeight': 'bold' };
            if (val >= 35) return { 'backgroundColor': '#ff990033', 'color': '#000' };
            return { 'backgroundColor': '#ea433533', 'color': '#000' };
        }
        """)

        bf_default_widths = {"Symbol": 120, "Score": 90, "Grade": 160, "CMP": 100, "Sector": 200, "Key Reasons": 400}
        for col in bf_scan_df.columns:
            if bf_sizing_mode == "✅ Fit to Row 1" and len(bf_scan_df) > 0:
                char_count = get_clean_text_length(bf_scan_df.iloc[0][col])
                header_count = len(str(col))
                dyn_w = int(max(char_count, header_count) * 7 + 22)
            elif bf_sizing_mode == "✅✅ Fit to Row 2" and len(bf_scan_df) > 1:
                char_count = get_clean_text_length(bf_scan_df.iloc[1][col])
                header_count = len(str(col))
                dyn_w = int(max(char_count, header_count) * 7 + 22)
            else:
                dyn_w = bf_default_widths.get(col, 120)

            pinned = "left" if col == "Symbol" else None
            if col == "Score":
                bf_gb.configure_column(col, width=dyn_w, pinned=pinned, cellStyle=bf_score_style)
            else:
                bf_gb.configure_column(col, width=dyn_w, pinned=pinned)

        bf_gb.configure_grid_options(domLayout="normal", rowHeight=40, headerHeight=45)
        bf_grid_ops = bf_gb.build()

        AgGrid(bf_scan_df, gridOptions=bf_grid_ops, theme="streamlit", allow_unsafe_jscode=True, fit_columns_on_grid_load=False, height=400, width='100%', key="bf_scanner_grid")

        # Export BF Scanner results
        bf_buffer = io.BytesIO()
        with pd.ExcelWriter(bf_buffer, engine='openpyxl') as writer:
            bf_scan_df.to_excel(writer, index=False, sheet_name="Bottom Fishing")
        st.download_button("📥 Download BF Scanner Results", data=bf_buffer.getvalue(),
            file_name=f"BottomFishing_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info(f"No stocks found with BF Score ≥ {min_bf_score}. Try lowering the minimum score.")

    # ==========================================
    # 🏆 DAILY DIRECT BADGES LEADERBOARD
    # ==========================================
    if pct_target:
        st.markdown("---")
        st.markdown("### 🏆 Top 10 & Bottom 10 Performers (Daily badges)")
        temp_df = filtered_df.copy()
        temp_df[pct_target] = pd.to_numeric(temp_df[pct_target].astype(str).str.replace(r'[%,]', '', regex=True), errors='coerce')
        temp_df = temp_df.dropna(subset=[pct_target])
        top_10 = temp_df.nlargest(10, pct_target)
        bottom_10 = temp_df.nsmallest(10, pct_target)

        colA, colB = st.columns(2)

        with colA:
            st.markdown("#### ⬆️ Top 10 (Daily)")
            for _, row in top_10.iterrows():
                clean_s = str(row.get('_raw_symbol_', '')).strip()
                v = row[pct_target]
                url = f"https://charting.nseindia.com/?symbol={clean_s}-EQ"
                st.markdown(f"<a href='{url}' target='_blank' style='text-decoration:none;'><div style='background-color:#16e37f; padding:8px; margin:4px; border-radius:5px; color:#000000; font-weight:bold;'>{clean_s}: +{v}%</div></a>", unsafe_allow_html=True)

        with colB:
            st.markdown("#### ⬇️ Bottom 10 (Daily)")
            for _, row in bottom_10.iterrows():
                clean_s = str(row.get('_raw_symbol_', '')).strip()
                v = row[pct_target]
                url = f"https://charting.nseindia.com/?symbol={clean_s}-EQ"
                st.markdown(f"<a href='{url}' target='_blank' style='text-decoration:none;'><div style='background-color:#f39991; padding:8px; margin:4px; border-radius:5px; color:#000000; font-weight:bold;'>{clean_s}: {v}%</div></a>", unsafe_allow_html=True)

else:
    st.warning("No data loaded. Check sheet sharing and secrets.")

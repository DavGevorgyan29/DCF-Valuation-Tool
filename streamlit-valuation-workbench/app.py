import os
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Valuation Workbench", page_icon="📈", layout="wide")


def api_key():
    return st.secrets.get("FMP_API_KEY", os.getenv("FMP_API_KEY", ""))


def workbench_style():
    st.markdown(
        """
        <style>
        .block-container {max-width:1180px; padding-top:1.4rem; padding-bottom:3rem;}
        [data-testid="stSidebar"] {background:#f4f7fb; border-right:1px solid #dce4ef;}
        [data-testid="stSidebar"] [data-testid="stRadio"] label {font-size:1rem; color:#17253c;}
        .workbench-header {background:#10284e; color:#fff; border-radius:12px 12px 0 0; padding:25px 30px; margin-bottom:0;}
        .workbench-header h1 {margin:0; font-size:1.75rem; letter-spacing:-.04em; color:#fff;}
        .workbench-header p {margin:5px 0 0; color:#c6d8f3; font-size:1rem;}
        .workbench-body {background:#f4f7fb; border:1px solid #dce4ef; border-top:0; border-radius:0 0 12px 12px; padding:26px; margin-bottom:18px;}
        .eyebrow {color:#2864ce; font-size:.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; margin-bottom:.25rem;}
        .section-heading {font-size:1.15rem; font-weight:700; color:#17253c; margin:.2rem 0 .2rem;}
        .section-copy {color:#66758c; font-size:.9rem; margin:0 0 .8rem;}
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {background:#fff; border-color:#cad6e4; border-radius:7px; color:#17253c;}
        [data-testid="stButton"] button {background:#2864ce; border-radius:7px; border:0; font-weight:600; padding:.52rem 1rem;}
        [data-testid="stMetric"] {background:#fff; border:1px solid #dce4ef; border-radius:10px; padding:14px 16px;}
        [data-testid="stMetricLabel"] {color:#66758c; font-size:.78rem;}
        [data-testid="stMetricValue"] {color:#17253c; font-size:1.35rem;}
        [data-testid="stDataFrame"] {border:1px solid #dce4ef; border-radius:10px; overflow:hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_company(ticker, key):
    base = "https://financialmodelingprep.com/stable/"
    params = {"symbol": ticker, "period": "annual", "limit": 2, "apikey": key}
    paths = ["profile", "income-statement", "balance-sheet-statement", "cash-flow-statement"]
    result = {}
    for path in paths:
        response = requests.get(base + path, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not payload:
            raise ValueError(f"No {path} data returned for {ticker}.")
        result[path] = payload
    return result


def dcf(revenue, margin, tax_rate, da_rate, capex_rate, nwc_rate, growth, fade, margin_step, wacc, terminal_growth, years):
    rows, present_value = [], 0.0
    for year in range(1, years + 1):
        year_growth = (growth - fade * (year - 1)) / 100
        year_margin = (margin + margin_step * (year - 1)) / 100
        revenue *= 1 + year_growth
        ebitda = revenue * year_margin
        da = revenue * da_rate / 100
        ebit = ebitda - da
        fcf = ebit * (1 - tax_rate / 100) + da - revenue * capex_rate / 100 - revenue * nwc_rate / 100
        pv = fcf / (1 + wacc / 100) ** year
        rows.append({"Year": year, "Revenue": revenue, "EBITDA": ebitda, "EBIT": ebit, "Unlevered FCF": fcf, "PV of FCF": pv})
        present_value += pv
    terminal_value = rows[-1]["Unlevered FCF"] * (1 + terminal_growth / 100) / (wacc / 100 - terminal_growth / 100)
    pv_terminal_value = terminal_value / (1 + wacc / 100) ** years
    return rows, present_value + pv_terminal_value, pv_terminal_value


mode = st.sidebar.radio("Company type", ["Public company", "Private company"], index=0)

if mode == "Public company":
    workbench_style()
    st.markdown(
        """
        <div class="workbench-header">
          <h1>Valuation Workbench</h1>
          <p>DCF valuations for public and private companies.</p>
        </div>
        <div class="workbench-body">
          <div class="eyebrow">Public company model</div>
          <div class="section-heading">Start a public-company valuation</div>
          <p class="section-copy">Enter a ticker to import reported financials. Your API key remains secure on the server.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    key = api_key()
    if not key:
        st.error("The app owner has not configured the market-data key yet. Add FMP_API_KEY to .env locally or Streamlit Secrets when deploying.")
        st.stop()
    with st.container(border=True):
        st.markdown('<div class="section-heading">1. Import company data</div><p class="section-copy">Any ticker covered by your FMP subscription can be loaded.</p>', unsafe_allow_html=True)
        ticker = st.text_input("Ticker", placeholder="e.g., ACMR").strip().upper()
        load_requested = st.button("Load reported financials", type="primary")
    if ticker and load_requested:
        try:
            data = load_company(ticker, key)
            st.session_state["company_data"] = data
            st.session_state["ticker"] = ticker
        except (requests.RequestException, ValueError) as error:
            st.error(f"Could not load {ticker}: {error}")
    data = st.session_state.get("company_data")
    if data:
        income, balance, cashflow = data["income-statement"][0], data["balance-sheet-statement"][0], data["cash-flow-statement"][0]
        prior = data["income-statement"][1] if len(data["income-statement"]) > 1 else income
        revenue = income["revenue"] / 1_000_000
        history_growth = ((income["revenue"] / prior["revenue"]) - 1) * 100 if prior.get("revenue") else 8.0
        company_name = data["profile"][0].get("companyName", st.session_state["ticker"])
        st.markdown(f'<div class="eyebrow">Loaded company</div><div class="section-heading">{company_name}</div><p class="section-copy">Review imported data and editable DCF assumptions.</p>', unsafe_allow_html=True)
        st.markdown('<div class="section-heading">2. Forecast & DCF assumptions</div>', unsafe_allow_html=True)
        a, b, c = st.columns(3)
        years = a.number_input("Forecast years", 2, 15, 5)
        wacc = b.number_input("WACC (%)", value=9.0, step=0.1)
        terminal_growth = c.number_input("Terminal growth (%)", value=2.5, step=0.1)
        a, b, c, d = st.columns(4)
        growth = a.number_input("Year 1 growth (%)", value=round(history_growth, 1), step=0.1)
        margin = b.number_input("EBITDA margin (%)", value=round(income.get("ebitda", 0) / income["revenue"] * 100, 1), step=0.1)
        tax = c.number_input("Tax rate (%)", value=25.0, step=0.1)
        fade = d.number_input("Annual growth fade (pp)", value=1.5, step=0.1)
        rows, enterprise_value, pv_terminal = dcf(revenue, margin, tax, abs(cashflow.get("depreciationAndAmortization", 0)) / income["revenue"] * 100, abs(cashflow.get("capitalExpenditure", 0)) / income["revenue"] * 100, abs(cashflow.get("changeInWorkingCapital", 0)) / income["revenue"] * 100, growth, fade, 0.5, wacc, terminal_growth, years)
        cash = (balance.get("cashAndCashEquivalents", 0) or 0) / 1_000_000
        debt = (balance.get("totalDebt", 0) or 0) / 1_000_000
        equity_value = enterprise_value + cash - debt
        st.markdown('<div class="section-heading" style="margin-top:1.2rem">3. Valuation summary</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise value", f"${enterprise_value:,.0f}m")
        m2.metric("Equity value", f"${equity_value:,.0f}m")
        m3.metric("EV / Year 1 EBITDA", f"{enterprise_value / rows[0]['EBITDA']:.1f}×")
        m4.metric("Terminal value / EV", f"{pv_terminal / enterprise_value:.1%}")
        st.markdown('<div class="section-heading" style="margin-top:1.2rem">Free cash flow forecast</div>', unsafe_allow_html=True)
        st.dataframe(rows, use_container_width=True, hide_index=True, column_config={key: st.column_config.NumberColumn(format="$%.1f") for key in rows[0] if key != "Year"})
else:
    st.title("Private Company DCF")
    st.caption("Enter your diligence inputs directly. This workflow does not use a market-data API.")
    model_html = Path(__file__).with_name("valuation-workbench.html").read_text(encoding="utf-8")
    private_only_html = model_html.replace("<body>", "<body><style>[data-mode=public]{display:none!important}.choices{grid-template-columns:1fr!important}</style>")
    components.html(private_only_html, height=1320, scrolling=True)

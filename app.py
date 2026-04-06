import os
import base64
import streamlit as st
from datetime import datetime, timedelta
from dotenv import load_dotenv

from meta_api import get_campaigns, get_ads_with_insights
from excel_export import generate_excel

load_dotenv()

st.set_page_config(page_title="Grownax — Vinson Meta Ads", page_icon="📊", layout="wide")

# =============================================
#  AUTH — Login screen
# =============================================
VALID_USER = os.environ.get("APP_USER", "vinson")
VALID_PASS = os.environ.get("APP_PASS", "456123Vinson")


def check_auth():
    if st.session_state.get("authenticated"):
        return True
    return False


def show_login():
    # Minimal dark CSS for login page too
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        .stApp { background: #060d1f; font-family: 'Inter', sans-serif; }
        header[data-testid="stHeader"] { background: #060d1f !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        button[data-testid="stSidebarCollapsedControl"] { display: none !important; }
        .login-box {
            max-width: 400px;
            margin: 80px auto;
            padding: 40px;
            background: rgba(10, 18, 40, 0.8);
            border: 1px solid rgba(42, 78, 203, 0.15);
            border-radius: 16px;
            backdrop-filter: blur(10px);
            text-align: center;
        }
        .login-box img {
            height: 80px;
            margin-bottom: 24px;
            filter: brightness(1.15);
        }
        .login-box h2 {
            color: #e0e7f1 !important;
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .login-box p {
            color: #546a8e !important;
            font-size: 0.8rem;
            margin-bottom: 24px;
        }
        .stTextInput input {
            background: rgba(12, 22, 48, 0.8) !important;
            border: 1px solid rgba(42, 78, 203, 0.15) !important;
            color: #e0e7f1 !important;
            border-radius: 8px !important;
        }
        .stTextInput input:focus {
            border-color: rgba(42, 78, 203, 0.5) !important;
            box-shadow: 0 0 12px rgba(42, 78, 203, 0.15) !important;
        }
        .stTextInput label { color: #6b82b0 !important; font-size: 0.8rem !important; }
        div[data-testid="stForm"] button {
            background: linear-gradient(135deg, #1a2b6b 0%, #2a4ecb 100%) !important;
            border: none !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 8px !important;
            box-shadow: 0 2px 12px rgba(42, 78, 203, 0.3) !important;
            width: 100%;
        }
    </style>
    """, unsafe_allow_html=True)

    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    logo_html = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        logo_html = f'<img src="data:image/png;base64,{b64}">'

    st.markdown(f"""
    <div class="login-box">
        {logo_html}
        <h2>Meta Ads Dashboard</h2>
        <p>Ingresá tus credenciales para continuar</p>
    </div>
    """, unsafe_allow_html=True)

    # Center the form
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2:
        with st.form("login_form"):
            user = st.text_input("Usuario")
            passwd = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)

            if submitted:
                if user == VALID_USER and passwd == VALID_PASS:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")


if not check_auth():
    show_login()
    st.stop()


def get_logo_base64():
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def fmt_money(value):
    if value >= 1_000_000:
        formatted = f"{value:,.0f}"
    else:
        formatted = f"{value:,.2f}"
    return "$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(value):
    return f"{value:,}".replace(",", ".")


def fmt_pct(value):
    return f"{value:.2f}%".replace(".", ",")


def fmt_roas(value):
    return f"{value:.2f}x".replace(".", ",")


def fmt_money_table(value):
    if value == 0:
        return "$ 0"
    return fmt_money(value)


# --- State defaults ---
if "period_days" not in st.session_state:
    st.session_state["period_days"] = 7
if "custom_mode" not in st.session_state:
    st.session_state["custom_mode"] = False
if "auto_fetch" not in st.session_state:
    st.session_state["auto_fetch"] = False

active_period = st.session_state.get("period_days", 7)
custom_active = st.session_state.get("custom_mode", False)

LOGO_B64 = get_logo_base64()
# Support both .env and Streamlit secrets
access_token = os.environ.get("META_ACCESS_TOKEN", "")
if not access_token:
    try:
        access_token = st.secrets.get("META_ACCESS_TOKEN", "")
    except Exception:
        pass

# --- CSS with animations ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* === ANIMATIONS === */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 8px rgba(42, 78, 203, 0.15), 0 0 20px rgba(42, 78, 203, 0.05); }
        50% { box-shadow: 0 0 16px rgba(42, 78, 203, 0.3), 0 0 36px rgba(42, 78, 203, 0.1); }
    }
    @keyframes logoFloat {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-8px); }
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes borderGlow {
        0%, 100% { border-color: rgba(42, 78, 203, 0.15); }
        50% { border-color: rgba(42, 78, 203, 0.35); }
    }
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }

    /* === BASE === */
    .stApp {
        background: #060d1f;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    header[data-testid="stHeader"] {
        background: #060d1f !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
        color: #f0f4fa !important;
        font-family: 'Inter', sans-serif !important;
        letter-spacing: -0.02em;
    }
    .stApp p, .stApp span, .stApp label, .stApp div {
        color: #b0bdd4;
        font-family: 'Inter', sans-serif !important;
    }
    hr {
        border-color: rgba(42, 78, 203, 0.1) !important;
        margin: 20px 0 !important;
    }

    /* === HIDE SIDEBAR === */
    section[data-testid="stSidebar"] { display: none !important; }
    button[data-testid="stSidebarCollapsedControl"] { display: none !important; }

    /* === HEADER === */
    .header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 20px 0 28px 0;
        border-bottom: 1px solid rgba(42, 78, 203, 0.08);
        margin-bottom: 28px;
        animation: fadeIn 0.6s ease;
    }
    .header-left {
        display: flex;
        align-items: center;
        gap: 20px;
    }
    .header-logo {
        animation: logoFloat 4s ease-in-out infinite;
    }
    .header-logo img {
        height: 120px;
        width: auto;
        filter: brightness(1.15) drop-shadow(0 4px 20px rgba(42, 78, 203, 0.25));
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .header-logo img:hover {
        filter: brightness(1.35) drop-shadow(0 8px 32px rgba(42, 78, 203, 0.4));
        transform: scale(1.06);
    }
    .header-sep {
        width: 1px;
        height: 64px;
        background: linear-gradient(180deg, transparent, rgba(42, 78, 203, 0.3), transparent);
    }
    .header-text .h-title {
        color: #e0e7f1;
        font-size: 1.05rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        margin: 0;
        line-height: 1.3;
    }
    .header-text .h-sub {
        color: #546a8e;
        font-size: 0.72rem;
        font-weight: 400;
        margin: 0;
        letter-spacing: 0.02em;
    }
    .client-badge {
        background: linear-gradient(135deg, rgba(42, 78, 203, 0.1), rgba(42, 78, 203, 0.05));
        border: 1px solid rgba(42, 78, 203, 0.2);
        color: #7b9ff0 !important;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 5px 14px;
        border-radius: 20px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        transition: all 0.3s ease;
    }
    .client-badge:hover {
        background: linear-gradient(135deg, rgba(42, 78, 203, 0.18), rgba(42, 78, 203, 0.08));
        border-color: rgba(42, 78, 203, 0.4);
        box-shadow: 0 0 12px rgba(42, 78, 203, 0.15);
    }

    /* === PERIOD BUTTONS === */
    .period-buttons button {
        background: rgba(12, 22, 48, 0.8) !important;
        border: 1px solid rgba(42, 78, 203, 0.12) !important;
        color: #6b82b0 !important;
        border-radius: 8px !important;
        padding: 6px 18px !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.4 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .period-buttons button:hover {
        background: rgba(42, 78, 203, 0.12) !important;
        border-color: rgba(42, 78, 203, 0.4) !important;
        color: #a8c0f0 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(42, 78, 203, 0.12) !important;
    }
    .glow-btn button {
        background: rgba(42, 78, 203, 0.08) !important;
        border: 1.5px solid rgba(42, 78, 203, 0.5) !important;
        color: #a8c0f0 !important;
        font-weight: 600 !important;
        animation: pulseGlow 3s ease-in-out infinite !important;
    }

    /* Custom fetch button */
    .fetch-btn button {
        background: linear-gradient(135deg, #1a2b6b 0%, #2a4ecb 100%) !important;
        border: none !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        padding: 6px 20px !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.4 !important;
        box-shadow: 0 2px 12px rgba(42, 78, 203, 0.25) !important;
        transition: all 0.3s ease !important;
    }
    .fetch-btn button:hover {
        background: linear-gradient(135deg, #2a3d8b 0%, #3a5edb 100%) !important;
        box-shadow: 0 4px 20px rgba(42, 78, 203, 0.4) !important;
        transform: translateY(-1px);
    }

    /* === METRIC CARDS === */
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(12, 22, 50, 0.9) 0%, rgba(18, 32, 65, 0.7) 100%);
        border: 1px solid rgba(42, 78, 203, 0.1);
        border-radius: 14px;
        padding: 20px 18px;
        backdrop-filter: blur(10px);
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        animation: fadeInUp 0.5s ease both;
    }
    [data-testid="stMetric"]:hover {
        border-color: rgba(42, 78, 203, 0.3);
        box-shadow: 0 8px 32px rgba(42, 78, 203, 0.12);
        transform: translateY(-3px);
    }
    [data-testid="stMetric"] label {
        color: #546a8e !important;
        font-size: 0.65rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.1em !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #e8edf5 !important;
        font-weight: 700 !important;
        font-size: 1.25rem !important;
        letter-spacing: -0.02em !important;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: unset !important;
    }

    /* Stagger animation for metric columns */
    [data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] { animation-delay: 0.05s; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] { animation-delay: 0.1s; }
    [data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] { animation-delay: 0.15s; }
    [data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] { animation-delay: 0.2s; }
    [data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"] { animation-delay: 0.25s; }
    [data-testid="stHorizontalBlock"] > div:nth-child(6) [data-testid="stMetric"] { animation-delay: 0.3s; }

    /* === EXPANDER / CAMPAIGN CARDS === */
    [data-testid="stExpander"] {
        background: rgba(8, 15, 35, 0.5);
        border: 1px solid rgba(42, 78, 203, 0.08);
        border-radius: 14px;
        margin-bottom: 12px;
        transition: all 0.35s ease;
        animation: fadeInUp 0.5s ease both;
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(42, 78, 203, 0.2);
        box-shadow: 0 4px 24px rgba(42, 78, 203, 0.06);
    }
    /* Hide the default toggle icon completely to avoid overlap */
    [data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] {
        display: none !important;
    }
    [data-testid="stExpander"] details > summary {
        padding: 16px 24px !important;
        color: #e0e7f1 !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        transition: all 0.2s ease;
        cursor: pointer;
        list-style: none !important;
    }
    [data-testid="stExpander"] details > summary::-webkit-details-marker {
        display: none !important;
    }
    [data-testid="stExpander"] details > summary:hover {
        color: #ffffff !important;
    }
    [data-testid="stExpander"] summary p {
        color: #e0e7f1 !important;
        white-space: normal !important;
        word-break: break-word !important;
        line-height: 1.6 !important;
        margin: 0 !important;
    }

    /* === DATAFRAME === */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid rgba(42, 78, 203, 0.06);
        animation: fadeIn 0.4s ease;
    }

    /* === SECTION LABELS === */
    .section-label {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 4px 0 16px 0;
        animation: slideInLeft 0.4s ease;
    }
    .section-label span {
        color: #546a8e !important;
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        white-space: nowrap;
    }
    .section-label .line {
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, rgba(42, 78, 203, 0.2) 0%, transparent 100%);
    }

    .adset-label {
        color: #546a8e !important;
        font-size: 0.6rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin: 16px 0 8px 0;
    }

    /* === DOWNLOAD === */
    [data-testid="stDownloadButton"] button {
        background: linear-gradient(135deg, #155a30 0%, #1e8a48 100%) !important;
        border: none !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 14px !important;
        box-shadow: 0 3px 16px rgba(30, 138, 72, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: linear-gradient(135deg, #1e8a48 0%, #28b05e 100%) !important;
        box-shadow: 0 6px 28px rgba(30, 138, 72, 0.35) !important;
        transform: translateY(-2px);
    }

    /* === EMPTY STATE === */
    .empty-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 80px 0;
        gap: 24px;
        animation: fadeInUp 0.7s ease;
    }
    .empty-hero img {
        width: 240px;
        opacity: 0.1;
        animation: logoFloat 5s ease-in-out infinite;
    }
    .empty-hero p {
        color: #3a4a6a !important;
        font-size: 0.95rem;
        font-weight: 400;
    }

    /* === FUTURISTIC LOADING BAR === */
    @keyframes loadSweep {
        0% { left: -40%; }
        100% { left: 100%; }
    }
    @keyframes loadPulse {
        0%, 100% { opacity: 0.4; }
        50% { opacity: 1; }
    }
    @keyframes loadGlow {
        0%, 100% { box-shadow: 0 0 8px rgba(42, 78, 203, 0.3), 0 0 16px rgba(90, 126, 240, 0.1); }
        50% { box-shadow: 0 0 16px rgba(42, 78, 203, 0.5), 0 0 32px rgba(90, 126, 240, 0.2); }
    }
    .loader-container {
        padding: 40px 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 24px;
        animation: fadeIn 0.5s ease;
    }
    .loader-track {
        width: 100%;
        max-width: 480px;
        height: 4px;
        background: rgba(42, 78, 203, 0.08);
        border-radius: 4px;
        position: relative;
        overflow: hidden;
        animation: loadGlow 2s ease-in-out infinite;
    }
    .loader-track::before {
        content: '';
        position: absolute;
        top: 0;
        left: -40%;
        width: 40%;
        height: 100%;
        background: linear-gradient(90deg, transparent, #2a4ecb, #5a7ef0, #8ab0ff, #5a7ef0, #2a4ecb, transparent);
        border-radius: 4px;
        animation: loadSweep 1.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }
    .loader-track::after {
        content: '';
        position: absolute;
        top: -2px;
        left: -40%;
        width: 40%;
        height: 8px;
        background: linear-gradient(90deg, transparent, rgba(90, 126, 240, 0.4), transparent);
        border-radius: 4px;
        filter: blur(4px);
        animation: loadSweep 1.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }
    .loader-dots {
        display: flex;
        gap: 6px;
    }
    .loader-dots span {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #2a4ecb;
        animation: loadPulse 1.2s ease-in-out infinite;
    }
    .loader-dots span:nth-child(2) { animation-delay: 0.2s; }
    .loader-dots span:nth-child(3) { animation-delay: 0.4s; }
    .loader-msg {
        color: #6b82b0 !important;
        font-size: 0.85rem;
        font-weight: 400;
        text-align: center;
        line-height: 1.6;
        animation: loadPulse 2.5s ease-in-out infinite;
    }
    .loader-msg strong {
        color: #8fa4d0 !important;
        font-weight: 600;
    }

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(8, 15, 35, 0.5);
        border-radius: 10px;
        padding: 4px;
        border: 1px solid rgba(42, 78, 203, 0.08);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        color: #6b82b0 !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        padding: 8px 20px !important;
        border-radius: 8px !important;
        transition: all 0.25s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #a8c0f0 !important;
        background: rgba(42, 78, 203, 0.08) !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(42, 78, 203, 0.12) !important;
        color: #a8c0f0 !important;
        font-weight: 600 !important;
        box-shadow: 0 0 12px rgba(42, 78, 203, 0.15);
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: transparent !important;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Ad link column */
    .ad-link a {
        color: #5a8ef0 !important;
        text-decoration: none;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .ad-link a:hover {
        color: #8ab4ff !important;
        text-decoration: underline;
    }

    /* === SCROLLBAR === */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #060d1f; }
    ::-webkit-scrollbar-thumb { background: rgba(42, 78, 203, 0.2); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(42, 78, 203, 0.35); }

    /* === TOOLTIP-STYLE CAPTIONS === */
    .stCaption {
        transition: all 0.2s ease;
    }
    .stCaption:hover {
        color: #8fa4d0 !important;
    }

    /* === AMBIENT BG === */
    .ambient-glow {
        position: fixed;
        top: -200px;
        left: -200px;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(42, 78, 203, 0.04) 0%, transparent 70%);
        pointer-events: none;
        z-index: -1;
    }
</style>
""", unsafe_allow_html=True)

# Ambient background glow
st.markdown('<div class="ambient-glow"></div>', unsafe_allow_html=True)

# =============================================
#  HEADER — Large logo + branding
# =============================================
if LOGO_B64:
    st.markdown(
        f"""<div class="header-bar">
            <div class="header-left">
                <div class="header-logo">
                    <img src="data:image/png;base64,{LOGO_B64}">
                </div>
                <div class="header-sep"></div>
                <div class="header-text">
                    <p class="h-title">Meta Ads Dashboard</p>
                    <p class="h-sub">Reportes automatizados de campañas</p>
                </div>
                <span class="client-badge">Vinson</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# =============================================
#  PERIOD BAR — auto-fetch on click
# =============================================
today = datetime.now().date()

pcols = st.columns([1, 1, 1, 1, 5])

with pcols[0]:
    cls = "glow-btn" if (active_period == 7 and not custom_active) else "period-buttons"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    btn_7 = st.button("7 días", key="btn7", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with pcols[1]:
    cls = "glow-btn" if (active_period == 14 and not custom_active) else "period-buttons"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    btn_14 = st.button("14 días", key="btn14", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with pcols[2]:
    cls = "glow-btn" if (active_period == 30 and not custom_active) else "period-buttons"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    btn_30 = st.button("30 días", key="btn30", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with pcols[3]:
    cls = "glow-btn" if custom_active else "period-buttons"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    btn_custom = st.button("Personalizar", key="btn_custom", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Handle period clicks — auto-fetch for preset periods
should_fetch = False

if btn_7:
    st.session_state["period_days"] = 7
    st.session_state["custom_mode"] = False
    st.session_state["auto_fetch"] = True
    st.rerun()
elif btn_14:
    st.session_state["period_days"] = 14
    st.session_state["custom_mode"] = False
    st.session_state["auto_fetch"] = True
    st.rerun()
elif btn_30:
    st.session_state["period_days"] = 30
    st.session_state["custom_mode"] = False
    st.session_state["auto_fetch"] = True
    st.rerun()
elif btn_custom:
    st.session_state["custom_mode"] = True
    st.session_state["auto_fetch"] = False
    st.rerun()

# Date range + custom mode UI
if custom_active:
    dc1, dc2, dc_fetch, dc_spacer = st.columns([1, 1, 0.8, 5.2])
    with dc1:
        date_from = st.date_input("Desde", value=today - timedelta(days=7), label_visibility="collapsed")
    with dc2:
        date_to = st.date_input("Hasta", value=today, label_visibility="collapsed")
    with dc_fetch:
        st.markdown('<div class="fetch-btn">', unsafe_allow_html=True)
        fetch_custom = st.button("Traer datos", key="fetch_custom", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    if fetch_custom:
        should_fetch = True
    period_label = f"{date_from.strftime('%d/%m/%Y')} — {date_to.strftime('%d/%m/%Y')}"
else:
    days = st.session_state["period_days"]
    date_from = today - timedelta(days=days)
    date_to = today
    period_label = f"Últimos {days} días  ·  {date_from.strftime('%d/%m/%Y')} — {date_to.strftime('%d/%m/%Y')}"

    # Auto-fetch on preset period click
    if st.session_state.get("auto_fetch"):
        should_fetch = True
        st.session_state["auto_fetch"] = False

st.markdown(
    f'<div class="section-label"><span>{period_label}</span><div class="line"></div></div>',
    unsafe_allow_html=True,
)

# =============================================
#  TOKEN CHECK
# =============================================
if not access_token:
    access_token = st.text_input("Meta Access Token", type="password", placeholder="Pegá tu token acá...")
    if not access_token:
        if LOGO_B64:
            st.markdown(
                f"""<div class="empty-hero">
                    <img src="data:image/png;base64,{LOGO_B64}">
                    <p>Ingresá tu Access Token de Meta para comenzar</p>
                </div>""",
                unsafe_allow_html=True,
            )
        st.stop()

# =============================================
#  FETCH DATA
# =============================================
if should_fetch and access_token:
    since = date_from.strftime("%Y-%m-%d")
    until = date_to.strftime("%Y-%m-%d")

    # Futuristic loading UI
    loader = st.empty()
    loader.markdown("""
        <div class="loader-container">
            <div class="loader-track"></div>
            <div class="loader-dots">
                <span></span><span></span><span></span>
            </div>
            <p class="loader-msg">
                Estamos buscando los datos correspondientes<br>
                Gracias por confiar en <strong>Grownax</strong>
            </p>
        </div>
    """, unsafe_allow_html=True)

    try:
        campaigns = get_campaigns(access_token, since, until)
        ads = get_ads_with_insights(access_token, since, until)
    except Exception as e:
        loader.empty()
        st.error(f"Error al consultar los datos: {e}")
        st.stop()

    loader.empty()

    if not campaigns:
        st.warning("No se encontraron campañas activas en ese período.")
        st.stop()

    st.session_state["campaigns"] = campaigns
    st.session_state["ads"] = ads
    st.session_state["date_from"] = date_from.strftime("%d/%m/%Y")
    st.session_state["date_to"] = date_to.strftime("%d/%m/%Y")
    st.session_state["period_label_saved"] = period_label
    st.rerun()

# =============================================
#  RESULTS
# =============================================
if "campaigns" in st.session_state:
    campaigns = st.session_state["campaigns"]
    ads = st.session_state.get("ads", [])
    date_from_display = st.session_state["date_from"]
    date_to_display = st.session_state["date_to"]

    # --- Summary metrics ---
    total_spend = sum(c["spend"] for c in campaigns)
    total_purchases = sum(c["purchases"] for c in campaigns)
    total_revenue = sum(c["revenue"] for c in campaigns)
    total_impressions = sum(c["impressions"] for c in campaigns)
    total_clicks = sum(c["clicks"] for c in campaigns)
    total_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    total_roas = (total_revenue / total_spend) if total_spend > 0 else 0
    total_cpr = (total_spend / total_purchases) if total_purchases > 0 else 0

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Inversión", fmt_money(total_spend))
    m2.metric("Ingresos", fmt_money(total_revenue))
    m3.metric("ROAS", fmt_roas(total_roas))
    m4.metric("Compras", fmt_int(total_purchases))
    m5.metric("Impresiones", fmt_int(total_impressions))
    m6.metric("CTR", fmt_pct(total_ctr))

    # Extra row: secondary metrics
    st.markdown("")
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("Clicks", fmt_int(total_clicks))
    s2.metric("CPR", fmt_money(total_cpr) if total_cpr > 0 else "—")
    s3.metric("CPC", fmt_money(total_spend / total_clicks) if total_clicks > 0 else "—")
    s4.metric("CPM", fmt_money(total_spend / total_impressions * 1000) if total_impressions > 0 else "—")
    total_adsets = sum(len(c.get("adsets", [])) for c in campaigns)
    s5.metric("Campañas", fmt_int(len(campaigns)))
    s6.metric("Conjuntos", fmt_int(total_adsets))

    st.markdown("")

    # =============================================
    #  TABS: Campañas / Anuncios
    # =============================================
    tab_campaigns, tab_categories, tab_ads = st.tabs(["Campañas", "Categorías", "Anuncios"])

    # --- TAB: CAMPAÑAS ---
    with tab_campaigns:
        st.markdown(
            '<div class="section-label"><span>Campañas activas</span><div class="line"></div></div>',
            unsafe_allow_html=True,
        )

        for c in campaigns:
            roas_display = fmt_roas(c["roas"]) if c["roas"] > 0 else "—"
            camp_short = c["campaign"].replace("grownax_", "").replace("vinson_", "").replace("_", " ").title()
            with st.expander(
                f"**{camp_short}**  ·  {c['objective']}  |  {fmt_money(c['spend'])}  |  ROAS {roas_display}",
                expanded=True,
            ):
                mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
                mc1.metric("Inversión", fmt_money(c["spend"]))
                mc2.metric("Ingresos", fmt_money(c["revenue"]))
                mc3.metric("ROAS", roas_display)
                mc4.metric("Compras", fmt_int(c["purchases"]))
                mc5.metric("Clicks", fmt_int(c["clicks"]))
                mc6.metric("CTR", fmt_pct(c["ctr"]))

                if c.get("creatives"):
                    st.caption(f"Creativos: {c['creatives']}")

                adsets = c.get("adsets", [])
                if adsets:
                    st.markdown('<p class="adset-label">Conjuntos de anuncios</p>', unsafe_allow_html=True)
                    adset_table = []
                    for a in adsets:
                        adset_table.append({
                            "Conjunto": a["adset"],
                            "Audiencia": a["audience"],
                            "Inversión": fmt_money_table(a["spend"]),
                            "Impresiones": fmt_int(a["impressions"]),
                            "Clicks": fmt_int(a["clicks"]),
                            "CTR": fmt_pct(a["ctr"]),
                            "Compras": fmt_int(a["purchases"]),
                            "Ingresos": fmt_money_table(a["revenue"]),
                            "ROAS": fmt_roas(a["roas"]) if a["roas"] > 0 else "—",
                            "CPR": fmt_money_table(a["cpr"]) if a["cpr"] > 0 else "—",
                        })
                    st.dataframe(adset_table, use_container_width=True, hide_index=True)
                else:
                    st.caption("Sin conjuntos activos en este período.")

    # --- TAB: CATEGORÍAS ---
    with tab_categories:
        st.markdown(
            '<div class="section-label"><span>Rendimiento por categoría de producto</span><div class="line"></div></div>',
            unsafe_allow_html=True,
        )

        # Collect all adsets from all campaigns and group by category
        from collections import defaultdict
        cat_data = defaultdict(lambda: {"spend": 0, "impressions": 0, "clicks": 0, "purchases": 0, "revenue": 0, "adsets": []})

        for c in campaigns:
            for a in c.get("adsets", []):
                cat = a.get("category", "Otros")
                cat_data[cat]["spend"] += a["spend"]
                cat_data[cat]["impressions"] += a["impressions"]
                cat_data[cat]["clicks"] += a["clicks"]
                cat_data[cat]["purchases"] += a["purchases"]
                cat_data[cat]["revenue"] += a["revenue"]
                cat_data[cat]["adsets"].append(a["adset"])

        # Sort categories by spend descending
        sorted_cats = sorted(cat_data.items(), key=lambda x: x[1]["spend"], reverse=True)

        # Summary table of all categories
        cat_table = []
        for cat_name, d in sorted_cats:
            ctr = (d["clicks"] / d["impressions"] * 100) if d["impressions"] > 0 else 0
            roas = (d["revenue"] / d["spend"]) if d["spend"] > 0 else 0
            cpr = (d["spend"] / d["purchases"]) if d["purchases"] > 0 else 0
            cat_table.append({
                "Categoría": cat_name,
                "Conjuntos": len(d["adsets"]),
                "Inversión": fmt_money_table(d["spend"]),
                "Impresiones": fmt_int(d["impressions"]),
                "Clicks": fmt_int(d["clicks"]),
                "CTR": fmt_pct(ctr),
                "Compras": fmt_int(d["purchases"]),
                "Ingresos": fmt_money_table(d["revenue"]),
                "ROAS": fmt_roas(roas) if roas > 0 else "—",
                "CPR": fmt_money_table(cpr) if cpr > 0 else "—",
            })

        st.dataframe(cat_table, use_container_width=True, hide_index=True)

        st.markdown("")

        # Expandable detail per category
        for cat_name, d in sorted_cats:
            cat_spend = d["spend"]
            cat_purchases = d["purchases"]
            cat_revenue = d["revenue"]
            cat_roas = (cat_revenue / cat_spend) if cat_spend > 0 else 0

            with st.expander(
                f"**{cat_name}**  ·  {len(d['adsets'])} conjuntos  |  {fmt_money(cat_spend)}  |  ROAS {fmt_roas(cat_roas) if cat_roas > 0 else '—'}",
                expanded=False,
            ):
                mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
                mc1.metric("Inversión", fmt_money(cat_spend))
                mc2.metric("Ingresos", fmt_money(cat_revenue))
                mc3.metric("ROAS", fmt_roas(cat_roas) if cat_roas > 0 else "—")
                mc4.metric("Compras", fmt_int(cat_purchases))
                mc5.metric("Clicks", fmt_int(d["clicks"]))
                cat_ctr = (d["clicks"] / d["impressions"] * 100) if d["impressions"] > 0 else 0
                mc6.metric("CTR", fmt_pct(cat_ctr))

                # Show adsets in this category
                st.markdown('<p class="adset-label">Conjuntos incluidos</p>', unsafe_allow_html=True)

                adset_rows = []
                for c in campaigns:
                    for a in c.get("adsets", []):
                        if a.get("category") == cat_name:
                            adset_rows.append({
                                "Conjunto": a["adset"],
                                "Audiencia": a["audience"],
                                "Inversión": fmt_money_table(a["spend"]),
                                "Impresiones": fmt_int(a["impressions"]),
                                "Clicks": fmt_int(a["clicks"]),
                                "CTR": fmt_pct(a["ctr"]),
                                "Compras": fmt_int(a["purchases"]),
                                "Ingresos": fmt_money_table(a["revenue"]),
                                "ROAS": fmt_roas(a["roas"]) if a["roas"] > 0 else "—",
                                "CPR": fmt_money_table(a["cpr"]) if a["cpr"] > 0 else "—",
                            })

                if adset_rows:
                    st.dataframe(adset_rows, use_container_width=True, hide_index=True)

    # --- TAB: ANUNCIOS ---
    with tab_ads:
        st.markdown(
            '<div class="section-label"><span>Anuncios activos</span><div class="line"></div></div>',
            unsafe_allow_html=True,
        )

        if ads:
            from collections import defaultdict
            ads_by_campaign = defaultdict(list)
            for ad in ads:
                camp_short = ad["campaign"].replace("grownax_", "").replace("vinson_", "").replace("_", " ").title()
                ads_by_campaign[camp_short].append(ad)

            for camp_name, camp_ads in ads_by_campaign.items():
                camp_spend = sum(a["spend"] for a in camp_ads)
                with st.expander(f"**{camp_name}**  ·  {len(camp_ads)} anuncios  |  {fmt_money(camp_spend)}", expanded=True):
                    ads_table = []
                    for ad in camp_ads:
                        row = {
                            "Anuncio": ad["ad_name"],
                            "Conjunto": ad["adset"],
                            "Inversión": fmt_money_table(ad["spend"]),
                            "Impresiones": fmt_int(ad["impressions"]),
                            "Clicks": fmt_int(ad["clicks"]),
                            "CTR": fmt_pct(ad["ctr"]),
                            "Compras": fmt_int(ad["purchases"]),
                            "Ingresos": fmt_money_table(ad["revenue"]),
                            "ROAS": fmt_roas(ad["roas"]) if ad["roas"] > 0 else "—",
                            "CPR": fmt_money_table(ad["cpr"]) if ad["cpr"] > 0 else "—",
                            "Link": ad.get("preview_link", ""),
                        }
                        ads_table.append(row)

                    st.dataframe(
                        ads_table,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Link": st.column_config.LinkColumn(
                                "Ver anuncio",
                                display_text="Abrir ↗",
                            ),
                        },
                    )
        else:
            st.caption("No hay datos de anuncios. Seleccioná un período y traé los datos.")

    # --- Export ---
    st.markdown("")
    st.markdown(
        '<div class="section-label"><span>Exportar</span><div class="line"></div></div>',
        unsafe_allow_html=True,
    )

    excel_buf = generate_excel(campaigns, date_from_display, date_to_display)
    filename = f"Vinson_MetaAds_{date_from_display.replace('/', '-')}_{date_to_display.replace('/', '-')}.xlsx"

    dl1, dl2, dl3 = st.columns([2, 1, 1])
    with dl1:
        st.download_button(
            label="Descargar reporte Excel",
            data=excel_buf,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )

elif access_token:
    if LOGO_B64:
        st.markdown(
            f"""<div class="empty-hero">
                <img src="data:image/png;base64,{LOGO_B64}">
                <p>Seleccioná un período para cargar los datos automáticamente</p>
            </div>""",
            unsafe_allow_html=True,
        )

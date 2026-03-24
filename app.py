"""
app.py
Calculadora de Retiro LSS-1997 — Interfaz Streamlit

Correr con:
    streamlit run app.py

Requiere:
    pip install -r requirements.txt
"""
import logging
import os
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Silenciar logs de fetchers en la UI
logging.basicConfig(level=logging.WARNING)
logging.getLogger("data_fetchers").setLevel(logging.ERROR)

#  Imports del proyecto 
from config import AFORES, BANXICO_TOKEN, SUPUESTOS_DEFAULT
from models.trabajador import Trabajador
from data_fetchers.uma             import fetch_uma, get_uma_mensual, cache_esta_vigente
from data_fetchers.udi              import fetch_udi
from data_fetchers.afore_comisiones import get_comision_afore, fetch_comisiones
from data_fetchers.afore_rendimientos import get_rendimiento_afore, fetch_rendimientos
from calculators.aportaciones      import calcular_aportaciones
from calculators.saldo_afore       import (
    proyectar_saldo_desde_trabajador,
    proyectar_escenarios,
)
from calculators.pension           import calcular_pension_desde_trabajador
from calculators.pension_excel     import (
    calcular_pension_metodo_excel,
    ultimo_salario_real,
    calcular_aportacion_extra_para_tasa,
)
import project_time

# Seed del cache al arrancar (no-op si ya existe)
from data_fetchers.uma              import seed_cache_desde_fallback as seed_uma
from data_fetchers.udi              import seed_cache_desde_fallback as seed_udi
from data_fetchers.afore_comisiones  import seed_cache_desde_fallback as seed_com
from data_fetchers.afore_rendimientos import seed_cache_desde_fallback as seed_rend
from data_fetchers.tablas_vida       import seed_cache_desde_fallback as seed_tv

#  Constantes UI 
COLOR_PRIMARIO  = "#1B4F72"
COLOR_ACENTO    = "#2ECC71"
COLOR_ALERTA    = "#E74C3C"
COLOR_NEUTRO    = "#95A5A6"
COLOR_PESIMISTA = "#E74C3C"
COLOR_BASE      = "#3498DB"
COLOR_OPTIMISTA = "#2ECC71"
FONDO_BASE      = "#FAFAFA"
FONDO_SUAVE     = "#DFE8E9"
FONDO_TARJETA   = "#EAEBE6"
FONDO_CALIDO    = "#E3CCA9"
BORDE_SUAVE     = "rgba(27, 79, 114, 0.14)"
TEXTO_BASE      = "#24343A"
TEXTO_MUTED     = "#66767A"
ANIO_HOY = project_time.current_year()


# 
# CONFIGURACIÓN STREAMLIT
# 

st.set_page_config(
    page_title="Calculadora de Retiro LSS-1997",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado
st.markdown("""
<style>
    :root {
        --bg: #f0f2f6;
        --bg-soft: #fcfcfd;
        --bg-panel: #fcfcfd;
        --bg-warm: #fcfcfd;
        --bg-cool: #bec9d8;
        --surface: rgba(252, 252, 253, 0.98);
        --surface-strong: rgba(252, 252, 253, 1);
        --text: #24343A;
        --text-muted: #66767A;
        --line: #bec9d8;
        --primary: #1B4F72;
        --primary-soft: rgba(27, 79, 114, 0.10);
        --accent: #2ECC71;
        --accent-soft: rgba(46, 204, 113, 0.12);
        --danger: #E74C3C;
        --danger-soft: rgba(231, 76, 60, 0.12);
        --secondary: #3498DB;
        --shadow: 0 14px 28px rgba(27, 79, 114, 0.06);
        --shadow-soft: 0 6px 18px rgba(27, 79, 114, 0.05);
        --radius-lg: 24px;
        --radius-md: 18px;
        --radius-sm: 12px;
    }

    html, body, [class*="css"]  {
        font-family: "Source Sans Pro", sans-serif;
        color: var(--text) !important;
    }

    .stApp {
        background: var(--bg);
    }

    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 3rem;
        max-width: 1280px;
    }

    h1, h2, h3 {
        font-family: "Source Sans Pro", sans-serif;
        letter-spacing: -0.02em !important;
        color: var(--text) !important;
    }

    h1 {
        font-size: clamp(2.1rem, 3.4vw, 3.3rem);
        line-height: 1.06;
    }

    h3 {
        font-size: 1.35rem;
    }

    p, label, .stCaption, .stMarkdown, .stTextInput, .stSelectbox, .stNumberInput {
        color: var(--text) !important;
    }

    header[data-testid="stHeader"],
    [data-testid="stToolbar"] {
        display: none !important;
    }

    section[data-testid="stSidebar"],
    div[data-testid="stSidebar"],
    div[data-testid="stSidebarContent"] {
        background: #dfe5ec !important;
    }

    div[data-testid="stSidebar"] {
        border-right: 1px solid var(--line);
    }

    div[data-testid="stSidebarContent"] {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
        color: var(--text);
    }

    div[data-testid="stSidebarContent"] h1,
    div[data-testid="stSidebarContent"] h2,
    div[data-testid="stSidebarContent"] h3,
    div[data-testid="stSidebarContent"] p,
    div[data-testid="stSidebarContent"] label,
    div[data-testid="stSidebarContent"] div {
        color: var(--text) !important;
    }

    div[data-testid="stSidebarContent"] [data-baseweb="input"],
    div[data-testid="stSidebarContent"] [data-baseweb="select"] > div,
    div[data-testid="stSidebarContent"] [data-baseweb="popover"] {
        background: #fcfcfd !important;
        border: 1px solid var(--line) !important;
        border-radius: 12px !important;
        color: var(--text) !important;
    }

    [data-baseweb="input"] input,
    [data-baseweb="select"] input {
        color: var(--text) !important;
    }

    [data-baseweb="input"],
    [data-baseweb="select"] > div,
    textarea {
        background: #fcfcfd !important;
        border-color: var(--line) !important;
    }

    .stButton > button {
        border-radius: 999px;
        border: 1px solid rgba(27, 79, 114, 0.10);
        background: var(--primary);
        color: white;
        font-weight: 700;
        letter-spacing: 0.01em;
        min-height: 2.8rem;
        box-shadow: var(--shadow-soft);
    }

    .stButton > button:hover {
        border-color: rgba(27, 79, 114, 0.16);
        background: #173F5A;
        color: white;
    }

    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.86);
        color: var(--primary);
        border: 1px solid rgba(27,79,114,0.14);
        box-shadow: none;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(223, 232, 233, 0.72);
        padding: 0.4rem;
        border-radius: 16px;
        border: 1px solid var(--line);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.55);
        margin-bottom: 1.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        height: 2.8rem;
        padding: 0.55rem 1rem;
        border-radius: 12px;
        color: var(--text-muted);
        font-weight: 600;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(27, 79, 114, 0.10) !important;
        color: var(--primary) !important;
        box-shadow: inset 0 0 0 1px rgba(27, 79, 114, 0.10);
    }

    div[data-testid="stMetric"] {
        background: var(--surface-strong);
        border: 1px solid var(--line);
        border-radius: var(--radius-md);
        padding: 1rem 1rem 0.85rem 1rem;
        box-shadow: var(--shadow-soft);
        min-height: 154px;
    }

    div[data-testid="stMetric"] label {
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
        font-weight: 700;
    }

    div[data-testid="stMetricValue"] {
        font-family: "Source Sans Pro", sans-serif;
        color: var(--text);
    }

    div[data-testid="stMetricDelta"] {
        color: var(--primary) !important;
        font-weight: 600;
    }

    div[data-testid="stAlert"] {
        border-radius: var(--radius-md);
        border: 1px solid var(--line);
        box-shadow: var(--shadow-soft);
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: var(--radius-md);
        overflow: hidden;
        box-shadow: var(--shadow-soft);
    }

    div[data-testid="stExpander"] {
        border: 1px solid var(--line);
        border-radius: var(--radius-md);
        background: rgba(255,255,255,0.75);
        box-shadow: var(--shadow-soft);
    }

    .stPlotlyChart,
    [data-testid="stPlotlyChart"] {
        background: #fcfcfd;
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 0.35rem 0.45rem;
        box-shadow: var(--shadow-soft);
        transform: none !important;
        animation: none !important;
        transition: none !important;
        will-change: auto !important;
        contain: layout paint;
    }

    .stPlotlyChart:hover,
    [data-testid="stPlotlyChart"]:hover {
        transform: none !important;
        animation: none !important;
        transition: none !important;
        box-shadow: var(--shadow-soft) !important;
        border-color: var(--line) !important;
    }

    .hero-shell {
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1.2rem 1.25rem;
        background: #fcfcfd;
        box-shadow: var(--shadow);
        margin-bottom: 1.4rem;
    }

    .hero-eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.38rem 0.7rem;
        border-radius: 999px;
        background: var(--primary-soft);
        color: var(--primary);
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.9rem;
    }

    .hero-title {
        color: var(--text);
        font-size: clamp(1.9rem, 3vw, 2.7rem);
        line-height: 1.08;
        margin: 0;
        max-width: 18ch;
    }

    .hero-copy {
        color: var(--text-muted);
        font-size: 0.98rem;
        line-height: 1.65;
        max-width: 64ch;
        margin-top: 0.75rem;
    }

    .hero-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-top: 0.95rem;
    }

    .hero-pill {
        padding: 0.48rem 0.8rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.74);
        border: 1px solid var(--line);
        color: var(--text);
        font-size: 0.85rem;
        font-weight: 600;
    }

    .summary-banner {
        display: grid;
        grid-template-columns: 1.6fr 0.95fr;
        gap: 1rem;
        align-items: stretch;
        margin-bottom: 1.2rem;
    }

    .summary-card, .summary-side {
        border-radius: 22px;
        border: 1px solid var(--line);
        box-shadow: var(--shadow-soft);
    }

    .summary-card {
        background: #fcfcfd;
        color: var(--text);
        padding: 1.3rem 1.35rem;
    }

    .summary-kicker {
        color: var(--primary);
        text-transform: uppercase;
        letter-spacing: 0.10em;
        font-size: 0.74rem;
        font-weight: 700;
    }

    .summary-main {
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1.06;
        margin: 0.5rem 0 0.45rem 0;
    }

    .summary-note {
        color: var(--text-muted);
        font-size: 0.97rem;
        line-height: 1.62;
        max-width: 58ch;
    }

    .summary-side {
        background: #fcfcfd;
        padding: 1.15rem 1.2rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .summary-side .label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.10em;
        color: var(--text-muted);
        font-weight: 700;
    }

    .summary-side .value {
        font-size: 2rem;
        color: var(--primary);
        margin: 0.3rem 0;
    }

    .summary-side .caption {
        color: var(--text-muted);
        font-size: 0.88rem;
        line-height: 1.5;
    }

    .status-banner {
        border-radius: 18px;
        border: 1px solid var(--line);
        padding: 1rem 1.1rem;
        margin: 0 0 1rem 0;
        box-shadow: var(--shadow-soft);
    }

    .status-banner.ok {
        background: rgba(46, 204, 113, 0.08);
    }

    .status-banner.warn {
        background: rgba(231, 76, 60, 0.08);
    }

    .status-banner.info {
        background: rgba(27, 79, 114, 0.08);
    }

    .status-title {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.10em;
        font-weight: 700;
        margin-bottom: 0.35rem;
        color: var(--text-muted);
    }

    .status-copy {
        color: var(--text);
        line-height: 1.65;
        font-size: 0.97rem;
    }

    .section-intro {
        color: var(--text-muted);
        margin-top: -0.25rem;
        margin-bottom: 0.9rem;
    }

    .scenario-card {
        border-radius: var(--radius-md);
        border: 1px solid var(--line);
        padding: 1rem;
        background: #fcfcfd;
        box-shadow: var(--shadow-soft);
    }

    .intro-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.85fr);
        gap: 1rem;
        align-items: stretch;
    }

    .intro-panel,
    .intro-side,
    .info-tile,
    .report-shell,
    .sidebar-panel {
        border: 1px solid var(--line);
        border-radius: 22px;
        box-shadow: var(--shadow-soft);
    }

    .intro-panel {
        background: #fcfcfd;
        padding: 1.45rem;
    }

    .intro-side {
        background: #fcfcfd;
        padding: 1.3rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .intro-value {
        font-size: 2.15rem;
        line-height: 1.05;
        color: var(--primary);
        margin: 0.35rem 0;
        font-weight: 700;
    }

    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.9rem;
        margin-top: 1rem;
    }

    .info-tile {
        background: #fcfcfd;
        padding: 1rem 1.05rem;
    }

    .info-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        font-weight: 700;
        margin-bottom: 0.45rem;
    }

    .app-toolbar {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: flex-start;
        gap: 1rem;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: #fcfcfd;
        padding: 1rem 1.05rem;
        margin: 1rem 0 1.25rem 0;
        box-shadow: var(--shadow-soft);
    }

    .app-toolbar-title {
        font-size: 0.95rem;
        color: var(--text);
        line-height: 1.6;
    }

    .app-toolbar-subtle {
        color: var(--text-muted);
        font-size: 0.92rem;
        line-height: 1.65;
    }

    .action-panel-label {
        font-size: 0.78rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
        margin-bottom: 0.55rem;
    }

    .hero-shell,
    .summary-card,
    .summary-side,
    .scenario-card,
    .report-shell,
    .app-toolbar,
    div[data-testid="stMetric"],
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"],
    div[data-testid="stExpander"] {
        animation: uiFadeUp 0.36s ease both;
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background-color 0.18s ease;
    }

    .hero-shell:hover,
    .summary-card:hover,
    .summary-side:hover,
    .scenario-card:hover,
    .report-shell:hover,
    div[data-testid="stMetric"]:hover,
    div[data-testid="stExpander"]:hover {
        transform: translateY(-2px) scale(1.04);
        box-shadow: 0 14px 30px rgba(27, 79, 114, 0.20);
        border-color: rgba(27, 79, 114, 0.22);
    }

    .stButton > button,
    [data-baseweb="input"],
    [data-baseweb="select"] > div,
    textarea,
    .stTabs [data-baseweb="tab"] {
        transition: all 0.18s ease;
    }

    .stButton > button:focus-visible,
    [data-baseweb="input"]:focus-within,
    [data-baseweb="select"] > div:focus-within,
    textarea:focus {
        outline: none;
        box-shadow: 0 0 0 3px rgba(27, 79, 114, 0.10);
        border-color: rgba(27, 79, 114, 0.28) !important;
    }

    div[data-testid="stSidebarContent"] .stTextInput,
    div[data-testid="stSidebarContent"] .stNumberInput,
    div[data-testid="stSidebarContent"] .stDateInput,
    div[data-testid="stSidebarContent"] .stSelectbox,
    div[data-testid="stSidebarContent"] .stCheckbox,
    div[data-testid="stSidebarContent"] div[data-testid="stExpander"] {
        background: #fcfcfd;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 0.55rem 0.65rem;
        box-shadow: var(--shadow-soft);
        margin-bottom: 0.55rem;
    }

    div[data-testid="stSidebarContent"] .stDivider {
        margin: 1rem 0 0.9rem 0;
    }

    @keyframes uiFadeUp {
        from {
            opacity: 0;
            transform: translateY(8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .sidebar-panel {
        background: #fcfcfd;
        padding: 0.95rem 0.95rem 0.4rem 0.95rem;
        margin-top: 0.85rem;
    }

    .slider-inline-label {
        font-size: 0.82rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        font-weight: 700;
        color: var(--text-muted);
        margin: 0.3rem 0 0.35rem 0;
    }

    .print-report {
        margin-top: 1.25rem;
    }

    .report-shell {
        background: #fcfcfd;
        padding: 1.15rem 1.2rem;
        margin-bottom: 1rem;
    }

    .report-title {
        color: var(--primary);
        font-size: 1.35rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .report-note {
        color: var(--text-muted);
        line-height: 1.55;
        margin-bottom: 0.85rem;
    }

    @media print {
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stSidebar"],
        .stTabs,
        .stButton,
        .stDownloadButton,
        .stTextInput,
        .stNumberInput,
        .stSelectbox,
        .stCheckbox,
        .stDateInput,
        .stExpander {
            display: none !important;
        }

        .block-container {
            padding: 0.4in 0.35in 0.6in 0.35in;
            max-width: none !important;
        }

        .stApp {
            background: white !important;
        }

        .hero-shell,
        .summary-card,
        .summary-side,
        .report-shell,
        div[data-testid="stMetric"],
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            box-shadow: none !important;
            background: white !important;
            border-color: rgba(27, 79, 114, 0.18) !important;
            break-inside: avoid;
        }

        .print-report {
            display: block !important;
        }
    }

    @media (max-width: 980px) {
        .intro-grid,
        .summary-banner {
            grid-template-columns: 1fr;
        }

        .hero-shell {
            padding: 1.15rem 1.1rem;
        }
    }
</style>
""", unsafe_allow_html=True)


# 
# INICIALIZACIÓN
# 

@st.cache_resource(show_spinner="Inicializando datos...")
def inicializar():
    seed_uma(); seed_udi(); seed_com(); seed_rend(); seed_tv()
    return True

inicializar()

if "mostrar_fuentes_externas" not in st.session_state:
    st.session_state.mostrar_fuentes_externas = False
if "mostrar_reporte_impresion" not in st.session_state:
    st.session_state.mostrar_reporte_impresion = False
if "banxico_token" not in st.session_state:
    st.session_state["banxico_token"] = ""
if "sidebar_visible" not in st.session_state:
    st.session_state.sidebar_visible = True

if st.session_state.get("app_iniciada", False) and not st.session_state.sidebar_visible:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        div[data-testid="stSidebar"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def aplicar_tema_grafica(fig, height=360):
    fig.update_layout(
        paper_bgcolor="rgba(250,250,250,0)",
        plot_bgcolor="rgba(255,255,255,0.75)",
        font=dict(family="Source Sans Pro, sans-serif", size=14),
        title_font=dict(family="Source Sans Pro, sans-serif", size=22, color=COLOR_PRIMARIO),
        font_color=TEXTO_BASE,
        margin=dict(t=56, b=36, l=20, r=20),
        height=height,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(250,250,250,0.88)",
            bordercolor="rgba(27,79,114,0.12)",
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor="rgba(255,255,255,0.96)",
            bordercolor="rgba(27,79,114,0.16)",
            font=dict(color=TEXTO_BASE),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="rgba(27,79,114,0.18)",
        tickfont=dict(color=TEXTO_MUTED),
        title_font=dict(color=COLOR_PRIMARIO),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(27,79,114,0.10)",
        zeroline=False,
        linecolor="rgba(27,79,114,0.18)",
        tickfont=dict(color=TEXTO_MUTED),
        title_font=dict(color=COLOR_PRIMARIO),
    )
    return fig


def banner_estado(clase: str, titulo: str, mensaje: str) -> None:
    st.markdown(
        f"""
        <div class="status-banner {clase}">
          <div class="status-title">{titulo}</div>
          <div class="status-copy">{mensaje}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_plotly(fig, key: str) -> None:
    st.plotly_chart(
    fig,
    use_container_width=True,
    key=key,
    config={
        "displaylogo": False,
        "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    },
)

def disparar_dialogo_impresion() -> None:
    components.html(
        """
        <script>
        const roots = [window, window.parent, window.top];
        for (const root of roots) {
          try {
            root.focus();
            root.print();
            break;
          } catch (error) {}
        }
        </script>
        """,
        height=0,
    )


# ═══════════════════════════════════════════════════════════════════════════
# PORTADA
# ═══════════════════════════════════════════════════════════════════════════
def slider_con_input(
    label: str,
    *,
    min_value,
    max_value,
    value,
    step,
    key: str,
    slider_format: str | None = None,
    number_format: str | None = None,
    help: str | None = None,
):
    number_key = f"{key}__number"

    if key not in st.session_state:
        st.session_state[key] = value
    if number_key not in st.session_state:
        st.session_state[number_key] = st.session_state[key]

    def _clamp(valor):
        return max(min_value, min(max_value, valor))

    def _sync_from_number():
        valor = _clamp(st.session_state[number_key])
        st.session_state[key] = valor
        st.session_state[number_key] = valor

    st.markdown(f"<div class='slider-inline-label'>{label}</div>", unsafe_allow_html=True)
    number_kwargs = {}
    if number_format is not None:
        number_kwargs["format"] = number_format
    st.number_input(
        f"{label} valor",
        min_value=min_value,
        max_value=max_value,
        value=st.session_state[key],
        step=step,
        key=number_key,
        label_visibility="collapsed",
        on_change=_sync_from_number,
        help=help,
        **number_kwargs,
    )
    return st.session_state[key]


def actualizar_fuentes_externas(token_banxico: str) -> tuple[list[str], list[str]]:
    if token_banxico.strip():
        os.environ["BANXICO_TOKEN"] = token_banxico.strip()

    exitos: list[str] = []
    advertencias: list[str] = []

    fuentes = [
        ("UMA (INEGI)", fetch_uma),
        ("Comisiones AFORE (CONSAR)", fetch_comisiones),
        ("Rendimientos AFORE (CONSAR)", fetch_rendimientos),
    ]

    for etiqueta, funcion in fuentes:
        try:
            funcion(forzar_actualizacion=True)
            exitos.append(etiqueta)
        except Exception as exc:
            advertencias.append(f"{etiqueta}: {exc}")

    token_disponible = bool(
        token_banxico.strip()
        or os.environ.get("BANXICO_TOKEN", "").strip()
        or BANXICO_TOKEN.strip()
    )
    try:
        fetch_udi(forzar_actualizacion=True)
        if token_disponible:
            exitos.append("UDI (Banxico)")
        else:
            advertencias.append(
                "UDI (Banxico): no se proporciono token; se conservo el cache local o el fallback."
            )
    except Exception as exc:
        advertencias.append(f"UDI (Banxico): {exc}")

    return exitos, advertencias


if "app_iniciada" not in st.session_state:
    st.session_state.app_iniciada = False

if not st.session_state.app_iniciada:

    # Ocultar sidebar en portada via CSS global
    st.markdown("""
    <style>
    [data-testid="stSidebar"]{display:none!important}
    [data-testid="stToolbar"]{display:none!important}

    .stButton > button[kind="primary"],
    .stButton > button[kind="primary"]:hover,
    .stButton > button[kind="primary"]:focus,
    .stButton > button[kind="primary"]:active {
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        """
        <section class="hero-shell" style="max-width:1120px;margin:3rem auto 0 auto;">
          <div class="hero-eyebrow">Calculadora actuarial LSS 1997</div>
          <div class="intro-grid">
            <div class="intro-panel">
              <h1 class="hero-title">Proyecciones de retiro.</h1>
              <p class="hero-copy">
                Reúne saldo AFORE, pensión, escenarios y metas de reemplazo en una vista clara,
                con datos de INEGI, Banxico y CONSAR.
              </p>
              <div class="hero-pills">
                <span class="hero-pill">Método CUS en UDIs</span>
                <span class="hero-pill">RCV vs PMG</span>
                <span class="hero-pill">Escenarios y metas</span>
                <span class="hero-pill">Datos vigentes y caché local</span>
              </div>
            </div>
            <div class="intro-side">
              <div>
                <div class="info-label">Qué puedes revisar</div>
                <div class="intro-value">Vistas clave</div>
                <div class="hero-copy" style="margin-top:0;">
                  Resumen, aportaciones, saldo proyectado, pensión y escenarios en un solo lugar.
                </div>
              </div>
              <div class="hero-copy" style="margin-top:1rem;">
                Pensado para escritorio y para exportar el caso completo cuando lo necesites.
              </div>
            </div>
          </div>
          <div class="info-grid">
            <div class="info-tile">
              <div class="info-label">Desarrollada por</div>
              <div style="line-height:1.75;color:#17324d;">
                Owen Paredes Conde<br>
                Heriberto Espino Montelongo<br>
                Pedro Jose Garcia Guevara
              </div>
            </div>
            <div class="info-tile">
              <div class="info-label">Dirección académica</div>
              <div style="line-height:1.75;color:#17324d;">
                Dr. Francisco Garcia Castillo<br>
                UDLAP
              </div>
            </div>
            <div class="info-tile">
              <div class="info-label">Advertencia</div>
              <div style="line-height:1.75;color:#17324d;">
                Herramienta de apoyo para análisis y simulación. No sustituye la asesoría
                profesional para decisiones de retiro.
              </div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("""
        <style>
        [data-testid="stButton"] > button[kind="primary"],
        [data-testid="stButton"] > button[kind="primary"]:hover,
        [data-testid="stButton"] > button[kind="primary"]:focus,
        [data-testid="stButton"] > button[kind="primary"]:active {
            color: #ffffff !important;
        }
        </style>
        """, unsafe_allow_html=True
    )

    col_btn = st.columns([1, 1, 1])[1]
    
    with col_btn:
        if st.button("Iniciar calculadora", type="primary", use_container_width=True):
            st.session_state.app_iniciada = True
            st.rerun()

    st.markdown(
        """
        <div style="text-align:center;margin:1rem auto 0 auto;color:#5f6f7d;max-width:760px;line-height:1.7;">
            Fuentes de referencia: INEGI, Banxico y CONSAR. La interfaz está pensada para leer,
            comparar y compartir resultados con claridad.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — DATOS DEL TRABAJADOR
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title(" Retiro LSS-1997")
    st.caption("Calculadora actuarial para el régimen 1997")

    st.divider()
    st.subheader(" Datos Personales")

    nombre = st.text_input("Nombre", value="Paquito García")

    col_fn, col_gen = st.columns(2)
    with col_fn:
        fecha_nacimiento = st.date_input(
            "Fecha de nacimiento",
            value=date(2004, 12, 16),
            min_value=date(1940, 1, 1),
            max_value=date(ANIO_HOY - 18, 12, 31),
        )
    with col_gen:
        genero = st.selectbox("Género", ["Hombre", "Mujer"], index=0)
        genero_int = 0 if genero == "Hombre" else 1

    edad_actual = ANIO_HOY - fecha_nacimiento.year
    st.caption(f"Edad actual: **{edad_actual} años**")

    st.divider()
    st.subheader(" Situación Laboral")

    sbc = slider_con_input(
        "SBC mensual actual ($)",
        min_value=3_000.0,
        max_value=500_000.0,
        value=30_000.0,
        step=500.0,
        key="sbc_actual",
        number_format="%.0f",
        help="Salario base de cotización mensual actual.",
    )

    semanas = slider_con_input(
        "Semanas cotizadas",
        min_value=0,
        max_value=3_000,
        value=0,
        step=1,
        key="semanas_cotizadas",
        number_format="%d",
        help="Semanas acumuladas en el IMSS, incluidos periodos anteriores.",
    )

    cotizo_antes_97 = st.checkbox(
        "Cotizó antes del 1° julio 1997",
        value=False,
        help="Activa la opción del 4.º transitorio.",
    )

    afore = st.selectbox("AFORE", AFORES, index=AFORES.index("XXI Banorte"))

    st.divider()
    st.subheader(" Retiro")

    edad_retiro = slider_con_input(
        "Edad de retiro deseada",
        min_value=55,
        max_value=75,
        value=65,
        step=1,
        key="edad_retiro_deseada",
        number_format="%d",
    )
    anio_retiro = fecha_nacimiento.year + edad_retiro
    st.caption(f"Año estimado de retiro: **{anio_retiro}**")

    st.divider()
    st.subheader(" Beneficiarios")

    casado = st.checkbox("Tiene cónyuge (pensión de viudez)", value=False)
    genero_conyuge_int = 0
    edad_conyuge = 0
    if casado:
        col_gc, col_ec = st.columns(2)
        with col_gc:
            gc = st.selectbox("Género cónyuge", ["Hombre", "Mujer"], index=1)
            genero_conyuge_int = 0 if gc == "Hombre" else 1
        with col_ec:
            edad_conyuge = st.number_input(
                "Edad cónyuge", min_value=18, max_value=90, value=edad_actual - 2
            )

    st.divider()
    st.subheader(" Supuestos Económicos")

    with st.expander("Ajustar supuestos"):
        inflacion = slider_con_input(
            "Inflación anual %",
            min_value=2.0,
            max_value=10.0,
            value=SUPUESTOS_DEFAULT["inflacion_anual"] * 100,
            step=0.1,
            key="inflacion_anual",
            slider_format="%.1f%%",
            number_format="%.1f",
        ) / 100

        crec_sbc = slider_con_input(
            "Crecimiento SBC anual %",
            min_value=2.0,
            max_value=12.0,
            value=SUPUESTOS_DEFAULT["crecimiento_sbc"] * 100,
            step=0.1,
            key="crecimiento_sbc",
            slider_format="%.1f%%",
            number_format="%.1f",
        ) / 100

        rendimiento_manual = st.checkbox("Especificar rendimiento manual")
        rendimiento_override = None
        comision_override    = None

        if rendimiento_manual:
            rendimiento_override = slider_con_input(
                "Rendimiento AFORE anual %",
                min_value=2.0,
                max_value=15.0,
                value=5.5,
                step=0.1,
                key="rendimiento_afore_manual",
                slider_format="%.1f%%",
                number_format="%.1f",
            ) / 100
            comision_override = slider_con_input(
                "Comisión AFORE anual %",
                min_value=0.1,
                max_value=2.0,
                value=0.54,
                step=0.01,
                key="comision_afore_manual",
                slider_format="%.2f%%",
                number_format="%.2f",
            ) / 100

    st.divider()
    st.subheader(" Actualización de datos")
    actualizar_datos = False
    banxico_token_input = st.session_state.get("banxico_token", "")

    if st.button(
        " Actualizar datos en línea",
        use_container_width=True,
        help="Abre el panel para actualizar UMA, UDI, rendimientos y comisiones.",
    ):
        st.session_state.mostrar_fuentes_externas = True

    if st.session_state.mostrar_fuentes_externas:
        st.markdown("**Fuentes externas**")
        banxico_token_input = st.text_input(
            "Token de Banxico",
            value=st.session_state.get("banxico_token", ""),
            type="password",
            help="Se usa solo para actualizar la UDI en esta sesión. Si lo dejas vacío, la app intentará usar el token del entorno o de la configuración.",
        )
        st.session_state["banxico_token"] = banxico_token_input
        token_banxico_disponible = bool(
            banxico_token_input.strip()
            or os.environ.get("BANXICO_TOKEN", "").strip()
            or BANXICO_TOKEN.strip()
        )
        st.caption(
            "La UDI se puede actualizar con Banxico."
            if token_banxico_disponible
            else "Sin token de Banxico: se usará el caché local o el respaldo."
        )

        col_fuentes_1, col_fuentes_2 = st.columns(2)
        with col_fuentes_1:
            actualizar_datos = st.button(
                "Actualizar ahora",
                use_container_width=True,
                type="primary",
            )
        with col_fuentes_2:
            if st.button("Cerrar", use_container_width=True):
                st.session_state.mostrar_fuentes_externas = False
                st.rerun()


# 
# CÁLCULO PRINCIPAL
# 

@st.cache_data(ttl=300, show_spinner=False)
def calcular(
    nombre, fecha_nac_str, genero_int, edad_retiro, semanas, sbc,
    cotizo_antes_97, afore, casado, genero_conyuge_int, edad_conyuge,
    crec_sbc, rendimiento_override, comision_override,
):
    fecha_nac = date.fromisoformat(fecha_nac_str)
    t = Trabajador(
        nombre              = nombre,
        fecha_nacimiento    = fecha_nac,
        genero              = genero_int,
        edad_retiro_deseada = edad_retiro,
        semanas_cotizadas   = semanas,
        sbc_mensual         = sbc,
        cotizo_antes_1997   = int(cotizo_antes_97),
        afore               = afore,
        casado              = int(casado),
        genero_conyuge      = genero_conyuge_int,
        edad_conyuge        = edad_conyuge,
        crecimiento_sbc     = crec_sbc,
        rendimiento_afore   = rendimiento_override,
        comision_afore      = comision_override,
    )
    resultado_saldo   = proyectar_saldo_desde_trabajador(t)
    resultado_pension = calcular_pension_desde_trabajador(t, resultado_saldo)

    # Método Excel (CUS — fórmula bimestral en UDIs)
    rend_neto_ex = (rendimiento_override - comision_override) if (rendimiento_override and comision_override) else None
    pension_excel = calcular_pension_metodo_excel(
        sbc_mensual        = sbc,
        fecha_nacimiento   = t.fecha_nacimiento,
        edad_retiro        = edad_retiro,
        genero             = genero_int,
        saldo_previo_pesos = 0.0,
        rend_neto_anual    = rend_neto_ex,
        casado             = int(casado),
        genero_conyuge     = genero_conyuge_int,
        edad_conyuge       = edad_conyuge,
    )
    escenarios        = proyectar_escenarios(
        sbc_mensual     = sbc,
        anio_inicio     = ANIO_HOY,
        anio_retiro     = t.anno_retiro,
        edad_inicio     = t.edad_actual,
        anno_nacimiento = t.anno_nacimiento,
        afore           = afore,
        semanas_previas = semanas,
    )
    aportaciones      = calcular_aportaciones(sbc, ANIO_HOY)
    return t, resultado_saldo, resultado_pension, escenarios, aportaciones, pension_excel


actualizacion_exitosa = []
actualizacion_advertencias = []
if actualizar_datos:
    st.cache_data.clear()
    with st.spinner("Actualizando fuentes externas..."):
        (
            actualizacion_exitosa,
            actualizacion_advertencias,
        ) = actualizar_fuentes_externas(banxico_token_input)
    st.session_state.mostrar_fuentes_externas = False

# Ejecutar cálculo
try:
    t, res_saldo, res_pension, escenarios, aportaciones, res_pension_excel = calcular(
        nombre, fecha_nacimiento.isoformat(), genero_int, edad_retiro,
        semanas, sbc, cotizo_antes_97, afore, casado,
        genero_conyuge_int, edad_conyuge, crec_sbc,
        rendimiento_override, comision_override,
    )
    calculo_ok = True
except Exception as e:
    st.error(f"Error en el cálculo: {e}")
    calculo_ok = False
    st.stop()


# 
# CONTENIDO PRINCIPAL
# 

st.markdown("")

if actualizacion_exitosa:
    banner_estado(
        "ok",
        "Fuentes actualizadas",
        "Se actualizó: " + ", ".join(actualizacion_exitosa) + ".",
    )
if actualizacion_advertencias:
    banner_estado(
        "warn",
        "Revisión de fuentes externas",
        " | ".join(actualizacion_advertencias),
    )

#  ALERT BAR 
pension_final  = res_pension["pension_final"]
fuente         = res_pension["fuente_pension"]
cumple         = res_pension["cumple_para_pensionarse"]
tasa_reemplazo = res_pension["tasa_reemplazo"]
saldo_final    = res_saldo["saldo_final"]
semanas_tot    = res_saldo["semanas_totales"]

# Pensión método CUS (Excel)
pension_cus = res_pension_excel["pension_mensual_pesos"]

# Tasa de reemplazo CORRECTA: pensión / último salario (ambos en pesos de hoy)
_sbc_retiro_real    = ultimo_salario_real(sbc, t.annos_para_retiro)
_tasa_reemplazo_cus = pension_cus / _sbc_retiro_real if _sbc_retiro_real > 0 else 0.0

# Pensión equivalente en salario de hoy:
# tasa_reemplazo × SBC_actual → "¿qué pensión recibirías si te jubilaras hoy?"
# Sirve como referencia intuitiva para anclar el porcentaje a pesos conocidos.
_pension_equiv_hoy  = _tasa_reemplazo_cus * sbc

#  CONVERSIÓN A PESOS DE HOY (términos reales) 
# El Excel trabaja en UDIs: muestra resultados en poder adquisitivo actual.
# Nosotros proyectamos en pesos nominales futuros. Para comparar con el Excel
# y dar al usuario una cifra intuitiva, deflamos por la inflación acumulada.
_inflacion_ef   = t.inflacion_anual or SUPUESTOS_DEFAULT["inflacion_anual"]
_factor_deflac  = (1 + _inflacion_ef) ** t.annos_para_retiro
pension_real    = pension_final / _factor_deflac   # pesos de hoy equivalentes
saldo_real      = saldo_final   / _factor_deflac   # pesos de hoy equivalentes

st.markdown(
    f"""
    <section class="summary-banner">
      <div class="summary-card">
        <div class="summary-kicker">Expediente del trabajador</div>
        <div class="summary-main">Proyeccion de retiro de {t.nombre}</div>
        <div class="summary-note">
          {t.genero_label} de {t.edad_actual} años, afiliado a {t.afore}, con retiro objetivo en
          {t.anno_retiro}. La lectura prioriza valores reales en pesos de {ANIO_HOY} para que
          la comparación sea más intuitiva y accionable.
        </div>
      </div>
      <div class="summary-side">
        <div>
          <div class="label">Horizonte restante</div>
          <div class="value">{t.annos_para_retiro} años</div>
        </div>
        <div class="caption">
          Semanas actuales: {t.semanas_cotizadas:,}<br>
          SBC actual: ${sbc:,.0f} al mes<br>
          Modalidad: {"con conyuge" if casado else "sin conyuge"}
        </div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

if not cumple:
    sem_req = res_pension["pension_rcv"]["semanas_requeridas"]
    sem_falt = max(0, sem_req - semanas_tot)
    banner_estado(
        "warn",
        "Requisito pendiente",
        f"Con la proyección actual no alcanza las {sem_req:,} semanas necesarias para retirarse en {t.anno_retiro}. "
        f"Faltarían unas {sem_falt:,} semanas, equivalentes a {sem_falt//52:.1f} años más de cotización.",
    )
elif fuente == "PMG":
    banner_estado(
        "info",
        "Resultado con PMG",
        "El saldo proyectado no alcanza para superar la Pensión Mínima Garantizada. "
        "Por eso se muestra la PMG como pensión final y la brecha correspondiente.",
    )
else:
    banner_estado(
        "ok",
        "Trayectoria suficiente",
        "Con los supuestos actuales, la proyección sí alcanza para una pensión financiada con el saldo de la AFORE.",
    )

toolbar_copy = """
<div class="app-toolbar">
  <div class="action-panel-label">Centro de acciones</div>
  <div class="app-toolbar-title">
    Revisa el caso en estas cinco vistas y, cuando quieras, abre la versión imprimible
    para compartir el expediente completo.
  </div>
"""

if st.session_state.mostrar_reporte_impresion:
    toolbar_copy += """
  <div class="app-toolbar-subtle">
    <strong>Reporte integral listo para impresión.</strong> Esta vista reúne la información principal de las cinco secciones.
    Puedes revisar el consolidado, usar el botón de impresión y guardar la salida como PDF desde el navegador si lo necesitas.
    Si tu navegador bloquea la impresión, permite la acción y vuelve a intentarlo.
  </div>
"""

toolbar_copy += "</div>"

toolbar_info_col, toolbar_actions_col = st.columns([1.9, 1.1], gap="medium")
with toolbar_info_col:
    st.markdown(toolbar_copy, unsafe_allow_html=True)

with toolbar_actions_col:
    st.markdown(
        """
        <div class="app-toolbar">
          <div class="action-panel-label">Acciones</div>
          <div class="app-toolbar-subtle">Desde aquí puedes mostrar la barra lateral, imprimir o cerrar la vista imprimible.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "Ocultar barra lateral" if st.session_state.sidebar_visible else "Mostrar barra lateral",
        use_container_width=True,
    ):
        st.session_state.sidebar_visible = not st.session_state.sidebar_visible
        st.rerun()
    if st.button("Imprimir / Exportar", use_container_width=True):
        st.session_state.mostrar_reporte_impresion = True
    if st.session_state.mostrar_reporte_impresion:
        if st.button("Abrir diálogo de impresión", use_container_width=True, type="primary"):
            disparar_dialogo_impresion()
        if st.button("Ocultar reporte", use_container_width=True):
            st.session_state.mostrar_reporte_impresion = False


# 
# TABS
# 

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    " Resumen",
    " Aportaciones",
    " Proyección Saldo",
    " Pensión",
    " Escenarios",
])


#  TAB 1: RESUMEN 
with tab1:
    st.subheader("Resultado Principal")
    st.markdown(
        "<div class='section-intro'>Aquí ves la pensión estimada, el saldo acumulado y la tasa de reemplazo en una lectura rápida.</div>",
        unsafe_allow_html=True,
    )

    # Banner explicativo sobre la métrica
    banner_estado(
        "info",
        f"Valores comparables en pesos de {ANIO_HOY}",
        "Todos los montos del resumen están expresados en pesos de hoy para que la comparación sea directa.",
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        _estado_c1 = " (con conyuge)" if res_pension_excel["casado"] else ""
        st.metric(
            label=f" Pensión mensual CUS{_estado_c1} — pesos de {ANIO_HOY}",
            value=f"${pension_cus:,.0f}",
            delta=f"Fuente: {fuente}",
            delta_color="normal",
        )

    with c2:
        st.metric(
            label=f" Saldo AFORE (pesos de {ANIO_HOY})",
            value=f"${saldo_real:,.0f}",
            delta=f"{t.annos_para_retiro} años de acumulación",
        )

    with c3:
        st.metric(
            label=" Semanas cotizadas (proyectadas)",
            value=f"{semanas_tot:,}",
            delta=f"Requisito: {res_pension['pension_rcv']['semanas_requeridas']:,}",
            delta_color="normal" if cumple else "inverse",
        )

    with c4:
        st.metric(
            label=" Tasa de reemplazo (pension / ultimo salario)",
            value=f"{_tasa_reemplazo_cus:.1%}",
            delta=f"SBC retiro estimado ${_sbc_retiro_real:,.0f}",
            delta_color="off",
        )

    # Métrica de referencia: pensión equivalente en salario de hoy
    st.markdown(
        f"""
        <div class="hero-shell" style="padding:1.25rem 1.35rem;margin-top:1rem;">
          <div class="hero-eyebrow">Ancla intuitiva</div>
          <div style="font-size:clamp(2.4rem,4vw,4.4rem);line-height:1;color:#17324d;">
            ${_pension_equiv_hoy:,.0f}<span style="font-size:1.05rem;color:#5f6f7d;"> / mes</span>
          </div>
          <div class="hero-copy" style="margin-top:0.6rem;">
            Es la pensión equivalente en salario de hoy: una forma más tangible de leer la tasa de reemplazo
            de <strong>{_tasa_reemplazo_cus:.1%}</strong> aplicada al SBC actual de <strong>${sbc:,.0f}</strong>.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Datos de referencia (año actual)")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        uma_hoy = get_uma_mensual(ANIO_HOY)
        st.metric("UMA mensual", f"${uma_hoy:,.2f}")
        st.metric("SBC tope (25 UMAs)", f"${uma_hoy * 25:,.2f}")

    with col_b:
        rend = get_rendimiento_afore(afore)
        com  = get_comision_afore(afore, ANIO_HOY)
        st.metric(f"Rendimiento {afore}", f"{rend:.2%}")
        st.metric(f"Comisión {afore}", f"{com:.4%}")

    with col_c:
        aport_mens = aportaciones["aportacion_total"]
        st.metric("Aportación mensual al AFORE", f"${aport_mens:,.2f}")
        st.metric("Rendimiento neto estimado", f"{rend - com:.2%}")


#  TAB 2: APORTACIONES 
with tab2:
    st.markdown(
        "<div class='section-intro'>Aquí se muestra quién aporta, cuánto entra cada mes a la AFORE y cómo cambia la cuota patronal durante el periodo transitorio.</div>",
        unsafe_allow_html=True,
    )
    st.subheader(f"Desglose de Aportaciones — {ANIO_HOY}")

    col_ap1, col_ap2 = st.columns([2, 1])

    with col_ap1:
        # Tabla desglose
        data_ap = {
            "Concepto":          ["Retiro (patrón)", "Cesantía y vejez (patrón)", "Trabajador", "Cuota social (gobierno)", "TOTAL"],
            "Tasa":              [
                f"{aportaciones['tasa_retiro']:.3%}",
                f"{aportaciones['tasa_cesantia_vejez']:.3%}",
                f"{aportaciones['tasa_trabajador']:.3%}",
                "N/A",
                f"{aportaciones['tasa_total']:.3%}",
            ],
            "Monto mensual":     [
                f"${aportaciones['cuota_retiro']:,.2f}",
                f"${aportaciones['cuota_cesantia_vejez']:,.2f}",
                f"${aportaciones['cuota_trabajador']:,.2f}",
                f"${aportaciones['cuota_social']:,.2f}",
                f"${aportaciones['aportacion_total']:,.2f}",
            ],
            "Monto anual":       [
                f"${aportaciones['cuota_retiro']*12:,.0f}",
                f"${aportaciones['cuota_cesantia_vejez']*12:,.0f}",
                f"${aportaciones['cuota_trabajador']*12:,.0f}",
                f"${aportaciones['cuota_social']*12:,.0f}",
                f"${aportaciones['aportacion_total']*12:,.0f}",
            ],
        }
        df_ap = pd.DataFrame(data_ap)
        st.dataframe(df_ap, hide_index=True, use_container_width=True)

        st.caption(
            f"SBC cotizable: **${aportaciones['sbc_cotizable']:,.2f}** " f"(bracket: {aportaciones['bracket']})" )

    with col_ap2:
        # Pie chart
        fig_pie = px.pie(
            values=[
                aportaciones["cuota_retiro"],
                aportaciones["cuota_cesantia_vejez"],
                aportaciones["cuota_trabajador"],
                max(aportaciones["cuota_social"], 0.01),
            ],
            names=["Retiro", "Cesantía/Vejez", "Trabajador", "Cuota social"],
            color_discrete_sequence=[COLOR_PRIMARIO, COLOR_BASE, COLOR_ACENTO, "#AED6F1"],
            hole=0.4,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent")
        aplicar_tema_grafica(fig_pie, height=300)
        fig_pie.update_layout(showlegend=True, margin=dict(t=24, b=10, l=10, r=10))
        render_plotly(fig_pie, "tab_aportaciones_pie")

    st.divider()
    st.subheader("Evolución de cuotas (2023-2031)")

    # Mostrar cómo suben las cuotas durante el período transitorio
    anios_trans = list(range(2023, 2032))
    datos_trans = []
    for ay in anios_trans:
        ap_ay = calcular_aportaciones(sbc, ay)
        datos_trans.append({
            "Año": ay,
            "Tasa total patronal": ap_ay["tasa_total_patronal"],
            "Aportación mensual":  ap_ay["aportacion_total"],
            "Bracket":             ap_ay["bracket"],
        })

    df_trans = pd.DataFrame(datos_trans)

    fig_trans = go.Figure()
    aplicar_tema_grafica(fig_trans, height=320)
    fig_trans.add_trace(go.Bar(
        x=df_trans["Año"],
        y=df_trans["Aportación mensual"],
        marker_color=COLOR_PRIMARIO,
        name="Aportación mensual ($)",
    ))
    fig_trans.update_layout(
        title="Aportación mensual al AFORE durante período transitorio",
        xaxis_title="Año",
        yaxis_title="$",
        yaxis_tickformat="$,.0f",
    )
    render_plotly(fig_trans, "tab_aportaciones_transicion")


#  TAB 3: PROYECCIÓN SALDO 
with tab3:
    st.markdown(
        "<div class='section-intro'>La trayectoria anual ayuda a separar lo que viene de aportaciones, rendimiento y crecimiento del SBC.</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Proyección del Saldo AFORE año a año")

    detalle = res_saldo["detalle_anual"]
    df_det  = pd.DataFrame(detalle)

    if not df_det.empty:
        # Gráfica principal: saldo acumulado
        fig_saldo = go.Figure()
        aplicar_tema_grafica(fig_saldo, height=390)
        fig_saldo.add_trace(go.Scatter(
            x=df_det["anio"],
            y=df_det["saldo_fin"],
            mode="lines",
            name="Saldo AFORE",
            line=dict(color=COLOR_PRIMARIO, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(27,79,114,0.1)",
        ))
        fig_saldo.add_trace(go.Scatter(
            x=df_det["anio"],
            y=df_det["aportacion_anual"].cumsum() + (0 if semanas == 0 else saldo_final * 0),
            mode="lines",
            name="Aportaciones acumuladas",
            line=dict(color=COLOR_ACENTO, width=1.5, dash="dot"),
        ))
        fig_saldo.update_layout(
            title="Saldo acumulado en AFORE",
            xaxis_title="Año",
            yaxis_title="Pesos corrientes",
            yaxis_tickformat="$,.0f",
        )
        render_plotly(fig_saldo, "tab_saldo_acumulado")

        # Gráfica: SBC proyectado
        fig_sbc = px.line(
            df_det, x="anio", y="sbc_mensual",
            title="SBC mensual proyectado",
            labels={"anio": "Año", "sbc_mensual": "SBC mensual ($)"},
            color_discrete_sequence=[COLOR_ACENTO],
        )
        aplicar_tema_grafica(fig_sbc, height=280)
        fig_sbc.update_traces(line=dict(width=3))
        fig_sbc.update_layout(yaxis_tickformat="$,.0f")
        render_plotly(fig_sbc, "tab_sbc_proyectado")

        # Tabla resumen cada 5 años
        st.subheader("Detalle cada 5 años")
        df_5 = df_det[df_det["anio"] % 5 == 0].copy()
        df_5_show = df_5[["anio", "edad", "sbc_mensual", "aportacion_anual",
                           "rendimiento_neto", "semanas_acum", "saldo_fin"]].copy()
        df_5_show.columns = ["Año", "Edad", "SBC mensual", "Aportación anual",
                              "Rend. neto", "Semanas acum.", "Saldo al fin"]
        df_5_show["SBC mensual"]     = df_5_show["SBC mensual"].map("${:,.0f}".format)
        df_5_show["Aportación anual"] = df_5_show["Aportación anual"].map("${:,.0f}".format)
        df_5_show["Rend. neto"]       = df_5_show["Rend. neto"].map("{:.2%}".format)
        df_5_show["Semanas acum."]    = df_5_show["Semanas acum."].map("{:,}".format)
        df_5_show["Saldo al fin"]     = df_5_show["Saldo al fin"].map("${:,.0f}".format)
        st.dataframe(df_5_show, hide_index=True, use_container_width=True)


#  TAB 4: PENSIÓN 
with tab4:
    st.markdown(
        "<div class='section-intro'>Esta vista separa el cálculo actuarial en UDIs de la referencia nominal con PMG para comparar requisitos y brechas de financiamiento.</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Cálculo de Pensión")

    #  Método CUS (fórmula actuarial del Excel) 
    pension_cus = res_pension_excel["pension_mensual_pesos"]
    udi_hoy_val = res_pension_excel["udi_hoy"]

    st.markdown("###  Método Actuarial CUS")
    st.caption(
        "Fórmula bimestral en UDIs con parámetros CONSAR/CUS.")
    c_cus1, c_cus2, c_cus3 = st.columns(3)
    with c_cus1:
        label_estado = "casado/a" if res_pension_excel["casado"] else "soltero/a"
        st.metric(
            f"Pension mensual — {label_estado} (pesos de {ANIO_HOY})",
            f"${pension_cus:,.0f}",
            delta=f"Tasa de reemplazo {_tasa_reemplazo_cus:.1%} del ultimo salario",
        )
    with c_cus2:
        st.metric(
            " Ahorro total (UDIs)",
            f"{res_pension_excel['total_udis']:,.0f}",
            delta=f"≈ ${res_pension_excel['total_udis']*udi_hoy_val:,.0f}",
        )
    with c_cus3:
        if res_pension_excel["casado"]:
            reduccion_pct = (1 - res_pension_excel["ratio_casado"]) * 100
            st.metric(
                " Conv(k) — factor con conyuge",
                f"{res_pension_excel['conv_k']:.4f}",
                delta=f"vs ax solo {res_pension_excel['ax_m']:.4f}  (-{reduccion_pct:.1f}% pension)",
                delta_color="inverse",
            )
        else:
            st.metric(
                " UDI actual",
                f"${udi_hoy_val:.4f}",
                delta=f"ax(m) = {res_pension_excel['ax_m']:.4f}",
            )

    with st.expander(" Desglose M1 / M2 / M3 en UDIs"):
        cd1, cd2, cd3, cd4 = st.columns(4)
        with cd1:
            st.metric("M1 — Transitorio 2026-2030",  f"{res_pension_excel['m1_udis']:,.0f}")
        with cd2:
            st.metric("M2 — Contribuciones 2030+",   f"{res_pension_excel['m2_udis']:,.0f}")
        with cd3:
            st.metric("M3 — Saldo previo",            f"{res_pension_excel['m3_udis']:.0f}")
        with cd4:
            st.metric("TOTAL",                         f"{res_pension_excel['total_udis']:,.0f}")
        params = res_pension_excel["parametros"]
        st.caption(
            f"i bimestral real = {params['i_bi']:.6f} ({(1+params['i_bi'])**6-1:.4%}/año)  ·  " f"q bimestral real = {params['q_bi']:.6f} ({(1+params['q_bi'])**6-1:.4%}/año)  ·  " f"n = {res_pension_excel['n_bi']:.2f} bi  ·  FM2 = {res_pension_excel['FM2']:.4f}" )
        st.caption(
            f"Factores CUS: b1={params['b1']} · FACBI={params['FACBI']:.6f} · " f"FI={params['FI']:.6f} · a={params['a']} · " f"ä1(12)={res_pension_excel['an_12']:.4f}" )

    # Banner resultado CUS
    _estado_label = "con conyugue" if res_pension_excel["casado"] else "soltero/a"
    _conv_k_info  = (
        f" | Conv(k) = {res_pension_excel['conv_k']:.4f}  " f"(reduccion por conyuge: -{(1-res_pension_excel['ratio_casado'])*100:.1f}%)" if res_pension_excel["casado"] else "" )
    st.markdown(
        f""" <div class="hero-shell" style="padding:1.3rem 1.35rem;margin:1rem 0;">
          <div class="hero-eyebrow">
            Lectura principal CUS
          </div>
          <div class="hero-title" style="font-size:clamp(2.3rem,3.8vw,3.8rem);margin:0.1rem 0 0 0;">
            ${pension_cus:,.2f} <span style="font-size:1rem;color:#5f6f7d;">/ mes</span>
          </div>
          <div class="hero-copy" style="margin-top:0.45rem;">
            Pensión CUS para trabajador {_estado_label} en pesos de {ANIO_HOY}. La tasa de reemplazo estimada es
            <strong>{_tasa_reemplazo_cus:.1%}</strong> del último salario real{_conv_k_info}.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    #  Método nominal / PMG (referencia adicional) 
    st.markdown(f"###  Referencia: proyección nominal (deflactada a {ANIO_HOY})")
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown("** Pensión RCV (saldo AFORE proyectado)**")
        rcv = res_pension["pension_rcv"]
        st.metric(f"Pensión real (pesos de {ANIO_HOY})", f"${pension_real:,.0f}")
        st.metric(f"Pensión nominal {t.anno_retiro}", f"${rcv['pension_mensual']:,.0f}")
        st.caption(
            f"äx(12): **{rcv['ax_utilizado']:.4f}** · Tipo: {rcv['tipo']}"
        )
        st.caption(
            f"{'OK' if rcv['cumple_requisitos'] else 'X'} Semanas: {semanas_tot:,} / {rcv['semanas_requeridas']:,} requeridas"
        )

    with col_p2:
        pmg = res_pension["pension_pmg"]
        st.markdown("** Pensión Mínima Garantizada (Art. 170)**")
        if pmg["aplica"]:
            st.metric("PMG mensual", f"${pmg['monto_mensual']:,.2f}")
            st.caption(
                f"Bracket: {pmg['bracket']} · " f"Semanas clave: {pmg['semanas_key']:,} · " f"Factor actualización: {pmg['factor_actualizacion']:.4f}" )
        else:
            banner_estado(
                "info",
                "PMG no aplicable",
                pmg.get("razon_no_aplica", "No cumple los requisitos."),
            )

    if res_pension["deficit_saldo"] > 0:
        banner_estado(
            "warn",
            "Hay una brecha para financiar la PMG",
            f"El Estado aportaría alrededor de ${res_pension['deficit_saldo']:,.0f}. Para financiar la PMG con recursos propios haría falta un saldo de ${res_pension['saldo_requerido_pmg']:,.0f}.",
        )

    st.divider()
    st.subheader(" Calculadora de Meta de Pensión")
    st.caption(
        "¿Cuánto tendrías que aportar cada mes para llegar a una tasa de reemplazo objetivo?" )

    col_meta1, col_meta2 = st.columns([1, 2])
    with col_meta1:
        tasa_meta = slider_con_input(
            "Tasa de reemplazo objetivo",
            min_value=10,
            max_value=100,
            value=30,
            step=5,
            key="tasa_reemplazo_objetivo",
            slider_format="%d%%",
            number_format="%d",
            help="Porcentaje del último salario que deseas recibir como pensión mensual",
        )
        tasa_meta_float = tasa_meta / 100.0

    with col_meta2:
        pension_meta_pesos = tasa_meta_float * _sbc_retiro_real
        st.metric(
            "Pensión objetivo (pesos de hoy)",
            f"${pension_meta_pesos:,.0f}/mes",
            delta=f"{tasa_meta}% de último salario ${_sbc_retiro_real:,.0f}",
            delta_color="off",
        )

    if tasa_meta_float <= _tasa_reemplazo_cus:
        st.success(
            f" ¡Ya alcanzas el {tasa_meta}%! Tu tasa de reemplazo actual es " f"**{_tasa_reemplazo_cus:.1%}** sin aportaciones voluntarias adicionales.",
        )
    else:
        r_inv = calcular_aportacion_extra_para_tasa(
            sbc_mensual      = sbc,
            fecha_nacimiento = t.fecha_nacimiento,
            edad_retiro      = edad_retiro,
            genero           = genero_int,
            tasa_objetivo    = tasa_meta_float,
            casado           = int(casado),
            rend_neto_anual  = (rendimiento_override - comision_override)
                               if (rendimiento_override and comision_override) else None,
        )

        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            st.metric(
                " Aportación mensual extra necesaria",
                f"${r_inv['aportacion_extra_pesos']:,.0f}",
                delta=f"{r_inv['pct_sbc']:.1%} del SBC actual",
                delta_color="off",
            )
        with ci2:
            st.metric(
                " Pensión con esa aportación",
                f"${r_inv['pension_objetivo']:,.0f}/mes",
                delta=f"+${r_inv['pension_objetivo']-r_inv['pension_actual']:,.0f} vs sin extra",
            )
        with ci3:
            st.metric(
                " Tasa de reemplazo lograda",
                f"{tasa_meta}%",
                delta=f"vs actual {_tasa_reemplazo_cus:.1%}",
            )

        # Tabla de sensibilidad: diferentes metas
        st.markdown("##### Tabla de sensibilidad — aportación extra por meta")
        filas_sens = []
        for t_pct in [10, 20, 30, 40, 50, 60, 70]:
            t_f = t_pct / 100.0
            if t_f <= _tasa_reemplazo_cus:
                filas_sens.append({
                    "Meta (%)":    f"{t_pct}%",
                    "Pension objetivo": f"${t_f * _sbc_retiro_real:,.0f}/mes",
                    "Aportacion extra": "Ya se alcanza ",
                    "% del SBC":  "—",
                })
            else:
                ri = calcular_aportacion_extra_para_tasa(
                    sbc, t.fecha_nacimiento, edad_retiro, genero_int,
                    t_f, int(casado),
                    rend_neto_anual=(rendimiento_override - comision_override)
                                    if (rendimiento_override and comision_override) else None,
                )
                filas_sens.append({
                    "Meta (%)":    f"{t_pct}%",
                    "Pension objetivo": f"${ri['pension_objetivo']:,.0f}/mes",
                    "Aportacion extra": f"${ri['aportacion_extra_pesos']:,.0f}/mes",
                    "% del SBC":  f"{ri['pct_sbc']:.1%}",
                })
        st.dataframe(pd.DataFrame(filas_sens), hide_index=True, use_container_width=True)

        st.caption(
            " Las aportaciones voluntarias al AFORE pueden deducirse de impuestos " "(hasta el 10% del ingreso anual o 5 UMAs anuales). " "Consulta con tu AFORE para abrir una subcuenta voluntaria." )


#  TAB 5: ESCENARIOS 
with tab5:
    st.markdown(
        "<div class='section-intro'>Los tres escenarios ayudan a ver cómo cambia el retiro cuando varían el rendimiento y el crecimiento salarial.</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Análisis de Escenarios")

    esc_pes = escenarios["pesimista"]
    esc_bas = escenarios["base"]
    esc_opt = escenarios["optimista"]

    from calculators.pension import calcular_pension_total as _cpt_esc

    def _pension_esc(res_esc):
        return _cpt_esc(
            saldo_afore       = res_esc["saldo_final"],
            sbc_promedio      = sbc,
            genero            = genero_int,
            edad_retiro       = edad_retiro,
            semanas_cotizadas = res_esc["semanas_totales"],
            anio_retiro       = t.anno_retiro,
            cotizo_antes_1997 = bool(cotizo_antes_97),
        )

    p_pes = _pension_esc(esc_pes)
    p_bas = _pension_esc(esc_bas)
    p_opt = _pension_esc(esc_opt)

    # Deflactar a pesos de hoy
    p_pes_real = p_pes["pension_final"] / _factor_deflac
    p_bas_real = p_bas["pension_final"] / _factor_deflac
    p_opt_real = p_opt["pension_final"] / _factor_deflac
    s_pes_real = esc_pes["saldo_final"] / _factor_deflac
    s_bas_real = esc_bas["saldo_final"] / _factor_deflac
    s_opt_real = esc_opt["saldo_final"] / _factor_deflac

    banner_estado(
        "info",
        f"Escenarios expresados en pesos de {ANIO_HOY}",
        "Comparar los tres escenarios en pesos de hoy ayuda a ver cuánto cambia el resultado según el rendimiento y la trayectoria salarial.",
    )

    c_e1, c_e2, c_e3 = st.columns(3)
    with c_e1:
        st.markdown("**Pesimista**")
        st.metric("Saldo", f"${s_pes_real:,.0f}")
        st.metric("Pensión", f"${p_pes_real:,.0f}/mes")
        st.caption("Rendimiento mínimo + crecimiento salarial bajo")

    with c_e2:
        st.markdown("**Base**")
        st.metric("Saldo", f"${s_bas_real:,.0f}")
        st.metric("Pensión", f"${p_bas_real:,.0f}/mes")
        st.caption("Rendimiento promedio + crecimiento histórico")

    with c_e3:
        st.markdown("**Optimista**")
        st.metric("Saldo", f"${s_opt_real:,.0f}")
        st.metric("Pensión", f"${p_opt_real:,.0f}/mes")
        st.caption("Rendimiento máximo + crecimiento salarial alto")

    # Gráfica de saldos por escenario
    st.divider()
    all_dets = {
        "Pesimista": esc_pes["detalle_anual"],
        "Base":      esc_bas["detalle_anual"],
        "Optimista": esc_opt["detalle_anual"],
    }

    fig_esc = go.Figure()
    aplicar_tema_grafica(fig_esc, height=390)
    colors  = {"Pesimista": COLOR_PESIMISTA, "Base": COLOR_BASE, "Optimista": COLOR_OPTIMISTA}

    for nombre_esc, det in all_dets.items():
        if det:
            df_e = pd.DataFrame(det)
            fig_esc.add_trace(go.Scatter(
                x=df_e["anio"],
                y=df_e["saldo_fin"],
                name=nombre_esc,
                mode="lines",
                line=dict(color=colors[nombre_esc], width=2),
            ))

    fig_esc.update_layout(
        title="Proyección de saldo por escenario",
        xaxis_title="Año",
        yaxis_title="Saldo ($)",
        yaxis_tickformat="$,.0f",
    )
    render_plotly(fig_esc, "tab_escenarios_saldo")

    # Tabla comparativa
    df_esc_comp = pd.DataFrame([
        {
            f"Escenario":                   "Pesimista ",
            f"Saldo (pesos de {ANIO_HOY})": f"${s_pes_real:,.0f}",
            f"Pensión/mes (pesos de {ANIO_HOY})": f"${p_pes_real:,.0f}",
            "Tasa reemplazo (pensión/último salario)":
                f"{p_pes_real/_sbc_retiro_real:.1%}" if _sbc_retiro_real > 0 else "N/A",
        },
        {
            f"Escenario":                   "Base ",
            f"Saldo (pesos de {ANIO_HOY})": f"${s_bas_real:,.0f}",
            f"Pensión/mes (pesos de {ANIO_HOY})": f"${p_bas_real:,.0f}",
            "Tasa reemplazo (pensión/último salario)":
                f"{p_bas_real/_sbc_retiro_real:.1%}" if _sbc_retiro_real > 0 else "N/A",
        },
        {
            f"Escenario":                   "Optimista ",
            f"Saldo (pesos de {ANIO_HOY})": f"${s_opt_real:,.0f}",
            f"Pensión/mes (pesos de {ANIO_HOY})": f"${p_opt_real:,.0f}",
            "Tasa reemplazo (pensión/último salario)":
                f"{p_opt_real/_sbc_retiro_real:.1%}" if _sbc_retiro_real > 0 else "N/A",
        },
    ])
    st.dataframe(df_esc_comp, hide_index=True, use_container_width=True)


# 
# REPORTE IMPRIMIBLE
# 

if st.session_state.mostrar_reporte_impresion:
    st.markdown(
        f"""
        <div class="report-shell">
          <div class="report-title">Resumen del trabajador</div>
          <div class="report-note">
            {t.nombre} · {t.genero_label} · {t.edad_actual} años actuales · retiro objetivo en {t.anno_retiro} ·
            AFORE {t.afore} · SBC actual ${sbc:,.0f} mensuales.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rep1, rep2, rep3, rep4 = st.columns(4)
    with rep1:
        st.metric(f"Pension CUS (pesos de {ANIO_HOY})", f"${pension_cus:,.0f}")
    with rep2:
        st.metric(f"Saldo AFORE (pesos de {ANIO_HOY})", f"${saldo_real:,.0f}")
    with rep3:
        st.metric("Semanas proyectadas", f"{semanas_tot:,}")
    with rep4:
        st.metric("Tasa de reemplazo", f"{_tasa_reemplazo_cus:.1%}")

    st.markdown(
        """
        <div class="report-shell">
          <div class="report-title">Aportaciones y referencias vigentes</div>
          <div class="report-note">
            Desglose mensual y anual de la aportacion al AFORE bajo el salario base capturado y las tasas vigentes.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(df_ap, hide_index=True, use_container_width=True)
    render_plotly(fig_pie, "report_aportaciones_pie")
    render_plotly(fig_trans, "report_aportaciones_transicion")

    st.markdown(
        """
        <div class="report-shell">
          <div class="report-title">Trayectoria del saldo</div>
          <div class="report-note">
            Evolucion anual del saldo acumulado y detalle operativo en cortes de cinco años.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not df_det.empty:
        render_plotly(fig_saldo, "report_saldo_acumulado")
        render_plotly(fig_sbc, "report_sbc_proyectado")
        st.dataframe(df_5_show, hide_index=True, use_container_width=True)

    st.markdown(
        """
        <div class="report-shell">
          <div class="report-title">Lectura de pension y metas</div>
          <div class="report-note">
            Se incluyen la pension bajo metodo CUS, la referencia nominal y la evaluacion de metas de reemplazo.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    pen1, pen2, pen3 = st.columns(3)
    with pen1:
        st.metric(f"Pension CUS (pesos de {ANIO_HOY})", f"${pension_cus:,.0f}")
    with pen2:
        st.metric(f"Pension real nominal (pesos de {ANIO_HOY})", f"${pension_real:,.0f}")
    with pen3:
        st.metric("Pension equivalente en salario de hoy", f"${_pension_equiv_hoy:,.0f}")
    if "filas_sens" in locals():
        st.dataframe(pd.DataFrame(filas_sens), hide_index=True, use_container_width=True)

    st.markdown(
        """
        <div class="report-shell">
          <div class="report-title">Escenarios</div>
          <div class="report-note">
            Comparativo entre casos pesimista, base y optimista para dimensionar la sensibilidad del retiro.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_plotly(fig_esc, "report_escenarios_saldo")
    st.dataframe(df_esc_comp, hide_index=True, use_container_width=True)


# 
# FOOTER
# 

st.divider()
st.caption(
    "**Calculadora de Retiro LSS-1997** · Datos: INEGI (UMA), Banxico (UDI), CONSAR (AFORE) · " f"Cache vigente: {'' if cache_esta_vigente() else ' actualizar'} · " " Esta herramienta es orientativa. Consulta a un asesor certificado para decisiones de retiro."
)

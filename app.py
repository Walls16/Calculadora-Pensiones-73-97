"""
app.py
Calculadora de Retiro LSS-1997 — Interfaz Streamlit

Correr con:
    streamlit run app.py

Requiere:
    pip install streamlit plotly pandas requests beautifulsoup4 lxml openpyxl
"""
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

#  Path setup 
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Silenciar logs de fetchers en la UI
logging.basicConfig(level=logging.WARNING)
logging.getLogger("data_fetchers").setLevel(logging.ERROR)

#  Imports del proyecto 
from config import AFORES, SUPUESTOS_DEFAULT
from models.trabajador import Trabajador
from data_fetchers.uma             import fetch_uma, get_uma_mensual, cache_esta_vigente
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
ANIO_HOY = date.today().year


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
    .metric-card {
        background-color: #f8f9fa;
        border-left: 4px solid #1B4F72;
        padding: 16px;
        border-radius: 4px;
        margin: 8px 0;
    }
    .metric-value { font-size: 2rem; font-weight: bold; color: #1B4F72; }
    .metric-label { font-size: 0.85rem; color: #666; text-transform: uppercase; }
    .alert-pmg {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 12px;
        border-radius: 4px;
    }
    .alert-ok {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 12px;
        border-radius: 4px;
    }
    div[data-testid="stSidebarContent"] { padding-top: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 20px; }
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


# ═══════════════════════════════════════════════════════════════════════════
# PORTADA
# ═══════════════════════════════════════════════════════════════════════════

if "app_iniciada" not in st.session_state:
    st.session_state.app_iniciada = False

if not st.session_state.app_iniciada:

    # Ocultar sidebar en portada via CSS global
    st.markdown("""
    <style>
    [data-testid="stSidebar"]{display:none!important}
    [data-testid="stToolbar"]{display:none!important}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;padding:40px 20px;text-align:center;font-family:sans-serif;">
    <p style="font-size:2.6rem;font-weight:800;color:#1B4F72;line-height:1.2;margin:0 0 10px 0;">Calculadora de Retiro LSS-1997</p>
    <p style="font-size:1rem;color:#999;line-height:1.6;max-width:560px;margin:0 0 48px 0;">Herramienta actuarial basada en la metodolog&iacute;a CUS de la CNSF y la normativa del IMSS &mdash; R&eacute;gimen de Cuentas Individuales</p>
    <p style="font-size:0.7rem;text-transform:uppercase;letter-spacing:2.5px;color:#666;margin:0 0 20px 0;">Desarrollada por</p>
    <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:12px 40px;margin-bottom:44px;">
    <div style="display:flex;flex-direction:column;align-items:center;gap:3px;">
    <a href="https://www.linkedin.com/in/owen-conde/" style="font-size:0.95rem;font-weight:600;color:#ddd;text-decoration:none;">Owen Paredes Conde</a>
    <span style="font-size:0.75rem;color:#0A66C2;">linkedin.com/in/owen-conde</span>
    </div>
    <div style="display:flex;flex-direction:column;align-items:center;gap:3px;">
    <a href="https://www.linkedin.com/in/heri-espino/" style="font-size:0.95rem;font-weight:600;color:#ddd;text-decoration:none;">Heriberto Espino Montelongo</a>
    <span style="font-size:0.75rem;color:#0A66C2;">linkedin.com/in/heri-espino</span>
    </div>
    <div style="display:flex;flex-direction:column;align-items:center;gap:3px;">
    <a href="https://www.linkedin.com/in/pedropgg/" style="font-size:0.95rem;font-weight:600;color:#ddd;text-decoration:none;">Pedro Jos&eacute; Garc&iacute;a Guevara</a>
    <span style="font-size:0.75rem;color:#0A66C2;">linkedin.com/in/pedropgg</span>
    </div>
    </div>
    <hr style="width:320px;border:none;border-top:1px solid #2c2c2c;margin:0 auto 28px auto;">
    <p style="font-size:0.88rem;color:#888;line-height:1.9;margin:0 0 48px 0;">Dirigida y supervisada por<br>
    <a href="https://www.linkedin.com/in/dr-francisco-garcia-castillo/" style="color:#5DADE2;font-weight:600;text-decoration:none;">Dr. Francisco Garc&iacute;a Castillo</a> &nbsp;&middot;&nbsp; UDLAP</p>
    </div>""", unsafe_allow_html=True)

    col_btn = st.columns([1, 1, 1])[1]
    with col_btn:
        if st.button("Iniciar calculadora", type="primary", use_container_width=True):
            st.session_state.app_iniciada = True
            st.rerun()

    st.markdown("""
    <div class="portada-nota" style="text-align:center; margin:0 auto;">
        Esta herramienta es orientativa. Consulta a un asesor certificado
        para decisiones de retiro. Datos: INEGI, Banxico, CONSAR.
    </div>
    """, unsafe_allow_html=True)

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — DATOS DEL TRABAJADOR
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title(" Retiro LSS-1997")
    st.caption("Calculadora actuarial bajo régimen 1997")

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

    sbc = st.number_input(
        "SBC mensual actual ($)",
        min_value=3_000.0,
        max_value=500_000.0,
        value=30_000.0,
        step=500.0,
        format="%.0f",
        help="Salario Base de Cotización mensual actual",
    )

    semanas = st.number_input(
        "Semanas cotizadas",
        min_value=0,
        max_value=3_000,
        value=0,
        step=1,
        help="Semanas ya cotizadas al IMSS (incluye periodos anteriores)",
    )

    cotizo_antes_97 = st.checkbox(
        "Cotizó antes del 1° julio 1997",
        value=False,
        help="Activa la opción del 4° Transitorio",
    )

    afore = st.selectbox("AFORE", AFORES, index=AFORES.index("XXI Banorte"))

    st.divider()
    st.subheader(" Retiro")

    edad_retiro = st.slider(
        "Edad de retiro deseada",
        min_value=55,
        max_value=75,
        value=65,
        step=1,
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
        inflacion = st.slider(
            "Inflación anual %",
            min_value=2.0, max_value=10.0,
            value=SUPUESTOS_DEFAULT["inflacion_anual"] * 100,
            step=0.1, format="%.1f%%",
        ) / 100

        crec_sbc = st.slider(
            "Crecimiento SBC anual %",
            min_value=2.0, max_value=12.0,
            value=SUPUESTOS_DEFAULT["crecimiento_sbc"] * 100,
            step=0.1, format="%.1f%%",
        ) / 100

        rendimiento_manual = st.checkbox("Especificar rendimiento manual")
        rendimiento_override = None
        comision_override    = None

        if rendimiento_manual:
            rendimiento_override = st.slider(
                "Rendimiento AFORE anual %",
                min_value=2.0, max_value=15.0, value=5.5, step=0.1, format="%.1f%%",
            ) / 100
            comision_override = st.slider(
                "Comisión AFORE anual %",
                min_value=0.1, max_value=2.0, value=0.54, step=0.01, format="%.2f%%",
            ) / 100

    actualizar_datos = st.button(
        " Actualizar datos de internet",
        use_container_width=True,
        help="Descarga UMA, rendimientos y comisiones actualizados",
    )


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


if actualizar_datos:
    st.cache_data.clear()
    st.success("Cache limpiado. Recalculando con datos actualizados...")

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

st.title(f" Proyección de Retiro — {t.nombre}")
st.caption(
    f"**{t.genero_label}** · {t.edad_actual} años · " f"AFORE: {t.afore} · Retiro en {t.anno_retiro} ({t.annos_para_retiro} años)"
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

if not cumple:
    sem_req = res_pension["pension_rcv"]["semanas_requeridas"]
    sem_falt = max(0, sem_req - semanas_tot)
    st.warning(
        f" Con la proyección actual **no cumple** los {sem_req:,} semanas requeridas " f"para retiro en {t.anno_retiro}. Faltan ~{sem_falt:,} semanas " f"({sem_falt//52:.1f} años de cotización adicional).",
        icon=None,
    )
elif fuente == "PMG":
    st.info(
        "ℹ Su saldo en el AFORE no es suficiente para superar la Pensión Mínima Garantizada. " "El Estado completará la diferencia. Se muestra la PMG como pensión final.",
        icon="ℹ",
    )
else:
    st.success(
        f" Cumple requisitos para pensión completa por saldo AFORE. ",
        icon=None,
    )


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

    # Banner explicativo sobre la métrica
    st.info(
        f" **Los valores se expresan en pesos de {ANIO_HOY}** (poder adquisitivo actual)",
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
        f""" <div style="text-align:center; padding:28px 0 20px 0;">
          <div style="font-size:0.85rem; color:#888; text-transform:uppercase;
                      letter-spacing:1.5px; margin-bottom:6px;">
            Pensión equivalente en salario de hoy
          </div>
          <div style="font-size:3.2rem; font-weight:800; color:{COLOR_PRIMARIO};
                      line-height:1.1;">
            ${_pension_equiv_hoy:,.0f}
            <span style="font-size:1.2rem; font-weight:400; color:#666;">/mes</span>
          </div>
          <div style="font-size:0.9rem; color:#888; margin-top:8px;">
            Tasa de reemplazo <strong>{_tasa_reemplazo_cus:.1%}</strong>
            aplicada al SBC actual de
            <strong>${sbc:,.0f}</strong>
          </div>
          <div style="font-size:0.8rem; color:#aaa; margin-top:4px;">
            Referencia intuitiva — si te jubilaras hoy con tu sueldo actual,
            recibirías este monto mensual
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
            color_discrete_sequence=["#1B4F72", "#2980B9", "#7FB3D3", "#AED6F1"],
            hole=0.4,
        )
        fig_pie.update_layout(
            showlegend=True,
            margin=dict(t=10, b=10, l=10, r=10),
            height=280,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

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
        height=300,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig_trans, use_container_width=True)


#  TAB 3: PROYECCIÓN SALDO 
with tab3:
    st.subheader("Proyección del Saldo AFORE año a año")

    detalle = res_saldo["detalle_anual"]
    df_det  = pd.DataFrame(detalle)

    if not df_det.empty:
        # Gráfica principal: saldo acumulado
        fig_saldo = go.Figure()
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
            height=380,
            margin=dict(t=40, b=40),
            hovermode="x unified",
        )
        st.plotly_chart(fig_saldo, use_container_width=True)

        # Gráfica: SBC proyectado
        fig_sbc = px.line(
            df_det, x="anio", y="sbc_mensual",
            title="SBC mensual proyectado",
            labels={"anio": "Año", "sbc_mensual": "SBC mensual ($)"},
            color_discrete_sequence=[COLOR_ACENTO],
        )
        fig_sbc.update_layout(height=250, margin=dict(t=40, b=30), yaxis_tickformat="$,.0f")
        st.plotly_chart(fig_sbc, use_container_width=True)

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
    st.subheader("Cálculo de Pensión")

    #  Método CUS (fórmula actuarial del Excel) 
    pension_cus = res_pension_excel["pension_mensual_pesos"]
    udi_hoy_val = res_pension_excel["udi_hoy"]

    st.markdown("###  Método Actuarial CUS")
    st.caption(
        "Fórmula bimestral en UDIs con parámetros CONSAR/CUS. ")
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
    color_cus = COLOR_ACENTO
    _estado_label = "con conyugue" if res_pension_excel["casado"] else "soltero/a"
    _conv_k_info  = (
        f" | Conv(k) = {res_pension_excel['conv_k']:.4f}  " f"(reduccion por conyuge: -{(1-res_pension_excel['ratio_casado'])*100:.1f}%)" if res_pension_excel["casado"] else "" )
    st.markdown(
        f""" <div style="background:{color_cus}22; border-left:5px solid {color_cus};
             padding:20px; border-radius:6px; margin:12px 0;">
          <div style="font-size:0.9rem; color:#444; text-transform:uppercase; letter-spacing:1px;">
            Pension CUS — {_estado_label} (pesos de {ANIO_HOY})
          </div>
          <div style="font-size:2.8rem; font-weight:bold; color:{COLOR_PRIMARIO};">
            ${pension_cus:,.2f} <span style="font-size:1rem;">/mes</span>
          </div>
          <div style="font-size:0.9rem; color:#666; margin-top:4px;">
            Tasa de reemplazo: {_tasa_reemplazo_cus:.1%} del ultimo salario real{_conv_k_info}
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
            st.info(
                f"PMG no aplica: {pmg.get('razon_no_aplica', 'no cumple requisitos')}",
                icon="ℹ",
            )

    if res_pension["deficit_saldo"] > 0:
        st.warning(
            f"El Estado aportaría ~${res_pension['deficit_saldo']:,.0f} adicionales " f"para financiar la PMG. Para autofinanciar la PMG se requeriría un saldo " f"de ${res_pension['saldo_requerido_pmg']:,.0f}.",
        )

    st.divider()
    st.subheader(" Calculadora de Meta de Pensión")
    st.caption(
        "¿Cuánto necesitas aportar voluntariamente cada mes para alcanzar " "una tasa de reemplazo objetivo (pensión / último salario)?" )

    col_meta1, col_meta2 = st.columns([1, 2])
    with col_meta1:
        tasa_meta = st.slider(
            "Tasa de reemplazo objetivo",
            min_value=10, max_value=100, value=30, step=5,
            format="%d%%",
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

    st.caption(f"Valores en pesos de {ANIO_HOY}")

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
        height=380,
        hovermode="x unified",
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig_esc, use_container_width=True)

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
# FOOTER
# 

st.divider()
st.caption(
    "**Calculadora de Retiro LSS-1997** · Datos: INEGI (UMA), Banxico (UDI), CONSAR (AFORE) · " f"Cache vigente: {'' if cache_esta_vigente() else ' actualizar'} · " " Esta herramienta es orientativa. Consulta a un asesor certificado para decisiones de retiro."
)

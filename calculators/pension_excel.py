"""
calculators/pension_excel.py

Metodologia exacta del Excel fuente (Dr. Francisco Garcia, UDLAP).
Trabaja en UDIs usando formula cerrada bimestral de la CUS.

Formulas:
  M2 = A_bi * FM2,  FM2 = ((1+q)^n - (1+i)^n) / (q - i)
  Pension soltero = Total * (1+a) / (b1 * ax_m * a1_12 * FACBI * FI)
  Pension casado  = Pension_soltero / ratio_CUS[genero]
    donde ratio_CUS ~1.36 (H) / ~1.35 (M)

Verificado para Owen Garcia (SBC=30k, retiro 65):
  Soltero ~42188/mes vs Excel 42667 (diff 1.1%)
  Casado  ~30985/mes vs Excel 30656 (diff 1.1%)
"""

import math
from datetime import date

from config import TASA_INTERES_TECNICO, SUPUESTOS_DEFAULT
from calculators.anualidades import get_ax
from calculators.aportaciones import calcular_aportaciones
from calculators.saldo_afore import get_densidad
from data_fetchers.udi import get_udi_hoy
import project_time

# ============================================================
# CONSTANTES CUS
# ============================================================

_B1    = 1.15
_FACBI = 1.0757672124703848
_FI    = 1.0371919843839832
_A     = 0.02

# Conv(k)/ax ratio por genero del titular (tabla Anualidades Contingentes)
# Derivado de la tabla del Excel, constante en edades 60-85.
_RATIO_CONV_K = {
    0: 1.3601,   # Hombre titular
    1: 1.3457,   # Mujer titular
}

_REND_BRUTO_EXCEL = 0.041483
_COMISION_EXCEL   = 0.0054
_INFLACION_EXCEL  = 0.054683
_REND_NETO_EXCEL  = _REND_BRUTO_EXCEL - _COMISION_EXCEL

_Q_BI_EXCEL = 0.010431139469391004


# ============================================================
# UTILIDADES ACTUARIALES
# ============================================================

def _an_12_cus(tasa_tecnica: float = TASA_INTERES_TECNICO) -> float:
    """a1(12) = (1-v)/(1-v^(1/12)) con v=1/(1+i). Para i=2.34%: 11.8737."""
    v = 1.0 / (1.0 + tasa_tecnica)
    return (1.0 - v) / (1.0 - v ** (1.0 / 12.0))


def _tasa_real_bimestral(rend_neto_anual: float, inflacion_anual: float) -> float:
    """Convierte tasas anuales a tasa real bimestral."""
    real_anual = (1.0 + rend_neto_anual) / (1.0 + inflacion_anual) - 1.0
    return (1.0 + real_anual) ** (1.0 / 6.0) - 1.0


# ============================================================
# CALCULO PRINCIPAL
# ============================================================

def calcular_pension_metodo_excel(
    sbc_mensual:        float,
    fecha_nacimiento:   date,
    edad_retiro:        int,
    genero:             int,
    semanas_previas:    int   = 0,
    saldo_previo_pesos: float = 0.0,
    rend_neto_anual:    object = None,
    inflacion_anual:    object = None,
    tasa_tecnica:       float = TASA_INTERES_TECNICO,
    casado:             int   = 0,
    genero_conyuge:     int   = 1,
    edad_conyuge:       int   = 0,
) -> dict:
    """
    Calcula la pension con metodologia exacta del Excel.

    Para el caso casado:
        pension_casado = pension_soltero / ratio_CUS[genero]
        ratio_CUS ~1.36 para H, ~1.35 para M (constante segun tabla Excel)

    Args:
        sbc_mensual:        SBC actual en pesos
        fecha_nacimiento:   Fecha de nacimiento
        edad_retiro:        Edad al retiro (55-75)
        genero:             0=Hombre, 1=Mujer
        casado:             1 si tiene conyuge, 0 si soltero
        genero_conyuge:     0=H, 1=M (solo afecta ratio si se actualiza tabla)
        edad_conyuge:       Edad actual del conyuge (no afecta Conv_k en formula CUS)
        saldo_previo_pesos: Saldo actual AFORE en pesos
        rend_neto_anual:    Rendimiento neto (None = default Excel)
        inflacion_anual:    Inflacion (None = default Excel)
        tasa_tecnica:       Tasa tecnica actuarial (default 2.34%)
    """
    anio_hoy    = project_time.current_year()
    anio_retiro = fecha_nacimiento.year + edad_retiro
    annos_work  = max(1, anio_retiro - anio_hoy)

    try:
        udi_hoy = get_udi_hoy()
    except Exception:
        udi_hoy = 8.672954

    rend_neto = rend_neto_anual if rend_neto_anual is not None else _REND_NETO_EXCEL
    inflacion = inflacion_anual if inflacion_anual is not None else _INFLACION_EXCEL

    i_bi = _tasa_real_bimestral(rend_neto, inflacion)
    q_bi = _Q_BI_EXCEL

    edad_actual = anio_hoy - fecha_nacimiento.year
    densidad    = get_densidad(int((edad_actual + edad_retiro) / 2))
    n_bi        = annos_work * 6.0 * densidad

    if abs(q_bi - i_bi) < 1e-12:
        FM2 = n_bi
    else:
        FM2 = ((1.0 + q_bi) ** n_bi - (1.0 + i_bi) ** n_bi) / (q_bi - i_bi)

    anios_ref   = min(7, annos_work)
    q_anual_nom = (1.0 + q_bi) ** 6 - 1.0
    sbc_ref     = sbc_mensual * (1.0 + q_anual_nom) ** anios_ref
    aport_bi    = sbc_ref * 0.15 * 2.0 / udi_hoy

    M2 = aport_bi * FM2

    M1    = 0.0
    sbc_t = sbc_mensual
    for anio in range(anio_hoy, min(2030, anio_retiro)):
        ap   = calcular_aportaciones(sbc_t, anio)
        M1  += ap["aportacion_total"] * 12.0 / udi_hoy
        sbc_t *= 1.0 + q_anual_nom

    M3 = saldo_previo_pesos / udi_hoy

    total_udi = M1 + M2 + M3

    ax_m  = get_ax(genero, edad_retiro, tasa_tecnica, mensual=True)
    an_12 = _an_12_cus(tasa_tecnica)

    # Pension soltero
    pension_udi = (total_udi * (1.0 + _A)) / (
        _B1 * ax_m * an_12 * _FACBI * _FI
    )

    # Ajuste por conyuge
    ratio_casado = 1.0
    conv_k       = ax_m

    if casado:
        ratio_conv_k = _RATIO_CONV_K.get(genero, 1.3601)
        conv_k       = ax_m * ratio_conv_k
        ratio_casado = 1.0 / ratio_conv_k   # ~0.735
        pension_udi *= ratio_casado

    pension_pesos = pension_udi * udi_hoy

    return {
        "pension_mensual_pesos": pension_pesos,
        "pension_mensual_udis":  pension_udi,
        "total_udis":            total_udi,
        "m1_udis":               M1,
        "m2_udis":               M2,
        "m3_udis":               M3,
        "udi_hoy":               udi_hoy,
        "ax_m":                  ax_m,
        "an_12":                 an_12,
        "n_bi":                  n_bi,
        "FM2":                   FM2,
        "conv_k":                conv_k,
        "ratio_casado":          ratio_casado,
        "casado":                bool(casado),
        "parametros": {
            "i_bi":      i_bi,
            "q_bi":      q_bi,
            "inflacion": inflacion,
            "rend_neto": rend_neto,
            "densidad":  densidad,
            "b1": _B1, "FACBI": _FACBI, "FI": _FI, "a": _A,
        },
    }


def calcular_ultimo_salario_real(
    sbc_mensual:      float,
    annos_trabajo:    int,
    crec_sbc_nominal: float,
    inflacion_anual:  float,
) -> float:
    """
    Proyecta el ultimo salario en pesos de hoy.
    ultimo_salario = sbc * (1 + q_real)^anos
    donde q_real = (1 + crec_nom) / (1 + inflacion) - 1
    """
    q_real = (1.0 + crec_sbc_nominal) / (1.0 + inflacion_anual) - 1.0
    return sbc_mensual * (1.0 + q_real) ** annos_trabajo


def calcular_aportacion_para_tasa(
    tasa_objetivo:    float,
    sbc_mensual:      float,
    fecha_nacimiento: date,
    edad_retiro:      int,
    genero:           int,
    crec_sbc_nominal: float = 0.062,
    inflacion_anual:  float = 0.035,
    casado:           int   = 0,
    tasa_tecnica:     float = TASA_INTERES_TECNICO,
) -> dict:
    """
    Funcion inversa: cuanto hay que aportar extra mensualmente para alcanzar
    la tasa de reemplazo objetivo (pension / ultimo_salario).

    Returns dict con aportacion_extra_mensual_pesos, aportacion_extra_pct_sbc,
    pension_objetivo_pesos, tasa_actual, ultimo_salario_pesos, factible,
    pension_actual, delta_udis_necesario.
    """
    annos = max(1, fecha_nacimiento.year + edad_retiro - project_time.current_year())

    r_base = calcular_pension_metodo_excel(
        sbc_mensual      = sbc_mensual,
        fecha_nacimiento = fecha_nacimiento,
        edad_retiro      = edad_retiro,
        genero           = genero,
        casado           = casado,
        tasa_tecnica     = tasa_tecnica,
    )

    udi_hoy      = r_base["udi_hoy"]
    ax_m         = r_base["ax_m"]
    an_12        = r_base["an_12"]
    FM2          = r_base["FM2"]
    total_actual = r_base["total_udis"]
    ratio_casado = r_base["ratio_casado"]
    pension_base = r_base["pension_mensual_pesos"]

    sbc_ultimo = calcular_ultimo_salario_real(
        sbc_mensual, annos, crec_sbc_nominal, inflacion_anual
    )
    pension_obj_pesos = sbc_ultimo * tasa_objetivo
    tasa_actual = pension_base / sbc_ultimo if sbc_ultimo > 0 else 0.0

    if pension_base >= pension_obj_pesos:
        return {
            "aportacion_extra_mensual_pesos": 0.0,
            "aportacion_extra_pct_sbc":       0.0,
            "pension_objetivo_pesos":         pension_obj_pesos,
            "tasa_actual":                    tasa_actual,
            "ultimo_salario_pesos":           sbc_ultimo,
            "factible":                       True,
            "pension_actual":                 pension_base,
            "delta_udis_necesario":           0.0,
        }

    # UDIs totales necesarios para la pension objetivo
    pension_obj_udi_soltero = (pension_obj_pesos / udi_hoy) / ratio_casado
    den = _B1 * ax_m * an_12 * _FACBI * _FI
    total_necesario = pension_obj_udi_soltero * den / (1.0 + _A)
    delta_udi = max(0.0, total_necesario - total_actual)

    aport_bi_extra_udi = delta_udi / FM2 if FM2 > 0 else 0.0
    aport_mensual_extra = aport_bi_extra_udi * udi_hoy / 2.0
    pct_sbc = aport_mensual_extra / sbc_mensual if sbc_mensual > 0 else 0.0

    return {
        "aportacion_extra_mensual_pesos": aport_mensual_extra,
        "aportacion_extra_pct_sbc":       pct_sbc,
        "pension_objetivo_pesos":         pension_obj_pesos,
        "tasa_actual":                    tasa_actual,
        "ultimo_salario_pesos":           sbc_ultimo,
        "factible":                       False,
        "pension_actual":                 pension_base,
        "delta_udis_necesario":           delta_udi,
    }


def calcular_ultimo_salario_real(
    sbc_mensual,
    annos_trabajo,
    crec_sbc_nominal,
    inflacion_anual,
):
    q_real = (1.0 + crec_sbc_nominal) / (1.0 + inflacion_anual) - 1.0
    return sbc_mensual * (1.0 + q_real) ** annos_trabajo


def calcular_aportacion_para_tasa(
    tasa_objetivo,
    sbc_mensual,
    fecha_nacimiento,
    edad_retiro,
    genero,
    crec_sbc_nominal=0.062,
    inflacion_anual=0.035,
    casado=0,
    tasa_tecnica=TASA_INTERES_TECNICO,
):
    annos = max(1, fecha_nacimiento.year + edad_retiro - project_time.current_year())

    r_base = calcular_pension_metodo_excel(
        sbc_mensual=sbc_mensual,
        fecha_nacimiento=fecha_nacimiento,
        edad_retiro=edad_retiro,
        genero=genero,
        casado=casado,
        tasa_tecnica=tasa_tecnica,
    )

    udi_hoy      = r_base["udi_hoy"]
    ax_m         = r_base["ax_m"]
    an_12        = r_base["an_12"]
    FM2          = r_base["FM2"]
    total_actual = r_base["total_udis"]
    ratio_casado = r_base["ratio_casado"]
    pension_base = r_base["pension_mensual_pesos"]

    sbc_ultimo        = calcular_ultimo_salario_real(sbc_mensual, annos, crec_sbc_nominal, inflacion_anual)
    pension_obj_pesos = sbc_ultimo * tasa_objetivo
    tasa_actual       = pension_base / sbc_ultimo if sbc_ultimo > 0 else 0.0

    if pension_base >= pension_obj_pesos:
        return {
            "aportacion_extra_mensual_pesos": 0.0,
            "aportacion_extra_pct_sbc":       0.0,
            "pension_objetivo_pesos":         pension_obj_pesos,
            "tasa_actual":                    tasa_actual,
            "ultimo_salario_pesos":           sbc_ultimo,
            "factible":                       True,
            "pension_actual":                 pension_base,
            "delta_udis_necesario":           0.0,
        }

    pension_obj_udi_soltero = (pension_obj_pesos / udi_hoy) / (ratio_casado if ratio_casado > 0 else 1.0)
    den           = _B1 * ax_m * an_12 * _FACBI * _FI
    total_nec     = pension_obj_udi_soltero * den / (1.0 + _A)
    delta_udi     = max(0.0, total_nec - total_actual)
    aport_bi_udi  = delta_udi / FM2 if FM2 > 0 else 0.0
    aport_mensual = aport_bi_udi * udi_hoy / 2.0
    pct_sbc       = aport_mensual / sbc_mensual if sbc_mensual > 0 else 0.0

    return {
        "aportacion_extra_mensual_pesos": aport_mensual,
        "aportacion_extra_pct_sbc":       pct_sbc,
        "pension_objetivo_pesos":         pension_obj_pesos,
        "tasa_actual":                    tasa_actual,
        "ultimo_salario_pesos":           sbc_ultimo,
        "factible":                       False,
        "pension_actual":                 pension_base,
        "delta_udis_necesario":           delta_udi,
    }


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def ultimo_salario_real(sbc_mensual: float, annos_trabajo: int) -> float:
    """
    Proyecta el SBC al momento del retiro en PESOS DE HOY.
    Usa la tasa de crecimiento real del CUS (q_anual = 6.42%).

    Pension / ultimo_salario_real = tasa de reemplazo correcta.
    """
    q_anual = (1.0 + _Q_BI_EXCEL) ** 6 - 1.0
    return sbc_mensual * (1.0 + q_anual) ** annos_trabajo


def calcular_aportacion_extra_para_tasa(
    sbc_mensual:        float,
    fecha_nacimiento:   date,
    edad_retiro:        int,
    genero:             int,
    tasa_objetivo:      float,
    casado:             int   = 0,
    rend_neto_anual:    object = None,
    inflacion_anual:    object = None,
    tasa_tecnica:       float = TASA_INTERES_TECNICO,
) -> dict:
    """
    Funcion inversa CUS: calcula la aportacion mensual ADICIONAL necesaria
    para alcanzar una tasa de reemplazo objetivo.

    tasa_objetivo = pension_deseada / SBC_retiro_real

    Algoritmo:
      1. Calcular pension_actual y SBC_retiro_real
      2. pension_necesaria = tasa_objetivo * SBC_retiro_real
      3. delta_UDIs = (pension_necesaria - pension_actual) en UDIs
      4. UDIs adicionales necesarios / FM2 / (2 meses/bimestre) / densidad
         = aportacion mensual extra en UDIs
      5. Convertir a pesos con UDI hoy

    Returns dict con:
        aportacion_extra_pesos: aportacion mensual adicional en pesos
        pension_actual:         pension actual en pesos de hoy
        pension_objetivo:       pension objetivo en pesos de hoy
        sbc_retiro_real:        SBC al retiro en pesos de hoy
        tasa_actual:            tasa de reemplazo actual
        tasa_objetivo:          tasa de reemplazo objetivo
        es_alcanzable:          si la meta es fisicamente posible
    """
    anio_hoy    = project_time.current_year()
    anio_retiro = fecha_nacimiento.year + edad_retiro
    annos_work  = max(1, anio_retiro - anio_hoy)

    try:
        udi_hoy = get_udi_hoy()
    except Exception:
        udi_hoy = 8.672954

    rend_neto = rend_neto_anual if rend_neto_anual is not None else _REND_NETO_EXCEL
    inflacion = inflacion_anual if inflacion_anual is not None else _INFLACION_EXCEL

    i_bi = _tasa_real_bimestral(rend_neto, inflacion)
    q_bi = _Q_BI_EXCEL

    # Densidad, n y FM2 (mismos que en calcular_pension_metodo_excel)
    edad_actual = anio_hoy - fecha_nacimiento.year
    densidad    = get_densidad(int((edad_actual + edad_retiro) / 2))
    n_bi        = annos_work * 6.0 * densidad

    if abs(q_bi - i_bi) < 1e-12:
        FM2 = n_bi
    else:
        FM2 = ((1.0 + q_bi) ** n_bi - (1.0 + i_bi) ** n_bi) / (q_bi - i_bi)

    # Pension y salario actuales
    r_actual = calcular_pension_metodo_excel(
        sbc_mensual=sbc_mensual, fecha_nacimiento=fecha_nacimiento,
        edad_retiro=edad_retiro, genero=genero, casado=casado,
        rend_neto_anual=rend_neto_anual, inflacion_anual=inflacion_anual,
        tasa_tecnica=tasa_tecnica,
    )

    pension_actual = r_actual["pension_mensual_pesos"]
    sbc_retiro_real = ultimo_salario_real(sbc_mensual, annos_work)
    tasa_actual = pension_actual / sbc_retiro_real if sbc_retiro_real > 0 else 0

    # Pension objetivo
    pension_objetivo_pesos = tasa_objetivo * sbc_retiro_real
    delta_pesos = max(0.0, pension_objetivo_pesos - pension_actual)

    # Factores actuariales para convertir pension -> saldo
    ax_m  = get_ax(genero, edad_retiro, tasa_tecnica, mensual=True)
    an_12 = _an_12_cus(tasa_tecnica)

    ratio_casado = 1.0 / _RATIO_CONV_K.get(genero, 1.3601) if casado else 1.0

    # Saldo extra en UDIs necesario:
    # delta_pension_UDIs = delta_pesos / udi_hoy
    # Saldo_extra_UDIs = delta_pension_UDIs * (b1 * ax * a1_12 * FACBI * FI) / (1+a) / ratio_casado
    delta_pen_udi = delta_pesos / udi_hoy
    saldo_extra_udi = (
        delta_pen_udi * _B1 * ax_m * an_12 * _FACBI * _FI
        / (1.0 + _A)
        / (ratio_casado if ratio_casado > 0 else 1.0)
    )

    # Convertir saldo_extra_udi a aportacion mensual extra:
    # saldo_extra = aport_extra_bi * FM2  => aport_extra_bi = saldo_extra / FM2
    # aport_extra_bi = aport_mensual_extra * 2 / udi_hoy (dos meses por bimestre)
    # => aport_mensual_extra = aport_extra_bi * udi_hoy / 2
    aport_bi_extra_udi = saldo_extra_udi / FM2 if FM2 > 0 else 0.0
    aportacion_extra_pesos = aport_bi_extra_udi * udi_hoy / 2.0

    # Porcentaje del SBC actual
    pct_sbc = aportacion_extra_pesos / sbc_mensual if sbc_mensual > 0 else 0.0

    return {
        "aportacion_extra_pesos": aportacion_extra_pesos,
        "pct_sbc":                pct_sbc,
        "pension_actual":         pension_actual,
        "pension_objetivo":       pension_objetivo_pesos,
        "sbc_retiro_real":        sbc_retiro_real,
        "tasa_actual":            tasa_actual,
        "tasa_objetivo":          tasa_objetivo,
        "delta_saldo_udi":        saldo_extra_udi,
        "FM2":                    FM2,
        "es_alcanzable":          delta_pesos > 0,
        "ya_cumple":              delta_pesos <= 0,
    }

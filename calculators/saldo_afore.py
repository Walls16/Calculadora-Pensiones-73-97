"""
calculators/saldo_afore.py
Proyección del saldo acumulado en el AFORE año a año hasta la edad de retiro.

Lógica año a año:
  saldo_fin = (saldo_ini + aportaciones_anuales) × (1 + rendimiento_neto)

donde:
  rendimiento_neto = rendimiento_bruto - comision
  aportaciones_anuales = aportacion_mensual × 12 × densidad_cotizacion

La densidad de cotización refleja que no todos los meses del año se cotiza
(desempleo, trabajo informal, etc.) — se toma de la tabla del Excel fuente.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    FACTOR_SALARIO_MAXIMO_COTIZABLE,
    get_siefore,
    SUPUESTOS_DEFAULT,
)
from data_fetchers.uma              import get_uma_mensual
from data_fetchers.afore_rendimientos import get_rendimiento_afore, get_rendimiento_promedio_siefore
from data_fetchers.afore_comisiones   import get_comision_afore
from calculators.aportaciones         import (
    aportacion_mensual_total,
    proyectar_sbc,
    salario_cotizable,
)


# ─────────────────────────────────────────────────────────────────────────────
# DENSIDAD DE COTIZACIÓN POR EDAD (del Excel fuente — hoja Densidad Cotización)
# ─────────────────────────────────────────────────────────────────────────────
_DENSIDAD_COTIZACION: dict[int, float] = {
    15: 0.799, 16: 0.827, 17: 0.838, 18: 0.847, 19: 0.854,
    20: 0.860, 21: 0.865, 22: 0.870, 23: 0.875, 24: 0.879,
    25: 0.883, 26: 0.887, 27: 0.890, 28: 0.893, 29: 0.896,
    30: 0.899, 31: 0.902, 32: 0.905, 33: 0.907, 34: 0.910,
    35: 0.912, 36: 0.914, 37: 0.916, 38: 0.919, 39: 0.920,
    40: 0.922, 41: 0.924, 42: 0.926, 43: 0.927, 44: 0.929,
    45: 0.930, 46: 0.932, 47: 0.933, 48: 0.934, 49: 0.935,
    50: 0.936, 51: 0.937, 52: 0.938, 53: 0.939, 54: 0.940,
    55: 0.941, 56: 0.942, 57: 0.943, 58: 0.944, 59: 0.945,
    60: 0.946, 61: 0.947, 62: 0.948, 63: 0.949, 64: 0.950,
}

def get_densidad(edad: int) -> float:
    """Retorna la densidad de cotización para una edad dada."""
    if edad in _DENSIDAD_COTIZACION:
        return _DENSIDAD_COTIZACION[edad]
    if edad < 15:
        return 0.80
    # Para edades > 64, usar el último valor disponible
    return 0.950


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def proyectar_saldo(
    sbc_mensual:        float,
    anio_inicio:        int,
    anio_retiro:        int,
    edad_inicio:        int,
    anno_nacimiento:    int,
    afore:              str  = "XXI Banorte",
    saldo_inicial:      float = 0.0,
    semanas_previas:    int   = 0,
    tasa_crecimiento_sbc: float = SUPUESTOS_DEFAULT["crecimiento_sbc"],
    rendimiento_override: float = None,
    comision_override:    float = None,
    usar_densidad:        bool  = True,
) -> dict:
    """
    Proyecta el saldo del AFORE año a año desde anio_inicio hasta anio_retiro.

    Args:
        sbc_mensual:           SBC mensual en pesos del anio_inicio
        anio_inicio:           Año en que inicia la proyección
        anio_retiro:           Año en que se retira el trabajador
        edad_inicio:           Edad del trabajador en anio_inicio
        anno_nacimiento:       Año de nacimiento (para determinar SIEFORE)
        afore:                 Nombre de la AFORE
        saldo_inicial:         Saldo acumulado al inicio (pesos del anio_inicio)
        semanas_previas:       Semanas ya cotizadas al inicio
        tasa_crecimiento_sbc:  Tasa anual de crecimiento del SBC
        rendimiento_override:  Si se da, usa esta tasa fija en vez de CONSAR
        comision_override:     Si se da, usa esta comisión fija en vez de CONSAR
        usar_densidad:         Si True, aplica factor de densidad de cotización

    Returns:
        {
          "saldo_final":        float,   # Saldo acumulado al retiro (pesos corrientes)
          "semanas_totales":    int,     # Semanas cotizadas al retiro
          "detalle_anual":      list[dict],  # Proyección año a año
          "supuestos":          dict,    # Parámetros usados
        }
    """
    if anio_retiro <= anio_inicio:
        return {
            "saldo_final":     saldo_inicial,
            "semanas_totales": semanas_previas,
            "detalle_anual":   [],
            "supuestos":       {},
        }

    saldo_actual   = saldo_inicial
    semanas_total  = semanas_previas
    detalle_anual  = []

    for anio in range(anio_inicio, anio_retiro):
        edad = edad_inicio + (anio - anio_inicio)

        # ── SBC proyectado en pesos corrientes del año ─────────────────────
        sbc_anio = proyectar_sbc(sbc_mensual, anio_inicio, anio, tasa_crecimiento_sbc)
        sbc_cot  = salario_cotizable(sbc_anio, anio)

        # ── Rendimiento neto ────────────────────────────────────────────────
        siefore    = get_siefore(anno_nacimiento)
        rend_bruto = (
            rendimiento_override
            if rendimiento_override is not None
            else get_rendimiento_afore(afore, siefore)
        )
        comision = (
            comision_override
            if comision_override is not None
            else get_comision_afore(afore, anio)
        )
        rend_neto = rend_bruto - comision

        # ── Aportaciones anuales ────────────────────────────────────────────
        aport_mes    = aportacion_mensual_total(sbc_cot, anio)
        densidad     = get_densidad(edad) if usar_densidad else 1.0
        aport_anual  = aport_mes * 12 * densidad

        # Semanas cotizadas: 52 semanas × densidad
        semanas_anio  = int(52 * densidad)
        semanas_total += semanas_anio

        # ── Fórmula de acumulación ──────────────────────────────────────────
        # (saldo + aportaciones al inicio del año) × (1 + rend_neto)
        # Simplificación: aportaciones entran al inicio del período
        saldo_fin_anio = (saldo_actual + aport_anual) * (1 + rend_neto)

        # ── Guardar detalle ─────────────────────────────────────────────────
        detalle_anual.append({
            "anio":             anio,
            "edad":             edad,
            "sbc_mensual":      sbc_anio,
            "sbc_cotizable":    sbc_cot,
            "saldo_inicio":     saldo_actual,
            "aportacion_anual": aport_anual,
            "rendimiento_bruto":rend_bruto,
            "comision":         comision,
            "rendimiento_neto": rend_neto,
            "densidad":         densidad,
            "semanas_anio":     semanas_anio,
            "semanas_acum":     semanas_total,
            "saldo_fin":        saldo_fin_anio,
            "siefore":          siefore,
        })

        saldo_actual = saldo_fin_anio

    return {
        "saldo_final":     saldo_actual,
        "semanas_totales": semanas_total,
        "detalle_anual":   detalle_anual,
        "supuestos": {
            "afore":                afore,
            "tasa_crecimiento_sbc": tasa_crecimiento_sbc,
            "rendimiento_override": rendimiento_override,
            "comision_override":    comision_override,
            "usar_densidad":        usar_densidad,
        },
    }


def proyectar_saldo_desde_trabajador(trabajador, uma_override: float = None) -> dict:
    """
    Wrapper conveniente que toma un objeto Trabajador y llama a proyectar_saldo.

    Args:
        trabajador:    Instancia de models.Trabajador
        uma_override:  Si se da, sobreescribe el valor de UMA (para escenarios)
    """
    from datetime import date

    anio_actual = date.today().year

    return proyectar_saldo(
        sbc_mensual          = trabajador.sbc_mensual,
        anio_inicio          = anio_actual,
        anio_retiro          = trabajador.anno_retiro,
        edad_inicio          = trabajador.edad_actual,
        anno_nacimiento      = trabajador.anno_nacimiento,
        afore                = trabajador.afore,
        saldo_inicial        = 0.0,
        semanas_previas      = trabajador.semanas_cotizadas,
        tasa_crecimiento_sbc = trabajador.crecimiento_sbc,
        rendimiento_override = trabajador.rendimiento_afore,
        comision_override    = trabajador.comision_afore,
        usar_densidad        = True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISIS DE ESCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

def proyectar_escenarios(
    sbc_mensual:     float,
    anio_inicio:     int,
    anio_retiro:     int,
    edad_inicio:     int,
    anno_nacimiento: int,
    afore:           str,
    saldo_inicial:   float = 0.0,
    semanas_previas: int   = 0,
) -> dict:
    """
    Proyecta tres escenarios: pesimista, base y optimista.

    Returns:
        {
          "pesimista": {...},
          "base":      {...},
          "optimista": {...},
        }
    """
    siefore = get_siefore(anno_nacimiento)

    # Obtener rango de rendimientos
    from data_fetchers.afore_rendimientos import (
        fetch_rendimientos, _FALLBACK_RENDIMIENTOS
    )
    stats = _FALLBACK_RENDIMIENTOS.get(siefore, {})
    rend_min  = stats.get("minimo",   0.045)
    rend_base = stats.get("promedio", 0.055)
    rend_max  = stats.get("maximo",   0.065)

    com_base = get_comision_afore(afore)

    args = dict(
        sbc_mensual     = sbc_mensual,
        anio_inicio     = anio_inicio,
        anio_retiro     = anio_retiro,
        edad_inicio     = edad_inicio,
        anno_nacimiento = anno_nacimiento,
        afore           = afore,
        saldo_inicial   = saldo_inicial,
        semanas_previas = semanas_previas,
    )

    return {
        "pesimista": proyectar_saldo(
            **args,
            rendimiento_override = rend_min,
            comision_override    = com_base,
            tasa_crecimiento_sbc = 0.040,  # crecimiento salarial conservador
        ),
        "base": proyectar_saldo(
            **args,
            rendimiento_override = rend_base,
            comision_override    = com_base,
        ),
        "optimista": proyectar_saldo(
            **args,
            rendimiento_override = rend_max,
            comision_override    = com_base * 0.9,  # asumir ligera bajada de comisión
            tasa_crecimiento_sbc = 0.080,  # crecimiento salarial optimista
        ),
    }

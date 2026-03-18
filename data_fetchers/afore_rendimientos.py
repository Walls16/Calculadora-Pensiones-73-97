"""
data_fetchers/afore_rendimientos.py
Descarga los rendimientos históricos de las SIEFOREs desde CONSAR.
Fuente: https://www.consar.gob.mx/gobmx/aplicativo/siset/tdf/FondosGeneracionales.aspx

CONSAR publica directamente un archivo Excel descargable con los rendimientos
a 5 años de todas las AFOREs por generación (SB0, SB55-59, SB60-64, etc.)

Estructura del cache (afore_rendimientos.csv):
  siefore,afore,fecha,rendimiento
  SB0,Azteca,2024-12-01,0.0611
  SB0,Citibanamex,2024-12-01,0.0468
  ...
"""

import io
import logging
import os
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CACHE_AFORE_REND, URL_CONSAR_RENDIMIENTOS, AFORES

log = logging.getLogger(__name__)

# Mapeo año_nacimiento → columna SIEFORE en el Excel de CONSAR
_SIEFORE_COLS = {
    "SB0":     1950,   # Generación 1950 o anterior (fondo conservador)
    "SB55-59": 1955,
    "SB60-64": 1960,
    "SB67-79": 1967,
    "SB90":    1990,   # Generación 1990+ (fondo más agresivo)
}

# Rendimientos fallback (promedio ponderado CONSAR, últimos 5 años — del Excel fuente)
_FALLBACK_RENDIMIENTOS = {
    "SB0":     {"promedio": 0.05548, "minimo": 0.04986, "maximo": 0.06240},
    "SB55-59": {"promedio": 0.05883, "minimo": 0.04995, "maximo": 0.06863},
    "SB60-64": {"promedio": 0.06370, "minimo": 0.04881, "maximo": 0.07936},
    "SB67-79": {"promedio": 0.07100, "minimo": 0.05200, "maximo": 0.09100},
    "SB90":    {"promedio": 0.07800, "minimo": 0.05500, "maximo": 0.10200},
}

# Rendimientos por AFORE — promedio ponderado CONSAR (SB0, del Excel fuente)
_FALLBACK_POR_AFORE = {
    "Azteca":        0.0611,
    "Citibanamex":   0.0468,
    "Coppel":        0.0612,
    "Inbursa":       0.0610,
    "Invercap":      0.0576,
    "PensionISSSTE": 0.0607,
    "Principal":     0.0549,
    "Profuturo GNP": 0.0472,
    "SURA":          0.0561,
    "XXI Banorte":   0.0555,
}


# ─────────────────────────────────────────────────────────────────────────────
# DESCARGA CONSAR
# ─────────────────────────────────────────────────────────────────────────────

def _descargar_excel_consar() -> pd.DataFrame:
    """
    Descarga el Excel de rendimientos CONSAR y lo retorna como DataFrame limpio.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.consar.gob.mx/",
        "Accept": "application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    resp = requests.get(URL_CONSAR_RENDIMIENTOS, headers=headers, timeout=30)
    resp.raise_for_status()

    # Leer el Excel desde bytes en memoria
    excel_data = io.BytesIO(resp.content)
    df_raw = pd.read_excel(excel_data, header=None)

    return df_raw


def _parsear_excel_consar(df_raw: pd.DataFrame) -> list[dict]:
    """
    Parsea el DataFrame crudo del Excel de CONSAR.
    Estructura esperada (basada en el Excel fuente analizado):
      - Fila 0: título
      - Fila 2: encabezados de AFOREs (col 0 = concepto, col 1 = año, cols 2+ = fechas)
      - Filas 5+: SB0 promedio ponderado, luego AFOREs individuales, luego siguiente SB

    Retorna lista de dicts:
      [{"siefore": "SB0", "afore": "Azteca", "fecha": "2024-12-01", "rendimiento": 0.0611}, ...]
    """
    registros = []

    # Identificar filas de inicio de cada SIEFORE
    # Buscamos filas donde col[1] contiene un año de nacimiento (1950, 1955, 1960...)
    siefore_filas: dict[str, int] = {}
    for idx, row in df_raw.iterrows():
        val = row.iloc[1] if len(row) > 1 else None
        if isinstance(val, (int, float)) and val in _SIEFORE_COLS.values():
            anio = int(val)
            siefore = [k for k, v in _SIEFORE_COLS.items() if v == anio]
            if siefore:
                siefore_filas[siefore[0]] = idx

    if not siefore_filas:
        raise ValueError("No se identificaron bloques de SIEFORE en el Excel de CONSAR.")

    # Obtener fila de fechas (encabezados de columna con fechas)
    fila_fechas = 4  # fila 4 (0-indexed) contiene las fechas en el Excel de CONSAR
    fechas_row = df_raw.iloc[fila_fechas]
    fechas = []
    for val in fechas_row.iloc[2:]:
        if pd.isna(val):
            fechas.append(None)
            continue
        if hasattr(val, "strftime"):
            fechas.append(val.strftime("%Y-%m-%d"))
        else:
            try:
                fechas.append(pd.to_datetime(val).strftime("%Y-%m-%d"))
            except Exception:
                fechas.append(None)

    # Parsear cada bloque de SIEFORE
    siefores_ordenadas = sorted(siefore_filas.items(), key=lambda x: x[1])

    for i, (siefore_nombre, fila_inicio) in enumerate(siefores_ordenadas):
        # Determinar hasta qué fila llega este bloque
        if i + 1 < len(siefores_ordenadas):
            fila_fin = siefores_ordenadas[i + 1][1]
        else:
            fila_fin = len(df_raw)

        # Recorrer filas del bloque
        for fila_idx in range(fila_inicio, fila_fin):
            row = df_raw.iloc[fila_idx]
            concepto = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else ""

            # Determinar nombre de AFORE
            if "Promedio Ponderado" in concepto or "promedio" in concepto.lower():
                afore_nombre = "Promedio Ponderado"
            else:
                # Buscar el nombre de AFORE más cercano en la columna concepto
                afore_nombre = concepto.strip()
                if not afore_nombre or afore_nombre == "nan":
                    continue

            # Extraer rendimientos por fecha
            for j, fecha in enumerate(fechas):
                if fecha is None:
                    continue
                col_idx = j + 2  # primeras 2 cols son concepto y año
                if col_idx >= len(row):
                    break
                val = row.iloc[col_idx]
                if pd.isna(val):
                    continue
                try:
                    rendimiento = float(val)
                    if 0 < rendimiento < 1:  # Sanity check: rendimiento entre 0% y 100%
                        registros.append({
                            "siefore":     siefore_nombre,
                            "afore":       afore_nombre,
                            "fecha":       fecha,
                            "rendimiento": rendimiento,
                        })
                except (ValueError, TypeError):
                    continue

    return registros


# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────

def _leer_cache() -> Optional[pd.DataFrame]:
    if not CACHE_AFORE_REND.exists():
        return None
    try:
        df = pd.read_csv(CACHE_AFORE_REND)
        log.info("Cache rendimientos cargado: %d registros", len(df))
        return df
    except Exception as e:
        log.warning("Error leyendo cache rendimientos: %s", e)
        return None


def _guardar_cache(registros: list[dict]) -> None:
    try:
        df = pd.DataFrame(registros)
        df.to_csv(CACHE_AFORE_REND, index=False)
        log.info("Cache rendimientos guardado: %d registros", len(df))
    except Exception as e:
        log.error("No se pudo guardar cache rendimientos: %s", e)


def _cache_vigente(max_dias: int = 35) -> bool:
    if not CACHE_AFORE_REND.exists():
        return False
    dias = (date.today() - date.fromtimestamp(CACHE_AFORE_REND.stat().st_mtime)).days
    return dias <= max_dias


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def fetch_rendimientos(forzar_actualizacion: bool = False) -> pd.DataFrame:
    """
    Obtiene los rendimientos históricos de todas las SIEFOREs y AFOREs.

    Returns:
        DataFrame con columnas: siefore, afore, fecha, rendimiento
    """
    if not forzar_actualizacion and _cache_vigente():
        df = _leer_cache()
        if df is not None:
            return df

    try:
        df_raw = _descargar_excel_consar()
        registros = _parsear_excel_consar(df_raw)
        if registros:
            _guardar_cache(registros)
            return pd.DataFrame(registros)
        else:
            raise ValueError("Sin registros parseados del Excel CONSAR.")
    except Exception as e:
        log.warning("No se pudo descargar rendimientos CONSAR (%s). Usando fallback.", e)

    # Fallback: construir DataFrame desde los valores hardcoded
    return _fallback_dataframe()


def get_rendimiento_afore(
    afore: str,
    siefore: str = "SB0",
    metodo: str = "promedio_5y",
) -> float:
    """
    Retorna el rendimiento para una AFORE y SIEFORE específicas.

    Args:
        afore:   Nombre de la AFORE (ej: "XXI Banorte")
        siefore: Código de SIEFORE (ej: "SB0", "SB90")
        metodo:  "promedio_5y" (promedio últimos 5 años) o "ultimo" (último dato)

    Returns:
        Tasa de rendimiento anual como float (ej: 0.0555 = 5.55%)
    """
    df = fetch_rendimientos()

    subset = df[(df["siefore"] == siefore) & (df["afore"] == afore)]

    if subset.empty:
        # Intentar con nombre parcial
        mask = df["afore"].str.contains(afore, case=False, na=False)
        subset = df[mask & (df["siefore"] == siefore)]

    if subset.empty:
        log.debug(
            "No hay rendimientos para AFORE='%s' SIEFORE='%s'. Usando fallback.", afore, siefore
        )
        return _FALLBACK_POR_AFORE.get(afore, _FALLBACK_RENDIMIENTOS.get(siefore, {}).get("promedio", 0.055))

    if metodo == "ultimo":
        return subset.sort_values("fecha").iloc[-1]["rendimiento"]

    # Promedio de los últimos 5 años (60 observaciones mensuales)
    ultimos = subset.sort_values("fecha").tail(60)
    return ultimos["rendimiento"].mean()


def get_rendimiento_promedio_siefore(siefore: str) -> float:
    """Retorna el rendimiento promedio ponderado del mercado para una SIEFORE."""
    df = fetch_rendimientos()
    subset = df[
        (df["siefore"] == siefore) &
        (df["afore"].str.contains("Promedio", case=False, na=False))
    ]
    if subset.empty:
        return _FALLBACK_RENDIMIENTOS.get(siefore, {}).get("promedio", 0.055)
    return subset.sort_values("fecha").tail(60)["rendimiento"].mean()


def _fallback_dataframe() -> pd.DataFrame:
    """Genera un DataFrame mínimo con los valores de fallback."""
    registros = []
    fecha_ref = date.today().isoformat()
    for siefore, stats in _FALLBACK_RENDIMIENTOS.items():
        registros.append({
            "siefore": siefore,
            "afore": "Promedio Ponderado",
            "fecha": fecha_ref,
            "rendimiento": stats["promedio"],
        })
    for afore, rend in _FALLBACK_POR_AFORE.items():
        registros.append({
            "siefore": "SB0",
            "afore": afore,
            "fecha": fecha_ref,
            "rendimiento": rend,
        })
    return pd.DataFrame(registros)


def seed_cache_desde_fallback() -> None:
    """Inicializa el cache si está vacío."""
    if CACHE_AFORE_REND.exists():
        return
    df = _fallback_dataframe()
    df.to_csv(CACHE_AFORE_REND, index=False)
    log.info("Cache rendimientos inicializado con fallback.")

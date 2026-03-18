"""
data_fetchers/afore_comisiones.py
Descarga las comisiones anuales de las AFOREs desde CONSAR.
Fuente: https://www.gob.mx/consar/articulos/comisiones-que-cobran-las-afores

Las comisiones se expresan como fracción del saldo (ej: 0.0054 = 0.54% anual).
CONSAR las autoriza una vez al año (enero).

Estructura del cache (afore_comisiones.json):
{
  "2024": {"Azteca": 0.0057, "Citibanamex": 0.0057, ...},
  "2025": {"Azteca": 0.0055, ...},
  "2026": {"Azteca": 0.0054, ...},
  "_meta": {"fecha_actualizacion": "2026-01-15", "fuente": "CONSAR scraping"}
}
"""

import json
import logging
import os
import re
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CACHE_AFORE_COM, URL_CONSAR_COMISIONES, AFORES

log = logging.getLogger(__name__)

# Comisiones fallback (del Excel fuente — hoja Comisiones)
_FALLBACK_COMISIONES: dict[str, dict[str, float]] = {
    "2020": {
        "PensionISSSTE": 0.0079, "Citibanamex": 0.0088, "XXI Banorte":  0.0088,
        "Profuturo GNP": 0.0092, "SURA":        0.0092, "Coppel":       0.0098,
        "Principal":     0.0097, "Azteca":       0.0098, "Inbursa":      0.0092,
        "Invercap":      0.0098,
    },
    "2021": {
        "PensionISSSTE": 0.0053, "Citibanamex": 0.0080, "XXI Banorte":  0.0080,
        "Profuturo GNP": 0.0083, "SURA":        0.0083, "Coppel":       0.0085,
        "Principal":     0.0085, "Azteca":       0.0086, "Inbursa":      0.0086,
        "Invercap":      0.0087,
    },
    "2022": {
        "PensionISSSTE": 0.0053, "Citibanamex": 0.0057, "XXI Banorte":  0.0080,
        "Profuturo GNP": 0.0057, "SURA":        0.0057, "Coppel":       0.0057,
        "Principal":     0.0057, "Azteca":       0.0057, "Inbursa":      0.0057,
        "Invercap":      0.0057,
    },
    "2023": {
        "PensionISSSTE": 0.0053, "Citibanamex": 0.0057, "XXI Banorte":  0.0057,
        "Profuturo GNP": 0.0057, "SURA":        0.0057, "Coppel":       0.0057,
        "Principal":     0.0057, "Azteca":       0.0057, "Inbursa":      0.0057,
        "Invercap":      0.0057,
    },
    "2024": {
        "PensionISSSTE": 0.0053, "Citibanamex": 0.0057, "XXI Banorte":  0.0057,
        "Profuturo GNP": 0.0057, "SURA":        0.0057, "Coppel":       0.0057,
        "Principal":     0.0057, "Azteca":       0.0057, "Inbursa":      0.0057,
        "Invercap":      0.0057,
    },
    "2025": {
        "PensionISSSTE": 0.0052, "Citibanamex": 0.0055, "XXI Banorte":  0.0055,
        "Profuturo GNP": 0.0055, "SURA":        0.0055, "Coppel":       0.0055,
        "Principal":     0.0055, "Azteca":       0.0055, "Inbursa":      0.0055,
        "Invercap":      0.0055,
    },
    "2026": {
        "PensionISSSTE": 0.0052, "Citibanamex": 0.0054, "XXI Banorte":  0.0054,
        "Profuturo GNP": 0.0054, "SURA":        0.0054, "Coppel":       0.0054,
        "Principal":     0.0054, "Azteca":       0.0054, "Inbursa":      0.0054,
        "Invercap":      0.0054,
    },
}

# Mapeos de nombres CONSAR → nombres internos del proyecto
_NOMBRE_MAP = {
    "pensionissste":  "PensionISSSTE",
    "banamex":        "Citibanamex",
    "citibanamex":    "Citibanamex",
    "xxi banorte":    "XXI Banorte",
    "xxibanorte":     "XXI Banorte",
    "profuturo":      "Profuturo GNP",
    "profuturo gnp":  "Profuturo GNP",
    "sura":           "SURA",
    "coppel":         "Coppel",
    "principal":      "Principal",
    "azteca":         "Azteca",
    "inbursa":        "Inbursa",
    "invercap":       "Invercap",
}


def _normalizar_afore(nombre: str) -> Optional[str]:
    """Normaliza el nombre de AFORE de CONSAR al nombre interno."""
    limpio = nombre.lower().strip()
    for clave, valor in _NOMBRE_MAP.items():
        if clave in limpio:
            return valor
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPER CONSAR
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_consar() -> dict[str, dict[str, float]]:
    """
    Scrapea la tabla de comisiones de CONSAR.
    La página tiene una tabla HTML con columnas por año y filas por AFORE.

    Returns:
        dict {anio_str: {afore: comision}}
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    resp = requests.get(URL_CONSAR_COMISIONES, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    resultado: dict[str, dict[str, float]] = {}

    # Buscar tabla que contenga "Comisión" o "AFORE" en los headers
    for table in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in table.find_all("th")]
        if not any("comis" in h.lower() or "afore" in h.lower() for h in ths):
            continue

        # Extraer años de los headers
        anios = []
        for th in ths:
            match = re.search(r"20\d{2}", th)
            if match:
                anios.append(match.group())

        if not anios:
            continue

        # Inicializar estructura
        for anio in anios:
            resultado.setdefault(anio, {})

        # Parsear filas
        for row in table.find_all("tr"):
            celdas = [td.get_text(strip=True) for td in row.find_all("td")]
            if not celdas:
                continue

            afore_raw = celdas[0]
            afore_norm = _normalizar_afore(afore_raw)
            if not afore_norm:
                continue

            for i, anio in enumerate(anios):
                if i + 1 < len(celdas):
                    try:
                        val_str = celdas[i + 1].replace("%", "").replace(",", ".").strip()
                        if not val_str or val_str.lower() in ("pendiente", "n/a", "-"):
                            continue
                        val = float(val_str)
                        # Normalizar: si viene como porcentaje (ej 0.54) vs fracción (0.0054)
                        if val > 1:
                            val = val / 100
                        resultado[anio][afore_norm] = val
                    except ValueError:
                        continue

    if not resultado:
        raise ValueError("No se encontró tabla de comisiones en CONSAR.")

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────

def _leer_cache() -> Optional[dict]:
    if not CACHE_AFORE_COM.exists():
        return None
    try:
        with open(CACHE_AFORE_COM, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Error leyendo cache comisiones: %s", e)
        return None


def _guardar_cache(datos: dict) -> None:
    try:
        with open(CACHE_AFORE_COM, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        log.info("Cache comisiones guardado en %s", CACHE_AFORE_COM)
    except OSError as e:
        log.error("No se pudo guardar cache comisiones: %s", e)


def _cache_vigente(max_dias: int = 60) -> bool:
    """Comisiones se fijan en enero — revisar cada 60 días es suficiente."""
    if not CACHE_AFORE_COM.exists():
        return False
    try:
        datos = _leer_cache()
        fecha_str = (datos or {}).get("_meta", {}).get("fecha_actualizacion", "")
        if not fecha_str:
            return False
        return (date.today() - date.fromisoformat(fecha_str)).days <= max_dias
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def fetch_comisiones(forzar_actualizacion: bool = False) -> dict[str, dict[str, float]]:
    """
    Obtiene las comisiones de todas las AFOREs por año.

    Returns:
        dict {anio_str: {afore: comision_fraccion}}
        Ej: {"2026": {"XXI Banorte": 0.0054, ...}}
    """
    if not forzar_actualizacion and _cache_vigente():
        datos = _leer_cache()
        if datos:
            return {k: v for k, v in datos.items() if k != "_meta"}

    try:
        datos = _scrape_consar()
        datos["_meta"] = {
            "fecha_actualizacion": date.today().isoformat(),
            "fuente": "CONSAR scraping",
        }
        _guardar_cache(datos)
        log.info("Comisiones CONSAR descargadas: %d años", len(datos) - 1)
        return {k: v for k, v in datos.items() if k != "_meta"}

    except Exception as e:
        log.warning("No se pudo descargar comisiones CONSAR (%s). Usando fallback.", e)

    return dict(_FALLBACK_COMISIONES)


def get_comision_afore(afore: str, anio: Optional[int] = None) -> float:
    """
    Retorna la comisión de una AFORE para un año dado.
    Si el año no está disponible, usa el último año conocido.

    Args:
        afore: Nombre de la AFORE (ej: "XXI Banorte")
        anio:  Año (ej: 2026). None = año actual.

    Returns:
        Comisión como fracción (ej: 0.0054)
    """
    if anio is None:
        anio = date.today().year

    datos = fetch_comisiones()
    anio_str = str(anio)

    # Si el año exacto no está, usar el último disponible
    if anio_str not in datos:
        anios_disp = sorted(k for k in datos if k.isdigit())
        if not anios_disp:
            return _FALLBACK_COMISIONES.get("2026", {}).get(afore, 0.0054)
        anio_str = anios_disp[-1]
        log.debug("Comisión año %d no disponible, usando %s.", anio, anio_str)

    comisiones_anio = datos[anio_str]
    if afore in comisiones_anio:
        return comisiones_anio[afore]

    # Buscar por nombre parcial
    for nombre, valor in comisiones_anio.items():
        if afore.lower() in nombre.lower() or nombre.lower() in afore.lower():
            return valor

    # Usar promedio del año como fallback
    valores = [v for v in comisiones_anio.values() if isinstance(v, float)]
    if valores:
        promedio = sum(valores) / len(valores)
        log.warning("AFORE '%s' no encontrada para %s. Usando promedio: %.4f", afore, anio_str, promedio)
        return promedio

    return 0.0054  # Último recurso


def get_comision_promedio(anio: Optional[int] = None) -> float:
    """Retorna la comisión promedio del mercado para un año."""
    if anio is None:
        anio = date.today().year
    datos = fetch_comisiones()
    anio_str = str(anio)
    if anio_str not in datos:
        anios_disp = sorted(k for k in datos if k.isdigit())
        anio_str = anios_disp[-1] if anios_disp else "2026"
    valores = [v for v in datos.get(anio_str, {}).values() if isinstance(v, float)]
    return sum(valores) / len(valores) if valores else 0.0054


def seed_cache_desde_fallback() -> None:
    """Inicializa el cache si está vacío."""
    if CACHE_AFORE_COM.exists():
        return
    datos = dict(_FALLBACK_COMISIONES)
    datos["_meta"] = {
        "fecha_actualizacion": "2026-01-01",
        "fuente": "seed inicial hardcoded",
    }
    _guardar_cache(datos)
    log.info("Cache comisiones inicializado con fallback.")

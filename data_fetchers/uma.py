"""
data_fetchers/uma.py
Descarga el valor de la UMA (Unidad de Medida y Actualización) desde INEGI.
Fuente: https://www.inegi.org.mx/temas/uma/

Estructura del cache (uma.json):
{
  "2024": {"diario": 108.57, "mensual": 3300.53, "anual": 39606.36},
  "2025": {"diario": 113.14, "mensual": 3439.46, "anual": 41273.52},
  "2026": {"diario": 117.31, "mensual": 3566.22, "anual": 42794.64},
  "_meta": {"fecha_actualizacion": "2026-01-15", "fuente": "INEGI"}
}
"""

import json
import logging
from datetime import datetime

import requests

from config import CACHE_UMA, URL_UMA
import project_time

log = logging.getLogger(__name__)

# ── Valores de respaldo (hardcoded del Excel fuente) ──────────────────────────
# Se usan cuando INEGI no está disponible Y no hay cache local
_FALLBACK_UMA: dict[str, dict] = {
    "2016": {"diario":  73.04, "mensual": 2220.42, "anual":  26645.04},
    "2017": {"diario":  75.49, "mensual": 2294.90, "anual":  27538.80},
    "2018": {"diario":  80.60, "mensual": 2450.24, "anual":  29402.88},
    "2019": {"diario":  84.49, "mensual": 2568.50, "anual":  30822.00},
    "2020": {"diario":  86.88, "mensual": 2641.15, "anual":  31693.80},
    "2021": {"diario":  89.62, "mensual": 2724.45, "anual":  32693.40},
    "2022": {"diario":  96.22, "mensual": 2925.09, "anual":  35101.08},
    "2023": {"diario": 103.74, "mensual": 3153.70, "anual":  37844.40},
    "2024": {"diario": 108.57, "mensual": 3300.53, "anual":  39606.36},
    "2025": {"diario": 113.14, "mensual": 3439.46, "anual":  41273.52},
    "2026": {"diario": 117.31, "mensual": 3566.22, "anual":  42794.64},
}


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_inegi() -> dict[str, dict]:
    """
    Descarga la tabla de UMA desde INEGI y la parsea.
    Retorna dict {año_str: {diario, mensual, anual}} o lanza excepción.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError(
            "Se requiere 'beautifulsoup4' para actualizar la UMA desde INEGI."
        ) from exc

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-MX,es;q=0.9",
    }

    resp = requests.get(URL_UMA, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    resultado: dict[str, dict] = {}

    # INEGI publica la tabla en un <table> dentro de un div con id="UMA_Data"
    # o con clase similar. Buscamos la tabla que tenga "Diario" en los headers.
    for table in soup.find_all("table"):
        headers_text = [
            th.get_text(strip=True).lower()
            for th in table.find_all("th")
        ]
        # Detectar si esta tabla tiene las columnas que buscamos
        if not any("diario" in h for h in headers_text):
            continue

        for row in table.find_all("tr"):
            cols = [td.get_text(strip=True).replace(",", "") for td in row.find_all("td")]
            if len(cols) < 4:
                continue
            try:
                anio    = str(int(cols[0]))
                diario  = float(cols[1])
                mensual = float(cols[2])
                anual   = float(cols[3])
                resultado[anio] = {"diario": diario, "mensual": mensual, "anual": anual}
            except (ValueError, IndexError):
                continue

    if not resultado:
        raise ValueError("No se encontró tabla de UMA en la página de INEGI.")

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def fetch_uma(forzar_actualizacion: bool = False) -> dict[str, dict]:
    """
    Obtiene los valores históricos de la UMA.

    Orden de preferencia:
      1. Cache local (uma.json) — si existe y no se fuerza actualización
      2. Scraping INEGI
      3. Valores fallback hardcoded (del Excel fuente)

    Args:
        forzar_actualizacion: Si True ignora el cache y descarga de INEGI.

    Returns:
        dict con años como keys:
        {
          "2026": {"diario": 117.31, "mensual": 3566.22, "anual": 42794.64},
          ...
          "_meta": {"fecha_actualizacion": "...", "fuente": "..."}
        }
    """
    # 1. Intentar desde cache
    if not forzar_actualizacion and CACHE_UMA.exists():
        try:
            with open(CACHE_UMA, encoding="utf-8") as f:
                datos = json.load(f)
            log.info("UMA cargada desde cache: %s", CACHE_UMA)
            return datos
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Cache UMA corrupto, se descargará: %s", e)

    # 2. Intentar scraping INEGI
    try:
        datos = _scrape_inegi()
        datos["_meta"] = {
            "fecha_actualizacion": project_time.today().isoformat(),
            "fuente": "INEGI scraping",
        }
        _guardar_cache(datos)
        log.info("UMA descargada de INEGI: %d años", len(datos) - 1)
        return datos

    except Exception as e:
        log.warning("No se pudo descargar UMA de INEGI (%s). Usando fallback.", e)

    # 3. Fallback hardcoded
    datos = dict(_FALLBACK_UMA)
    datos["_meta"] = {
        "fecha_actualizacion": "2026-01-01",
        "fuente": "fallback hardcoded",
    }
    return datos


def get_uma_anio(anio: int, forzar_actualizacion: bool = False) -> dict:
    """
    Retorna los valores de UMA para un año específico.

    Returns:
        {"diario": float, "mensual": float, "anual": float}

    Raises:
        KeyError si el año no está disponible.
    """
    datos = fetch_uma(forzar_actualizacion)
    key = str(anio)
    if key not in datos or key == "_meta":
        # Intentar proyectar con el último año disponible
        anios_disp = sorted(k for k in datos if k != "_meta" and k.isdigit())
        if not anios_disp:
            raise KeyError(f"No hay datos de UMA disponibles.")
        ultimo = anios_disp[-1]
        log.debug(
            "UMA %d no en cache. Usando último año conocido: %s", anio, ultimo
        )
        return datos[ultimo]
    return datos[key]


def get_uma_mensual(anio: int) -> float:
    """Atajo: retorna solo el valor mensual de la UMA para un año."""
    return get_uma_anio(anio)["mensual"]


def get_uma_diaria(anio: int) -> float:
    """Atajo: retorna solo el valor diario de la UMA para un año."""
    return get_uma_anio(anio)["diario"]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _guardar_cache(datos: dict) -> None:
    try:
        with open(CACHE_UMA, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        log.info("Cache UMA guardado en %s", CACHE_UMA)
    except OSError as e:
        log.error("No se pudo guardar cache UMA: %s", e)


def cache_esta_vigente(max_dias: int = 31) -> bool:
    """
    Verifica si el cache de UMA tiene menos de max_dias días.
    La UMA se actualiza en febrero de cada año, así que 31 días es conservador.
    """
    if not CACHE_UMA.exists():
        return False
    try:
        with open(CACHE_UMA, encoding="utf-8") as f:
            datos = json.load(f)
        fecha_str = datos.get("_meta", {}).get("fecha_actualizacion", "")
        if not fecha_str:
            return False
        fecha = datetime.fromisoformat(fecha_str).date()
        return (project_time.today() - fecha).days <= max_dias
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SEED DE CACHE (para correr sin internet desde el primer momento)
# ─────────────────────────────────────────────────────────────────────────────

def seed_cache_desde_fallback() -> None:
    """
    Escribe el cache local con los valores hardcoded si no existe aún.
    Útil para la primera ejecución o en entornos sin internet.
    """
    if CACHE_UMA.exists():
        return
    datos = dict(_FALLBACK_UMA)
    datos["_meta"] = {
        "fecha_actualizacion": "2026-01-01",
        "fuente": "seed inicial hardcoded",
    }
    _guardar_cache(datos)
    log.info("Cache UMA inicializado con valores fallback.")

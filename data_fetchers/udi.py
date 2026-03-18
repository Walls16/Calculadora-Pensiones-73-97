"""
data_fetchers/udi.py
Descarga el valor diario de la UDI (Unidad de Inversión) desde Banxico SIE API.
Serie: SP68257

API docs: https://www.banxico.org.mx/SieAPIRest/service/v1/doc/consultaDatosSerieRango
Token gratuito en: https://www.banxico.org.mx/SieAPIRest/service/v1/token

Estructura del cache (udis.csv):
  fecha,valor
  1995-04-04,1.0
  1995-04-05,1.001918
  ...
  2026-03-12,8.652310

Para proyecciones se usa el último valor conocido + inflación implícita.
"""

import csv
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CACHE_UDI, URL_BANXICO_UDI

log = logging.getLogger(__name__)

# Token de Banxico — se lee de variable de entorno o del config
# Registrar token gratis en: https://www.banxico.org.mx/SieAPIRest/service/v1/token
_BANXICO_TOKEN = os.environ.get("BANXICO_TOKEN", "")

# Últimos valores conocidos (del Excel fuente) para seed inicial del cache
# Formato: [(fecha_str, valor), ...]
_FALLBACK_UDIS_ANUALES = [
    ("2010-12-31", 4.526308),
    ("2011-12-31", 4.691316),
    ("2012-12-31", 4.874624),
    ("2013-12-31", 5.058731),
    ("2014-12-31", 5.270368),
    ("2015-12-31", 5.381175),
    ("2016-12-31", 5.562883),
    ("2017-12-31", 5.934551),
    ("2018-12-31", 6.226631),
    ("2019-12-31", 6.399018),
    ("2020-12-31", 6.605597),
    ("2021-12-31", 7.108233),
    ("2022-12-31", 7.718000),  # aprox
    ("2023-12-31", 8.087000),  # aprox
    ("2024-12-31", 8.470000),  # aprox
    ("2025-12-31", 8.610000),  # aprox
]


# ─────────────────────────────────────────────────────────────────────────────
# BANXICO API
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_banxico(fecha_ini: str, fecha_fin: str) -> list[tuple[str, float]]:
    """
    Llama a la API REST de Banxico para obtener valores UDI en un rango de fechas.
    Fechas en formato YYYY-MM-DD.

    Returns:
        Lista de (fecha_str, valor_udi)

    Raises:
        requests.HTTPError, ValueError
    """
    if not _BANXICO_TOKEN:
        raise ValueError(
            "Token de Banxico no configurado. "
            "Registra uno en https://www.banxico.org.mx/SieAPIRest/service/v1/token "
            "y ponlo en la variable de entorno BANXICO_TOKEN."
        )

    url = URL_BANXICO_UDI.format(fecha_ini=fecha_ini, fecha_fin=fecha_fin)
    headers = {
        "Bmx-Token": _BANXICO_TOKEN,
        "Accept": "application/json",
    }

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    # Estructura de respuesta Banxico:
    # {"bmx": {"series": [{"idSerie": "SP68257", "datos": [{"fecha": "04/04/1995", "dato": "1"}]}]}}
    series = data.get("bmx", {}).get("series", [])
    if not series:
        raise ValueError("Respuesta Banxico vacía o sin series.")

    resultados: list[tuple[str, float]] = []
    for punto in series[0].get("datos", []):
        try:
            # Banxico usa formato DD/MM/YYYY
            fecha_obj = datetime.strptime(punto["fecha"], "%d/%m/%Y").date()
            valor = float(punto["dato"])
            resultados.append((fecha_obj.isoformat(), valor))
        except (ValueError, KeyError):
            continue

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# CACHE CSV
# ─────────────────────────────────────────────────────────────────────────────

def _leer_cache() -> dict[str, float]:
    """Lee el cache CSV y retorna {fecha_iso: valor}."""
    if not CACHE_UDI.exists():
        return {}
    datos: dict[str, float] = {}
    try:
        with open(CACHE_UDI, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                datos[row["fecha"]] = float(row["valor"])
    except (OSError, KeyError, ValueError) as e:
        log.warning("Error leyendo cache UDI: %s", e)
    return datos


def _guardar_cache(datos: dict[str, float]) -> None:
    """Guarda el dict {fecha_iso: valor} en el CSV, ordenado por fecha."""
    try:
        filas = sorted(datos.items())
        with open(CACHE_UDI, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["fecha", "valor"])
            for fecha, valor in filas:
                writer.writerow([fecha, valor])
        log.info("Cache UDI guardado: %d registros en %s", len(filas), CACHE_UDI)
    except OSError as e:
        log.error("No se pudo guardar cache UDI: %s", e)


def _ultima_fecha_cache(datos: dict[str, float]) -> Optional[date]:
    if not datos:
        return None
    return date.fromisoformat(max(datos.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def fetch_udi(forzar_actualizacion: bool = False) -> dict[str, float]:
    """
    Obtiene el histórico completo de valores UDI.

    Orden de preferencia:
      1. Cache local (udis.csv) + descarga solo lo nuevo
      2. Si no hay token Banxico, usa cache o fallback

    Returns:
        dict {fecha_iso_str: valor_udi}
        Ej: {"2026-03-12": 8.652310, ...}
    """
    cache = _leer_cache()

    # Seed inicial si el cache está vacío
    if not cache:
        cache = {f: v for f, v in _FALLBACK_UDIS_ANUALES}
        _guardar_cache(cache)

    if forzar_actualizacion or not cache:
        fecha_ini = "1995-04-04"
    else:
        ultima = _ultima_fecha_cache(cache)
        hoy = date.today()
        if ultima and ultima >= hoy - timedelta(days=1):
            log.info("UDI cache vigente (último: %s)", ultima)
            return cache
        fecha_ini = (ultima + timedelta(days=1)).isoformat() if ultima else "1995-04-04"

    fecha_fin = date.today().isoformat()

    try:
        nuevos = _fetch_banxico(fecha_ini, fecha_fin)
        if nuevos:
            cache.update({f: v for f, v in nuevos})
            _guardar_cache(cache)
            log.info("UDI actualizada: +%d registros hasta %s", len(nuevos), fecha_fin)
    except ValueError as e:
        # Sin token — no es error crítico, trabajamos con lo que hay
        log.info("Banxico no disponible: %s. Usando cache.", e)
    except requests.RequestException as e:
        log.warning("Error de red al descargar UDI: %s. Usando cache.", e)

    return cache


def get_udi_fecha(fecha: date) -> float:
    """
    Retorna el valor UDI para una fecha específica.
    Si no existe el dato exacto, usa el valor más cercano anterior.

    Raises:
        KeyError si no hay ningún dato disponible.
    """
    datos = fetch_udi()
    fecha_str = fecha.isoformat()

    if fecha_str in datos:
        return datos[fecha_str]

    # Buscar el valor más cercano anterior
    fechas_disp = sorted(k for k in datos.keys() if k <= fecha_str)
    if not fechas_disp:
        raise KeyError(f"No hay valor UDI disponible para o antes de {fecha_str}.")

    return datos[fechas_disp[-1]]


def get_udi_hoy() -> float:
    """Retorna el valor UDI de hoy (o el más reciente disponible)."""
    return get_udi_fecha(date.today())


def get_udi_anio(anio: int) -> float:
    """
    Retorna el valor UDI promedio anual.
    Promedia todos los valores disponibles para ese año calendario.
    """
    datos = fetch_udi()
    prefix = str(anio)
    valores = [v for k, v in datos.items() if k.startswith(prefix)]
    if not valores:
        log.warning("No hay datos UDI para %d, proyectando desde último disponible.", anio)
        return _proyectar_udi(anio)
    return sum(valores) / len(valores)


def _proyectar_udi(anio_objetivo: int) -> float:
    """
    Proyecta el valor UDI para un año futuro usando la tasa de inflación implícita
    de los últimos 3 años disponibles en el cache.
    """
    datos = fetch_udi()
    anios_disp = sorted(
        int(k[:4]) for k in datos if len(k) >= 4 and k[:4].isdigit()
    )
    anios_disp = sorted(set(anios_disp))

    if len(anios_disp) < 2:
        # Sin historial suficiente — usar inflación de 3.5%
        ultimo_valor = list(datos.values())[-1] if datos else 6.0
        annos_diff = anio_objetivo - date.today().year
        return ultimo_valor * (1.035 ** max(annos_diff, 0))

    # Calcular tasa implícita de los últimos 3 años
    n = min(3, len(anios_disp) - 1)
    anio_base  = anios_disp[-(n + 1)]
    anio_final = anios_disp[-1]

    vals_base  = [v for k, v in datos.items() if k.startswith(str(anio_base))]
    vals_final = [v for k, v in datos.items() if k.startswith(str(anio_final))]

    if not vals_base or not vals_final:
        ultimo_valor = list(datos.values())[-1]
        return ultimo_valor * (1.035 ** (anio_objetivo - anio_final))

    promedio_base  = sum(vals_base)  / len(vals_base)
    promedio_final = sum(vals_final) / len(vals_final)
    tasa_implicita = (promedio_final / promedio_base) ** (1 / n) - 1

    annos_proyectar = anio_objetivo - anio_final
    return promedio_final * (1 + tasa_implicita) ** annos_proyectar


# ─────────────────────────────────────────────────────────────────────────────
# SEED
# ─────────────────────────────────────────────────────────────────────────────

def seed_cache_desde_fallback() -> None:
    """Inicializa el cache con valores anuales de respaldo si está vacío."""
    if CACHE_UDI.exists():
        return
    datos = {f: v for f, v in _FALLBACK_UDIS_ANUALES}
    _guardar_cache(datos)
    log.info("Cache UDI inicializado con valores anuales de respaldo.")

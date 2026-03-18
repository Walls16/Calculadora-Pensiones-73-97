"""
seed_cache.py
Inicializa todos los archivos de cache con valores de respaldo.
Correr una sola vez al configurar el proyecto, o cuando se quiera resetear.

Uso:
    python seed_cache.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger(__name__)

from data_fetchers.uma             import seed_cache_desde_fallback as seed_uma
from data_fetchers.udi             import seed_cache_desde_fallback as seed_udi
from data_fetchers.afore_comisiones import seed_cache_desde_fallback as seed_comisiones
from data_fetchers.afore_rendimientos import seed_cache_desde_fallback as seed_rendimientos
from data_fetchers.tablas_vida     import seed_cache_desde_fallback as seed_tablas_vida

def main():
    log.info("Inicializando caches...")

    seed_uma()
    log.info("  ✅ UMA")

    seed_udi()
    log.info("  ✅ UDI")

    seed_comisiones()
    log.info("  ✅ Comisiones AFORE")

    seed_rendimientos()
    log.info("  ✅ Rendimientos AFORE")

    seed_tablas_vida()
    log.info("  ✅ Tablas de vida (qx)")

    log.info("Cache inicializado. Ya puedes correr la app sin internet.")

if __name__ == "__main__":
    main()

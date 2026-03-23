import os
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_PATCHER = None


def setUpModule():
    global _PATCHER
    _PATCHER = patch("project_time.today", return_value=date(2026, 1, 15))
    _PATCHER.start()


def tearDownModule():
    if _PATCHER is not None:
        _PATCHER.stop()


class TestDeterminism(unittest.TestCase):
    def test_current_year_defaults_are_deterministic(self):
        from data_fetchers.afore_comisiones import get_comision_afore
        from models.trabajador import Trabajador

        trabajador = Trabajador(
            nombre="Test",
            fecha_nacimiento=date(2004, 12, 16),
            genero=0,
            edad_retiro_deseada=65,
            semanas_cotizadas=0,
            sbc_mensual=30_000,
            cotizo_antes_1997=0,
            afore="XXI Banorte",
        )

        self.assertEqual(trabajador.edad_actual, 21)
        self.assertAlmostEqual(get_comision_afore("XXI Banorte"), 0.0054, places=6)


class TestImportIsolation(unittest.TestCase):
    def _run_inline(self, code: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_uma_import_and_fallback_without_bs4(self):
        code = """
import sys
sys.path.insert(0, r'%s')
sys.modules['bs4'] = None
from data_fetchers.uma import fetch_uma, get_uma_mensual
assert get_uma_mensual(2026) > 0
assert fetch_uma(forzar_actualizacion=True)['2026']['mensual'] > 0
print('ok')
""" % str(ROOT).replace("\\", "\\\\")
        result = self._run_inline(code)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)

    def test_comisiones_fallback_without_bs4(self):
        code = """
import sys
sys.path.insert(0, r'%s')
sys.modules['bs4'] = None
from data_fetchers.afore_comisiones import fetch_comisiones, get_comision_afore
assert get_comision_afore('XXI Banorte', 2026) > 0
assert fetch_comisiones(forzar_actualizacion=True)['2026']['XXI Banorte'] > 0
print('ok')
""" % str(ROOT).replace("\\", "\\\\")
        result = self._run_inline(code)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)

    def test_projection_import_without_pandas(self):
        code = """
import sys
sys.path.insert(0, r'%s')
sys.modules['pandas'] = None
from calculators.saldo_afore import get_densidad
assert get_densidad(21) > 0
print('ok')
""" % str(ROOT).replace("\\", "\\\\")
        result = self._run_inline(code)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)


class TestBanxicoTokenResolution(unittest.TestCase):
    def test_udi_prefers_env_token_over_config(self):
        from data_fetchers import udi

        with patch.dict(os.environ, {"BANXICO_TOKEN": "env-token"}, clear=True):
            with patch.object(udi, "BANXICO_TOKEN", "config-token"):
                self.assertEqual(udi._get_banxico_token(), "env-token")

    def test_udi_uses_config_token_when_env_missing(self):
        from data_fetchers import udi

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(udi, "BANXICO_TOKEN", "config-token"):
                self.assertEqual(udi._get_banxico_token(), "config-token")


class TestDataSanity(unittest.TestCase):
    def test_pmg_table_is_monotonic_by_weeks(self):
        from config import PMG_BASE_2025

        for bracket, edades in PMG_BASE_2025.items():
            for edad, semanas in edades.items():
                ordenadas = [semanas[k] for k in sorted(semanas)]
                self.assertEqual(
                    ordenadas,
                    sorted(ordenadas),
                    msg=f"PMG no monotona para {bracket} edad {edad}",
                )

    def test_densidad_range_and_post_90_constant(self):
        from calculators.saldo_afore import get_densidad

        for edad in range(15, 111):
            valor = get_densidad(edad)
            self.assertGreaterEqual(valor, 0.0)
            self.assertLessEqual(valor, 1.0)

        self.assertAlmostEqual(get_densidad(90), get_densidad(110), places=6)

    def test_afore_coverage_matches_config(self):
        from config import AFORES
        from data_fetchers.afore_comisiones import _FALLBACK_COMISIONES
        from data_fetchers.afore_rendimientos import _FALLBACK_POR_AFORE

        self.assertEqual(set(AFORES), set(_FALLBACK_COMISIONES["2026"]))
        self.assertEqual(set(AFORES), set(_FALLBACK_POR_AFORE))

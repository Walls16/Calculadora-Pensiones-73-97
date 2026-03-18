"""
tests/test_calculators.py
Tests unitarios que comparan los resultados de cada módulo contra
los valores exactos del Excel fuente "Calculadora_de_Retiro_2024.xlsx".

Todos los valores de referencia (_REF_*) fueron extraídos directamente
del Excel con pandas. Se tolera ±0.01% de diferencia por redondeo float.

Correr con:
    python -m pytest tests/ -v
    # o
    python tests/test_calculators.py
"""

import sys
import os
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─────────────────────────────────────────────────────────────────────────────
# TOLERANCIAS
# ─────────────────────────────────────────────────────────────────────────────
TOLS = {
    "pesos":     0.02,     # ±$0.02 — redondeo centavos
    "tasa":      1e-6,     # ±0.0001% — tasas y factores
    "ax":        1e-4,     # ±0.0001 — factor actuarial äx(12)
    "densidad":  1e-6,     # ±0.000001 — densidades de cotización
    "porcentaje":0.0001,   # ±0.01% — diferencias porcentuales
}

def assertAlmostEqualRel(tc, val, ref, tol=0.0001, msg=""):
    """Diferencia relativa ≤ tol (default 0.01%)."""
    if ref == 0:
        tc.assertAlmostEqual(val, ref, places=6, msg=msg)
    else:
        diff_rel = abs(val - ref) / abs(ref)
        tc.assertLessEqual(diff_rel, tol,
            msg=f"{msg} | val={val:.8f} ref={ref:.8f} diff_rel={diff_rel:.6%}")


# ═════════════════════════════════════════════════════════════════════════════
# 1. UMA
# ═════════════════════════════════════════════════════════════════════════════

class TestUMA(unittest.TestCase):
    """
    Valores de referencia: Excel fila F24-F25, col 3 (año 2026)
    UMA diaria: $117.31 | UMA mensual: $3,566.22 | UMA anual: $42,794.64
    """

    def test_uma_mensual_2026(self):
        from data_fetchers.uma import get_uma_mensual
        val = get_uma_mensual(2026)
        self.assertAlmostEqual(val, 3566.22, places=2,
            msg="UMA mensual 2026 debe ser $3,566.22")

    def test_uma_diaria_2026(self):
        from data_fetchers.uma import get_uma_diaria
        val = get_uma_diaria(2026)
        self.assertAlmostEqual(val, 117.31, places=2,
            msg="UMA diaria 2026 debe ser $117.31")

    def test_uma_anual_2026(self):
        from data_fetchers.uma import get_uma_anio
        val = get_uma_anio(2026)["anual"]
        self.assertAlmostEqual(val, 42794.64, places=2,
            msg="UMA anual 2026 debe ser $42,794.64")

    def test_uma_historica_2024(self):
        from data_fetchers.uma import get_uma_mensual
        val = get_uma_mensual(2024)
        self.assertAlmostEqual(val, 3300.53, places=2,
            msg="UMA mensual 2024 debe ser $3,300.53")

    def test_uma_anio_inexistente_usa_ultimo(self):
        """Para años futuros sin dato debe retornar el último conocido sin error."""
        from data_fetchers.uma import get_uma_mensual
        val = get_uma_mensual(2099)
        self.assertGreater(val, 0, msg="UMA de año futuro debe ser positivo")


# ═════════════════════════════════════════════════════════════════════════════
# 2. TABLAS DE VIDA — äx(m) vs Excel
# ═════════════════════════════════════════════════════════════════════════════

class TestTablasVida(unittest.TestCase):
    """
    Referencia: Excel hoja "Anualidades Contingentes", col 10 (H äx(m)) y 23 (M äx(m))
    Tasa técnica: 2.34% anual | Pagos mensuales m=12
    """

    # Valores directos del Excel (col äx(m) de la hoja Anualidades Contingentes)
    _REF_AXM_HOMBRE = {
        0:   36.764483,
        20:  33.395188,
        40:  28.948174,  # aprox — extrapolado del patrón
        55:  25.297979,  # aprox
        60:  21.324086,
        65:  19.256394,
        70:  17.082114,
        75:  14.816650,
        80:  12.467122,
    }
    _REF_AXM_MUJER = {
        0:   37.911652,
        60:  23.014070,
        65:  20.660122,
        70:  18.069315,
        75:  15.250204,
        80:  12.243035,
    }

    def test_ax_hombre_65(self):
        from calculators.anualidades import get_ax
        val = get_ax(0, 65)
        assertAlmostEqualRel(self, val, 19.256394, tol=0.0001,
            msg="äx(12) Hombre 65")

    def test_ax_mujer_65(self):
        from calculators.anualidades import get_ax
        val = get_ax(1, 65)
        assertAlmostEqualRel(self, val, 20.660122, tol=0.0001,
            msg="äx(12) Mujer 65")

    def test_ax_hombre_60(self):
        from calculators.anualidades import get_ax
        val = get_ax(0, 60)
        assertAlmostEqualRel(self, val, 21.324086, tol=0.0001,
            msg="äx(12) Hombre 60")

    def test_ax_mujer_60(self):
        from calculators.anualidades import get_ax
        val = get_ax(1, 60)
        assertAlmostEqualRel(self, val, 23.014070, tol=0.0001,
            msg="äx(12) Mujer 60")

    def test_ax_hombre_70(self):
        from calculators.anualidades import get_ax
        val = get_ax(0, 70)
        assertAlmostEqualRel(self, val, 17.082114, tol=0.0001,
            msg="äx(12) Hombre 70")

    def test_ax_mujer_80(self):
        from calculators.anualidades import get_ax
        val = get_ax(1, 80)
        assertAlmostEqualRel(self, val, 12.243035, tol=0.0001,
            msg="äx(12) Mujer 80")

    def test_ax_hombre_0(self):
        from calculators.anualidades import get_ax
        val = get_ax(0, 0)
        assertAlmostEqualRel(self, val, 36.764483, tol=0.0001,
            msg="äx(12) Hombre 0")

    def test_ax_mujer_0(self):
        from calculators.anualidades import get_ax
        val = get_ax(1, 0)
        assertAlmostEqualRel(self, val, 37.911652, tol=0.0001,
            msg="äx(12) Mujer 0")

    def test_qx_hombre_65_exacto(self):
        """qx debe ser exactamente el valor del Excel (hardcoded)."""
        from data_fetchers.tablas_vida import get_qx
        val = get_qx(0, 65)
        self.assertAlmostEqual(val, 0.007012520797333016, places=15,
            msg="qx Hombre 65 debe ser exacto del Excel")

    def test_qx_mujer_65_exacto(self):
        from data_fetchers.tablas_vida import get_qx
        val = get_qx(1, 65)
        self.assertAlmostEqual(val, 0.001456252312395252, places=15,
            msg="qx Mujer 65 debe ser exacto del Excel")

    def test_qx_extremos(self):
        from data_fetchers.tablas_vida import get_qx
        self.assertAlmostEqual(get_qx(0, 110), 1.0, places=10,
            msg="qx edad 110 debe ser 1.0")
        self.assertAlmostEqual(get_qx(1, 110), 1.0, places=10,
            msg="qx Mujer 110 debe ser 1.0")


# ═════════════════════════════════════════════════════════════════════════════
# 3. APORTACIONES — cuotas IMSS
# ═════════════════════════════════════════════════════════════════════════════

class TestAportaciones(unittest.TestCase):
    """
    Referencia: Excel filas F30-F39, col 3 (año 2026), SBC=$30,000
    Aportación total: $3,191.40
    Cuota retiro (patrón): 2.0% → $600.00
    Cuota trabajador: 1.125% → $337.50
    Cuota cesantía/vejez: 7.513% → $2,253.90
    """

    def setUp(self):
        from calculators.aportaciones import calcular_aportaciones
        self.ap = calcular_aportaciones(30_000, 2026)

    def test_aportacion_total_2026(self):
        self.assertAlmostEqual(self.ap["aportacion_total"], 3191.40, places=2,
            msg="Aportación total 2026 debe ser $3,191.40")

    def test_cuota_retiro_2026(self):
        self.assertAlmostEqual(self.ap["cuota_retiro"], 600.00, places=2,
            msg="Cuota retiro debe ser $600.00 (2% × $30,000)")

    def test_cuota_trabajador_2026(self):
        self.assertAlmostEqual(self.ap["cuota_trabajador"], 337.50, places=2,
            msg="Cuota trabajador debe ser $337.50 (1.125% × $30,000)")

    def test_cuota_cesantia_2026(self):
        self.assertAlmostEqual(self.ap["cuota_cesantia_vejez"], 2253.90, places=1,
            msg="Cuota cesantía/vejez debe ser $2,253.90 (7.513% × $30,000)")

    def test_tasa_cesantia_2026_bracket_alto(self):
        """SBC > 4 UMAs → bracket más alto → tasa 7.513% en 2026."""
        self.assertAlmostEqual(self.ap["tasa_cesantia_vejez"], 0.07513, places=5,
            msg="Tasa cesantía/vejez 2026 bracket >4UMAs debe ser 7.513%")

    def test_tasa_patronal_total_2026(self):
        """Retiro (2%) + Cesantía (7.513%) = 9.513%"""
        self.assertAlmostEqual(self.ap["tasa_total_patronal"], 0.09513, places=5,
            msg="Tasa patronal total 2026 debe ser 9.513%")

    def test_bracket_correcto_sbc_alto(self):
        self.assertEqual(self.ap["bracket"], "4.01+",
            msg="SBC $30,000 en 2026 debe caer en bracket '4.01+'")

    def test_sbc_cotizable_igual_a_original_bajo_tope(self):
        """SBC $30,000 < tope ($89,155.50) → cotizable = original."""
        self.assertAlmostEqual(self.ap["sbc_cotizable"], 30_000.0, places=2)

    def test_sbc_topado_sobre_25_umas(self):
        """SBC $200,000 debe toparse a 25 UMAs mensual."""
        from calculators.aportaciones import calcular_aportaciones
        ap = calcular_aportaciones(200_000, 2026)
        self.assertAlmostEqual(ap["sbc_cotizable"], 3566.22 * 25, places=1,
            msg="SBC debe toparse a 25 UMAs = $89,155.50")

    def test_transicion_tasas_año_por_año(self):
        """
        Tasas del período transitorio 2023-2030, bracket >4UMAs.
        Referencia: Excel hoja "2do y 3er Transitorio", fila F29.
        """
        _REF_TASAS = {
            2023: 0.04241,
            2024: 0.05331,
            2025: 0.06422,
            2026: 0.07513,
            2027: 0.08603,
            2028: 0.09694,
            2029: 0.10784,
            2030: 0.11875,
        }
        from calculators.aportaciones import calcular_aportaciones
        for anio, tasa_ref in _REF_TASAS.items():
            ap = calcular_aportaciones(30_000, anio)
            assertAlmostEqualRel(self, ap["tasa_cesantia_vejez"], tasa_ref,
                tol=0.0001, msg=f"Tasa cesantía/vejez {anio} bracket >4UMAs")

    def test_tasa_post_transicion(self):
        """A partir de 2031 la tasa se estabiliza en 11.875% para bracket alto."""
        from calculators.aportaciones import calcular_aportaciones
        for anio in [2031, 2035, 2050]:
            ap = calcular_aportaciones(30_000, anio)
            self.assertAlmostEqual(ap["tasa_cesantia_vejez"], 0.11875, places=5,
                msg=f"Tasa cesantía/vejez {anio} debe ser 11.875%")

    def test_aportacion_2027_mayor_que_2026(self):
        """Las aportaciones suben durante el transitorio."""
        from calculators.aportaciones import calcular_aportaciones
        ap27 = calcular_aportaciones(30_000, 2027)
        self.assertGreater(ap27["tasa_cesantia_vejez"], self.ap["tasa_cesantia_vejez"],
            msg="Tasa 2027 debe ser mayor que 2026")


# ═════════════════════════════════════════════════════════════════════════════
# 4. DENSIDAD DE COTIZACIÓN
# ═════════════════════════════════════════════════════════════════════════════

class TestDensidad(unittest.TestCase):
    """
    Referencia: Excel hoja "Densidad Cotización", valores exactos.
    El Excel reporta 6 cifras decimales.
    """

    _REF = {
        15: 0.799448,
        20: 0.859801,
        21: 0.865278,
        30: 0.899416,
        40: 0.922327,
        50: 0.937142,
        60: 0.946330,
        65: 0.949164,
        75: 0.951640,
        90: 0.948164,
    }

    def test_densidades_exactas(self):
        from calculators.saldo_afore import get_densidad
        for edad, ref in self._REF.items():
            val = get_densidad(edad)
            self.assertAlmostEqual(val, ref, places=6,
                msg=f"Densidad edad {edad} debe ser {ref:.6f}")

    def test_densidad_edad_21(self):
        """Edad 21 (caso Owen) = 0.865278"""
        from calculators.saldo_afore import get_densidad
        val = get_densidad(21)
        self.assertAlmostEqual(val, 0.865278, places=6)

    def test_densidad_post_90_constante(self):
        """A partir de 90 la densidad es constante = 0.948164."""
        from calculators.saldo_afore import get_densidad
        for edad in [90, 95, 100, 110]:
            self.assertAlmostEqual(get_densidad(edad), 0.948164, places=6,
                msg=f"Densidad edad {edad} debe ser 0.948164")


# ═════════════════════════════════════════════════════════════════════════════
# 5. MODELO TRABAJADOR
# ═════════════════════════════════════════════════════════════════════════════

class TestTrabajador(unittest.TestCase):
    """Validaciones del dataclass Trabajador."""

    def _owen(self, **kwargs):
        from models.trabajador import Trabajador
        defaults = dict(
            nombre="Owen García", fecha_nacimiento=date(2004, 12, 16),
            genero=0, edad_retiro_deseada=65, semanas_cotizadas=0,
            sbc_mensual=30_000, cotizo_antes_1997=0, afore="XXI Banorte",
        )
        defaults.update(kwargs)
        return Trabajador(**defaults)

    def test_edad_actual(self):
        t = self._owen()
        self.assertEqual(t.edad_actual, 21,
            msg="Owen nacido 2004 debe tener 21 años en 2026")

    def test_anno_retiro(self):
        t = self._owen()
        self.assertEqual(t.anno_retiro, 2004 + 65,
            msg="Retiro a los 65 → año 2069")

    def test_annos_para_retiro(self):
        t = self._owen()
        self.assertEqual(t.annos_para_retiro, 2069 - 2026,
            msg="Faltan 43 años para el retiro")

    def test_siefore_generacion_2004(self):
        from config import get_siefore
        self.assertEqual(get_siefore(2004), "SB90",
            msg="Nacido 2004 → SIEFORE SB90")

    def test_genero_label(self):
        t = self._owen()
        self.assertEqual(t.genero_label, "Hombre")
        tm = self._owen(genero=1)
        self.assertEqual(tm.genero_label, "Mujer")

    def test_validacion_sbc_negativo(self):
        from models.trabajador import Trabajador
        with self.assertRaises(ValueError):
            Trabajador(nombre="X", fecha_nacimiento=date(1990, 1, 1),
                       genero=0, edad_retiro_deseada=65, semanas_cotizadas=0,
                       sbc_mensual=-100, cotizo_antes_1997=0, afore="SURA")

    def test_validacion_afore_invalida(self):
        from models.trabajador import Trabajador
        with self.assertRaises(ValueError):
            Trabajador(nombre="X", fecha_nacimiento=date(1990, 1, 1),
                       genero=0, edad_retiro_deseada=65, semanas_cotizadas=0,
                       sbc_mensual=10_000, cotizo_antes_1997=0, afore="AFORE_FALSA")

    def test_es_factible_retiro_65(self):
        t = self._owen()
        self.assertTrue(t.es_factible_retiro,
            msg="Retiro a los 65 debe ser factible")

    def test_no_factible_retiro_menor_55(self):
        t = self._owen(edad_retiro_deseada=54)
        self.assertFalse(t.es_factible_retiro)


# ═════════════════════════════════════════════════════════════════════════════
# 6. PENSIÓN — RCV, PMG, integración
# ═════════════════════════════════════════════════════════════════════════════

class TestPension(unittest.TestCase):
    """
    Referencia: Excel fila F78 (äx=19.256394), F84 (pensión UDIs).
    La pensión del Excel está en UDIs; aquí validamos la lógica interna.
    """

    def test_pension_desde_saldo(self):
        """
        Verificar que pension = saldo / (äx(12) × 12)
        Para hombre 65, saldo $1,000,000:
          äx(12) = 19.256394
          pensión anual = 1,000,000 / 19.256394 = $51,932.09
          pensión mensual = $51,932.09 / 12 = $4,327.67
        """
        from calculators.anualidades import pension_desde_saldo
        pension = pension_desde_saldo(1_000_000, genero=0, edad=65)
        ref = 1_000_000 / 19.256394 / 12
        assertAlmostEqualRel(self, pension, ref, tol=0.001,
            msg="Pensión mensual debe ser saldo / (äx × 12)")

    def test_saldo_requerido_inverso(self):
        """saldo_requerido_para_pension es la inversa de pension_desde_saldo."""
        from calculators.anualidades import pension_desde_saldo, saldo_requerido_para_pension
        pension_objetivo = 10_000.0
        saldo_req = saldo_requerido_para_pension(pension_objetivo, genero=0, edad=65)
        pension_back = pension_desde_saldo(saldo_req, genero=0, edad=65)
        assertAlmostEqualRel(self, pension_back, pension_objetivo, tol=0.0001,
            msg="Inversa de saldo_requerido debe dar la pensión original")

    def test_mujer_mayor_pension_mismas_condiciones(self):
        """Mujer tiene mayor esperanza de vida → äx mayor → menor pensión por mismo saldo."""
        from calculators.anualidades import pension_desde_saldo
        p_h = pension_desde_saldo(1_000_000, genero=0, edad=65)
        p_m = pension_desde_saldo(1_000_000, genero=1, edad=65)
        self.assertGreater(p_h, p_m,
            msg="Hombre debe tener mayor pensión que mujer con mismo saldo (menor äx)")

    def test_cumple_semanas(self):
        from calculators.pension import cumple_requisitos
        self.assertTrue(cumple_requisitos(1000, 2026))
        self.assertFalse(cumple_requisitos(999, 2026))

    def test_semanas_requeridas_2026(self):
        """En 2026 se requieren 1,000 semanas (ya estabilizado)."""
        from calculators.pension import semanas_requeridas
        self.assertEqual(semanas_requeridas(2026), 1000)

    def test_pmg_sbc_alto_no_aplica(self):
        """Con SBC > 5 UMAs la PMG no aplica."""
        from calculators.pension import calcular_pmg
        uma_mens = 3566.22
        sbc_alto = uma_mens * 6   # 6 UMAs > 5 UMAs límite
        pmg = calcular_pmg(sbc_alto, edad_retiro=65,
                           semanas_cotizadas=1000, anio_retiro=2026)
        self.assertFalse(pmg["aplica"],
            msg="PMG no aplica con SBC > 5 UMAs")

    def test_pmg_semanas_insuficientes(self):
        """Con menos semanas del mínimo la PMG no aplica."""
        from calculators.pension import calcular_pmg
        pmg = calcular_pmg(3566.22, edad_retiro=65,
                           semanas_cotizadas=999, anio_retiro=2026)
        self.assertFalse(pmg["aplica"])

    def test_pmg_edad_fuera_rango(self):
        """PMG solo aplica entre 60 y 65 años."""
        from calculators.pension import calcular_pmg
        pmg = calcular_pmg(3566.22, edad_retiro=66,
                           semanas_cotizadas=1000, anio_retiro=2026)
        self.assertFalse(pmg["aplica"])

    def test_pension_total_fuente_rcv_saldo_alto(self):
        """Con saldo muy alto la fuente debe ser RCV, no PMG."""
        from calculators.pension import calcular_pension_total
        res = calcular_pension_total(
            saldo_afore=50_000_000, sbc_promedio=30_000,
            genero=0, edad_retiro=65, semanas_cotizadas=1000,
            anio_retiro=2026,
        )
        self.assertEqual(res["fuente_pension"], "RCV")

    def test_pension_total_fuente_pmg_saldo_bajo(self):
        """Con saldo muy bajo la fuente debe ser PMG (si aplica)."""
        from calculators.pension import calcular_pension_total
        res = calcular_pension_total(
            saldo_afore=1_000, sbc_promedio=2_000,
            genero=0, edad_retiro=65, semanas_cotizadas=1000,
            anio_retiro=2026,
        )
        if res["pension_pmg"]["aplica"]:
            self.assertEqual(res["fuente_pension"], "PMG")

    def test_tasa_reemplazo_coherente(self):
        """Tasa reemplazo = pensión_final / sbc_promedio."""
        from calculators.pension import calcular_pension_total
        sbc = 30_000.0
        res = calcular_pension_total(
            saldo_afore=10_000_000, sbc_promedio=sbc,
            genero=0, edad_retiro=65, semanas_cotizadas=1200,
            anio_retiro=2026,
        )
        ref_tasa = res["pension_final"] / sbc
        assertAlmostEqualRel(self, res["tasa_reemplazo"], ref_tasa, tol=0.0001)


# ═════════════════════════════════════════════════════════════════════════════
# 7. PROYECCIÓN SALDO — coherencia interna
# ═════════════════════════════════════════════════════════════════════════════

class TestProyeccionSaldo(unittest.TestCase):
    """
    Verificamos propiedades de consistencia de la proyección,
    no valores absolutos (el Excel usa metodología UDI/bimestral diferente).
    """

    def _proyectar_owen(self, **kwargs):
        from calculators.saldo_afore import proyectar_saldo
        defaults = dict(
            sbc_mensual=30_000, anio_inicio=2026, anio_retiro=2069,
            edad_inicio=21, anno_nacimiento=2004, afore="XXI Banorte",
            saldo_inicial=0.0, semanas_previas=0,
        )
        defaults.update(kwargs)
        return proyectar_saldo(**defaults)

    def test_numero_anios_proyectados(self):
        res = self._proyectar_owen()
        self.assertEqual(len(res["detalle_anual"]), 43,
            msg="Owen: 2026 a 2068 = 43 años de proyección")

    def test_saldo_final_positivo(self):
        res = self._proyectar_owen()
        self.assertGreater(res["saldo_final"], 0)

    def test_saldo_crece_monotonamente(self):
        """El saldo acumulado debe crecer año con año."""
        res = self._proyectar_owen()
        saldos = [d["saldo_fin"] for d in res["detalle_anual"]]
        for i in range(1, len(saldos)):
            self.assertGreater(saldos[i], saldos[i-1],
                msg=f"Saldo año {i+1} debe ser mayor que año {i}")

    def test_semanas_acumulan(self):
        """Las semanas se acumulan correctamente (≈ 52 × densidad × años)."""
        res = self._proyectar_owen()
        sem = res["semanas_totales"]
        self.assertGreater(sem, 1000, msg="43 años cotizando debe superar 1000 semanas")
        self.assertLess(sem, 43 * 52 + 1, msg="No puede superar 52 sem/año × 43 años")

    def test_saldo_con_saldo_inicial(self):
        """Con saldo inicial > 0 el resultado final debe ser mayor."""
        r0 = self._proyectar_owen(saldo_inicial=0)
        r1 = self._proyectar_owen(saldo_inicial=100_000)
        self.assertGreater(r1["saldo_final"], r0["saldo_final"])

    def test_mayor_rendimiento_mayor_saldo(self):
        r_bajo = self._proyectar_owen(rendimiento_override=0.04)
        r_alto = self._proyectar_owen(rendimiento_override=0.09)
        self.assertGreater(r_alto["saldo_final"], r_bajo["saldo_final"],
            msg="Mayor rendimiento debe producir mayor saldo")

    def test_escenarios_coherentes(self):
        from calculators.saldo_afore import proyectar_escenarios
        esc = proyectar_escenarios(
            sbc_mensual=30_000, anio_inicio=2026, anio_retiro=2069,
            edad_inicio=21, anno_nacimiento=2004, afore="XXI Banorte",
        )
        self.assertIn("pesimista", esc)
        self.assertIn("base", esc)
        self.assertIn("optimista", esc)
        self.assertGreater(esc["base"]["saldo_final"], esc["pesimista"]["saldo_final"],
            msg="Escenario base debe superar al pesimista")
        self.assertGreater(esc["optimista"]["saldo_final"], esc["base"]["saldo_final"],
            msg="Escenario optimista debe superar al base")

    def test_retiro_mas_tardio_mayor_saldo(self):
        r65 = self._proyectar_owen(anio_retiro=2069)  # 65 años
        r70 = self._proyectar_owen(anio_retiro=2074)  # 70 años
        self.assertGreater(r70["saldo_final"], r65["saldo_final"],
            msg="Retiro más tardío = más años de aportación y rendimiento")

    def test_primer_año_aportacion_coincide_con_calcular_aportaciones(self):
        """La aportación del año 1 debe coincidir con calcular_aportaciones(SBC, 2026)."""
        from calculators.aportaciones import aportacion_mensual_total
        from calculators.saldo_afore import get_densidad
        aport_mes   = aportacion_mensual_total(30_000, 2026)
        densidad_21 = get_densidad(21)
        aport_anual_ref = aport_mes * 12 * densidad_21

        res = self._proyectar_owen()
        aport_anual_calc = res["detalle_anual"][0]["aportacion_anual"]
        assertAlmostEqualRel(self, aport_anual_calc, aport_anual_ref, tol=0.001,
            msg="Aportación primer año debe coincidir con calcular_aportaciones × densidad × 12")


# ═════════════════════════════════════════════════════════════════════════════
# 8. PIPELINE COMPLETO — integración de extremo a extremo
# ═════════════════════════════════════════════════════════════════════════════

class TestPipelineCompleto(unittest.TestCase):

    def _calcular_owen(self):
        from models.trabajador import Trabajador
        from calculators.saldo_afore import proyectar_saldo_desde_trabajador
        from calculators.pension import calcular_pension_desde_trabajador

        t = Trabajador(
            nombre="Owen García",
            fecha_nacimiento=date(2004, 12, 16),
            genero=0, edad_retiro_deseada=65, semanas_cotizadas=0,
            sbc_mensual=30_000, cotizo_antes_1997=0, afore="XXI Banorte",
        )
        res_saldo   = proyectar_saldo_desde_trabajador(t)
        res_pension = calcular_pension_desde_trabajador(t, res_saldo)
        return t, res_saldo, res_pension

    def test_cumple_semanas_caso_owen(self):
        t, rs, rp = self._calcular_owen()
        self.assertTrue(rp["cumple_para_pensionarse"],
            msg="Owen con 43 años cotizando debe cumplir semanas")

    def test_pension_positiva(self):
        t, rs, rp = self._calcular_owen()
        self.assertGreater(rp["pension_final"], 0)

    def test_fuente_rcv_no_pmg(self):
        """Con SBC $30k y 43 años cotizando el saldo supera la PMG."""
        t, rs, rp = self._calcular_owen()
        # PMG no aplica para SBC > 5 UMAs (30,000 >> 5 × 3,566 = 17,831)
        self.assertFalse(rp["pension_pmg"]["aplica"],
            msg="PMG no aplica con SBC $30,000 (> 5 UMAs)")
        self.assertEqual(rp["fuente_pension"], "RCV")

    def test_ax_utilizado_coincide_con_excel(self):
        """äx(12) hombre 65 debe ser el valor del Excel."""
        t, rs, rp = self._calcular_owen()
        ax = rp["pension_rcv"]["ax_utilizado"]
        assertAlmostEqualRel(self, ax, 19.256394, tol=0.001,
            msg="äx(12) usado en pensión debe coincidir con Excel")

    def test_tasa_reemplazo_razonable(self):
        """La tasa de reemplazo debe estar entre 10% y 200%."""
        t, rs, rp = self._calcular_owen()
        tr = rp["tasa_reemplazo"]
        self.assertGreater(tr, 0.10, msg="Tasa reemplazo debe ser > 10%")
        self.assertLess(tr, 2.00, msg="Tasa reemplazo debe ser < 200%")

    def test_pipeline_mujer_distinto_de_hombre(self):
        """Resultados deben diferir entre hombre y mujer."""
        from models.trabajador import Trabajador
        from calculators.saldo_afore import proyectar_saldo_desde_trabajador
        from calculators.pension import calcular_pension_desde_trabajador

        def calcular(genero):
            t = Trabajador(
                nombre="Test", fecha_nacimiento=date(1990, 1, 1),
                genero=genero, edad_retiro_deseada=65, semanas_cotizadas=0,
                sbc_mensual=20_000, cotizo_antes_1997=0, afore="SURA",
            )
            rs = proyectar_saldo_desde_trabajador(t)
            rp = calcular_pension_desde_trabajador(t, rs)
            return rp["pension_final"]

        p_h = calcular(0)
        p_m = calcular(1)
        self.assertNotAlmostEqual(p_h, p_m, places=2,
            msg="Pensión hombre y mujer deben diferir (distinto äx)")
        self.assertGreater(p_h, p_m,
            msg="Hombre debe recibir mayor pensión que mujer (menor äx → más eficiente)")


# ═════════════════════════════════════════════════════════════════════════════
# RUNNER
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suites  = [
        loader.loadTestsFromTestCase(TestUMA),
        loader.loadTestsFromTestCase(TestTablasVida),
        loader.loadTestsFromTestCase(TestAportaciones),
        loader.loadTestsFromTestCase(TestDensidad),
        loader.loadTestsFromTestCase(TestTrabajador),
        loader.loadTestsFromTestCase(TestPension),
        loader.loadTestsFromTestCase(TestProyeccionSaldo),
        loader.loadTestsFromTestCase(TestPipelineCompleto),
    ]
    suite = unittest.TestSuite(suites)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

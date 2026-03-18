"""
models/trabajador.py — Dataclass central con todos los datos del trabajador
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AFORES, SUPUESTOS_DEFAULT


@dataclass
class Trabajador:
    # ── Datos biométricos ──────────────────────────────────────────────────
    nombre:              str
    fecha_nacimiento:    date
    genero:              int        # 0 = Hombre, 1 = Mujer
    edad_retiro_deseada: int = 65

    # ── Datos laborales ────────────────────────────────────────────────────
    semanas_cotizadas:   int   = 0
    sbc_mensual:         float = 0.0      # Salario Base de Cotización mensual actual
    cotizo_antes_1997:   int   = 0        # 0 = No, 1 = Sí

    # ── Datos del cónyuge (para cálculo de pensión de viudez) ──────────────
    casado:              int   = 0        # 0 = No, 1 = Sí
    genero_conyuge:      int   = 0        # 0 = Hombre, 1 = Mujer
    edad_conyuge:        int   = 0

    # ── AFORE ──────────────────────────────────────────────────────────────
    afore:               str   = "XXI Banorte"

    # ── Supuestos macroeconómicos (sobreescribibles por el usuario) ────────
    inflacion_anual:     float = SUPUESTOS_DEFAULT["inflacion_anual"]
    crecimiento_sbc:     float = SUPUESTOS_DEFAULT["crecimiento_sbc"]
    rendimiento_afore:   Optional[float] = None   # None = usar CONSAR
    comision_afore:      Optional[float] = None   # None = usar CONSAR

    # ── Campos calculados (se llenan automáticamente al hacer @property) ──
    _anno_calculo: int = field(default_factory=lambda: date.today().year, init=False, repr=False)

    # ──────────────────────────────────────────────────────────────────────
    # PROPIEDADES CALCULADAS
    # ──────────────────────────────────────────────────────────────────────

    @property
    def edad_actual(self) -> int:
        hoy = date.today()
        return (
            hoy.year - self.fecha_nacimiento.year
            - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        )

    @property
    def anno_nacimiento(self) -> int:
        return self.fecha_nacimiento.year

    @property
    def anno_retiro(self) -> int:
        return self.fecha_nacimiento.year + self.edad_retiro_deseada

    @property
    def annos_para_retiro(self) -> int:
        return self.anno_retiro - self._anno_calculo

    @property
    def es_factible_retiro(self) -> bool:
        """El trabajador puede retirarse: edad ≥ 55 y el retiro aún no pasó."""
        return self.edad_retiro_deseada >= 55 and self.annos_para_retiro > 0

    @property
    def genero_label(self) -> str:
        return "Mujer" if self.genero == 1 else "Hombre"

    @property
    def afore_valida(self) -> bool:
        return self.afore in AFORES

    # ──────────────────────────────────────────────────────────────────────
    # VALIDACIÓN
    # ──────────────────────────────────────────────────────────────────────

    def __post_init__(self):
        errores = []

        if not self.nombre.strip():
            errores.append("El nombre no puede estar vacío.")

        if self.fecha_nacimiento >= date.today():
            errores.append("La fecha de nacimiento debe ser anterior a hoy.")

        if self.genero not in (0, 1):
            errores.append("Género debe ser 0 (Hombre) o 1 (Mujer).")

        if not (1 <= self.edad_retiro_deseada <= 100):
            errores.append("La edad de retiro debe ser un valor positivo razonable.")

        if self.semanas_cotizadas < 0:
            errores.append("Las semanas cotizadas no pueden ser negativas.")

        if self.sbc_mensual < 0:
            errores.append("El SBC no puede ser negativo.")

        if self.cotizo_antes_1997 not in (0, 1):
            errores.append("cotizo_antes_1997 debe ser 0 o 1.")

        if self.casado not in (0, 1):
            errores.append("casado debe ser 0 o 1.")

        if self.casado == 1:
            if self.genero_conyuge not in (0, 1):
                errores.append("Género del cónyuge debe ser 0 o 1.")
            if not (18 <= self.edad_conyuge <= 100):
                errores.append("Edad del cónyuge debe estar entre 18 y 100.")

        if self.afore not in AFORES:
            errores.append(f"AFORE '{self.afore}' no reconocida. Opciones: {AFORES}")

        if errores:
            raise ValueError("Errores en datos del trabajador:\n" + "\n".join(f"  • {e}" for e in errores))

    # ──────────────────────────────────────────────────────────────────────
    # SERIALIZACIÓN
    # ──────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "nombre":               self.nombre,
            "fecha_nacimiento":     self.fecha_nacimiento.isoformat(),
            "genero":               self.genero,
            "genero_label":         self.genero_label,
            "edad_actual":          self.edad_actual,
            "anno_nacimiento":      self.anno_nacimiento,
            "edad_retiro_deseada":  self.edad_retiro_deseada,
            "anno_retiro":          self.anno_retiro,
            "annos_para_retiro":    self.annos_para_retiro,
            "es_factible_retiro":   self.es_factible_retiro,
            "semanas_cotizadas":    self.semanas_cotizadas,
            "sbc_mensual":          self.sbc_mensual,
            "cotizo_antes_1997":    self.cotizo_antes_1997,
            "casado":               self.casado,
            "genero_conyuge":       self.genero_conyuge,
            "edad_conyuge":         self.edad_conyuge,
            "afore":                self.afore,
            "inflacion_anual":      self.inflacion_anual,
            "crecimiento_sbc":      self.crecimiento_sbc,
            "rendimiento_afore":    self.rendimiento_afore,
            "comision_afore":       self.comision_afore,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Trabajador":
        data = data.copy()
        if isinstance(data.get("fecha_nacimiento"), str):
            data["fecha_nacimiento"] = date.fromisoformat(data["fecha_nacimiento"])
        # Quitar campos calculados que no son parámetros del constructor
        for key in ("genero_label", "edad_actual", "anno_nacimiento",
                    "anno_retiro", "annos_para_retiro", "es_factible_retiro"):
            data.pop(key, None)
        return cls(**data)

    def __str__(self) -> str:
        return (
            f"Trabajador: {self.nombre} | {self.genero_label} | "
            f"Edad: {self.edad_actual} | Retiro: {self.anno_retiro} "
            f"({self.annos_para_retiro} años) | SBC: ${self.sbc_mensual:,.2f} | "
            f"Semanas: {self.semanas_cotizadas} | AFORE: {self.afore}"
        )

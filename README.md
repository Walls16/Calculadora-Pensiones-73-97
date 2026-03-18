# Calculadora de Retiro LSS-1997

Herramienta actuarial para proyectar la pensión bajo el régimen de la Ley del Seguro Social 1997 (AFORE/RCV), con datos en tiempo real desde INEGI, Banxico y CONSAR.

---

## Instalación rápida

```bash
# 1. Clonar / copiar el proyecto
cd calculadora_retiro/

# 2. Instalar dependencias
pip install streamlit plotly pandas requests beautifulsoup4 lxml openpyxl

# 3. Inicializar caché local (solo la primera vez)
python seed_cache.py

# 4. Lanzar la app
streamlit run app.py
```

---

## Estructura del proyecto

```
calculadora_retiro/
├── app.py                          # Interfaz Streamlit (5 pestañas)
├── config.py                       # Constantes legales, tablas, parámetros
├── seed_cache.py                   # Inicializa caché sin internet
├── requirements.txt
│
├── models/
│   └── trabajador.py               # Dataclass con validación automática
│
├── calculators/
│   ├── aportaciones.py             # Cuotas IMSS (retiro, trabajador, cesantía)
│   ├── saldo_afore.py              # Proyección año a año + escenarios
│   ├── anualidades.py              # Tablas de conmutación, äx(12), anualidad conjunta
│   └── pension.py                  # RCV vs PMG, decisión final, 4to Transitorio
│
├── data_fetchers/
│   ├── uma.py                      # INEGI → UMA diaria/mensual/anual
│   ├── udi.py                      # Banxico SIE API → valor UDI
│   ├── afore_rendimientos.py       # CONSAR Excel → rendimientos por AFORE/SIEFORE
│   ├── afore_comisiones.py         # CONSAR → comisiones anuales
│   └── tablas_vida.py              # EMSSA-09 tasa mejora 2023 (exactas del Excel fuente)
│
├── cache/                          # Archivos JSON/CSV locales (auto-generados)
│
└── tests/
    └── test_calculators.py         # 66 tests — todos pasando ✅
```

---

## Funcionalidades

### Pestañas de la app

| Pestaña | Contenido |
|---|---|
| **Resumen** | 4 KPIs + datos de referencia UMA/rendimiento/comisión |
| **Aportaciones** | Desglose cuotas IMSS + evolución transitorio 2023–2031 |
| **Proyección Saldo** | Gráfica acumulación + tabla por quinquenio |
| **Pensión** | RCV vs PMG + comparativa entre las 10 AFOREs |
| **Escenarios** | Pesimista / Base / Optimista con gráficas |

### Lógica actuarial

- **Aportaciones**: cuotas exactas del 2do y 3er Transitorio (2023–2031+) con 8 brackets salariales por año
- **Saldo**: rendimiento bruto − comisión = neto; densidad de cotización por edad (hoja Excel fuente)
- **Anualidades**: tablas de conmutación EMSSA-09 con tasa técnica 2.34% y pagos mensuales m=12
- **Pensión**: max(RCV, PMG); PMG solo aplica ≤ 5 UMAs, edad 60–65, semanas mínimas
- **4to Transitorio**: semanas escalonadas 750→1,000 (2021–2030) solo para cotizantes pre-1997
- **Anualidad conjunta**: pensión de viudez al 90% para cónyuge (Art. 130 LSS)

### Fuentes de datos

| Dato | Fuente | Caché |
|---|---|---|
| UMA | INEGI (scraping) | Anual (feb), 31 días |
| UDI | Banxico SIE API (`SP68257`) | Diaria, incremental |
| Rendimientos AFORE | CONSAR Excel SIEFORE | Mensual, 35 días |
| Comisiones AFORE | CONSAR tabla HTML | Anual (ene), 60 días |
| Tablas qx | EMSSA-09 hardcoded (222 valores exactos) | Permanente |

---

## Tests

```bash
python -m pytest tests/ -v
# o
python tests/test_calculators.py
```

66 tests en 8 grupos: UMA, Tablas de vida, Aportaciones, Densidad, Trabajador, Pensión, Proyección Saldo, Pipeline completo.

---

## Variables de entorno opcionales

```bash
# Token Banxico para la API de UDI (sin token usa fallback anual)
export BANXICO_TOKEN="tu_token_aqui"
```

Regístrate en https://www.banxico.org.mx/SieAPIRest/ para obtener un token gratuito.

---

## Valores verificados contra el Excel fuente

| Dato | Calculadora | Excel fuente |
|---|---|---|
| UMA mensual 2026 | $3,566.22 | $3,566.22 ✅ |
| Aportación SBC=$30,000 en 2026 | $3,191.40 | $3,191.40 ✅ |
| äx(12) Hombre 65 | 19.2566 | 19.2564 ✅ (Δ < 0.001) |
| äx(12) Mujer 65 | 20.6603 | 20.6601 ✅ (Δ < 0.001) |
| Tasa cesantía/vejez bracket >4UMAs 2026 | 7.513% | 7.513% ✅ |

---

## Advertencia

Esta herramienta es orientativa. Los resultados dependen de supuestos sobre rendimientos futuros, inflación y densidad de cotización. Consulta a un asesor de retiro certificado antes de tomar decisiones financieras.

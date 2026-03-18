"""
config.py — Constantes globales, URLs y parámetros de la Calculadora de Retiro LSS-1997
"""

from pathlib import Path

# ─────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CACHE_DIR  = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "outputs"

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Archivos de cache
CACHE_UMA              = CACHE_DIR / "uma.json"
CACHE_UDI              = CACHE_DIR / "udis.csv"
CACHE_AFORE_REND       = CACHE_DIR / "afore_rendimientos.csv"
CACHE_AFORE_COM        = CACHE_DIR / "afore_comisiones.json"
CACHE_TABLAS_VIDA      = CACHE_DIR / "tablas_vida.json"

# ─────────────────────────────────────────────
# URLs DE FUENTES EXTERNAS
# ─────────────────────────────────────────────
URL_UMA = "https://www.inegi.org.mx/temas/uma/"

# Banxico SIE REST API — serie SP68257 = Valor UDI diario
# Docs: https://www.banxico.org.mx/SieAPIRest/service/v1/doc/consultaDatosSerieRango
URL_BANXICO_UDI = (
    "https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
    "SP68257/datos/{fecha_ini}/{fecha_fin}"
)
BANXICO_TOKEN = ""  # Se puede poner aquí o en variable de entorno BANXICO_TOKEN
# Token gratuito en: https://www.banxico.org.mx/SieAPIRest/service/v1/token

# CONSAR — Rendimientos de SIEFOREs (descarga Excel directo)
URL_CONSAR_RENDIMIENTOS = (
    "https://www.consar.gob.mx/gobmx/aplicativo/siset/tdf/FondosGeneracionales.aspx"
)

# CONSAR — Comisiones (página con tabla HTML)
URL_CONSAR_COMISIONES = (
    "https://www.gob.mx/consar/articulos/"
    "comisiones-que-cobran-las-afores"
)

# INEGI — UMA histórica (respaldo JSON si el scraping falla)
URL_INEGI_UMA_JSON = (
    "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/"
    "jsonxml/INDICATOR/6207019839/es/0700/false/BIE/2.0/"
    "?type=json"
)

# ─────────────────────────────────────────────
# PARÁMETROS ACTUARIALES FIJOS
# ─────────────────────────────────────────────

# Tasa de interés técnico para anualidades (CNSF)
TASA_INTERES_TECNICO = 0.0234

# Número máximo de pagos por año en anualidades (mensual = 12)
PAGOS_POR_ANIO = 12

# Edad máxima en tablas de mortalidad
EDAD_MAXIMA = 110

# ─────────────────────────────────────────────
# PARÁMETROS IMSS LSS-1997
# ─────────────────────────────────────────────

# Salario máximo cotizable: 25 UMAs mensuales
FACTOR_SALARIO_MAXIMO_COTIZABLE = 25

# Semanas mínimas para pensión (régimen 1997 puro)
SEMANAS_MINIMAS_RCV = 1000

# Fecha de inicio del régimen 1997
FECHA_INICIO_1997 = "1997-07-01"

# Cuotas FIJAS (no cambian con la reforma 2020)
CUOTAS_FIJAS = {
    "retiro":               0.02,       # 2% patrón — no cambia
    "trabajador":           0.01125,    # 1.125% trabajador — no cambia
    "cuota_social_umbral":  1.0,        # Solo aplica hasta 1 UMA
}

# Cuota patronal CESANTÍA Y VEJEZ (transitorio 2do/3er):
# Varía por año Y por bracket salarial (múltiplos de UMA)
# Estructura: {año: {bracket_label: tasa}}
# Brackets: "1SM", "1.01-1.50", "1.51-2.00", "2.01-2.50",
#           "2.51-3.00", "3.01-3.50", "3.51-4.00", "4.01+"
CUOTAS_CESANTIA_VEJEZ = {
    2023: {"1SM": 0.0315, "1.01-1.50": 0.03281, "1.51-2.00": 0.03575,
           "2.01-2.50": 0.03751, "2.51-3.00": 0.03869, "3.01-3.50": 0.03953,
           "3.51-4.00": 0.04016, "4.01+":     0.04241},
    2024: {"1SM": 0.0315, "1.01-1.50": 0.03413, "1.51-2.00": 0.04000,
           "2.01-2.50": 0.04353, "2.51-3.00": 0.04588, "3.01-3.50": 0.04756,
           "3.51-4.00": 0.04882, "4.01+":     0.05331},
    2025: {"1SM": 0.0315, "1.01-1.50": 0.03544, "1.51-2.00": 0.04426,
           "2.01-2.50": 0.04954, "2.51-3.00": 0.05307, "3.01-3.50": 0.05559,
           "3.51-4.00": 0.05747, "4.01+":     0.06422},
    2026: {"1SM": 0.0315, "1.01-1.50": 0.03676, "1.51-2.00": 0.04851,
           "2.01-2.50": 0.05556, "2.51-3.00": 0.06026, "3.01-3.50": 0.06361,
           "3.51-4.00": 0.06613, "4.01+":     0.07513},
    2027: {"1SM": 0.0315, "1.01-1.50": 0.03807, "1.51-2.00": 0.05276,
           "2.01-2.50": 0.06157, "2.51-3.00": 0.06745, "3.01-3.50": 0.07164,
           "3.51-4.00": 0.07479, "4.01+":     0.08603},
    2028: {"1SM": 0.0315, "1.01-1.50": 0.03939, "1.51-2.00": 0.05701,
           "2.01-2.50": 0.06759, "2.51-3.00": 0.07464, "3.01-3.50": 0.07967,
           "3.51-4.00": 0.08345, "4.01+":     0.09694},
    2029: {"1SM": 0.0315, "1.01-1.50": 0.04070, "1.51-2.00": 0.06126,
           "2.01-2.50": 0.07360, "2.51-3.00": 0.08183, "3.01-3.50": 0.08770,
           "3.51-4.00": 0.09211, "4.01+":     0.10784},
    2030: {"1SM": 0.0315, "1.01-1.50": 0.04202, "1.51-2.00": 0.06552,
           "2.01-2.50": 0.07962, "2.51-3.00": 0.08902, "3.01-3.50": 0.09573,
           "3.51-4.00": 0.10077, "4.01+":     0.11875},
}
# A partir de 2031 la tasa se estabiliza en el nivel final (11.875% para 4.01+)
CUOTA_CESANTIA_VEJEZ_FINAL = {
    "1SM": 0.0315, "1.01-1.50": 0.04202, "1.51-2.00": 0.06552,
    "2.01-2.50": 0.07962, "2.51-3.00": 0.08902, "3.01-3.50": 0.09573,
    "3.51-4.00": 0.10077, "4.01+":     0.11875,
}

# ─────────────────────────────────────────────
# 4TO TRANSITORIO — SEMANAS REQUERIDAS POR AÑO
# ─────────────────────────────────────────────
SEMANAS_4TO_TRANSITORIO = {
    2021: 750,  2022: 775,  2023: 800,  2024: 825,
    2025: 850,  2026: 875,  2027: 900,  2028: 925,
    2029: 950,  2030: 975,
}
# De 2031 en adelante: 1000 semanas
SEMANAS_4TO_TRANSITORIO_FINAL = 1000

# ─────────────────────────────────────────────
# TABLA PMG (Pensión Mínima Garantizada) ART. 170
# Valores base 2025 en pesos — se actualizan con INPC
# Estructura: {bracket_salarial: {edad: {semanas: monto}}}
# ─────────────────────────────────────────────
PMG_BASE_2025 = {
    "1SM-1.99UMA": {
        60: {1000: 2622, 1025: 2716, 1050: 2809, 1075: 2903, 1100: 2997,
             1125: 3090, 1150: 3184, 1175: 3278, 1200: 3371, 1225: 3465, 1250: 3559},
        61: {1000: 2660, 1025: 2753, 1050: 2847, 1075: 2941, 1100: 3034,
             1125: 3128, 1150: 3221, 1175: 3315, 1200: 3409, 1225: 3502, 1250: 3596},
        62: {1000: 2697, 1025: 2791, 1050: 2884, 1075: 2978, 1100: 3072,
             1125: 3165, 1150: 3259, 1175: 3353, 1200: 3446, 1225: 3540, 1250: 3634},
        63: {1000: 2734, 1025: 2828, 1050: 2922, 1075: 3015, 1100: 3109,
             1125: 3203, 1150: 3296, 1175: 3390, 1200: 3484, 1225: 3577, 1250: 3671},
        64: {1000: 2772, 1025: 2866, 1050: 2959, 1075: 3053, 1100: 3147,
             1125: 3240, 1150: 3334, 1175: 3427, 1200: 3521, 1225: 3615, 1250: 3708},
        65: {1000: 2809, 1025: 2903, 1050: 2997, 1075: 3090, 1100: 3184,
             1125: 3278, 1150: 3371, 1175: 3465, 1200: 3559, 1225: 3652, 1250: 3746},
    },
    "2-2.99UMA": {
        60: {1000: 3409, 1025: 3530, 1050: 3652, 1075: 3774, 1100: 3896,
             1125: 4017, 1150: 4139, 1175: 4261, 1200: 4383, 1225: 4504, 1250: 4626},
        61: {1000: 3457, 1025: 3579, 1050: 3701, 1075: 3823, 1100: 3944,
             1125: 4066, 1150: 4188, 1175: 4310, 1200: 4431, 1225: 4553, 1250: 4675},
        62: {1000: 3506, 1025: 3628, 1050: 3750, 1075: 3871, 1100: 3993,
             1125: 4115, 1150: 4237, 1175: 4358, 1200: 4480, 1225: 4602, 1250: 4724},
        63: {1000: 3555, 1025: 3677, 1050: 3798, 1075: 3920, 1100: 4042,
             1125: 4164, 1150: 4285, 1175: 4407, 1200: 4529, 1225: 4651, 1250: 4772},
        64: {1000: 3604, 1025: 3125, 1050: 3847, 1075: 3969, 1100: 4091,
             1125: 4212, 1150: 4334, 1175: 4456, 1200: 4577, 1225: 4699, 1250: 4821},
        65: {1000: 3652, 1025: 3774, 1050: 3896, 1075: 4017, 1100: 4139,
             1125: 4261, 1150: 4383, 1175: 4504, 1200: 4626, 1225: 4748, 1250: 4870},
    },
    "3-3.99UMA": {
        60: {1000: 4195, 1025: 4345, 1050: 4495, 1075: 4645, 1100: 4795,
             1125: 4945, 1150: 5094, 1175: 5244, 1200: 5394, 1225: 5544, 1250: 5694},
        61: {1000: 4255, 1025: 4405, 1050: 4555, 1075: 4705, 1100: 4855,
             1125: 5005, 1150: 5154, 1175: 5304, 1200: 5454, 1225: 5604, 1250: 5754},
        62: {1000: 4315, 1025: 4465, 1050: 4615, 1075: 4765, 1100: 4915,
             1125: 5064, 1150: 5214, 1175: 5364, 1200: 5514, 1225: 5664, 1250: 5814},
        63: {1000: 4375, 1025: 4525, 1050: 4675, 1075: 4825, 1100: 4975,
             1125: 5124, 1150: 5274, 1175: 5424, 1200: 5574, 1225: 5724, 1250: 5874},
        64: {1000: 4435, 1025: 4585, 1050: 4735, 1075: 4885, 1100: 5034,
             1125: 5184, 1150: 5334, 1175: 5484, 1200: 5634, 1225: 5784, 1250: 5933},
        65: {1000: 4495, 1025: 4645, 1050: 4795, 1075: 4945, 1100: 5094,
             1125: 5244, 1150: 5394, 1175: 5544, 1200: 5694, 1225: 5844, 1250: 5993},
    },
    "4-4.99UMA": {
        60: {1000: 4982, 1025: 5160, 1050: 5338, 1075: 5516, 1100: 5694,
             1125: 5872, 1150: 6050, 1175: 6228, 1200: 6405, 1225: 6583, 1250: 6761},
        61: {1000: 5053, 1025: 5231, 1050: 5409, 1075: 5587, 1100: 5765,
             1125: 5943, 1150: 6121, 1175: 6299, 1200: 6477, 1225: 6655, 1250: 6832},
        62: {1000: 5124, 1025: 5302, 1050: 5480, 1075: 5658, 1100: 5836,
             1125: 6014, 1150: 6192, 1175: 6370, 1200: 6548, 1225: 6726, 1250: 6904},
        63: {1000: 5196, 1025: 5373, 1050: 5551, 1075: 5729, 1100: 5907,
             1125: 6085, 1150: 6263, 1175: 6441, 1200: 6619, 1225: 6797, 1250: 6975},
        64: {1000: 5267, 1025: 5445, 1050: 5623, 1075: 5801, 1100: 5978,
             1125: 6156, 1150: 6334, 1175: 6512, 1200: 6690, 1225: 6868, 1250: 7046},
        65: {1000: 5338, 1025: 5516, 1050: 5694, 1075: 5872, 1100: 6050,
             1125: 6228, 1150: 6405, 1175: 6583, 1200: 6761, 1225: 6939, 1250: 7117},
    },
}

# ─────────────────────────────────────────────
# AFORES REGISTRADAS
# ─────────────────────────────────────────────
AFORES = [
    "Azteca",
    "Citibanamex",
    "Coppel",
    "Inbursa",
    "Invercap",
    "PensionISSSTE",
    "Principal",
    "Profuturo GNP",
    "SURA",
    "XXI Banorte",
]

# ─────────────────────────────────────────────
# SIEFORES POR GENERACIÓN (año de nacimiento → SB)
# ─────────────────────────────────────────────
def get_siefore(anio_nacimiento: int) -> str:
    if anio_nacimiento >= 1994:
        return "SB90"      # Menores de ~30 años → mayor riesgo
    elif anio_nacimiento >= 1979:
        return "SB67-79"
    elif anio_nacimiento >= 1969:
        return "SB60-66"
    elif anio_nacimiento >= 1964:
        return "SB55-59"
    elif anio_nacimiento >= 1960:
        return "SB50-54"
    else:
        return "SB0"       # Mayores, ya en etapa conservadora

# ─────────────────────────────────────────────
# SUPUESTOS MACROECONÓMICOS (ajustables por usuario)
# ─────────────────────────────────────────────
SUPUESTOS_DEFAULT = {
    "inflacion_anual":      0.0350,   # 3.5% meta Banxico
    "crecimiento_sbc":      0.0620,   # Crecimiento histórico SBC real + inflación
    "rendimiento_afore":    None,     # None = usar promedio CONSAR del fondo correspondiente
    "comision_afore":       None,     # None = usar dato CONSAR del año en curso
}

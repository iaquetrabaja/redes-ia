"""Piezas compartidas por todas las herramientas: palabras, números y normalización.

Todo funciona con la librería estándar. El texto se compara sin tildes y en
minúsculas (así «vídeo» y «video» cuentan igual), pero lo que se devuelve
siempre es el texto original.
"""

import json
import os
import re
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ"
PALABRA_RE = re.compile(rf"[{LETRAS}0-9€$%'’]+(?:[.,]\d+)*")
# Nombre propio: mayúscula que no abre frase. En español se escriben en mayúscula
# muchas menos palabras que en inglés, así que esto casi siempre es una marca,
# una persona o un sitio.
PROPIO_RE = re.compile(r"(?<!^)(?<![.!?¿¡:\n]\s)(?<![.!?¿¡:\n])\b[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]{2,}\b",
                       re.MULTILINE)
HASHTAG_RE = re.compile(r"(?:^|\s)(#[\wÁÉÍÓÚÜÑáéíóúüñ]+)")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
CIFRA_RE = re.compile(
    r"[$€]\s?\d[\d.,]*"                                   # dinero con símbolo delante
    r"|\b\d[\d.,]*\s?(?:%|€|\$|k\b|x\b|h\b|min\b|seg\b|s\b|euros?\b|pavos\b|horas?\b"
    r"|minutos?\b|segundos?\b|d[ií]as?\b|semanas?\b|meses\b|mes\b|a[ñn]os?\b)?",
    re.IGNORECASE)

# Los números dichos en voz alta también son concretos: «veinte mil euros»
# cuenta igual que «20.000 €». «Uno» y «primero» no están a propósito: casi
# siempre son relleno, no una cantidad.
NUMEROS_HABLADOS = {
    "cero", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "veinte", "treinta",
    "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa", "cien",
    "ciento", "doscientos", "trescientos", "quinientos", "mil", "millon",
    "millones", "docena", "mitad", "doble", "triple", "medio",
}
PALABRAS_DINERO = {
    "euros", "euro", "pavos", "dolares", "dolar", "centimos", "facturacion",
    "beneficio", "beneficios", "sueldo", "alquiler", "factura", "facturas",
    "precio", "presupuesto", "gratis", "millonario",
}


def sin_tildes(texto):
    """«Vídeo» -> «video». Se mantiene la ñ, que no es una tilde."""
    texto = texto.replace("ñ", "\x00").replace("Ñ", "\x01")
    base = unicodedata.normalize("NFD", texto)
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return base.replace("\x00", "ñ").replace("\x01", "Ñ")


def normal(texto):
    """Minúsculas y sin tildes: la forma en la que se compara todo."""
    return sin_tildes(texto or "").lower()


def palabras(texto):
    # «18.000» y «2,5» son una palabra cuando se dicen, así que aquí también.
    return PALABRA_RE.findall(texto or "")


def palabras_norm(texto):
    return [normal(p).strip("'’") for p in palabras(texto)]


def cargar_json(nombre):
    with open(os.path.join(AQUI, nombre), encoding="utf-8") as fh:
        return json.load(fh)


def acotar(n):
    return max(0.0, min(100.0, float(n)))


def escala(valor, humano, maquina):
    """Lleva un valor a 0-100: `humano` -> 100 y `maquina` -> 0."""
    if humano == maquina:
        return 50.0
    return acotar((valor - maquina) / (humano - maquina) * 100)


def barra(score, ancho=24):
    lleno = round(score / 100 * ancho)
    return "#" * lleno + "." * (ancho - lleno)


def leer_entrada(ruta):
    import sys
    if ruta in (None, "-"):
        return sys.stdin.read()
    with open(ruta, encoding="utf-8") as fh:
        return fh.read()


def consola_utf8():
    """En Windows la consola a veces no es UTF-8 y las tildes revientan el print."""
    import sys
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

# Siglas y marcas con mayúsculas por dentro: IA, GPT, ChatGPT, TikTok, iPhone.
MARCA_RE = re.compile(r"\b(?:[A-Z]{2,}[A-Za-z0-9]*|[A-Za-z][a-z0-9]*[A-Z][A-Za-z0-9]*)\b")

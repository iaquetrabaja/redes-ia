"""detectar.py - cinco comprobaciones que puntúan cuánto parece escrito por una máquina.

Qué es: cinco heurísticas locales basadas en las señales que miran los
detectores públicos: variación del largo de las frases, cosas concretas,
muletillas, huella tipográfica y voz. Todo se calcula aquí, con el texto, y no
se sube nada a ningún sitio.

Qué NO es: GPTZero, Originality, Copyleaks, Winston ni Turnitin. No llama a
sus APIs y no puede prometer su veredicto. Mide lo mismo de fondo, y por eso
arreglar lo que marca suele mover también sus números, pero esa es toda la
promesa.

Cada comprobación da una puntuación HUMANA de 0 a 100. Más es mejor.

Uso
  python -m herramientas.detectar borrador.txt
  python -m herramientas.detectar antes.txt despues.txt      # compara dos versiones
  python -m herramientas.detectar borrador.txt --json
"""

import argparse
import json
import re
import statistics
import sys
import unicodedata

from ._comun import (CIFRA_RE, MARCA_RE, PROPIO_RE, acotar, barra, consola_utf8, escala,
                     leer_entrada, normal)
from .humanizar import lexico, patron_flexible

FRASE_RE = re.compile(r"[^.!?\n]+[.!?]*")
PALABRA_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+")
PERSONA_RE = re.compile(r"\b(?:yo|me|mi|mis|conmigo|nosotros|nosotras|nos|nuestro|nuestra|nuestros|"
                        r"nuestras|tu|tus|te|ti|contigo|vosotros|vosotras|os|vuestro|vuestra|usted)\b")
# En español no hay contracciones como en inglés; lo que delata el registro oral
# son las muletillas de verdad de la gente, las preguntas y exclamaciones, y
# las frases cortas.
ORAL_RE = re.compile(r"\b(?:vale|pues|mira|o sea|la verdad|en plan|oye|ojo|venga|bueno|vamos|"
                     r"fijate|tio|tia|anda|claro|eh|joder|hostia|madre mia|que va)\b")

CHECKS = ["burstiness", "especificidad", "muletillas", "huella", "voz"]
NOMBRES = {"burstiness": "variación", "especificidad": "concreción", "muletillas": "muletillas",
           "huella": "huella", "voz": "voz"}


def _frases(texto):
    return [f.strip() for f in FRASE_RE.findall(texto) if len(f.split()) > 2]


def _palabras(texto):
    return PALABRA_RE.findall(texto)


def _burstiness(texto):
    largos = [len(f.split()) for f in _frases(texto)]
    if len(largos) < 4:
        return 50.0, "muy corto para juzgarlo"
    media = statistics.mean(largos)
    cv = statistics.pstdev(largos) / media if media else 0
    return escala(cv, humano=0.70, maquina=0.22), f"variación {cv:.2f} en {len(largos)} frases (lo humano: 0,55 o más)"


def _especificidad(texto):
    p = _palabras(texto)
    if len(p) < 25:
        return 50.0, "muy corto para juzgarlo"
    n = (len([c for c in CIFRA_RE.findall(texto) if re.search(r"\d", c)])
         + len(set(PROPIO_RE.findall(texto))) + len(set(MARCA_RE.findall(texto))))
    densidad = n * 100 / len(p)
    return escala(densidad, humano=6.0, maquina=0.5), f"{n} cosas concretas, {densidad:.1f} por cada 100 palabras (lo humano: 4 o más)"


def _muletillas(texto, lex):
    p = _palabras(texto)
    if not p:
        return 50.0, "vacío", []
    hits, vistas = 0, []
    for e in lex["palabras"] + lex["frases"]:
        n = len(patron_flexible(e["busca"]).findall(texto))
        if n:
            hits += n
            vistas.append(e["busca"])
    densidad = hits * 100 / len(p)
    detalle = f"{hits} muletillas, {densidad:.1f} por cada 100 palabras"
    if vistas:
        detalle += " (" + ", ".join(sorted(vistas)[:4]) + (", ..." if len(vistas) > 4 else "") + ")"
    return escala(densidad, humano=0.0, maquina=4.0), detalle, vistas


def _huella(texto):
    invisibles = sum(1 for c in texto if unicodedata.category(c) == "Cf")
    rayas = len(re.findall(r"(?<!^)(?<!\n)\s?—", texto))      # la raya de diálogo a principio de línea no cuenta
    curvas = sum(texto.count(c) for c in "‘’“”")
    puntos = texto.count("…")
    duros = sum(texto.count(c) for c in "   ")
    total = invisibles * 4 + rayas * 2 + curvas + puntos + duros
    por_mil = total * 1000 / max(len(texto), 1)
    return (escala(por_mil, humano=0.0, maquina=12.0),
            f"{invisibles} invisibles, {rayas} rayas, {curvas} comillas curvas, {puntos} «…», {duros} espacios duros")


def _voz(texto, lex):
    p = _palabras(texto)
    if len(p) < 25:
        return 50.0, "muy corto para juzgarlo"
    t = normal(texto)
    por100 = 100 / len(p)
    oral = (len(ORAL_RE.findall(t)) + texto.count("¿") + texto.count("¡")) * por100
    persona = len(PERSONA_RE.findall(t)) * por100
    señales, nombres = 0, []
    for s in lex["senales"]:
        try:
            n = len(re.compile(s["regex"], re.MULTILINE).findall(texto))
        except re.error:
            continue
        if n:
            señales += n
            nombres.append(s["id"])
    viñetas = [len(b.split()) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", texto)]
    uniformes = len(viñetas) >= 3 and statistics.pstdev(viñetas) < 1.6
    score = (escala(oral, humano=3.0, maquina=0.0) * 0.35
             + escala(persona, humano=8.0, maquina=1.0) * 0.35
             + acotar(100 - señales * 22) * 0.30)
    if uniformes:
        score -= 12
        nombres.append("viñetas-iguales")
    detalle = (f"{oral:.1f} marcas orales y {persona:.1f} pronombres personales por cada 100 palabras, "
               f"{señales} señal(es) de estructura")
    if nombres:
        detalle += " [" + ", ".join(nombres[:4]) + "]"
    return acotar(score), detalle


def puntuar(texto):
    """Puntúa un texto. Devuelve un dict serializable:

    {human_score (0-100), veredicto ("PASA"|"REVISAR"|"MARCADO"),
     checks {burstiness|especificidad|muletillas|huella|voz: {score, detalle}},
     peor (clave del check más bajo), avisos [str]}
    """
    texto = texto or ""
    lex = lexico()
    m_score, m_detalle, vistas = _muletillas(texto, lex)
    resultados = {
        "burstiness": _burstiness(texto),
        "especificidad": _especificidad(texto),
        "muletillas": (m_score, m_detalle),
        "huella": _huella(texto),
        "voz": _voz(texto, lex),
    }
    puntos = [resultados[c][0] for c in CHECKS]
    # La comprobación más floja arrastra el veredicto: a un detector le basta una señal.
    total = statistics.mean(puntos) * 0.6 + min(puntos) * 0.4
    veredicto = ("PASA" if total >= 70 and min(puntos) >= 55
                 else "REVISAR" if total >= 50 else "MARCADO")
    peor = min(CHECKS, key=lambda c: resultados[c][0])
    avisos = []
    if resultados["burstiness"][0] < 55:
        avisos.append("Las frases miden casi lo mismo. Parte alguna y deja que otra se alargue.")
    if resultados["especificidad"][0] < 55:
        avisos.append("Faltan cosas concretas: cifras, nombres, sitios, precios.")
    if vistas:
        avisos.append("Quita las muletillas: " + ", ".join(sorted(vistas)[:6]) + ".")
    if resultados["huella"][0] < 55:
        avisos.append("Hay rayas, comillas curvas o caracteres invisibles: pásalo por humanizar.")
    if resultados["voz"][0] < 55:
        avisos.append("Suena a redacción: háblale a alguien (tú), cuenta algo tuyo (yo) y quita las estructuras marcadas.")
    return {"human_score": round(total, 1), "veredicto": veredicto,
            "checks": {c: {"score": round(resultados[c][0], 1), "detalle": resultados[c][1]} for c in CHECKS},
            "peor": peor, "avisos": avisos}


def _pintar(r, titulo, out):
    cab = "PANEL DE DETECCIÓN" + (f"  -  {titulo}" if titulo else "")
    print("\n" + cab, file=out)
    print("=" * max(len(cab), 62), file=out)
    for c in CHECKS:
        d = r["checks"][c]
        print(f"  {NOMBRES[c]:<13} {barra(d['score'])} {d['score']:5.1f}", file=out)
        print(f"  {'':<13} {d['detalle']}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HUMANO':<13} {barra(r['human_score'])} {r['human_score']:5.1f}   {r['veredicto']}", file=out)
    if r["veredicto"] != "PASA":
        print(f"\n  Lo más flojo: {NOMBRES[r['peor']]}. Arregla eso primero.", file=out)
    print("", file=out)


def main(argv=None):
    consola_utf8()
    ap = argparse.ArgumentParser(description="Puntúa cuánto parece escrito por una máquina un texto en español.")
    ap.add_argument("entrada", nargs="?", default="-", help="fichero, o -")
    ap.add_argument("comparar", nargs="?", help="segundo fichero para ver el antes y el después")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    textos = [(args.entrada, leer_entrada(args.entrada))]
    if args.comparar:
        textos.append((args.comparar, leer_entrada(args.comparar)))
    res = [puntuar(t) for _, t in textos]
    if args.json:
        print(json.dumps(res if args.comparar else res[0], indent=2, ensure_ascii=False))
        return 0
    for (nombre, _), r in zip(textos, res):
        _pintar(r, nombre if args.comparar else None, sys.stdout)
    if args.comparar:
        a, b = res
        print(f"  {a['human_score']:.1f} {a['veredicto']}  ->  {b['human_score']:.1f} {b['veredicto']}"
              f"   ({b['human_score'] - a['human_score']:+.1f})\n")
    return 0 if res[-1]["veredicto"] == "PASA" else 1


if __name__ == "__main__":
    sys.exit(main())

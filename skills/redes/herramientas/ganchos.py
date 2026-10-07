"""ganchos.py - puntúa la primera frase de un vídeo corto y ordena varias opciones.

Qué es: cinco heurísticas locales calculadas solo con el texto. Miden lo que
suelen tener los ganchos que retienen: se dicen en menos de tres segundos,
llevan algo concreto (una cifra, un nombre), hay algo en juego, lo importante
va delante y le hablan a alguien.

Qué NO es: un predictor de visitas. El original en inglés se probó con 74
ganchos reales: separa bien un gancho real de uno malo a propósito (AUC 0,83),
pero apenas distingue los aciertos de un creador de sus fallos (AUC 0,56, casi
una moneda al aire). Úsalo para lo que mide bien: cazar saludos, preámbulos,
ganchos sin nada concreto y ganchos que tardan cinco segundos en decirse. Qué
gancho de dos buenos va a funcionar lo deciden tu cara, tu montaje, el audio y
a quién se lo enseñe la app. Fíate más de la gráfica de retención.

Uso
  python -m herramientas.ganchos --gancho "18.000 euros me costó no poner una cláusula."
  python -m herramientas.ganchos ganchos.txt          # uno por línea, ordenados
  python -m herramientas.ganchos ganchos.txt --json
"""

import argparse
import json
import re
import statistics
import sys

from ._comun import (CIFRA_RE, EMOJI_RE, HASHTAG_RE, MARCA_RE, NUMEROS_HABLADOS, PALABRAS_DINERO,
                     PROPIO_RE, acotar, barra, cargar_json, consola_utf8, leer_entrada,
                     normal, palabras, palabras_norm)

PPM = 170  # palabras por minuto habladas en español, ritmo de vídeo corto

# Palabras que ponen algo en juego. Sin ninguna, el gancho es una afirmación;
# con una, es un motivo para quedarse. Sin tildes, porque se compara normalizado.
TENSION = {
    "deja", "dejar", "dejad", "nunca", "jamas", "mal", "error", "errores",
    "fallo", "fallos", "perdi", "perder", "pierdes", "perdiendo", "perdido", "costo",
    "cuesta", "cuestan", "costado", "roto", "fracaso", "fracase", "nadie", "no", "sin",
    "despedido", "borre", "borra", "borrar", "sustituye", "sustituido", "sustituyo",
    "gratis", "pagas", "pagando", "pague", "cobrar", "cobras", "cobro", "ahorrar",
    "ahorro", "ahorre", "prohibido", "ilegal", "peor", "odio", "odiaba", "tire",
    "tirar", "estafa", "mentira", "verdad", "secreto", "oculto", "escondido", "robe",
    "antes", "pero", "salvo", "problema", "riesgo", "peligro", "cuidado",
    "ojo", "arrepiento", "deberias", "todavia", "solo", "contra", "vs",
    "realmente", "cuidado", "cambia", "cambio", "dejo", "desaparece", "muerto",
    "trampa", "caro", "barato", "nada", "ninguno", "miedo", "vergonzoso",
    "llevaba", "tardaba", "costaba", "ahora",
}

# Arranques que gastan el primer segundo en no decir nada.
ARRANQUES_FLOJOS = [
    "hola", "buenas", "bueno", "vale", "chicos", "chicas", "gente", "familia", "hey",
    "hoy", "basicamente", "sinceramente", "escucha", "eh", "pues", "a ver", "solo",
    "queria", "quiero contaros", "quiero contarte", "os quiero", "vamos a", "uno de",
    "sabias", "habeis visto", "has visto", "alguna vez", "esto es", "hay una", "hay un",
    "en este", "en el video", "como ya", "cuando se", "como sabeis", "que tal",
    "bienvenidos", "bienvenidas", "venga", "a ver", "mmm", "o sea",
]

# Órdenes que se ganan el primer puesto.
IMPERATIVOS = {
    "deja", "copia", "borra", "prueba", "mira", "lee", "guarda", "usa", "haz", "escribe",
    "manda", "coge", "empieza", "nunca", "pon", "apunta", "revisa", "apaga", "quita",
    "fijate", "ojo", "cambia", "sube", "no", "olvida", "evita", "cobra",
}

ROMPE_TRATOS = [
    (re.compile(r"^\s*(?:¡\s*)?(?:deja de hacer scroll|no hagas scroll|para de deslizar|no pases|espera,? no (?:pases|deslices))"),
     "Empieza pidiendo que no hagan scroll. Pedir atención demuestra que no te la has ganado."),
    (re.compile(r"\b(?:en (?:este|el) (?:video|reel|tiktok)(?: de hoy)?|hoy (?:os|te) (?:voy a|traigo)|(?:os|te) voy a (?:ensenar|contar|explicar|mostrar))\b"),
     "Preámbulo de vídeo. Bórralo y empieza por el resultado."),
    (re.compile(r"^\s*(?:¡\s*)?(?:hola|buenas|hey|que tal|que pasa|bienvenid[oa]s)\b"),
     "Saludo. Nadie ha venido a la app a que le saluden."),
    (HASHTAG_RE, "Hashtag en el gancho. Los hashtags van al final del texto, si es que van."),
    (EMOJI_RE, "Emoji en el gancho. En texto de gancho hay sitio para palabras o para un emoji, no para los dos."),
]

PROPIEDADES = ["LONGITUD", "CONCRECION", "TENSION", "DELANTE", "A_QUIEN"]
NOMBRES = {
    "LONGITUD": "longitud", "CONCRECION": "concreción", "TENSION": "tensión",
    "DELANTE": "lo importante delante", "A_QUIEN": "a quién le habla",
}

_FORMULAS = None


def _formulas():
    global _FORMULAS
    if _FORMULAS is None:
        datos = cargar_json("ganchos.json")
        por_id = {g["id"]: g for g in datos["ganchos"]}
        _FORMULAS = [(por_id[i]["id"], por_id[i]["nombre"], re.compile(por_id[i]["match"]))
                     for i in datos["orden_clasificacion"] if i in por_id]
    return _FORMULAS


def formulas():
    """Las 26 fórmulas completas (plantilla, ejemplo, en pantalla...)."""
    return cargar_json("ganchos.json")["ganchos"]


def clasificar_formula(texto):
    """{'id': n, 'nombre': ...} de la primera fórmula que encaja, o None."""
    t = normal(texto)
    for fid, nombre, patron in _formulas():
        if patron.search(t):
            return {"id": fid, "nombre": nombre}
    return None


def _longitud(texto):
    n = len(palabras(texto))
    segundos = n / (PPM / 60)
    caracteres = len(texto.strip())
    if 5 <= n <= 13:
        score = 100.0
    elif n < 5:
        score = 100 - (5 - n) * 20
    else:
        score = 100 - (n - 13) * 11
    if caracteres > 70:      # dos líneas de texto grande en pantalla
        score -= 12
    return acotar(score), f"{n} palabras, {caracteres} caracteres, ~{segundos:.1f} s dicho (lo bueno: 5-13 palabras)"


def _concrecion(texto):
    cifras = [c.strip() for c in CIFRA_RE.findall(texto) if c.strip() and re.search(r"\d", c)]
    propios = sorted(set(PROPIO_RE.findall(texto)) | set(MARCA_RE.findall(texto)))
    en_cifras = normal(" ".join(cifras))
    hablados = [p for p in palabras_norm(texto)
                if p in NUMEROS_HABLADOS or (p in PALABRAS_DINERO and p not in en_cifras)]
    n = len(cifras) + len(propios) + len(hablados)
    score = 15.0 if n == 0 else acotar(45 + n * 30)
    vistos = ", ".join(cifras[:2] + propios[:2] + hablados[:2])
    detalle = f"{n} cosa(s) concreta(s)" + (f": {vistos}" if vistos else
                                            " - ni número, ni nombre, nada comprobable")
    return score, detalle


def _tension(texto):
    marcas = sorted({p for p in palabras_norm(texto) if p in TENSION})
    if re.search(r"\d[\d.,]*\s?(?:€|euros?)|[$€]\s?\d", texto):
        marcas.append("un precio")
    n = len(marcas)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detalle = f"{n} marca(s) de tensión" + (f": {', '.join(marcas[:4])}" if marcas else
                                            " - no hay nada en juego en esta frase")
    return score, detalle


def _delante(texto):
    originales = palabras(texto)
    if not originales:
        return 0.0, "vacío"
    low = [normal(p) for p in originales]
    inicio = " ".join(low[:3])
    castigo, flojo = 0, None
    for arranque in ARRANQUES_FLOJOS:
        if inicio.startswith(arranque + " ") or inicio == arranque or low[0] == arranque:
            castigo, flojo = 30, arranque
            break
    carga = None
    for i, token in enumerate(low):
        if (token in TENSION or token in NUMEROS_HABLADOS or token in PALABRAS_DINERO
                or re.match(r"[$€]?\d", originales[i])
                or MARCA_RE.fullmatch(originales[i])
                or (i and PROPIO_RE.match(originales[i]))):
            carga = i
            break
    if carga is None:
        base, donde = 30.0, "no hay ninguna palabra con carga en toda la frase"
    elif carga <= 3:
        base, donde = 100.0, f"lo importante en la palabra {carga + 1}"
    elif carga <= 6:
        base, donde = 70.0, f"lo importante en la palabra {carga + 1}, puede ir antes"
    else:
        base, donde = 40.0, f"lo importante en la palabra {carga + 1}, demasiado tarde"
    return acotar(base - castigo), donde + (f"; arranque flojo «{flojo}»" if flojo else "")


def _a_quien(texto):
    t = normal(texto)
    low = palabras_norm(texto)
    if re.search(r"\b(?:tu|tus|te|ti|contigo|tienes|haces|sabes|puedes|quieres|necesitas|estas|eres"
                 r"|vosotros|os|vuestro|vuestra|vuestros|teneis|haceis|sabeis|podeis|quereis)\b", t):
        return 100.0, "le habla a quien lo ve"
    if low and low[0] in IMPERATIVOS:
        return 90.0, f"empieza con una orden («{low[0]}»)"
    if re.search(r"\b(?:yo|me|mi|mis|conmigo|nosotros|nos|nuestro|nuestra|llevo|he|hice|perdi|gane)\b", t):
        return 70.0, "en primera persona, sin nombrar a quien lo ve"
    return 35.0, "en tercera persona, no le habla a nadie"


def puntuar_gancho(texto):
    """Puntúa un gancho. Devuelve un dict serializable a JSON:

    {gancho, score (0-100), nivel ("FUERTE"|"VALE"|"FLOJO"),
     propiedades {LONGITUD|CONCRECION|TENSION|DELANTE|A_QUIEN: {score, detalle}},
     peor (nombre de la propiedad más baja), rompe_tratos [str], formula {id, nombre}|None}
    """
    texto = (texto or "").strip()
    resultados = {
        "LONGITUD": _longitud(texto),
        "CONCRECION": _concrecion(texto),
        "TENSION": _tension(texto),
        "DELANTE": _delante(texto),
        "A_QUIEN": _a_quien(texto),
    }
    t = normal(texto)
    rotos = [msg for patron, msg in ROMPE_TRATOS if patron.search(t if patron not in (HASHTAG_RE, EMOJI_RE) else texto)]
    puntos = [resultados[p][0] for p in PROPIEDADES]
    # La peor propiedad tira del total: con una mala basta para que el pulgar siga.
    total = acotar(statistics.mean(puntos) * 0.6 + min(puntos) * 0.4 - len(rotos) * 15)
    nivel = ("FUERTE" if total >= 70 and min(puntos) >= 55 and not rotos
             else "VALE" if total >= 50 else "FLOJO")
    peor = min(PROPIEDADES, key=lambda p: resultados[p][0])
    return {
        "gancho": texto,
        "score": round(total, 1),
        "nivel": nivel,
        "propiedades": {p: {"score": round(resultados[p][0], 1), "detalle": resultados[p][1]}
                        for p in PROPIEDADES},
        "peor": peor,
        "rompe_tratos": rotos,
        "formula": clasificar_formula(texto),
    }


def ranking(ganchos):
    """Lista de puntuar_gancho() ordenada de mejor a peor (ignora líneas vacías)."""
    filas = [puntuar_gancho(g) for g in ganchos if g and g.strip()]
    return sorted(filas, key=lambda r: -r["score"])


def _uno(r, out):
    print("\nPUNTUACIÓN DEL GANCHO", file=out)
    print("=" * 66, file=out)
    print(f"  «{r['gancho']}»\n", file=out)
    for p in PROPIEDADES:
        d = r["propiedades"][p]
        print(f"  {NOMBRES[p]:<22} {barra(d['score'])} {d['score']:5.1f}", file=out)
        print(f"  {'':<22} {d['detalle']}", file=out)
    print("-" * 66, file=out)
    print(f"  {'TOTAL':<22} {barra(r['score'])} {r['score']:5.1f}   {r['nivel']}", file=out)
    if r["formula"]:
        print(f"  fórmula: #{r['formula']['id']} {r['formula']['nombre']}", file=out)
    for f in r["rompe_tratos"]:
        print(f"\n  ROMPE TRATOS  {f}", file=out)
    if r["nivel"] != "FUERTE":
        print(f"\n  Lo más flojo: {NOMBRES[r['peor']]}. Arregla eso y vuelve a pasarlo.", file=out)
    print("", file=out)


def _tabla(filas, out):
    print("\nRANKING DE GANCHOS\n" + "=" * 78, file=out)
    for i, r in enumerate(filas, 1):
        marca = "->" if i == 1 else "  "
        g = r["gancho"] if len(r["gancho"]) <= 60 else r["gancho"][:57] + "..."
        print(f"{marca} {r['score']:5.1f} {r['nivel']:<7} {g}", file=out)
        print(f"        lo más flojo: {NOMBRES[r['peor']]} ({r['propiedades'][r['peor']]['score']:.0f})", file=out)
        for f in r["rompe_tratos"]:
            print(f"        rompe tratos: {f}", file=out)
    print("\nGraba el primero. Si el primero no llega a 50, ninguno de estos es el gancho.\n", file=out)


def main(argv=None):
    consola_utf8()
    ap = argparse.ArgumentParser(description="Puntúa ganchos de vídeo corto en cinco propiedades.")
    ap.add_argument("entrada", nargs="?", default="-", help="fichero con un gancho por línea, o -")
    ap.add_argument("--gancho", help="puntúa un solo gancho escrito aquí")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    lineas = [args.gancho] if args.gancho else [
        l.strip() for l in leer_entrada(args.entrada).splitlines() if l.strip()]
    if not lineas:
        print("no hay nada que puntuar", file=sys.stderr)
        return 2
    filas = ranking(lineas)
    if args.json:
        print(json.dumps(filas[0] if len(filas) == 1 else filas, indent=2, ensure_ascii=False))
    elif len(filas) == 1:
        _uno(filas[0], sys.stdout)
    else:
        _tabla(filas, sys.stdout)
    return 0 if filas[0]["score"] >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())

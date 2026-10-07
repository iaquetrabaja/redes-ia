"""pie.py - revisa el texto de un post y enseña lo que se ve antes del «... más».

Instagram enseña unos 125 caracteres del texto en el feed y esconde el resto
detrás de un toque. TikTok enseña todavía menos de la descripción encima del
vídeo, unas dos líneas. Casi todos los textos que fallan, fallan ahí: el
gancho está en la tercera frase, la primera línea es un saludo o todo empieza
con un hashtag. Esto pinta la ventana visible en una caja para que la leas
como la lee un desconocido haciendo scroll, y después revisa lo que merece la
pena revisar.

Los cortes (125 en Instagram, 90 en TikTok) son aproximados: cambian con el
móvil, el tamaño de letra y los saltos de línea. Por eso conviene dejar margen
en vez de clavar el corte. Cámbialo con --corte.

Uso
  python -m herramientas.pie texto.txt
  python -m herramientas.pie texto.txt --red tiktok
  python -m herramientas.pie texto.txt --palabras "automatizar facturas,presupuestos"
  python -m herramientas.pie texto.txt --json
"""

import argparse
import json
import re
import sys
import textwrap

from ._comun import (CIFRA_RE, EMOJI_RE, MARCA_RE, PROPIO_RE, consola_utf8, leer_entrada,
                     normal)

REDES = {
    # límite de caracteres, corte visible aprox., máximo de hashtags (None = sin tope)
    "instagram": {"limite": 2200, "corte": 125, "max_hashtags": 5, "tope_duro": True},
    "tiktok": {"limite": 4000, "corte": 90, "max_hashtags": 6, "tope_duro": False},
}
# Instagram limitó los hashtags a cinco por publicación el 18 de diciembre de
# 2025 (antes eran 30). TikTok no tiene ese tope, pero más de 5-6 no ayuda y se
# lee como un texto antiguo, así que ahí es un aviso, no un fallo.

HASHTAG_RE = re.compile(r"(?:^|\s)(#[\wÁÉÍÓÚÜÑáéíóúüñ]+)")
MENCION_RE = re.compile(r"(?:^|\s)(@[\w.]+)")
ENLACE_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|es|co|io|net|org|ai|app)/\S*",
                       re.IGNORECASE)

LLAMADAS = [
    (re.compile(r"\b[Cc]omenta(?:d)?\s+(?:la palabra\s+|el emoji\s+|\"|«)?[A-ZÁÉÍÓÚÑ0-9]{2,}\b"), "comentar una palabra clave"),
    (re.compile(r"(?i)\b(?:escribeme|mandame (?:un )?(?:mensaje|md|dm)|por (?:privado|md|dm))\b"), "escribir por privado"),
    (re.compile(r"(?i)\bguarda(?:lo|la|te este|te esto| este| esto)\b"), "guardarlo"),
    (re.compile(r"(?i)\bcomparte(?:lo|la| este| esto| con)\b|\bmandaselo\b"), "compartirlo"),
    (re.compile(r"(?i)\bsigueme\b|\bsiguenos\b"), "seguir la cuenta"),
    (re.compile(r"(?i)\b(?:link|enlace) (?:en )?(?:la |mi )?bio\b"), "enlace en la bio"),
    (re.compile(r"(?i)\bdesliza\b"), "deslizar"),
    (re.compile(r"(?i)\b(?:dime|cuentame|que opinas)\b|¿(?:cual|que) (?:prefieres|usas|harias)"), "responder una pregunta"),
]

RELLENO = {"#viral", "#fyp", "#parati", "#foryou", "#foryoupage", "#explore", "#explorepage",
           "#trending", "#tendencia", "#reels", "#reelsinstagram", "#instagood", "#love",
           "#follow", "#seguidores", "#likes", "#viralvideo", "#xyzbca", "#fy", "#viralreels",
           "#instadaily", "#tiktok", "#tiktokespaña", "#paratii"}


def _ventana(texto, corte):
    plano = texto.strip()
    return plano if len(plano) <= corte else plano[:corte]


def revisar_pie(texto, palabras_clave=None, red="instagram", corte=None):
    """Revisa el texto de un post. Devuelve un dict serializable:

    {red, caracteres, limite, corte, lo_que_se_ve, cortado (bool), primera_linea_caracteres,
     hashtags [str], menciones [str], enlaces [str], emojis (int), llamadas [str],
     checks [{check, estado ("PASS"|"WARN"|"FAIL"), detalle}], veredicto ("LISTO"|"REVISAR"|"ARREGLAR")}
    """
    red = (red or "instagram").lower()
    conf = REDES.get(red, REDES["instagram"])
    corte = corte or conf["corte"]
    limpio = (texto or "").strip()
    n = len(limpio)
    lineas = limpio.split("\n") if limpio else []
    primera = lineas[0].strip() if lineas else ""
    tags = HASHTAG_RE.findall(limpio)
    menciones = MENCION_RE.findall(limpio)
    enlaces = ENLACE_RE.findall(limpio)
    emojis = EMOJI_RE.findall(limpio)
    ventana = _ventana(limpio, corte)
    norm = normal(limpio)
    llamadas = [nombre for patron, nombre in LLAMADAS
                if patron.search(limpio if nombre == "comentar una palabra clave" else norm)]
    relleno = [t for t in tags if t.lower() in RELLENO]
    palabras_clave = [p.strip() for p in (palabras_clave or []) if p and p.strip()]

    checks = []

    def add(nombre, estado, detalle):
        checks.append({"check": nombre, "estado": estado, "detalle": detalle})

    add("LONGITUD", "FAIL" if n > conf["limite"] else "PASS",
        f"{n} / {conf['limite']} caracteres" + (f", te pasas {n - conf['limite']}" if n > conf["limite"] else ""))

    if not primera:
        add("PRIMERA LÍNEA", "FAIL", "el texto empieza con una línea en blanco")
    elif primera.startswith(("#", "@")):
        add("PRIMERA LÍNEA", "FAIL", "empieza con un hashtag o una mención, justo en el único sitio que vale una frase")
    elif re.match(r"^\s*(?:¡\s*)?(?:hola|buenas|hey|que tal)\b", normal(primera)):
        add("PRIMERA LÍNEA", "FAIL", "empieza saludando. Nadie hace scroll para que le saluden")
    elif len(primera) > corte:
        add("PRIMERA LÍNEA", "WARN", f"{len(primera)} caracteres: se corta en el {corte} a mitad de idea. "
            "Vale si el corte deja con la intriga; mal si corta una subordinada")
    else:
        add("PRIMERA LÍNEA", "PASS", f"{len(primera)} caracteres, se ve entera")

    concretos = (len([c for c in CIFRA_RE.findall(ventana) if re.search(r"\d", c)])
                 + len(PROPIO_RE.findall(ventana)) + len(MARCA_RE.findall(ventana)))
    add("GANCHO CONCRETO", "PASS" if concretos else "WARN",
        f"{concretos} número(s) o nombre(s) en lo que se ve" + ("" if concretos else " - nada comprobable antes del «más»"))

    maxi = conf["max_hashtags"]
    if len(tags) > maxi and conf["tope_duro"]:
        add("HASHTAGS", "FAIL", f"{len(tags)} hashtags, por encima del tope de {maxi} de Instagram. "
            "Los que pasan del quinto no cuentan y el bloque se lee como antiguo")
    elif len(tags) > maxi:
        add("HASHTAGS", "WARN", f"{len(tags)} hashtags. En TikTok no hay tope, pero más de {maxi} no ayuda; "
            "mejor pocos y del tema")
    elif relleno:
        add("HASHTAGS", "WARN", f"{len(tags)} hashtags, {len(relleno)} genéricos ({', '.join(relleno[:3])}). "
            "No describen nada")
    else:
        add("HASHTAGS", "PASS", f"{len(tags)} hashtag(s)" + (f": {' '.join(tags)}" if tags else ""))

    if not tags:
        add("SITIO DE LOS HASHTAGS", "PASS", "no hay hashtags que colocar")
    elif any(t in ventana for t in tags):
        add("SITIO DE LOS HASHTAGS", "WARN", "hay un hashtag en lo que se ve: estás gastando espacio en una etiqueta")
    else:
        add("SITIO DE LOS HASHTAGS", "PASS", "los hashtags quedan debajo del corte")

    add("ENLACES", "WARN" if enlaces else "PASS",
        f"{len(enlaces)} enlace(s) en el texto, y en el texto no se puede pulsar. Llévalo a la bio o al privado"
        if enlaces else "ningún enlace muerto en el texto")

    if len(llamadas) == 1:
        add("UNA SOLA PETICIÓN", "PASS", f"una llamada a la acción: {llamadas[0]}")
    elif not llamadas:
        add("UNA SOLA PETICIÓN", "WARN", "no pides nada. Decide para qué es este post")
    else:
        add("UNA SOLA PETICIÓN", "WARN", f"{len(llamadas)} peticiones ({', '.join(llamadas)}). Pedir dos cosas es como no pedir ninguna")

    densidad = len(emojis) * 100 / max(n, 1)
    add("EMOJIS", "WARN" if densidad > 4 else "PASS",
        f"{len(emojis)} emoji(s), {densidad:.1f} por cada 100 caracteres" + (" - parece decoración" if densidad > 4 else ""))

    if palabras_clave:
        encontrados = [p for p in palabras_clave if normal(p) in norm]
        faltan = [p for p in palabras_clave if normal(p) not in norm]
        en_ventana = [p for p in encontrados if normal(p) in normal(ventana)]
        estado = "PASS" if not faltan else ("WARN" if encontrados else "FAIL")
        add("TÉRMINOS DE BÚSQUEDA", estado,
            f"{len(encontrados)}/{len(palabras_clave)} presentes"
            + (f", {len(en_ventana)} en lo que se ve" if encontrados else "")
            + (f". Faltan: {', '.join(faltan)}" if faltan else ""))

    fails = sum(1 for c in checks if c["estado"] == "FAIL")
    warns = sum(1 for c in checks if c["estado"] == "WARN")
    veredicto = "ARREGLAR" if fails else ("REVISAR" if warns else "LISTO")
    return {"red": red, "caracteres": n, "limite": conf["limite"], "corte": corte,
            "lo_que_se_ve": ventana, "cortado": n > corte, "primera_linea_caracteres": len(primera),
            "hashtags": tags, "menciones": menciones, "enlaces": enlaces, "emojis": len(emojis),
            "llamadas": llamadas, "checks": checks, "veredicto": veredicto}


def _pintar(a, out, ancho=52):
    cab = (f"REVISIÓN DEL TEXTO ({a['red']})  ·  {a['caracteres']} / {a['limite']}  ·  "
           f"{len(a['hashtags'])} hashtags  ·  {len(a['llamadas'])} petición(es)")
    print("\n" + cab, file=out)
    print("=" * max(len(cab), 62), file=out)
    print("\n  LO QUE SE VE ANTES DEL «MÁS»", file=out)
    print("  +" + "-" * (ancho + 2) + "+", file=out)
    lineas = []
    for crudo in a["lo_que_se_ve"].split("\n"):
        lineas.extend(textwrap.wrap(crudo, ancho) or [""])
    for l in lineas[:8]:
        print(f"  | {l:<{ancho}} |", file=out)
    cola = "... más" if a["cortado"] else "(cabe entero)"
    print("  +" + "-" * (ancho + 2 - len(cola) - 2) + f" {cola} " + "+", file=out)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['estado']:<5} {c['check']:<22} {c['detalle']}", file=out)
    print("-" * max(len(cab), 62), file=out)
    print(f"  VEREDICTO  {a['veredicto']}\n", file=out)


def main(argv=None):
    consola_utf8()
    ap = argparse.ArgumentParser(description="Revisa el texto de un post de Instagram o TikTok.")
    ap.add_argument("entrada", nargs="?", default="-", help="fichero con el texto, o -")
    ap.add_argument("--red", default="instagram", choices=sorted(REDES))
    ap.add_argument("--corte", type=int, help="caracteres visibles antes del «más»")
    ap.add_argument("--palabras", default="", help="términos de búsqueda separados por comas")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    a = revisar_pie(leer_entrada(args.entrada), args.palabras.split(","), args.red, args.corte)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        _pintar(a, sys.stdout)
    return 0 if a["veredicto"] == "LISTO" else 1


if __name__ == "__main__":
    sys.exit(main())

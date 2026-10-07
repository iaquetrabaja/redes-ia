"""humanizar.py - quita la huella de máquina de un borrador.

Tres pasadas, en este orden:

  1. INVISIBLES   borra o normaliza los caracteres que un teclado no escribe:
                  espacios de ancho cero, uniones, guiones blandos, BOM,
                  caracteres de etiqueta, espacios sin salto. Sobreviven al
                  copiar y pegar y son la huella más mecánica de un texto generado.
  2. TIPOGRAFÍA   raya -> coma, semirraya -> guion, comillas curvas -> rectas,
                  «…» en un carácter -> tres puntos, viñeta -> guion. Las
                  comillas latinas «» y los signos ¿ ¡ se respetan: son español.
  3. LÉXICO       sustituye las muletillas de muletillas.json por palabras
                  normales, respetando mayúsculas y sin tocar los enlaces.

Las señales de estructura (no es solo X es Y, tríadas, muros de hashtags...) se
AVISAN, nunca se reescriben solas: cambiar la forma de una frase pide criterio.

Uso
  python -m herramientas.humanizar borrador.txt
  python -m herramientas.humanizar borrador.txt --informe
  python -m herramientas.humanizar borrador.txt --json
"""

import argparse
import json
import re
import sys
import unicodedata

from ._comun import cargar_json, consola_utf8, leer_entrada

ENLACE_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
FRASE_RE = re.compile(r"[^.!?\n]+[.!?]*")
_VOCALES = {"a": "aáà", "e": "eéè", "i": "iíì", "o": "oóò", "u": "uúü"}

_LEX = None


def lexico():
    global _LEX
    if _LEX is None:
        _LEX = cargar_json("muletillas.json")
    return _LEX


def patron_flexible(busca):
    """Regex que encuentra la expresión con o sin tildes y con espacios variables."""
    trozos = []
    for c in busca.lower():
        base = unicodedata.normalize("NFD", c)[0]
        if c == " ":
            trozos.append(r"\s+")
        elif base in _VOCALES:
            trozos.append("[" + _VOCALES[base] + _VOCALES[base].upper() + "]")
        else:
            trozos.append(re.escape(c))
    return re.compile(r"(?<![\wÁÉÍÓÚÜÑáéíóúüñ])" + "".join(trozos) + r"(?![\wÁÉÍÓÚÜÑáéíóúüñ])",
                      re.IGNORECASE)


def _cp(spec):
    if "-" in spec:
        a, b = spec.split("-")
        return (int(a[2:], 16), int(b[2:], 16))
    return int(spec[2:], 16)


def _proteger(texto):
    guardados = []

    def guarda(m):
        guardados.append(m.group(0))
        return f"\x00E{len(guardados) - 1}\x00"

    return ENLACE_RE.sub(guarda, texto), guardados


def _restaurar(texto, guardados):
    for i, url in enumerate(guardados):
        texto = texto.replace(f"\x00E{i}\x00", url)
    return texto


def _invisibles(texto, lex):
    cambios = []
    for e in lex["invisibles"]:
        cp = _cp(e["cp"])
        patron = (f"[{re.escape(chr(cp[0]))}-{re.escape(chr(cp[1]))}]" if isinstance(cp, tuple)
                  else re.escape(chr(cp)))
        n = len(re.findall(patron, texto))
        if n:
            cambios.append({"tipo": "invisible", "que": f"{e['cp']} {e['nombre']}",
                            "por": "(borrado)" if e["accion"] == "borrar" else "(espacio)", "veces": n})
            texto = re.sub(patron, "" if e["accion"] == "borrar" else " ", texto)
    sueltos = [c for c in texto if unicodedata.category(c) == "Cf" and c != "\x00"]
    if sueltos:
        cambios.append({"tipo": "invisible", "que": "otros caracteres de formato invisibles",
                        "por": "(borrado)", "veces": len(sueltos)})
        texto = "".join(c for c in texto if unicodedata.category(c) != "Cf" or c == "\x00")
    return texto, cambios


def _tipografia(texto, lex):
    cambios = []
    for e in lex["tipografia"]:
        ch = e["de"]
        n = texto.count(ch)
        if not n:
            continue
        cambios.append({"tipo": "tipografia", "que": f"{ch} {e['nombre']}",
                        "por": e["a"].strip() or "(espacio)", "veces": n})
        if ch == "—":
            # Una raya al principio de línea es un diálogo y se queda como guion;
            # en mitad de frase (inciso) se convierte en coma.
            texto = re.sub(r"(?m)^(\s*)—\s*", r"\1- ", texto)
            texto = re.sub(r"\s*—\s*", ", ", texto)
        elif ch == "–":
            texto = re.sub(r"\s*–\s*(?=\d)", "-", texto)
            texto = re.sub(r"\s+–\s+", ", ", texto)
            texto = texto.replace("–", "-")
        else:
            texto = texto.replace(ch, e["a"])
    texto = re.sub(r",\s*([,.;:!?])", r"\1", texto)
    texto = re.sub(r",\s*\n", "\n", texto)
    return texto, cambios


def _como(original, nuevo):
    if not nuevo:
        return nuevo
    if original.isupper() and len(original) > 1:
        return nuevo.upper()
    if original[0].isupper():
        return nuevo[0].upper() + nuevo[1:]
    return nuevo


def _lexico(texto, lex):
    cambios = []
    entradas = sorted(lex["frases"] + lex["palabras"], key=lambda e: len(e["busca"]), reverse=True)
    for e in entradas:
        patron = patron_flexible(e["busca"])
        vistos = patron.findall(texto)
        if not vistos:
            continue
        cambios.append({"tipo": "lexico", "que": e["busca"], "por": e["cambia"] or "(borrado)",
                        "veces": len(vistos), "familia": e["familia"]})
        texto = patron.sub(lambda m: _como(m.group(0), e["cambia"]), texto)
    # Limpieza tras borrar: un borrado deja puntuación huérfana («sistema. .» o una
    # línea que empieza por coma) y eso queda peor que la muletilla.
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    texto = re.sub(r"(?m)^[ \t]*(?:[,.;:]+[ \t]*)+", "", texto)
    texto = re.sub(r"(?m)^[ \t](?=\S)", "", texto)
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    texto = re.sub(r",\s*([,.;:!?])", r"\1", texto)
    texto = re.sub(r"([.!?])\s*,\s*", r"\1 ", texto)
    # «Sin embargo, X» -> «Pero, X»: la coma sobra detrás de estas conjunciones.
    texto = re.sub(r"(?i)\b(pero|así que|asi que|porque|y)\s*,\s*", r"\1 ", texto)
    # Si al borrar solo queda una conjunción suelta («Y.»), fuera la frase entera.
    texto = re.sub(r"(?im)(^|(?<=[.!?] ))[ \t]*(?:y|o|e|pero|así que)[ \t]*[.!?]+[ \t]*", r"\1", texto)
    texto = texto.replace("...", "\x00PS\x00")
    texto = re.sub(r"\.\s*\.+", ".", texto)
    texto = re.sub(r"([!?])\s*\.", r"\1", texto)
    texto = texto.replace("\x00PS\x00", "...")
    texto = re.sub(r"(?m)^[ \t]+$", "", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto, cambios


def senales(texto, lex=None):
    """Señales de estructura que hay que reescribir a mano. Lista de {nombre, veces, arreglo}."""
    lex = lex or lexico()
    avisos = []
    for s in lex["senales"]:
        try:
            n = len(re.compile(s["regex"], re.MULTILINE).findall(texto))
        except re.error:
            continue
        if n:
            avisos.append({"id": s["id"], "nombre": s["nombre"], "veces": n, "arreglo": s["arreglo"]})
    largos = [len(f.split()) for f in FRASE_RE.findall(texto) if len(f.split()) > 2]
    if len(largos) >= 4:
        media = sum(largos) / len(largos)
        var = sum((x - media) ** 2 for x in largos) / len(largos)
        cv = (var ** 0.5) / media if media else 0
        if cv < 0.35:
            avisos.append({"id": "frases-iguales", "nombre": f"Frases de largo uniforme (variación {cv:.2f})",
                           "veces": len(largos),
                           "arreglo": "Parte una frase por la mitad. Deja que otra se alargue. Las máquinas escriben parejo."})
    return avisos


def _mayusculas(original, texto):
    """Al borrar un arranque, la palabra siguiente queda en minúscula. Solo se
    arregla si quien escribe pone mayúscula al empezar frase: escribir todo en
    minúscula a propósito es un estilo, no un defecto."""
    inicios = re.findall(r"(?:^|[.!?]\s+|\n)\s*[¿¡]?([A-Za-zÁÉÍÓÚÑáéíóúñ])", original)
    if not inicios or sum(1 for c in inicios if c.isupper()) * 2 < len(inicios):
        return texto
    return re.sub(r"(?:^|(?<=[.!?] )|(?<=[.!?]\n)|(?<=\n))(\s*[¿¡]?)([a-záéíóúñ])",
                  lambda m: m.group(1) + m.group(2).upper(), texto)


def humanizar(texto):
    """Limpia un borrador. Devuelve un dict serializable:

    {texto (limpio), cambios [{tipo ("invisible"|"tipografia"|"lexico"), que, por, veces, familia?}],
     senales [{id, nombre, veces, arreglo}], total_cambios (int)}
    """
    lex = lexico()
    original = texto or ""
    t, enlaces = _proteger(original)
    t, c1 = _invisibles(t, lex)
    t, c2 = _tipografia(t, lex)
    t, c3 = _lexico(t, lex)
    t = _mayusculas(original, t)
    t = _restaurar(t, enlaces).strip()
    cambios = c1 + c2 + c3
    return {"texto": t, "cambios": cambios, "senales": senales(t, lex),
            "total_cambios": sum(c["veces"] for c in cambios)}


def _informe(r, out):
    print("\nINFORME DE HUMANIZADO", file=out)
    print("-" * 22, file=out)
    print(f"{r['total_cambios']} restos de máquina quitados, {len(r['senales'])} señales de estructura "
          "para reescribir a mano", file=out)
    titulos = {"invisible": "1. INVISIBLES", "tipografia": "2. TIPOGRAFÍA", "lexico": "3. MULETILLAS"}
    for tipo, titulo in titulos.items():
        filas = [c for c in r["cambios"] if c["tipo"] == tipo]
        if filas:
            print(f"\n{titulo}", file=out)
            for c in filas:
                print(f"  {c['veces']:>3}x  {c['que']}  -> {c['por']}", file=out)
    if r["senales"]:
        print("\n4. SEÑALES DE ESTRUCTURA (no se arreglan solas: reescríbelas tú)", file=out)
        for s in r["senales"]:
            print(f"  {s['veces']:>3}x  {s['nombre']}\n        {s['arreglo']}", file=out)
    if not r["cambios"] and not r["senales"]:
        print("\nLIMPIO. No había nada que quitar.", file=out)
    print("", file=out)


def main(argv=None):
    consola_utf8()
    ap = argparse.ArgumentParser(description="Quita la huella de máquina de un borrador en español.")
    ap.add_argument("entrada", nargs="?", default="-", help="fichero, o -")
    ap.add_argument("--informe", action="store_true", help="enseña qué ha cambiado (por stderr)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    r = humanizar(leer_entrada(args.entrada))
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    sys.stdout.write(r["texto"] + "\n")
    if args.informe:
        _informe(r, sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

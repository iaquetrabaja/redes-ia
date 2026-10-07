"""ritmo.py - convierte un guion en una hoja de ritmo con tiempos antes de grabarlo.

Calcula cuánto se tarda en decir cada línea, las apila en tiempos y avisa de
las cuatro cosas que matan un vídeo corto en el montaje: un gancho que pasa de
los tres segundos, un plano tan largo que da tiempo a irse, varias líneas
seguidas sin nada concreto y un final que no vuelve al principio.

Los tiempos salen del número de palabras a un ritmo de palabras por minuto.
Sirven para planificar el montaje, no sustituyen a grabarlo. En español, a
ritmo de vídeo corto, casi todo el mundo está entre 160 y 190; aquí se usa 170.
Mídete leyendo un guion en voz alta y ajústalo con --ppm.

Uso
  python -m herramientas.ritmo guion.txt
  python -m herramientas.ritmo guion.txt --objetivo 30
  python -m herramientas.ritmo guion.txt --ppm 185 --json
"""

import argparse
import json
import re
import sys

from ._comun import (CIFRA_RE, MARCA_RE, NUMEROS_HABLADOS, PALABRAS_DINERO, PROPIO_RE,
                     consola_utf8, leer_entrada, normal, palabras, palabras_norm)

FRASE_RE = re.compile(r"[^.!?]+[.!?]*")
VACIAS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "pero", "si", "de",
    "del", "a", "al", "en", "por", "para", "con", "sin", "que", "esto", "este", "esta",
    "es", "son", "era", "fue", "ser", "tu", "tus", "te", "yo", "mi", "mis", "me", "se",
    "lo", "le", "les", "nos", "os", "no", "ya", "muy", "mas", "como", "cuando", "eso",
    "hay", "he", "ha", "has", "han", "solo", "todo", "nada", "uno", "asi", "aqui",
}

VENTANA_GANCHO = 3.0   # segundos. A partir de aquí el pulgar ya ha decidido.
MAX_BEAT = 4.0         # segundos con una sola idea y nada que cambie en pantalla.
TRAMO_ABSTRACTO = 3    # líneas seguidas sin nada comprobable.


def _concretos(texto):
    hablados = [p for p in palabras_norm(texto) if p in NUMEROS_HABLADOS or p in PALABRAS_DINERO]
    return (len([c for c in CIFRA_RE.findall(texto) if re.search(r"\d", c)])
            + len(PROPIO_RE.findall(texto)) + len(MARCA_RE.findall(texto)) + len(hablados))


def _tc(segundos):
    m, s = divmod(segundos, 60)
    return f"{int(m)}:{s:04.1f}"


def _partir(texto, pps):
    """Una línea es un beat, salvo que sea demasiado larga para serlo."""
    beats = []
    for linea in [l.strip() for l in texto.splitlines()]:
        if not linea:
            continue
        if len(palabras(linea)) / pps <= MAX_BEAT * 1.5:
            beats.append(linea)
            continue
        trozos = [t.strip() for t in FRASE_RE.findall(linea) if t.strip()]
        buf = ""
        for trozo in trozos:
            candidato = (buf + " " + trozo).strip()
            if buf and len(palabras(candidato)) / pps > MAX_BEAT:
                beats.append(buf)
                buf = trozo
            else:
                buf = candidato
        if buf:
            beats.append(buf)
    return beats


def hoja_de_ritmo(guion, objetivo_s=30, ppm=170):
    """Hoja de ritmo de un guion (una línea = un beat). Devuelve un dict serializable:

    {ppm, objetivo_s, total_s, total_palabras,
     beats [{n, inicio, duracion, palabras, texto, concretos, tipo ("GANCHO"|"MEDIO"|"CTA"|"GANCHO/CTA"|""), avisos [str]}],
     avisos [str], vuelve_al_inicio (bool)}
    Con un guion vacío devuelve beats = [] y un aviso.
    """
    pps = ppm / 60.0
    lineas = _partir(guion or "", pps)
    if not lineas:
        return {"ppm": ppm, "objetivo_s": objetivo_s, "total_s": 0.0, "total_palabras": 0,
                "beats": [], "avisos": ["El guion está vacío."], "vuelve_al_inicio": False}

    beats, reloj = [], 0.0
    for i, texto in enumerate(lineas):
        n = len(palabras(texto))
        dur = n / pps
        beats.append({"n": i + 1, "inicio": round(reloj, 2), "duracion": round(dur, 2),
                      "palabras": n, "texto": texto, "concretos": _concretos(texto),
                      "tipo": "", "avisos": []})
        reloj += dur
    total = reloj

    for b in beats:
        if b["n"] == 1 or b["inicio"] + b["duracion"] <= VENTANA_GANCHO:
            b["tipo"] = "GANCHO"
    beats[-1]["tipo"] = "CTA" if beats[-1]["tipo"] != "GANCHO" else "GANCHO/CTA"
    mitad = total / 2
    for b in beats:
        if not b["tipo"] and b["inicio"] <= mitad < b["inicio"] + b["duracion"]:
            b["tipo"] = "MEDIO"

    avisos = []
    primero = beats[0]
    if primero["duracion"] > VENTANA_GANCHO:
        primero["avisos"].append(f"el gancho dura {primero['duracion']:.1f} s, pasa de los {VENTANA_GANCHO:.0f} s")
        avisos.append(f"La línea 1 tarda {primero['duracion']:.1f} s en decirse. Déjala en "
                      f"{int(VENTANA_GANCHO * pps)} palabras o menos, o el gancho llega cuando ya han decidido.")
    if primero["concretos"] == 0:
        avisos.append("La línea 1 no tiene ni un número ni un nombre. Los ganchos sin nada "
                      "comprobable son los que se pasan.")

    for b in beats:
        if b["duracion"] > MAX_BEAT:
            b["avisos"].append(f"{b['duracion']:.1f} s en un solo plano")
    largos = [b["n"] for b in beats if b["duracion"] > MAX_BEAT]
    if largos:
        avisos.append(f"La(s) línea(s) {', '.join(map(str, largos))} pasan de {MAX_BEAT:.0f} s. "
                      "Pártelas o cambia lo que se ve en pantalla dentro de ellas. "
                      "Un plano quieto es donde la gente se va.")

    racha, desde = 0, None
    for b in beats:
        if b["concretos"] == 0:
            racha += 1
            desde = desde if desde is not None else b["n"]
            if racha == TRAMO_ABSTRACTO:
                avisos.append(f"Las líneas {desde}-{b['n']} no tienen nada concreto. "
                              "Mete un número, un nombre o un precio en alguna.")
        else:
            racha, desde = 0, None

    clave = lambda t: {normal(p) for p in palabras(t) if normal(p) not in VACIAS and len(p) > 2}
    eco = sorted(clave(primero["texto"]) & clave(beats[-1]["texto"]))
    vuelve = bool(eco) and len(beats) > 1
    if vuelve:
        avisos.append(f"Bucle: la última línea repite «{', '.join(eco[:3])}» del gancho. "
                      "Las segundas vueltas son alcance gratis.")
    elif len(beats) > 1:
        avisos.append("Sin bucle. La última línea no comparte ninguna palabra con el gancho y el "
                      "vídeo acaba plano. Repetir una palabra de la línea 1 es la segunda vuelta más barata.")

    if objetivo_s:
        delta = total - objetivo_s
        if abs(delta) <= objetivo_s * 0.1:
            avisos.append(f"Duración en el objetivo ({total:.1f} s de {objetivo_s} s).")
        elif delta > 0:
            avisos.append(f"Te pasas {delta:.1f} s. Quita unas {int(delta * pps)} palabras.")
        else:
            avisos.append(f"Te faltan {-delta:.1f} s. Añade unas {int(-delta * pps)} palabras "
                          "o grábalo más corto. Más corto suele ser lo correcto.")

    return {"ppm": ppm, "objetivo_s": objetivo_s, "total_s": round(total, 2),
            "total_palabras": sum(b["palabras"] for b in beats), "beats": beats,
            "avisos": avisos, "vuelve_al_inicio": vuelve}


def _pintar(a, out):
    cab = (f"HOJA DE RITMO  ·  {a['total_palabras']} palabras  ·  ~{a['total_s']:.1f} s "
           f"a {a['ppm']:g} ppm" + (f"  ·  objetivo {a['objetivo_s']:g} s" if a["objetivo_s"] else ""))
    print("\n" + cab, file=out)
    print("=" * max(len(cab), 72), file=out)
    for b in a["beats"]:
        tipo = f"{b['tipo']:<11}" if b["tipo"] else " " * 11
        print(f"  {_tc(b['inicio'])}  {b['duracion']:4.1f}s  {tipo}{b['texto']}", file=out)
        for av in b["avisos"]:
            print(f"  {'':>6}  {'':>5}  {'':<11}^ {av}", file=out)
    print("-" * max(len(cab), 72), file=out)
    for av in a["avisos"]:
        print(f"  - {av}", file=out)
    print("", file=out)


def main(argv=None):
    consola_utf8()
    ap = argparse.ArgumentParser(description="Hoja de ritmo de un guion de vídeo corto.")
    ap.add_argument("entrada", nargs="?", default="-", help="fichero del guion, o -")
    ap.add_argument("--ppm", type=float, default=170, help="palabras por minuto (170 por defecto)")
    ap.add_argument("--objetivo", type=float, default=30, help="duración objetivo en segundos (0 = sin objetivo)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    a = hoja_de_ritmo(leer_entrada(args.entrada), objetivo_s=args.objetivo or None, ppm=args.ppm)
    if not a["beats"]:
        print("el guion está vacío", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        _pintar(a, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

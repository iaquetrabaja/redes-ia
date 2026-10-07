"""viral.py - ordena los vídeos que has recogido por cuánto superan a su propia cuenta,
pone nombre a la fórmula del gancho y escribe el fichero de referencias.

La idea es una sola corrección: las visitas a secas no son prueba de nada. Una
cuenta de dos millones de seguidores con 400.000 visitas ha tenido un martes
flojo. Una de 4.000 seguidores con 400.000 visitas ha encontrado algo, y eso sí
se puede copiar. Aquí se ordena por el MÚLTIPLO sobre la mediana de la cuenta.

Entrada (CLI): un TSV que vas rellenando mientras miras, una fila por vídeo,
con cabecera:

    cuenta    seguidores   mediana   vistas    gancho
    @alguien  48000        11000     412000    nadie te cuenta que tus primeros 30 vídeos van a fallar

«mediana» son las visitas típicas recientes de esa cuenta y es la mejor base.
Si solo tienes «seguidores», deja la mediana vacía y se avisa.

Uso
  python -m herramientas.viral recogidos.tsv
  python -m herramientas.viral recogidos.tsv --md ~/.claude/redes/viral.md
  python -m herramientas.viral recogidos.tsv --json
"""

import argparse
import json
import os
import re
import statistics
import sys

from ._comun import consola_utf8, leer_entrada, palabras
from .ganchos import clasificar_formula, puntuar_gancho


def _num(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    texto = str(valor).strip().lower().replace(" ", "")
    m = re.match(r"^([\d.,]+)\s*(k|mil|m|millones?)?$", texto)
    if m:
        base = m.group(1)
        mult = m.group(2)
        if mult:
            n = float(base.replace(".", "").replace(",", ".")) if "," in base else float(base)
            return int(n * (1_000 if mult in ("k", "mil") else 1_000_000))
    dig = re.sub(r"[^\d]", "", texto)
    return int(dig) if dig else None


def ranking_viral(filas):
    """Ordena vídeos por múltiplo sobre la base de su cuenta.

    filas: lista de dicts con claves cuenta, seguidores, mediana, vistas, gancho (las
    cifras pueden ser números o textos como «12k», «1,2 M», «48.000»).

    Devuelve un dict serializable:
    {base ("mediana de la cuenta"|"seguidores"), n, cuentas,
     videos [{cuenta, seguidores, mediana, vistas, gancho, base, multiplo, formula_id, formula,
              palabras, gancho_score, gancho_nivel}],   (de mayor a menor múltiplo)
     formulas_top [[nombre, veces]], score_top, score_abajo, palabras_top, palabras_abajo,
     sin_clasificar}
    """
    videos = []
    for f in filas or []:
        vistas = _num(f.get("vistas"))
        gancho = (f.get("gancho") or "").strip()
        if not vistas or not gancho:
            continue
        seguidores = _num(f.get("seguidores"))
        mediana = _num(f.get("mediana"))
        base = mediana or seguidores or 0
        formula = clasificar_formula(gancho)
        p = puntuar_gancho(gancho)
        videos.append({
            "cuenta": f.get("cuenta", ""), "seguidores": seguidores, "mediana": mediana,
            "vistas": vistas, "gancho": gancho, "base": base,
            "multiplo": round(vistas / base, 2) if base else None,
            "formula_id": formula["id"] if formula else None,
            "formula": formula["nombre"] if formula else "sin clasificar",
            "palabras": len(palabras(gancho)),
            "gancho_score": p["score"], "gancho_nivel": p["nivel"],
        })
    con_mediana = any(v["mediana"] for v in videos)
    orden = sorted(videos, key=lambda v: -(v["multiplo"] or 0))
    tercio = max(1, len(orden) // 3) if orden else 0
    arriba, abajo = orden[:tercio], orden[-tercio:] if tercio else []

    def med(items, clave):
        vals = [i[clave] for i in items if i.get(clave) is not None]
        return round(statistics.median(vals), 1) if vals else None

    cuenta_formulas = {}
    for v in arriba:
        cuenta_formulas[v["formula"]] = cuenta_formulas.get(v["formula"], 0) + 1
    return {
        "base": "mediana de la cuenta" if con_mediana else "seguidores",
        "n": len(orden), "cuentas": len({v["cuenta"] for v in orden}), "videos": orden,
        "formulas_top": [[k, n] for k, n in sorted(cuenta_formulas.items(), key=lambda kv: -kv[1])],
        "score_top": med(arriba, "gancho_score"), "score_abajo": med(abajo, "gancho_score"),
        "palabras_top": med(arriba, "palabras"), "palabras_abajo": med(abajo, "palabras"),
        "sin_clasificar": sum(1 for v in orden if v["formula"] == "sin clasificar"),
    }


def leer_tsv(texto):
    lineas = [l for l in texto.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lineas:
        return []
    cab = [c.strip().lower() for c in lineas[0].split("\t")]
    if "vistas" in cab and "gancho" in cab:
        cols, cuerpo = cab, lineas[1:]
    else:
        cols, cuerpo = ["cuenta", "seguidores", "vistas", "gancho"], lineas
    filas = []
    for l in cuerpo:
        celdas = [c.strip() for c in l.split("\t")]
        celdas += [""] * (len(cols) - len(celdas))
        filas.append(dict(zip(cols, celdas)))
    return filas


def a_markdown(a):
    lineas = ["# Referencias virales", "",
              f"{a['n']} vídeos de {a['cuentas']} cuentas, ordenados por múltiplo sobre {a['base']}.", ""]
    for v in a["videos"]:
        mult = f"{v['multiplo']:.1f}x" if v["multiplo"] else "?"
        lineas += [f"## {mult}  {v['formula']}  ({v['cuenta']})",
                   f"- vistas: {v['vistas']:,}  base: {v['base']:,}".replace(",", "."),
                   f"- gancho: {v['gancho_score']} ({v['gancho_nivel']}), {v['palabras']} palabras",
                   f"- «{v['gancho']}»", ""]
    return "\n".join(lineas) + "\n"


def _pintar(a, out):
    cab = f"REFERENCIAS  ·  {a['n']} vídeos  ·  {a['cuentas']} cuentas  ·  base: {a['base']}"
    print("\n" + cab, file=out)
    print("=" * max(len(cab), 78), file=out)
    for v in a["videos"]:
        mult = f"{v['multiplo']:.1f}x" if v["multiplo"] else "   ?"
        fid = f"#{v['formula_id']:<2}" if v["formula_id"] else "-  "
        print(f"  {mult:>7}  gancho {v['gancho_score']:>4.0f}  {fid} {v['formula'][:24]:<24} "
              f"{str(v['cuenta'])[:16]:<16} {v['vistas']:>10,}".replace(",", "."), file=out)
        print(f"           «{v['gancho'][:96]}»", file=out)
    print("-" * max(len(cab), 78), file=out)
    print("QUÉ ESTÁ FUNCIONANDO EN ESTE LOTE", file=out)
    if a["formulas_top"]:
        print("  tercio de arriba:      " + ", ".join(f"{n} x{c}" for n, c in a["formulas_top"][:4]), file=out)
    if a["score_top"] is not None:
        print(f"  gancho (mediana):      arriba {a['score_top']:.0f}  vs  abajo {a['score_abajo']:.0f}", file=out)
    print(f"  largo del gancho:      arriba {a['palabras_top']} palabras  vs  abajo {a['palabras_abajo']}", file=out)
    print(f"  sin clasificar:        {a['sin_clasificar']} de {a['n']}. Léelos a mano: ahí se esconde "
          "una fórmula que todavía no tienes.", file=out)
    print("\n  Un lote recogido a mano es una pista, no una prueba. Doce vídeos no dicen nada;\n"
          "  cuarenta de seis cuentas ya dicen algo. Recoge más antes de creértelo.\n", file=out)


def main(argv=None):
    consola_utf8()
    ap = argparse.ArgumentParser(description="Ordena vídeos recogidos por múltiplo sobre su cuenta.")
    ap.add_argument("entrada", nargs="?", default="-", help="TSV, o -")
    ap.add_argument("--md", help="escribe también el fichero de referencias en markdown aquí")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    filas = leer_tsv(leer_entrada(args.entrada))
    a = ranking_viral(filas)
    if not a["n"]:
        print("no hay filas útiles. Hace falta un TSV con al menos vistas y gancho.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        _pintar(a, sys.stdout)
    if args.md:
        ruta = os.path.expanduser(args.md)
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(a_markdown(a))
        print(f"escrito {ruta}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Cálculos: últimos datos de cada vídeo, mediana por cuenta, múltiplo (outlier), engagement, resumen por periodo y
comparativa con la competencia."""
from datetime import date, timedelta
from statistics import median

from ..db import q

REDES = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube Shorts"}
INTERACCIONES = ("likes", "comentarios", "compartidos", "guardados")


def _ultimo(campo: str) -> str:
    # la última foto puede no traer ese dato (la página pública de TikTok solo da vistas): se toma el último conocido
    return (f"COALESCE(m.{campo}, (SELECT {campo} FROM metricas WHERE video_id = v.id AND {campo} IS NOT NULL "
            f"ORDER BY fecha DESC LIMIT 1)) AS {campo}")


SQL = f"""
SELECT v.*, c.usuario, c.mia, c.nombre AS cuenta_nombre, m.vistas, m.alcance, m.fecha AS foto,
       {", ".join(_ultimo(k) for k in INTERACCIONES)}
FROM videos v JOIN cuentas c ON c.id = v.cuenta_id
LEFT JOIN metricas m ON m.video_id = v.id AND m.fecha = (SELECT MAX(fecha) FROM metricas WHERE video_id = v.id)
WHERE c.activa = 1
"""


def engagement(v: dict) -> float | None:
    """(me gusta + comentarios + compartidos + guardados) / vistas, en %. None si no hay vistas o interacciones."""
    if not v.get("vistas") or all(v.get(k) is None for k in INTERACCIONES):
        return None
    return round(100 * sum(v.get(k) or 0 for k in INTERACCIONES) / v["vistas"], 2)


def videos(donde: str = "", params=()) -> list[dict]:
    rows = q(SQL + donde, params)
    por_cuenta: dict[int, list[int]] = {}
    for r in rows:
        base = r["vistas"] if r["vistas"] else r["likes"]
        if base:
            por_cuenta.setdefault(r["cuenta_id"], []).append(base)
    for r in rows:
        med = median(por_cuenta.get(r["cuenta_id"]) or [0]) or None
        base = r["vistas"] if r["vistas"] else r["likes"]
        r["multiplo"] = round(base / med, 1) if (base and med) else None
        r["edad"] = edad(r.get("publicado"))
        r["er"] = engagement(r)
    return rows


def edad(fecha: str | None) -> int | None:
    try:
        return (date.today() - date.fromisoformat((fecha or "")[:10])).days
    except ValueError:
        return None


def _cambio(a, b):
    """% de cambio de b a a (None si no se puede calcular)."""
    if a is None or not b:
        return None
    return round(100 * (a - b) / abs(b))


def _media(vals, nd=2):
    vals = [x for x in vals if x is not None]
    return round(sum(vals) / len(vals), nd) if vals else None


def _mediana(vals):
    vals = [x for x in vals if x]
    return round(median(vals)) if vals else None


# ---------------------------------------------------------------- seguidores
def serie_seguidores(cuenta_id: int, dias: int) -> list[dict]:
    desde = (date.today() - timedelta(days=dias)).isoformat()
    return q("SELECT fecha, seguidores FROM seguidores WHERE cuenta_id=? AND fecha>=? AND seguidores IS NOT NULL "
             "ORDER BY fecha", (cuenta_id, desde))


def variacion_seguidores(cuenta_id: int, dias: int) -> dict:
    """Seguidores ahora, ganados en el periodo y % de crecimiento. Toma como punto de partida el último dato del
    día de inicio o anterior; si no lo hay, el primero del periodo."""
    desde = (date.today() - timedelta(days=dias)).isoformat()
    ultimo = q("SELECT fecha, seguidores FROM seguidores WHERE cuenta_id=? AND seguidores IS NOT NULL "
               "ORDER BY fecha DESC LIMIT 1", (cuenta_id,), one=True)
    inicio = q("SELECT fecha, seguidores FROM seguidores WHERE cuenta_id=? AND fecha<=? AND seguidores IS NOT NULL "
               "ORDER BY fecha DESC LIMIT 1", (cuenta_id, desde), one=True) or \
        q("SELECT fecha, seguidores FROM seguidores WHERE cuenta_id=? AND fecha>? AND seguidores IS NOT NULL "
          "ORDER BY fecha LIMIT 1", (cuenta_id, desde), one=True)
    if not ultimo:
        return {"seguidores": None, "ganados": None, "crecimiento": None}
    if not inicio or inicio["fecha"] == ultimo["fecha"]:
        return {"seguidores": ultimo["seguidores"], "ganados": None, "crecimiento": None}
    g = ultimo["seguidores"] - inicio["seguidores"]
    return {"seguidores": ultimo["seguidores"], "ganados": g,
            "crecimiento": round(100 * g / inicio["seguidores"], 1) if inicio["seguidores"] else None}


# ---------------------------------------------------------------- estadísticas de un grupo de vídeos
def estadisticas(vids: list[dict], dias: int) -> dict:
    """Lo que se compara de cada cuenta en el periodo: nº de vídeos, frecuencia, mediana de vistas, engagement medio,
    mejor vídeo y cuántos superan x2 su mediana.

    La frecuencia se calcula sobre los días que cubren los vídeos guardados (TikTok sin login da los ~10 últimos):
    si solo hay vídeos de las últimas 2 semanas, no se divide entre 90 días."""
    hoy = date.today()
    desde = (hoy - timedelta(days=dias)).isoformat()
    per = [v for v in vids if (v.get("publicado") or "")[:10] >= desde]
    fechas = [v["publicado"][:10] for v in vids if v.get("publicado")]
    if fechas:
        cubre = (hoy - date.fromisoformat(min(fechas))).days + 1
        dias_ef = max(min(dias, cubre), min(dias, 7))
        frecuencia = round(len(per) * 7 / dias_ef, 1)
    else:
        frecuencia = None
    mejor = max(per, key=lambda v: v.get("vistas") or v.get("likes") or 0) if per else None
    return {"n": len(per), "frecuencia": frecuencia, "mediana": _mediana(v.get("vistas") for v in per),
            "engagement": _media(v.get("er") for v in per), "mejor": mejor,
            "sobre2": sum(1 for v in per if (v.get("multiplo") or 0) >= 2), "vistas": sum(v.get("vistas") or 0 for v in per)}


def _cuentas(red: str | None = None, mia: bool | None = None) -> list[dict]:
    sql, p = "SELECT * FROM cuentas WHERE activa=1", []
    if red:
        sql, p = sql + " AND red=?", p + [red]
    if mia is not None:
        sql, p = sql + " AND mia=?", p + [int(mia)]
    return q(sql + " ORDER BY mia DESC, seguidores DESC, usuario", tuple(p))


def competencia(dias: int = 7) -> list[dict]:
    """Todas las cuentas (tuyas y de la competencia) por red, con sus números del periodo."""
    todos = videos()
    out = []
    for red, nombre in REDES.items():
        filas = []
        for c in _cuentas(red):
            vs = [v for v in todos if v["cuenta_id"] == c["id"]]
            filas.append({**c, **variacion_seguidores(c["id"], dias), **estadisticas(vs, dias),
                          "seguidores": c["seguidores"]})
        if filas:
            out.append({"red": red, "nombre": nombre, "cuentas": filas})
    return out


def ficha(cid: int, dias: int = 30) -> dict | None:
    c = q("SELECT * FROM cuentas WHERE id=?", (cid,), one=True)
    if not c:
        return None
    vs = sorted(videos(" AND v.cuenta_id=?", (cid,)), key=lambda v: v.get("publicado") or "", reverse=True)
    serie = serie_seguidores(cid, max(dias, 30))
    return {"c": c, "s": {**variacion_seguidores(cid, dias), **estadisticas(vs, dias)},
            "serie": serie, "grafica": {"seguidores": {"@" + c["usuario"]: [[p["fecha"], p["seguidores"]] for p in serie]}},
            "videos": vs,
            "mediana_total": _mediana(v.get("vistas") for v in vs),
            "funcionan": sorted([v for v in vs if (v.get("multiplo") or 0) >= 1.5], key=lambda v: -v["multiplo"])[:6]}


# ---------------------------------------------------------------- tú contra tu competencia
METRICAS_COMP = [
    ("mediana", "Mediana de vistas por vídeo", ""),
    ("engagement", "Engagement medio", "%"),
    ("frecuencia", "Vídeos por semana", ""),
    ("crecimiento", "Crecimiento de seguidores", "%"),
]
CONSEJOS = {
    "mediana": "tus vídeos llegan a menos gente: mira en sus fichas «sus vídeos que funcionan» y copia el tipo de "
               "gancho y de tema, no el vídeo",
    "engagement": "tu público interactúa menos: cierra cada vídeo pidiendo una acción concreta (guardar, comentar "
                  "una palabra) y responde a los comentarios",
    "frecuencia": "publicar más a menudo es lo que más te acercaría a ellos",
    "crecimiento": "ganas seguidores más despacio: deja claro en los primeros segundos para quién es tu canal",
}


def redes_comparables() -> list[str]:
    return [r for r in REDES if q("SELECT 1 FROM cuentas WHERE activa=1 AND mia=1 AND red=?", (r,), one=True)
            and q("SELECT 1 FROM cuentas WHERE activa=1 AND mia=0 AND red=?", (r,), one=True)]


def comparativa(dias: int = 7, red: str | None = None) -> dict:
    redes = redes_comparables()
    if not redes:
        return {"redes": [], "red": None}
    red = red if red in redes else redes[0]
    vs = videos(" AND v.red=?", (red,))
    mias = _cuentas(red, True)
    ids = [c["id"] for c in mias]
    tu = estadisticas([v for v in vs if v["cuenta_id"] in ids], dias)
    var = [variacion_seguidores(i, dias) for i in ids]
    base = sum((x["seguidores"] or 0) - (x["ganados"] or 0) for x in var if x["ganados"] is not None)
    gan = sum(x["ganados"] for x in var if x["ganados"] is not None)
    tu["crecimiento"] = round(100 * gan / base, 1) if base and any(x["ganados"] is not None for x in var) else None
    tu["nombre"] = " + ".join("@" + c["usuario"] for c in mias)
    rivales = []
    for c in _cuentas(red, False):
        s = estadisticas([v for v in vs if v["cuenta_id"] == c["id"]], dias)
        s.update(nombre="@" + c["usuario"], id=c["id"], crecimiento=variacion_seguidores(c["id"], dias)["crecimiento"])
        rivales.append(s)
    filas = []
    for k, etiqueta, suf in METRICAS_COMP:
        vals = [x[k] for x in rivales if x[k] is not None]
        med = round(median(vals), 2) if vals else None
        barras = [{"nombre": "Tú · " + tu["nombre"], "valor": tu[k], "mia": True}] + \
                 [{"nombre": x["nombre"], "valor": x[k], "mia": False, "id": x["id"]} for x in rivales]
        barras.sort(key=lambda b: -(b["valor"] if b["valor"] is not None else -1e9))
        tope = max([abs(b["valor"]) for b in barras if b["valor"] is not None] or [0]) or 1
        for b in barras:
            b["ancho"] = round(100 * abs(b["valor"]) / tope, 1) if b["valor"] is not None else 0
        filas.append({"clave": k, "etiqueta": etiqueta, "suf": suf, "tu": tu[k], "mediana": med, "barras": barras,
                      "puesto": next((i + 1 for i, b in enumerate(barras) if b["mia"]), None),
                      "diferencia": _diferencia(k, tu[k], med)})
    return {"redes": redes, "red": red, "tu": tu, "rivales": rivales, "filas": filas,
            "conclusion": conclusion(filas, REDES[red]) if rivales else None}


def _diferencia(clave: str, tu, med):
    """Diferencia con la mediana de la competencia: % para todo salvo el crecimiento (puntos)."""
    if tu is None or med is None:
        return None
    if clave == "crecimiento":
        return round(tu - med, 1)
    return round(100 * (tu - med) / med) if med else None


def _num(x, suf=""):
    if x is None:
        return "—"
    if suf == "%" or (abs(x) < 100 and not float(x).is_integer()):
        t = f"{x:.1f}".replace(".", ",")
    else:
        t = f"{int(round(x)):,}".replace(",", ".")
    return t + (" %" if suf == "%" else "")


UNIDADES = {"mediana": " vistas", "frecuencia": " vídeos/semana"}


def conclusion(filas: list[dict], red_nombre: str) -> str:
    """Una frase que resume la comparativa y dice qué mejorar primero."""
    frases = {
        "mediana": ("tu mediana de vistas es un {d} % mayor", "tu mediana de vistas es un {d} % menor"),
        "engagement": ("tu engagement es un {d} % mayor", "tu engagement es un {d} % menor"),
        "frecuencia": ("publicas un {d} % más", "publicas un {d} % menos"),
        "crecimiento": ("creces {d} puntos más rápido en seguidores", "creces {d} puntos más despacio en seguidores"),
    }
    bien, mal = [], []
    for f in filas:
        d = f["diferencia"]
        if d is None:
            continue
        umbral = 0.5 if f["clave"] == "crecimiento" else 10
        u = UNIDADES.get(f["clave"], "")
        detalle = f" ({_num(f['tu'], f['suf'])} frente a {_num(f['mediana'], f['suf'])}{u})"
        if d >= umbral:
            bien.append((d if f["clave"] != "crecimiento" else d * 10, frases[f["clave"]][0].format(d=_num(abs(d))) + detalle, f["clave"]))
        elif d <= -umbral:
            mal.append((-d if f["clave"] != "crecimiento" else -d * 10, frases[f["clave"]][1].format(d=_num(abs(d))) + detalle, f["clave"]))
    if not bien and not mal:
        return f"En {red_nombre} estás a la par de la mediana de tu competencia en todo. Busca un vídeo suyo que " \
               "funcione y prueba su tipo de gancho."
    bien.sort(reverse=True)
    mal.sort(reverse=True)
    partes = []
    if bien:
        partes.append(" y ".join(x[1] for x in bien[:2]))
    if mal:
        partes.append(("pero " if bien else "") + " y ".join(x[1] for x in mal[:2]))
    texto = f"Frente a la mediana de tu competencia en {red_nombre}, " + ", ".join(partes) + "."
    if mal:
        texto += " Lo primero a mejorar: " + CONSEJOS[mal[0][2]] + "."
    else:
        texto += " Vas por delante en lo que se puede medir: mantén el ritmo y vigila sus vídeos que funcionan."
    return texto


# ---------------------------------------------------------------- resumen (tus cuentas)
def _kpis(lst: list[dict]) -> dict:
    vistas = [v.get("vistas") for v in lst if v.get("vistas") is not None]
    out = {"publicaciones": len(lst), "vistas": sum(vistas) if vistas else None,
           "media": round(sum(vistas) / len(vistas)) if vistas else None,
           "engagement": _media(v.get("er") for v in lst)}
    for k in INTERACCIONES:
        vals = [v.get(k) for v in lst if v.get(k) is not None]
        out[k] = sum(vals) if vals else None
    return out


def kpis_periodo(mios: list[dict], cuentas: list[dict], dias: int) -> dict:
    hoy = date.today()
    desde, antes = (hoy - timedelta(days=dias)).isoformat(), (hoy - timedelta(days=2 * dias)).isoformat()
    act = [v for v in mios if (v.get("publicado") or "")[:10] >= desde]
    prev = [v for v in mios if antes <= (v.get("publicado") or "")[:10] < desde]
    a, b = _kpis(act), _kpis(prev)
    cambio = {k: _cambio(a[k], b[k]) for k in a}
    var = [variacion_seguidores(c["id"], dias) for c in cuentas]
    segs = [x["seguidores"] for x in var if x["seguidores"] is not None]
    gan = [x["ganados"] for x in var if x["ganados"] is not None]
    return {"act": a, "prev": b, "cambio": cambio, "seguidores": sum(segs) if segs else None,
            "ganados": sum(gan) if gan else None, "videos": act}


def vistas_ganadas(video_ids: list[int], dias: int) -> dict[str, int]:
    """Vistas nuevas por día: diferencia entre la foto de cada día y la anterior de cada vídeo. La primera foto de un
    vídeo cuenta entera solo si se hizo en los dos días siguientes a publicarlo (si no, sería un salto falso)."""
    hoy = date.today()
    desde = (hoy - timedelta(days=dias - 1)).isoformat()
    out = {(hoy - timedelta(days=i)).isoformat(): 0 for i in range(dias - 1, -1, -1)}
    if not video_ids:
        return out
    marcas = ",".join("?" * len(video_ids))
    filas = q(f"SELECT m.video_id, m.fecha, m.vistas, v.publicado FROM metricas m JOIN videos v ON v.id = m.video_id "
              f"WHERE m.video_id IN ({marcas}) AND m.vistas IS NOT NULL ORDER BY m.video_id, m.fecha", tuple(video_ids))
    previo: dict[int, int] = {}
    for f in filas:
        vid, n = f["video_id"], f["vistas"]
        if vid in previo:
            g = max(0, n - previo[vid])
        else:
            pub = (f["publicado"] or "")[:10]
            reciente = pub and (date.fromisoformat(f["fecha"]) - date.fromisoformat(pub)).days <= 2
            g = n if reciente else 0
        previo[vid] = n
        if f["fecha"] >= desde and f["fecha"] in out:
            out[f["fecha"]] += g
    return out


def resumen(dias: int = 7, red: str | None = None) -> dict:
    """Todo lo que pinta la página de Resumen (tus cuentas): KPIs contra el periodo anterior, tabla por red,
    gráficas de vistas ganadas por día y seguidores, mejores vídeos y tus vídeos del periodo."""
    todos_mios = videos(" AND c.mia=1")
    mios = [v for v in todos_mios if red in (None, v["red"])]
    cuentas = _cuentas(red, True)
    k = kpis_periodo(mios, cuentas, dias)
    redes_mias = [r for r in REDES if any(c["red"] == r for c in _cuentas(None, True))]
    por_red = {} if red else {
        r: kpis_periodo([v for v in todos_mios if v["red"] == r], _cuentas(r, True), dias) for r in redes_mias}
    seg = []
    for c in cuentas:
        seg.append({"id": c["id"], "red": c["red"], "usuario": c["usuario"], "error": c["error"], "ultimo": c["ultimo"],
                    **variacion_seguidores(c["id"], dias), "serie": serie_seguidores(c["id"], dias)})
    grafica = {
        "ganadas": {REDES[r]: [[d, n] for d, n in vistas_ganadas([v["id"] for v in mios if v["red"] == r], dias).items()]
                    for r in (redes_mias if not red else [red]) if r in REDES},
        "seguidores": {f"{REDES[s['red']]} @{s['usuario']}": [[p["fecha"], p["seguidores"]] for p in s["serie"]]
                       for s in seg if len(s["serie"]) > 1},
    }
    act = k["videos"]
    mejores = sorted(act or mios, key=lambda v: -(v.get("vistas") or v.get("likes") or 0))[:8]
    tabla = sorted(act, key=lambda v: v.get("publicado") or "", reverse=True)
    return {"k": k, "por_red": por_red, "seguidores": seg, "grafica": grafica, "mejores": mejores, "tabla": tabla,
            "dias": dias, "red": red, "hay": {x: any(v.get(x) is not None for v in mios) for x in INTERACCIONES}}


def destacados_competencia(dias: int = 14, minimo: float = 1.5, por_red: int = 8) -> list[dict]:
    """Vídeos de la competencia que superan claramente la mediana de su propia cuenta."""
    vs = [v for v in videos(" AND c.mia=0") if v["multiplo"] and v["multiplo"] >= minimo
          and (v["edad"] is None or v["edad"] <= dias)]
    out = []
    for red in ("tiktok", "instagram", "youtube"):
        out += sorted([v for v in vs if v["red"] == red], key=lambda v: -v["multiplo"])[:por_red]
    return out

"""Cálculos: últimos datos de cada vídeo, mediana por cuenta, múltiplo (outlier) y resumen por periodo."""
from datetime import date, timedelta
from statistics import median

from ..db import q

SQL = """
SELECT v.*, c.usuario, c.mia, c.nombre AS cuenta_nombre, m.vistas, m.likes, m.comentarios, m.compartidos,
       m.guardados, m.alcance, m.fecha AS foto
FROM videos v JOIN cuentas c ON c.id = v.cuenta_id
LEFT JOIN metricas m ON m.video_id = v.id AND m.fecha = (SELECT MAX(fecha) FROM metricas WHERE video_id = v.id)
WHERE c.activa = 1
"""


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
        inter = sum(r.get(k) or 0 for k in ("likes", "comentarios", "compartidos", "guardados"))
        r["er"] = round(100 * inter / r["vistas"], 1) if r.get("vistas") else None
    return rows


def edad(fecha: str | None) -> int | None:
    try:
        return (date.today() - date.fromisoformat((fecha or "")[:10])).days
    except ValueError:
        return None


def resumen(dias: int = 7, red: str | None = None) -> dict:
    hoy = date.today()
    desde, antes = hoy - timedelta(days=dias), hoy - timedelta(days=2 * dias)
    mios = [v for v in videos(" AND c.mia=1") if red in (None, v["red"])]
    act = [v for v in mios if (v.get("publicado") or "")[:10] >= desde.isoformat()]
    prev = [v for v in mios if antes.isoformat() <= (v.get("publicado") or "")[:10] < desde.isoformat()]

    def tot(lst, k):
        return sum(v.get(k) or 0 for v in lst)

    kpis = {}
    for k in ("vistas", "likes", "comentarios", "compartidos", "guardados"):
        a, b = tot(act, k), tot(prev, k)
        kpis[k] = {"valor": a, "antes": b, "cambio": round(100 * (a - b) / b) if b else None,
                   "hay": any(v.get(k) is not None for v in mios)}
    kpis["publicaciones"] = {"valor": len(act), "antes": len(prev), "cambio": None, "hay": True}
    cuentas = q("SELECT * FROM cuentas WHERE mia=1 AND activa=1" + (" AND red=?" if red else ""),
                (red,) if red else ())
    seg = []
    for c in cuentas:
        serie = q("SELECT fecha, seguidores FROM seguidores WHERE cuenta_id=? AND fecha>=? ORDER BY fecha",
                  (c["id"], desde.isoformat()))
        ganados = (serie[-1]["seguidores"] - serie[0]["seguidores"]) if len(serie) > 1 else None
        seg.append({"red": c["red"], "usuario": c["usuario"], "seguidores": c["seguidores"], "ganados": ganados,
                    "serie": serie, "error": c["error"], "ultimo": c["ultimo"]})
    top = sorted(act or mios, key=lambda v: -(v.get("vistas") or v.get("likes") or 0))[:8]
    return {"kpis": kpis, "seguidores": seg, "top": top, "dias": dias, "red": red,
            "por_dia": _por_dia(act, dias)}


def _por_dia(lst: list[dict], dias: int) -> list[dict]:
    hoy = date.today()
    out = []
    for i in range(dias - 1, -1, -1):
        d = (hoy - timedelta(days=i)).isoformat()
        out.append({"fecha": d, "vistas": sum(v.get("vistas") or 0 for v in lst if (v.get("publicado") or "")[:10] == d)})
    return out


def destacados_competencia(dias: int = 14, minimo: float = 1.5, por_red: int = 8) -> list[dict]:
    """Vídeos de la competencia que superan claramente la mediana de su propia cuenta."""
    vs = [v for v in videos(" AND c.mia=0") if v["multiplo"] and v["multiplo"] >= minimo
          and (v["edad"] is None or v["edad"] <= dias)]
    out = []
    for red in ("tiktok", "instagram", "youtube"):
        out += sorted([v for v in vs if v["red"] == red], key=lambda v: -v["multiplo"])[:por_red]
    return out

"""Ideas de vídeo con IA: competencia que supera su media, tus mejores vídeos, tendencias y tus comentarios."""
import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

from .. import ajustes as A
from .. import llm
from ..db import ex, q
from . import metricas, tendencias

log = logging.getLogger("ideas")
GUARDAR_SOLA = 9.5
TIPOS = {"competencia": "Competencia", "tendencia": "Tendencia", "combinada": "Combinada",
         "segunda_parte": "Segunda parte", "automatizacion": "Automatización", "propia": "Tuya"}

SISTEMA = ("Eres estratega de contenido para TikTok, Instagram Reels y YouTube Shorts en español de España. Usas datos "
           "reales, no inventas cifras y das ideas concretas, accionables y honestas. Respondes solo con JSON.")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def parecida(titulo: str, otros: list[str], limite: float = 0.72) -> bool:
    a = _norm(titulo)
    wa = {w for w in a.split() if len(w) > 3}
    for o in otros:
        b = _norm(o)
        if SequenceMatcher(None, a, b).ratio() >= limite:
            return True
        wb = {w for w in b.split() if len(w) > 3}
        if wa and wb and len(wa & wb) / min(len(wa), len(wb)) >= 0.75:
            return True
    return False


def titulos_recientes(n: int = 40) -> list[str]:
    return [r["titulo"] for r in q("SELECT titulo FROM ideas WHERE estado!='descartada' AND titulo IS NOT NULL "
                                   "AND creada>=datetime('now','-14 days') ORDER BY id DESC LIMIT ?", (n,))]


def _fmt_video(v: dict) -> str:
    quien = "MÍO" if v["mia"] else f"COMPETIDOR @{v['usuario']}"
    base = f"vistas {v['vistas']}" if v.get("vistas") else f"me gusta {v.get('likes')}"
    return (f"- ref={v['id']} | {v['red']} | {quien} | hace {v.get('edad', '?')} días | {base} | "
            f"x{v.get('multiplo') or '?'} sobre su mediana | texto: {(v.get('texto') or '').replace(chr(10), ' ')[:300]}")


def _comentarios_utiles(limite: int = 25) -> list[dict]:
    """Preguntas e ideas de tus comentarios; fuera los de una palabra («info», «link»…)."""
    return [c for c in q("SELECT texto, autor, red FROM comentarios ORDER BY creado DESC LIMIT 300")
            if len((c["texto"] or "").split()) >= 4][:limite]


def generar(extra: int = 4, n_tendencias: int = 4) -> dict:
    try:
        tendencias.actualizar()
    except Exception as e:  # noqa: BLE001
        log.info("tendencias: %s", e)
    comp = metricas.destacados_competencia()
    mios = sorted(metricas.videos(" AND c.mia=1"), key=lambda v: -(v.get("multiplo") or 0))[:6]
    tr = tendencias.recientes()
    coms = _comentarios_utiles()
    if not (comp or mios or tr):
        raise ValueError("Aún no hay datos: añade tus cuentas y la competencia y pulsa «Actualizar datos».")
    prompt = f"""Contexto del canal: {A.get('contexto')}
Voz del canal: {A.get('voz') or '(sin definir)'}

MIS VÍDEOS QUE MEJOR FUNCIONAN:
{chr(10).join(_fmt_video(v) for v in mios) or '(sin datos)'}

COMPETENCIA QUE SUPERA SU PROPIA MEDIA (últimas 2 semanas):
{chr(10).join(_fmt_video(v) for v in comp) or '(ninguna)'}

TENDENCIAS (GitHub, Hacker News, Reddit):
{chr(10).join(f"- ref=T{t['id']} | {t['fuente']} | {t['etiqueta']} | {t['titulo']} — {(t['resumen'] or '')[:180]}" for t in tr) or '(ninguna)'}

LO QUE PREGUNTAN EN MIS COMENTARIOS:
{chr(10).join(f"- «{c['texto'][:160]}»" for c in coms) or '(nada)'}

Ya tengo estas ideas recientes; no las repitas ni hagas variantes casi iguales:
{chr(10).join('- ' + t for t in titulos_recientes()) or '(ninguna)'}

Tarea:
1. tipo="competencia": una idea por cada vídeo de la competencia que merezca la pena (ref = su número).
2. tipo="tendencia": {n_tendencias} ideas a partir de las tendencias que encajen (ref = "T<id>").
3. tipo="combinada": {extra} ideas que combinen patrones que funcionan (fuentes = refs).
4. tipo="segunda_parte": SOLO si mis comentarios muestran dudas claras sobre un vídeo mío (máximo 2).
Campos: "tipo", "ref", "fuentes" (lista), "titulo" (máx 90 caracteres), "por_que" (2-3 frases con datos),
"como" (3-5 frases: estructura, plano, cierre), "gancho" (frase exacta de los 2 primeros segundos, concreta, sin
saludos), "nota" (0-10 con un decimal; 9.5+ solo si casi seguro es un éxito), "motivo_nota" (una frase).
Responde SOLO JSON: {{"ideas": [ ... ]}}"""
    data = llm.generar_json(prompt, SISTEMA)
    items = data.get("ideas", data if isinstance(data, list) else [])
    ids_v = {v["id"] for v in comp + mios}
    ids_t = {t["id"] for t in tr}
    vistos = titulos_recientes(60)
    guardadas, n = [], 0
    for it in items:
        titulo = (it.get("titulo") or "").strip()
        if not titulo or parecida(titulo, vistos):
            continue
        tipo = it.get("tipo") if it.get("tipo") in TIPOS else "combinada"
        ref = str(it.get("ref") or "")
        video_id = int(ref) if ref.isdigit() and int(ref) in ids_v else None
        tend_id = int(ref[1:]) if ref[:1].upper() == "T" and ref[1:].isdigit() and int(ref[1:]) in ids_t else None
        if video_id and q("SELECT 1 FROM ideas WHERE video_id=? AND estado!='descartada' "
                          "AND creada>=datetime('now','-7 days')", (video_id,), one=True):
            continue
        try:
            nota = max(0.0, min(10.0, round(float(it.get("nota")), 1)))
        except (TypeError, ValueError):
            nota = None
        estado = "guardada" if (nota or 0) >= GUARDAR_SOLA else "nueva"
        ex("INSERT INTO ideas(tipo,titulo,por_que,como,gancho,nota,motivo_nota,video_id,tendencia_id,fuentes,estado) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
           (tipo, titulo, it.get("por_que"), it.get("como"), it.get("gancho"), nota, it.get("motivo_nota"), video_id,
            tend_id, json.dumps(it.get("fuentes") or []), estado))
        vistos.append(titulo)
        n += 1
        if estado == "guardada":
            guardadas.append(titulo)
    return {"ideas": n, "guardadas_solas": guardadas}


def listar(estado: str = "activas", tipo: str = "", orden: str = "recientes") -> list[dict]:
    donde, args = [], []
    if estado == "activas":
        donde.append("i.estado IN ('nueva','guardada')")
    elif estado in ("nueva", "guardada", "hecha", "descartada"):
        donde.append("i.estado=?")
        args.append(estado)
    if tipo in TIPOS:
        donde.append("i.tipo=?")
        args.append(tipo)
    sql = ("SELECT i.*, v.url AS v_url, v.texto AS v_texto, v.portada AS v_portada, c.usuario AS v_usuario, "
           "c.red AS v_red, t.url AS t_url, t.titulo AS t_titulo, t.etiqueta AS t_etiqueta FROM ideas i "
           "LEFT JOIN videos v ON v.id=i.video_id LEFT JOIN cuentas c ON c.id=v.cuenta_id "
           "LEFT JOIN tendencias t ON t.id=i.tendencia_id")
    if donde:
        sql += " WHERE " + " AND ".join(donde)
    sql += (" ORDER BY i.nota DESC, i.id DESC" if orden == "nota" else " ORDER BY date(i.creada) DESC, i.nota DESC, i.id DESC")
    rows = q(sql + " LIMIT 200", tuple(args))
    for r in rows:
        r["edad"] = metricas.edad(r["creada"])
        try:
            r["det"] = json.loads(r.get("detalle") or "null") or {}
        except ValueError:
            r["det"] = {}
    return rows

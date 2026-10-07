"""Estudio: auditoría de tus vídeos, comentarios clasificados, plan semanal, voz del canal y guion listo para grabar.

Usa las herramientas de la skill (skills/redes/herramientas): puntuar ganchos, hoja de ritmo, revisar el pie,
humanizar y detector. Todo lo que sale es un borrador: nada se publica solo.
"""
import json
import logging
import time
from statistics import median

from .. import ajustes as A
from .. import llm
from ..db import ex, q
from . import metricas

log = logging.getLogger("estudio")
SISTEMA = ("Eres estratega de contenido para TikTok e Instagram en español de España. Trabajas con datos reales, no "
           "inventas cifras (si falta un dato escribes {{tu dato}}) y escribes como una persona: frases de largo variado, "
           "concretas, sin muletillas de IA ni rayas largas. Respondes solo con JSON.")
CATEGORIAS = {"cliente": "Cliente potencial", "pregunta": "Pregunta", "idea": "Idea de vídeo", "apoyo": "Apoyo",
              "queja": "Queja o crítica", "ruido": "Ruido"}
OBJETIVO_S = 35


def H():
    """Las herramientas de la skill."""
    import herramientas
    return herramientas


def nota_gancho(texto: str) -> dict | None:
    if not (texto or "").strip():
        return None
    try:
        return H().puntuar_gancho(texto)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- auditoría
def auditoria(red: str | None = None, dias: int = 90) -> dict:
    out = []
    for v in metricas.videos(" AND c.mia=1"):
        if red and v["red"] != red or (v["edad"] is not None and v["edad"] > dias):
            continue
        vistas = v.get("vistas") or 0
        primera = ((v.get("texto") or "").strip().split("\n") or [""])[0][:160]
        try:
            f = H().clasificar_formula(primera) if primera else None
        except Exception:  # noqa: BLE001
            f = None
        out.append({"id": v["id"], "red": v["red"], "url": v["url"], "fecha": (v.get("publicado") or "")[:10],
                    "texto": primera, "vistas": vistas, "multiplo": v["multiplo"],
                    "comp_1k": round(1000 * (v.get("compartidos") or 0) / vistas, 1) if vistas and v.get("compartidos") is not None else None,
                    "guard_1k": round(1000 * (v.get("guardados") or 0) / vistas, 1) if vistas and v.get("guardados") is not None else None,
                    "formula": f["nombre"] if f else None})
    out.sort(key=lambda r: -(r["multiplo"] or 0))
    n = len(out)
    for i, r in enumerate(out):
        r["tercio"] = "arriba" if i < n / 3 else ("abajo" if i >= 2 * n / 3 else "medio")
    medianas = {rd: int(median([r["vistas"] for r in out if r["red"] == rd and r["vistas"]] or [0]))
                for rd in ("tiktok", "instagram", "youtube")}
    return {"videos": out, "medianas": medianas, "conclusiones": json.loads(A.get("auditoria") or "null")}


def auditoria_ia() -> dict:
    a = auditoria(None, 90)
    if len(a["videos"]) < 4:
        raise ValueError("Hacen falta al menos 4 vídeos tuyos con datos para sacar conclusiones.")
    lineas = "\n".join(
        f"- [{r['tercio']}] {r['red']} · x{r['multiplo']} tu media · {r['vistas']} vistas · {r['comp_1k']} compartidos/1k"
        f" · {r['guard_1k']} guardados/1k · fórmula {r['formula'] or '—'} · «{r['texto'][:120]}»" for r in a["videos"][:40])
    prompt = f"""Voz del canal: {A.get('voz') or '(sin definir)'}
Mis vídeos de los últimos 90 días, ordenados por múltiplo sobre mi propia mediana:
{lineas}

Haz la autopsia como un analista honesto: no mires las vistas brutas, mira el múltiplo y compartidos/guardados por
1.000 vistas. Devuelve JSON: {{"funciona": [3-5 patrones con el dato que lo demuestra], "no_funciona": [2-4],
"repetir": [3 vídeos que harías otra vez con otro ángulo], "dejar": [2 cosas], "siguiente": "una frase"}}"""
    data = llm.generar_json(prompt, SISTEMA)
    data["actualizado"] = time.strftime("%Y-%m-%d %H:%M")
    A.set("auditoria", json.dumps(data, ensure_ascii=False))
    return data


# ---------------------------------------------------------------- comentarios
def es_palabra_clave(texto: str) -> bool:
    """Comentarios de 1-3 palabras («info», «link», «quiero»): llamadas a la acción, no conversación."""
    return len((texto or "").split()) <= 3


def clasificar_comentarios(maximo: int = 80) -> dict:
    pend = [c for c in q("SELECT c.*, v.texto AS v_texto, v.url AS v_url FROM comentarios c "
                         "LEFT JOIN videos v ON v.id=c.video_id WHERE c.categoria IS NULL ORDER BY c.creado DESC LIMIT ?",
                         (maximo,))]
    sin = [c for c in pend if es_palabra_clave(c["texto"])]
    for c in sin:
        ex("UPDATE comentarios SET categoria='ruido', motivo='solo una palabra', analizado=? WHERE id=?",
           (time.strftime("%Y-%m-%d %H:%M"), c["id"]))
    pend = [c for c in pend if not es_palabra_clave(c["texto"])]
    hechos = 0
    for i in range(0, len(pend), 30):
        lote = pend[i:i + 30]
        videos = {}
        for c in lote:
            videos.setdefault((c.get("v_texto") or "")[:250], len(videos) + 1)
        lista = "\n".join(f"{k}. [vídeo V{videos[(c.get('v_texto') or '')[:250]]}] @{c['autor']}: «{c['texto'][:300]}»"
                          for k, c in enumerate(lote))
        vids = "\n".join(f"V{n}: {t or '(sin texto)'}" for t, n in videos.items())
        prompt = f"""Voz del canal: {A.get('voz') or 'cercano, directo, español de España'}
Contexto: {A.get('contexto')}
De qué va cada vídeo:
{vids}

Comentarios de MIS vídeos:
{lista}

Clasifica cada uno en: cliente (podría contratar o tiene un negocio con un problema), pregunta, idea (pide o sugiere un
vídeo), queja, apoyo, ruido. Escribe un borrador de respuesta como lo escribiría yo desde el móvil: máximo 2 frases y
30 palabras, concreto, usando lo que dice el vídeo; si no lo sé, «No lo he probado, lo miro y te digo». A un cliente
potencial, invítale a escribirme por privado. Apoyo simple y ruido: borrador vacío. Prohibido empezar con «El vídeo…».
Devuelve JSON: {{"items": [{{"i": n, "categoria": "...", "motivo": "6-10 palabras", "borrador": "..."}}]}}"""
        data = llm.generar_json(prompt, SISTEMA)
        for it in data.get("items", []):
            try:
                c = lote[int(it.get("i"))]
            except (TypeError, ValueError, IndexError):
                continue
            borr = (it.get("borrador") or "").strip()
            if borr:
                try:
                    borr = H().humanizar(borr)["texto"]
                except Exception:  # noqa: BLE001
                    pass
            cat = it.get("categoria") if it.get("categoria") in CATEGORIAS else "ruido"
            ex("UPDATE comentarios SET categoria=?, motivo=?, borrador=?, analizado=? WHERE id=?",
               (cat, (it.get("motivo") or "")[:200], borr, time.strftime("%Y-%m-%d %H:%M"), c["id"]))
            hechos += 1
    return {"clasificados": hechos, "palabra_clave": len(sin)}


def comentarios(categoria: str = "", estado: str = "pendiente") -> list[dict]:
    sql = ("SELECT c.*, v.url AS v_url FROM comentarios c LEFT JOIN videos v ON v.id=c.video_id "
           "WHERE c.categoria IS NOT NULL AND c.categoria!='ruido'")
    args = []
    if categoria in CATEGORIAS:
        sql += " AND c.categoria=?"
        args.append(categoria)
    if estado in ("pendiente", "hecho"):
        sql += " AND c.estado=?"
        args.append(estado)
    sql += (" ORDER BY CASE c.categoria WHEN 'cliente' THEN 0 WHEN 'pregunta' THEN 1 WHEN 'idea' THEN 2 "
            "WHEN 'queja' THEN 3 ELSE 4 END, c.creado DESC LIMIT 200")
    return q(sql, tuple(args))


def conteo_comentarios() -> dict:
    return {r["categoria"]: r["n"] for r in q("SELECT categoria, COUNT(*) n FROM comentarios WHERE estado='pendiente' "
                                              "AND categoria IS NOT NULL GROUP BY categoria")}


# ---------------------------------------------------------------- plan, voz
def plan_semanal() -> dict:
    guard = q("SELECT id, tipo, titulo, gancho, nota FROM ideas WHERE estado='guardada' ORDER BY nota DESC LIMIT 12")
    nuevas = q("SELECT id, tipo, titulo, gancho, nota FROM ideas WHERE estado='nueva' "
               "AND creada>=datetime('now','-7 days') ORDER BY nota DESC LIMIT 15")
    lst = lambda rs: "\n".join(f"- id={r['id']} [{r['tipo']}] {r['nota']} · {r['titulo']}" for r in rs)  # noqa: E731
    prompt = f"""Voz del canal: {A.get('voz') or '(sin definir)'}
Contexto: {A.get('contexto')}
Conclusiones de la auditoría: {(A.get('auditoria') or '(sin auditoría)')[:1500]}
Ideas GUARDADAS (prioridad):
{lst(guard) or '(ninguna)'}
Otras ideas recientes con buena nota:
{lst(nuevas) or '(ninguna)'}

Prepara el plan de los próximos 7 días (el mismo vídeo va a TikTok e Instagram). Ritmo realista: 3-5 vídeos. Para cada
día: qué publicar (usa el id de la idea), formato, hora recomendada (España), el gancho exacto y una palabra clave si
el vídeo ofrece un recurso. Días sin vídeo: una tarea corta (responder comentarios, grabar en bloque…).
Devuelve JSON: {{"dias": [{{"dia": "lunes", "tipo": "video"|"tarea", "idea_id": n|null, "titulo": "...", "formato": "...",
"hora": "HH:MM", "gancho": "...", "palabra": "..."|null, "nota": "..."}}], "foco": "una frase"}}"""
    data = llm.generar_json(prompt, SISTEMA)
    data["creado"] = time.strftime("%Y-%m-%d %H:%M")
    A.set("plan", json.dumps(data, ensure_ascii=False))
    return data


def plan_actual() -> dict | None:
    return json.loads(A.get("plan") or "null")


def generar_voz() -> str:
    mios = sorted(metricas.videos(" AND c.mia=1"), key=lambda v: -(v.get("vistas") or v.get("likes") or 0))[:15]
    textos = "\n".join(f"- {(v.get('texto') or '')[:400]}" for v in mios)
    if not textos.strip():
        raise ValueError("Primero añade tu cuenta y actualiza los datos: la voz sale de tus propios textos.")
    prompt = f"""Textos de mis vídeos con más vistas:
{textos}
Contexto: {A.get('contexto')}
Escribe mi «voz del canal» en Markdown con secciones cortas: Quién soy y para quién hablo · Tono · Cómo hablo ·
Palabras que uso · Palabras y muletillas que NUNCA uso · Cómo cierro un vídeo. Máximo 220 palabras, concreto.
Devuelve JSON {{"voz": "..."}}"""
    v = (llm.generar_json(prompt, SISTEMA).get("voz") or "").strip()
    if v:
        A.set("voz", v)
    return v


# ---------------------------------------------------------------- guion listo para grabar
def datos_reales() -> str:
    out = []
    for c in q("SELECT red, usuario, seguidores FROM cuentas WHERE mia=1 AND activa=1"):
        if c["seguidores"]:
            out.append(f"- Seguidores en {c['red']} (@{c['usuario']}): {c['seguidores']}")
    return "\n".join(out)


def _evaluar(data: dict) -> dict:
    h = H()
    res = {}
    ganchos = []
    for g in data.get("ganchos") or []:
        t = (g.get("texto") or "").strip() if isinstance(g, dict) else str(g).strip()
        if not t:
            continue
        n = nota_gancho(t) or {}
        ganchos.append({"texto": t, "formula": g.get("formula") if isinstance(g, dict) else None,
                        "nota": n.get("score"), "nivel": n.get("nivel"), "peor": n.get("peor"),
                        "avisos": n.get("rompe_tratos") or []})
    ganchos.sort(key=lambda x: -(x["nota"] or 0))
    res["ganchos"] = ganchos
    lineas = [dict(x) for x in (data.get("guion") or []) if isinstance(x, dict) and (x.get("texto") or "").strip()]
    if ganchos and lineas:
        lineas[0]["texto"] = ganchos[0]["texto"]
    for x in lineas:
        try:
            x["texto"] = h.humanizar(x["texto"])["texto"]
        except Exception:  # noqa: BLE001
            pass
    res["guion"] = lineas
    if lineas:
        res["ritmo"] = h.hoja_de_ritmo("\n".join(x["texto"] for x in lineas), objetivo_s=OBJETIVO_S)
        res["humano"] = h.puntuar("\n".join(x["texto"] for x in lineas))
    for clave, red in (("pie_instagram", "instagram"), ("descripcion_tiktok", "tiktok")):
        txt = (data.get(clave) or "").strip()
        rev = None
        if txt:
            txt = h.humanizar(txt)["texto"]
            rev = h.revisar_pie(txt, [], red=red)
        res[clave] = {"texto": txt, "revision": rev}
    res["palabra"] = data.get("palabra")
    return res


def nota_total(res: dict) -> float:
    g = (res.get("ganchos") or [{}])[0].get("nota") or 0
    t = (res.get("ritmo") or {}).get("total_s") or OBJETIVO_S
    dur = max(0, 100 - 4 * abs(t - OBJETIVO_S))
    pen = 0
    for k in ("pie_instagram", "descripcion_tiktok"):
        for c in ((res.get(k) or {}).get("revision") or {}).get("checks", []):
            pen += 10 if c.get("estado") == "FAIL" else (3 if c.get("estado") == "WARN" else 0)
    hum = (res.get("humano") or {}).get("human_score") or 50
    return 0.45 * g + 0.25 * dur + 0.3 * hum - pen


def notas_para_corregir(res: dict) -> str:
    out = [f"- Gancho «{h['texto']}»: {h['nota']}/100 ({h['nivel']}); punto débil {h['peor']}"
           + (f"; {'; '.join(h['avisos'])}" if h["avisos"] else "") for h in (res.get("ganchos") or [])[:3]]
    r = res.get("ritmo") or {}
    if r:
        out.append(f"- Duración {r.get('total_s')} s para un objetivo de {OBJETIVO_S} s.")
        out += [f"- Ritmo: {a}" for a in r.get("avisos", [])]
    for k, lbl in (("pie_instagram", "Pie de Instagram"), ("descripcion_tiktok", "Descripción de TikTok")):
        rev = (res.get(k) or {}).get("revision") or {}
        out += [f"- {lbl}: {c['check']} {c['estado']}: {c['detalle']}" for c in rev.get("checks", [])
                if c.get("estado") in ("WARN", "FAIL")]
    hm = res.get("humano") or {}
    if hm:
        out.append(f"- Suena humano: {hm.get('human_score')}/100 ({hm.get('veredicto')}); peor: {hm.get('peor')}")
    return "\n".join(out)


def preparar_guion(idea_id: int, vueltas: int = 2) -> dict:
    """Genera el guion, lo pasa por las herramientas y lo corrige con sus avisos (hasta 2 vueltas)."""
    idea = q("SELECT * FROM ideas WHERE id=?", (idea_id,), one=True)
    if not idea:
        raise ValueError("No existe esa idea")
    try:
        formulas = "\n".join(f"- {f['id']}: {f['nombre']} — {f['plantilla']}" for f in H().formulas())
    except Exception:  # noqa: BLE001
        formulas = ""
    prompt = f"""Voz del canal: {A.get('voz') or 'cercano, directo, español de España'}
Contexto: {A.get('contexto')}
Idea: «{idea['titulo']}»
Por qué: {idea.get('por_que') or ''}
Cómo: {idea.get('como') or ''}
Gancho propuesto: {idea.get('gancho') or ''}
Datos reales que puedes usar:
{datos_reales() or '(ninguno)'}
Las cifras de la idea y de estos datos son reales: úsalas. No inventes otras; si falta una, escribe {{{{tu dato}}}}.

Prepara el vídeo corto ({OBJETIVO_S} s) listo para grabar:
1. "ganchos": 3 ganchos para los 2 primeros segundos, cada uno con una fórmula distinta{(' de esta lista (id en "formula"):' + chr(10) + formulas) if formulas else ''}.
2. "guion": frases en orden, cada una con "texto", "pantalla" (qué se ve) y "rotulo" (máx 6 palabras o ""). La
   primera es el gancho; la última enlaza con el principio.
3. "pie_instagram" (primera línea que enganche en 125 caracteres, máx 5 hashtags, una sola llamada a la acción) y
   "descripcion_tiktok" (corta, 3-5 hashtags).
4. "palabra": palabra clave para pedir el recurso por comentario, o null.
Devuelve JSON: {{"ganchos": [{{"texto": "...", "formula": "..."}}], "guion": [...], "pie_instagram": "...",
"descripcion_tiktok": "...", "palabra": "..."}}"""
    data = llm.generar_json(prompt, SISTEMA)
    mejor = _evaluar(data)
    versiones = 1
    for _ in range(vueltas):
        notas = notas_para_corregir(mejor)
        if not notas:
            break
        fix = (f"{prompt}\n\nYa hay un borrador y las herramientas lo han revisado. Corrígelo con estas notas y devuelve "
               f"el JSON completo. Arregla sobre todo el gancho (concreto, lo importante delante, menos de 8 palabras), la "
               f"duración (unas {OBJETIVO_S * 170 // 60} palabras) y las frases largas.\nBorrador: "
               f"{json.dumps({k: data.get(k) for k in ('ganchos', 'guion', 'pie_instagram', 'descripcion_tiktok')}, ensure_ascii=False)[:6000]}"
               f"\nNotas:\n{notas}")
        try:
            data2 = llm.generar_json(fix, SISTEMA)
        except Exception as e:  # noqa: BLE001
            log.info("corrección: %s", e)
            break
        res2 = _evaluar(data2)
        versiones += 1
        if nota_total(res2) > nota_total(mejor):
            mejor, data = res2, data2
        else:
            break
    mejor["versiones"] = versiones
    mejor["creado"] = time.strftime("%Y-%m-%d %H:%M")
    det = json.loads(idea.get("detalle") or "null") or {}
    det["guion"] = mejor
    ex("UPDATE ideas SET detalle=? WHERE id=?", (json.dumps(det, ensure_ascii=False), idea_id))
    return mejor

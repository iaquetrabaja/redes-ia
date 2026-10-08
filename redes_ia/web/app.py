"""Panel web local (FastAPI). Solo escucha en 127.0.0.1: nadie de fuera de tu ordenador puede abrirlo."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import RAIZ, __version__
from .. import ajustes as A
from .. import llm, tareas
from ..db import ex, iniciar, q
from ..servicios import automatizaciones, datos, estudio, ideas, metricas

AQUI = Path(__file__).parent
app = FastAPI(title="Redes IA", version=__version__, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
import os as _os

# Para publicar una demo detrás de un proxy: prefijo de la URL, modo solo lectura y orígenes permitidos.
# En tu ordenador no hace falta tocar nada.
BASE = (_os.environ.get("REDES_IA_BASE") or "").rstrip("/")
SOLO_LECTURA = _os.environ.get("REDES_IA_SOLO_LECTURA") == "1"
ORIGENES = [o.strip() for o in (_os.environ.get("REDES_IA_ORIGENES") or "").split(",") if o.strip()]

plantillas = Jinja2Templates(directory=AQUI / "templates")
plantillas.env.globals.update(B=BASE, SOLO_LECTURA=SOLO_LECTURA, TIPOS=ideas.TIPOS, REDES=datos.REDES, CATEGORIAS=estudio.CATEGORIAS, version=__version__)


def miles(n):
    if n is None:
        return "—"
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


plantillas.env.filters["miles"] = miles


def _negrita(texto: str):
    from markupsafe import Markup, escape
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(escape(texto))))


plantillas.env.filters["negrita"] = _negrita


def _dec(n, d: int = 1):
    """Número con decimales a la española: 4,3"""
    if n is None:
        return "—"
    return f"{n:.{d}f}".replace(".", ",")


plantillas.env.filters["dec"] = _dec


@app.on_event("startup")
def _arranque():
    iniciar()
    tareas.iniciar()


@app.middleware("http")
async def _solo_local(request: Request, call_next):
    """Las peticiones que cambian algo solo se aceptan desde esta misma web (evita que otra página las dispare)."""
    if request.method == "POST":
        origen = request.headers.get("origin") or request.headers.get("referer") or ""
        if origen and not any(origen.startswith(f"http://{h}") for h in ("127.0.0.1", "localhost")) \
                and not origen.startswith("http://testserver") and not any(origen.startswith(o) for o in ORIGENES) \
                and not (ORIGENES and origen == "null"):
            # «null»: detrás de un proxy con Referrer-Policy no-referrer el navegador no manda el origen. Solo se
            # acepta en instalaciones publicadas (con REDES_IA_ORIGENES); en tu ordenador sigue rechazándose.
            return JSONResponse({"error": "origen no permitido"}, status_code=403)
        if SOLO_LECTURA and request.url.path != "/herramientas":
            seccion = request.url.path.strip("/").split("/")[0]
            vuelta = BASE + "/" + ("" if seccion in ("", "actualizar") else seccion)
            return RedirectResponse(vuelta + "?err=" + quote("Es una demo de solo lectura: descarga Redes IA para "
                                                              "usarlo con tus datos y tu IA."), status_code=303)
    return await call_next(request)


def ver(request: Request, nombre: str, **ctx):
    from .explicaciones import EXPLICACIONES, clave
    ctx.setdefault("explica", EXPLICACIONES.get(clave(request.url.path, request.query_params)))
    if nombre == "ideas.html":
        ctx.setdefault("explica_guion", EXPLICACIONES.get("guion"))
    ctx.update(request=request, ruta=request.url.path, ok=request.query_params.get("ok"),
               err=request.query_params.get("err"), demo=A.get("modo_demo") == "1", en_marcha=tareas.en_marcha(),
               ia_ok=llm.configurado(), proveedor=llm.PROVEEDORES.get(llm.proveedor(), {}).get("nombre"))
    return plantillas.TemplateResponse(request, nombre, ctx)


def ir(url: str, ok: str | None = None, err: str | None = None) -> RedirectResponse:
    url, _, frag = url.partition("#")
    sep = "&" if "?" in url else "?"
    if ok:
        url += f"{sep}ok={quote(ok)}"
    elif err:
        url += f"{sep}err={quote(err)}"
    if url.startswith("/") and not url.startswith(BASE + "/"):
        url = BASE + url
    return RedirectResponse(url + (f"#{frag}" if frag else ""), status_code=303)


def _necesita_ia(destino: str):
    if A.get("modo_demo") == "1":
        return ir(destino, err="En el modo demo la IA no está conectada. Arranca sin --demo y elige tu proveedor.")
    if not llm.configurado():
        return ir("/ajustes?tab=ia", err="Primero conecta una IA (Gemini es gratis).")
    return None


# ---------------------------------------------------------------- inicio y bienvenida
@app.get("/", response_class=HTMLResponse)
def resumen(request: Request, dias: int = 0, red: str = ""):
    if (A.get("modo_demo") != "1" and not llm.configurado() and not q("SELECT 1 FROM cuentas", one=True)
            and not request.query_params.get("saltar")):
        return RedirectResponse(BASE + "/bienvenida", status_code=303)
    _demo_al_dia()
    dias = dias if dias in (3, 7, 30, 90) else int(A.get("dias_resumen") or 7)
    red = red if red in datos.REDES else ""
    r = metricas.resumen(dias, red or None)
    cp = metricas.comparativa(dias, red or None)
    return ver(request, "resumen.html", r=r, dias=dias, red=red, tareas=tareas.ultimas(4), cp=cp,
               hay_cuentas=bool(q("SELECT 1 FROM cuentas WHERE mia=1", one=True)))


def _demo_al_dia():
    """En modo demo, los datos de ejemplo se rehacen una vez al día para que las gráficas lleguen hasta hoy."""
    if A.get("modo_demo") == "1":
        from ..servicios import demo
        demo.cargar()


def _periodo(dias: int) -> int:
    return dias if dias in (3, 7, 30, 90) else 7


# ---------------------------------------------------------------- competencia
@app.get("/competencia", response_class=HTMLResponse)
def ver_competencia(request: Request, dias: int = 7, red: str = ""):
    _demo_al_dia()
    dias = _periodo(dias)
    return ver(request, "competencia.html", dias=dias, grupos=metricas.competencia(dias),
               cp=metricas.comparativa(dias, red or None))


@app.get("/competencia/{cid}", response_class=HTMLResponse)
def ver_ficha(request: Request, cid: int, dias: int = 30):
    f = metricas.ficha(cid, _periodo(dias))
    if not f:
        return ir("/competencia", err="Esa cuenta ya no está")
    return ver(request, "ficha.html", f=f, dias=_periodo(dias))


@app.get("/api/comprobar")
def api_comprobar(red: str = "tiktok", usuario: str = ""):
    """Lee la página pública de la cuenta y dice si funciona (nombre, seguidores, últimos vídeos) o qué falla."""
    if SOLO_LECTURA:
        return {"ok": False, "tipo": "demo", "mensaje": "En la demo de solo lectura no se comprueban cuentas.",
                "que_hacer": "Descarga Redes IA y pruébalo con tu @: tarda unos segundos.", "videos": []}
    if red not in datos.REDES:
        return {"ok": False, "tipo": "otro", "mensaje": "Red no válida", "que_hacer": "", "videos": []}
    return datos.comprobar_cuenta(red, usuario)


def anadir_cuenta_comprobada(red: str, usuario: str, mia: bool, vuelta: str):
    """Comprueba la cuenta antes de guardarla. Si no existe, es privada o el @ está mal, no se guarda y se dice qué
    hacer. Si TikTok solo está frenando, se guarda y se leerá en la próxima actualización."""
    if red not in datos.REDES:
        return ir(vuelta, err="Red no válida")
    if A.get("modo_demo") == "1":
        return ir(vuelta, err="En el modo demo no se añaden cuentas reales. Arranca sin --demo para usar las tuyas.")
    aviso = ""
    if red in ("tiktok", "youtube"):
        r = datos.comprobar_cuenta(red, usuario)
        if not r["ok"] and r["tipo"] not in ("frena", "sin_conexion"):
            return ir(vuelta, err=f"{r['mensaje']} {r['que_hacer']}".strip())
        if not r["ok"]:
            aviso = f" Ojo: {r['mensaje']} Se leerá en la próxima actualización."
        elif r["tipo"] == "sin_videos":
            aviso = " " + r["mensaje"]
        usuario = r.get("usuario") or usuario
    try:
        cid = datos.anadir_cuenta(red, usuario, mia)
    except Exception as e:  # noqa: BLE001
        return ir(vuelta, err=str(e))
    c = q("SELECT * FROM cuentas WHERE id=?", (cid,), one=True)
    if not aviso:
        tareas.ejecutar(f"cuenta-{cid}", datos.actualizar_cuenta, c)
    return ir(vuelta, ok=f"@{c['usuario']} añadida{' (tuya)' if mia else ''}; leyendo sus vídeos…{aviso}")


@app.post("/competencia/cuenta")
def competencia_cuenta(red: str = Form(...), usuario: str = Form(""), mia: str = Form("0")):
    return anadir_cuenta_comprobada(red, usuario, mia == "1", "/competencia")


def _borrar_cuenta(cid: int):
    vids = [r["id"] for r in q("SELECT id FROM videos WHERE cuenta_id=?", (cid,))]
    for v in vids:
        ex("DELETE FROM metricas WHERE video_id=?", (v,))
        ex("DELETE FROM comentarios WHERE video_id=?", (v,))
    ex("DELETE FROM videos WHERE cuenta_id=?", (cid,))
    ex("DELETE FROM seguidores WHERE cuenta_id=?", (cid,))
    ex("DELETE FROM cuentas WHERE id=?", (cid,))


@app.post("/competencia/cuenta/{cid}/borrar")
def competencia_cuenta_borrar(cid: int):
    _borrar_cuenta(cid)
    return ir("/competencia", ok="Cuenta quitada")


@app.get("/bienvenida", response_class=HTMLResponse)
def bienvenida(request: Request, paso: int = 1):
    return ver(request, "bienvenida.html", paso=paso, proveedores=llm.PROVEEDORES, actual=llm.proveedor())


@app.post("/bienvenida/ia")
def bienvenida_ia(proveedor: str = Form(...), clave: str = Form(""), ollama_url: str = Form("")):
    if proveedor not in llm.PROVEEDORES:
        return ir("/bienvenida", err="Elige un proveedor")
    _guardar_ia(proveedor, clave, ollama_url)
    try:
        m = llm.modelo_por_defecto(proveedor)
        A.set("modelo", m)
        llm.probar(proveedor, m)
    except Exception as e:  # noqa: BLE001
        return ir("/bienvenida", err=f"No funciona todavía: {e}")
    return ir("/bienvenida?paso=2", ok=f"Conectado con {llm.PROVEEDORES[proveedor]['nombre']} ({m})")


@app.post("/bienvenida/cuentas")
def bienvenida_cuentas(tiktok: str = Form(""), competencia: str = Form(""), contexto: str = Form("")):
    if contexto.strip():
        A.set("contexto", contexto.strip()[:600])
    if tiktok.strip() and A.get("modo_demo") != "1":
        r = datos.comprobar_cuenta("tiktok", tiktok)
        if not r["ok"] and r["tipo"] not in ("frena", "sin_conexion"):
            return ir("/bienvenida?paso=2", err=f"Tu TikTok: {r['mensaje']} {r['que_hacer']}".strip())
        datos.anadir_cuenta("tiktok", r.get("usuario") or tiktok, True)
    for u in [x for x in competencia.replace("\n", ",").split(",") if x.strip()][:15]:
        datos.anadir_cuenta("tiktok", u, False)
    tareas.ejecutar("datos", datos.actualizar_todo)
    return ir("/", ok="¡Listo! Estoy leyendo tus vídeos y los de tu competencia; tarda un par de minutos.")


def _guardar_ia(proveedor: str, clave: str, ollama_url: str = ""):
    A.set("proveedor", proveedor)
    info = llm.PROVEEDORES[proveedor]
    if info["clave"] and clave.strip():
        A.set(info["clave"], clave.strip())
    if proveedor == "ollama" and ollama_url.strip():
        A.set("ollama_url", ollama_url.strip())


# ---------------------------------------------------------------- datos
@app.post("/actualizar")
def actualizar(request: Request):
    if A.get("modo_demo") == "1":
        return ir("/", err="En el modo demo no se leen datos reales.")
    lanzado = tareas.ejecutar("datos", datos.actualizar_todo)
    return ir(request.headers.get("referer") or "/", ok="Actualizando tus datos… tarda un par de minutos." if lanzado
              else None, err=None if lanzado else "Ya se está actualizando")


@app.get("/api/estado")
def estado():
    return {"en_marcha": sorted(tareas.en_marcha()), "ultimas": tareas.ultimas(5)}


# ---------------------------------------------------------------- ideas
@app.get("/ideas", response_class=HTMLResponse)
def ver_ideas(request: Request, estado_: str = "activas", tipo: str = "", orden: str = "recientes"):
    estado_ = request.query_params.get("estado", estado_)
    lista = ideas.listar(estado_, tipo, orden)
    for i in lista:
        i["gnota"] = estudio.nota_gancho(i.get("gancho") or "")
    return ver(request, "ideas.html", ideas=lista, estado=estado_, tipo=tipo, orden=orden)


@app.post("/ideas/generar")
def generar_ideas():
    if (r := _necesita_ia("/ideas")):
        return r
    ok = tareas.ejecutar("ideas", ideas.generar)
    return ir("/ideas", ok="Buscando ideas con IA… recarga en 1-2 minutos." if ok else None,
              err=None if ok else "Ya se están generando")


@app.post("/ideas/nueva")
def idea_nueva(titulo: str = Form(...), gancho: str = Form(""), por_que: str = Form("")):
    ex("INSERT INTO ideas(tipo,titulo,gancho,por_que,estado,fuentes) VALUES('propia',?,?,?,'guardada','[]')",
       (titulo.strip()[:200], gancho.strip()[:300], por_que.strip()[:1000]))
    return ir("/ideas?estado=guardada", ok="Idea guardada")


@app.post("/ideas/{iid}/estado")
def idea_estado(request: Request, iid: int, estado: str = Form(...)):
    if estado in ("nueva", "guardada", "hecha", "descartada"):
        ex("UPDATE ideas SET estado=? WHERE id=?", (estado, iid))
    return ir((request.headers.get("referer") or "/ideas").split("?ok=")[0].split("&ok=")[0])


@app.post("/ideas/{iid}/guion")
def idea_guion(request: Request, iid: int):
    vuelta = (request.headers.get("referer") or "/ideas").split("#")[0] + f"#idea-{iid}"
    if (r := _necesita_ia(vuelta)):
        return r
    ok = tareas.ejecutar(f"guion-{iid}", estudio.preparar_guion, iid)
    return ir(vuelta, ok="Preparando el guion: ganchos puntuados, tiempos y textos revisados… recarga en un minuto."
              if ok else None, err=None if ok else "Ya se está preparando")


@app.get("/automatizaciones", response_class=HTMLResponse)
def ver_automatizaciones(request: Request):
    lista = ideas.listar("activas", "automatizacion")
    for i in lista:
        i["gnota"] = estudio.nota_gancho(i.get("gancho") or "")
    return ver(request, "automatizaciones.html", ideas=lista)


@app.post("/automatizaciones/generar")
def generar_automatizaciones():
    if (r := _necesita_ia("/automatizaciones")):
        return r
    ok = tareas.ejecutar("automatizaciones", automatizaciones.generar)
    return ir("/automatizaciones", ok="Pensando automatizaciones… recarga en 1-2 minutos." if ok else None,
              err=None if ok else "Ya se están generando")


# ---------------------------------------------------------------- estudio
@app.get("/estudio", response_class=HTMLResponse)
def ver_estudio(request: Request, tab: str = "auditoria", red: str = "", cat: str = "", estado: str = "pendiente"):
    tab = tab if tab in ("auditoria", "comentarios", "plan", "voz") else "auditoria"
    ctx = {"tab": tab}
    if tab == "auditoria":
        ctx.update(a=estudio.auditoria(red or None), red=red)
    elif tab == "comentarios":
        ctx.update(items=estudio.comentarios(cat, estado), conteo=estudio.conteo_comentarios(), cat=cat, estado=estado,
                   sin_clasificar=q("SELECT COUNT(*) n FROM comentarios WHERE categoria IS NULL", one=True)["n"])
    elif tab == "plan":
        ctx["plan"] = estudio.plan_actual()
    else:
        ctx["voz"] = A.get("voz")
    return ver(request, "estudio.html", **ctx)


@app.post("/estudio/{accion}")
def estudio_accion(accion: str, voz: str = Form(""), generar: str = Form("")):
    destinos = {"auditoria": ("auditoria", estudio.auditoria_ia, "Sacando conclusiones…"),
                "comentarios": ("comentarios", estudio.clasificar_comentarios, "Clasificando comentarios…"),
                "plan": ("plan", estudio.plan_semanal, "Preparando el plan de la semana…")}
    if accion == "voz":
        if generar:
            if (r := _necesita_ia("/estudio?tab=voz")):
                return r
            tareas.ejecutar("voz", estudio.generar_voz)
            return ir("/estudio?tab=voz", ok="Escribiendo tu voz a partir de tus vídeos… recarga en un minuto.")
        A.set("voz", voz.strip()[:4000])
        return ir("/estudio?tab=voz", ok="Voz guardada")
    if accion not in destinos:
        return ir("/estudio")
    tab, fn, msg = destinos[accion]
    if (r := _necesita_ia(f"/estudio?tab={tab}")):
        return r
    ok = tareas.ejecutar(accion, fn)
    return ir(f"/estudio?tab={tab}", ok=msg + " recarga en un minuto." if ok else None,
              err=None if ok else "Ya está en marcha")


@app.post("/comentarios/{cid}/estado")
def comentario_estado(request: Request, cid: str, estado: str = Form("hecho")):
    ex("UPDATE comentarios SET estado=? WHERE id=?", ("hecho" if estado == "hecho" else "pendiente", cid))
    return ir(request.headers.get("referer") or "/estudio?tab=comentarios")


# ---------------------------------------------------------------- herramientas
@app.get("/herramientas", response_class=HTMLResponse)
def ver_herramientas(request: Request, h: str = "gancho"):
    return ver(request, "herramientas.html", h=h, res=None, entrada={})


@app.post("/herramientas", response_class=HTMLResponse)
async def usar_herramienta(request: Request):
    import herramientas as H
    f = await request.form()
    h = f.get("h", "gancho")
    entrada = dict(f)
    try:
        if h == "gancho":
            lineas = [x for x in (f.get("texto") or "").splitlines() if x.strip()]
            res = H.ranking(lineas) if len(lineas) > 1 else [H.puntuar_gancho(lineas[0] if lineas else "")]
        elif h == "ritmo":
            res = H.hoja_de_ritmo(f.get("texto") or "", objetivo_s=float(f.get("objetivo") or 30))
        elif h == "pie":
            res = H.revisar_pie(f.get("texto") or "", [x.strip() for x in (f.get("palabras") or "").split(",") if x.strip()],
                                red=f.get("red") or "instagram")
        elif h == "humanizar":
            res = H.humanizar(f.get("texto") or "")
            res["detector_antes"] = H.puntuar(f.get("texto") or "")
            res["detector_despues"] = H.puntuar(res["texto"])
        elif h == "viral":
            filas = []
            for linea in (f.get("texto") or "").splitlines():
                partes = [p.strip() for p in linea.replace(";", "\t").split("\t")]
                if len(partes) >= 3:
                    filas.append({"cuenta": partes[0], "mediana": partes[1], "vistas": partes[2],
                                  "gancho": partes[3] if len(partes) > 3 else ""})
            res = H.ranking_viral(filas)
        else:
            res = None
    except Exception as e:  # noqa: BLE001
        return ver(request, "herramientas.html", h=h, res=None, entrada=entrada, error=str(e))
    return ver(request, "herramientas.html", h=h, res=res, entrada=entrada)


# ---------------------------------------------------------------- ajustes
@app.get("/ajustes", response_class=HTMLResponse)
def ver_ajustes(request: Request, tab: str = "ia"):
    py = sys.executable.replace("\\", "/")
    raiz = str(RAIZ).replace("\\", "/")
    mcp_cfg = {"mcpServers": {"redes-ia": {"command": py, "args": [f"{raiz}/mcp_redes.py"]}}}
    claves = {p: A.oculta(A.get(i["clave"])) if i["clave"] else "" for p, i in llm.PROVEEDORES.items()}
    return ver(request, "ajustes.html", tab=tab, proveedores=llm.PROVEEDORES, actual=llm.proveedor(),
               modelo=llm.modelo(), claves=claves, cuentas=q("SELECT * FROM cuentas ORDER BY mia DESC, red, usuario"),
               ig=A.oculta(A.get("ig_token")), fb=A.oculta(A.get("fb_token")), fb_ig_id=A.get("fb_ig_id"),
               cfg=lambda k: A.get(k), mcp_json=json.dumps(mcp_cfg, indent=2, ensure_ascii=False), py=py, raiz=raiz,
               tareas_lista=tareas.ultimas(10))


@app.post("/ajustes/ia")
def ajustes_ia(proveedor: str = Form(...), clave: str = Form(""), modelo: str = Form(""), ollama_url: str = Form(""),
               probar: str = Form("")):
    if proveedor not in llm.PROVEEDORES:
        return ir("/ajustes?tab=ia", err="Proveedor no válido")
    cambio = proveedor != llm.proveedor()
    _guardar_ia(proveedor, clave, ollama_url)
    if modelo.strip():
        A.set("modelo", modelo.strip())
    elif cambio or not A.get("modelo"):
        A.set("modelo", llm.modelo_por_defecto(proveedor))
    if probar:
        try:
            resp = llm.probar(proveedor, llm.modelo())
            return ir("/ajustes?tab=ia", ok=f"Funciona: {llm.PROVEEDORES[proveedor]['nombre']} con {llm.modelo()} respondió «{resp}»")
        except Exception as e:  # noqa: BLE001
            return ir("/ajustes?tab=ia", err=str(e))
    return ir("/ajustes?tab=ia", ok="Guardado")


@app.get("/ajustes/modelos")
def ajustes_modelos(proveedor: str):
    try:
        return {"modelos": llm.listar_modelos(proveedor)}
    except Exception as e:  # noqa: BLE001
        return {"modelos": [], "error": str(e)}


@app.post("/ajustes/cuenta")
def ajustes_cuenta(red: str = Form(...), usuario: str = Form(""), mia: str = Form("0")):
    return anadir_cuenta_comprobada(red, usuario, mia == "1", "/competencia")


@app.post("/ajustes/cuenta/{cid}/borrar")
def ajustes_cuenta_borrar(cid: int):
    _borrar_cuenta(cid)
    return ir("/competencia", ok="Cuenta quitada")


@app.post("/ajustes/instagram")
def ajustes_instagram(token: str = Form(""), fb_token: str = Form(""), fb_ig_id: str = Form("")):
    from ..colectores import instagram
    if token.strip():
        A.set("ig_token", token.strip())
        try:
            p = instagram.perfil()
            datos.anadir_cuenta("instagram", p.get("username") or "mi_cuenta", True)
        except Exception as e:  # noqa: BLE001
            return ir("/ajustes?tab=redes", err=f"Token guardado, pero Instagram responde: {e}")
    if fb_token.strip():
        A.set("fb_token", fb_token.strip())
    if fb_ig_id.strip():
        A.set("fb_ig_id", fb_ig_id.strip())
    return ir("/ajustes?tab=redes", ok="Instagram conectado")


@app.post("/ajustes/csv")
async def ajustes_csv(request: Request):
    f = await request.form()
    texto = f.get("csv") or ""
    archivo = f.get("archivo")
    if archivo is not None and hasattr(archivo, "read"):
        texto = (await archivo.read()).decode("utf-8-sig", "ignore") or texto
    try:
        n = datos.importar_csv(texto)
    except Exception as e:  # noqa: BLE001
        return ir("/competencia", err=f"No se pudo leer el CSV: {e}")
    return ir("/competencia", ok=f"{n} vídeos importados")


@app.post("/ajustes/general")
def ajustes_general(contexto: str = Form(""), temas: str = Form(""), subreddits: str = Form(""),
                    hora_diaria: str = Form("6"), dias_resumen: str = Form("7")):
    A.set("contexto", contexto.strip()[:800])
    A.set("temas", temas.strip()[:400])
    A.set("subreddits", subreddits.strip()[:200])
    A.set("hora_diaria", str(max(0, min(23, int(hora_diaria or 6)))))
    A.set("dias_resumen", dias_resumen if dias_resumen in ("3", "7", "30", "90") else "7")
    tareas.reprogramar()
    return ir("/ajustes?tab=general", ok="Guardado")

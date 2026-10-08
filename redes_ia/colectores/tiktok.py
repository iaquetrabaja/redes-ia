"""TikTok sin login ni contraseñas, solo datos públicos.

- Perfil y últimos vídeos (con vistas): la página pública de «insertar perfil» (tiktok.com/embed/@usuario), la misma
  que usan las webs para mostrar tu TikTok. Da seguidores y los ~10 últimos vídeos con sus reproducciones.
- Detalle de un vídeo (likes, comentarios, compartidos, guardados): yt-dlp, sin descargar el vídeo.
- Comentarios: el listado público de comentarios, con pausas.

Va despacio a propósito: pocas peticiones, con esperas y reintentos suaves. Si TikTok cambia algo, se avisa y se
sigue con lo demás.
"""
import json
import logging
import random
import re
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("tiktok")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/141.0 Safari/537.36")


class ErrorTikTok(Exception):
    """Error con un motivo concreto (tipo) para poder decir al usuario qué hacer."""

    def __init__(self, mensaje: str, tipo: str = "otro"):
        super().__init__(mensaje)
        self.tipo = tipo


# Qué hacer en cada caso. Se enseña tal cual en el panel.
QUE_HACER = {
    "vacio": "Escribe tu @ de TikTok (por ejemplo @tu_usuario) o pega el enlace de tu perfil.",
    "formato": "Un @ de TikTok solo lleva letras, números, puntos y guiones bajos (sin espacios ni tildes). Cópialo "
               "desde tu perfil: en la app, debajo de tu foto; en la web, en la barra de direcciones tras «tiktok.com/@».",
    "no_existe": "Revisa que esté bien escrito: es el @ que sale debajo de tu foto en la app, no tu nombre. Si lo "
                 "cambiaste hace poco, usa el nuevo.",
    "privada": "TikTok no enseña los vídeos de las cuentas privadas a nadie. En la app: Perfil → ☰ → Ajustes y "
               "privacidad → Privacidad → desactiva «Cuenta privada».",
    "sin_videos": "La cuenta existe, pero no tiene vídeos públicos todavía. Publica uno (o cambia los que tengas a "
                  "«Todo el mundo») y vuelve a comprobar.",
    "frena": "TikTok está frenando las lecturas ahora mismo. Espera 10-15 minutos y pulsa «Comprobar» otra vez. Si "
             "usas una VPN, apágala.",
    "sin_conexion": "No hay conexión con TikTok. Mira que tengas internet; si estás en una red de empresa, colegio o "
                    "con VPN, puede que bloquee TikTok.",
    "otro": "Vuelve a intentarlo en unos minutos. Si sigue igual varios días, actualiza Redes IA.",
}


def limpiar_usuario(u: str) -> str:
    """Acepta @usuario, usuario o el enlace del perfil (o de un vídeo) y devuelve el usuario en minúsculas."""
    u = (u or "").strip()
    m = re.search(r"tiktok\.com/@([\w.\-]+)", u)
    if m:
        u = m.group(1)
    return u.strip().lstrip("@").strip().strip("/").lower()


def usuario_valido(u: str) -> bool:
    """TikTok solo admite letras, números, «_» y «.», de 2 a 24 caracteres (sin acabar en punto)."""
    return bool(re.fullmatch(r"[a-z0-9_.]{2,24}", u or "")) and not u.endswith(".")


def fecha_de_id(vid: str) -> str | None:
    """Los id de TikTok llevan la fecha dentro: los 32 bits altos son los segundos desde 1970."""
    try:
        return datetime.fromtimestamp(int(vid) >> 32, timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        return None


def _get(cliente: httpx.Client, url: str, intentos: int = 3, **kw) -> httpx.Response:
    """GET con reintentos suaves (2 s, 5 s…). Los errores que no se arreglan reintentando (400, 404, 500: en la
    página de «insertar perfil» suelen ser una cuenta que no existe) se devuelven a la primera."""
    espera, sin_red = 2, 0
    for intento in range(intentos):
        try:
            r = cliente.get(url, **kw)
            if r.status_code == 200 and r.text:
                return r
            if r.status_code in (400, 404, 410, 500):
                return r
        except httpx.HTTPError as e:
            log.info("TikTok %s: %s", url, e)
            sin_red += isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout))
        if intento < intentos - 1:
            time.sleep(espera + random.random())
            espera = espera * 2 + 1
    if sin_red == intentos:
        raise ErrorTikTok("No se puede conectar con TikTok.", "sin_conexion")
    raise ErrorTikTok("TikTok no responde ahora mismo (está frenando las lecturas).", "frena")


def _diagnostico(cliente: httpx.Client, u: str) -> ErrorTikTok:
    """La página de insertar no dio el perfil: la página normal dice si no existe, si es privada o si TikTok frena."""
    try:
        r = _get(cliente, f"https://www.tiktok.com/@{u}", intentos=2)
    except ErrorTikTok as e:
        return e
    t = r.text or ""
    codigo = re.search(r'"statusCode":(\d+)', t)
    codigo = int(codigo.group(1)) if codigo else None
    if r.status_code == 404 or codigo in (10202, 10221, 10223):
        return ErrorTikTok(f"No existe ninguna cuenta @{u} en TikTok.", "no_existe")
    if codigo == 10222 or '"privateAccount":true' in t:
        return ErrorTikTok(f"@{u} es una cuenta privada.", "privada")
    return ErrorTikTok("TikTok no ha devuelto el perfil (suele ser que está frenando las lecturas).", "frena")


def perfil(usuario: str) -> dict:
    u = limpiar_usuario(usuario)
    if not u:
        raise ErrorTikTok("Falta el usuario de TikTok.", "vacio")
    if not usuario_valido(u):
        raise ErrorTikTok(f"«{u}» no parece un @ de TikTok.", "formato")
    with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"}, follow_redirects=True,
                      timeout=30) as c:
        r = _get(c, f"https://www.tiktok.com/embed/@{u}")
        m = re.search(r'<script id="__FRONTITY_CONNECT_STATE__"[^>]*>(.*?)</script>', r.text or "", re.S) \
            if r.status_code == 200 else None
        try:
            data = json.loads(m.group(1)).get("source", {}).get("data", {}) if m else {}
        except ValueError:
            data = {}
        bloque = next((v for k, v in data.items() if k.lower().endswith(f"@{u}")), None) or {}
        info = bloque.get("userInfo") or {}
        if not info:
            raise _diagnostico(c, u)
    if info.get("privateAccount"):
        raise ErrorTikTok(f"@{u} es una cuenta privada.", "privada")
    videos = []
    for v in bloque.get("videoList") or []:
        vid = str(v.get("id") or "")
        if not vid or v.get("privateItem"):
            continue
        videos.append({"vid": vid, "url": f"https://www.tiktok.com/@{u}/video/{vid}", "texto": v.get("desc") or "",
                       "portada": v.get("coverUrl") or v.get("originCoverUrl"), "publicado": fecha_de_id(vid),
                       "vistas": v.get("playCount"), "likes": v.get("diggCount"),
                       "comentarios": v.get("commentCount")})
    return {"usuario": u, "nombre": info.get("nickname") or u, "seguidores": info.get("followerCount"),
            "videos": videos}


def comprobar(usuario: str) -> dict:
    """Prueba una cuenta antes de guardarla. Nunca lanza: devuelve si funciona, el motivo si no y qué hacer.

    {"ok": bool, "tipo": "ok"|"sin_videos"|"no_existe"|"privada"|"frena"|…, "mensaje": str, "que_hacer": str,
     "usuario": str, "nombre": str|None, "seguidores": int|None, "videos": [{texto, vistas, publicado, url}…]}
    """
    u = limpiar_usuario(usuario)
    base = {"usuario": u, "nombre": None, "seguidores": None, "videos": []}
    try:
        p = perfil(usuario)
    except ErrorTikTok as e:
        return {**base, "ok": False, "tipo": e.tipo, "mensaje": str(e), "que_hacer": QUE_HACER.get(e.tipo, "")}
    except Exception as e:  # noqa: BLE001
        log.info("comprobar @%s: %s", u, e)
        return {**base, "ok": False, "tipo": "otro", "mensaje": "No se pudo leer la página de TikTok.",
                "que_hacer": QUE_HACER["otro"]}
    vids = [{k: v.get(k) for k in ("texto", "vistas", "publicado", "url")} for v in p["videos"]]
    if not vids:
        return {**p, "ok": True, "tipo": "sin_videos", "videos": [],
                "mensaje": f"@{p['usuario']} existe, pero no tiene vídeos públicos.", "que_hacer": QUE_HACER["sin_videos"]}
    return {**p, "ok": True, "tipo": "ok", "videos": vids[:5], "n_videos": len(vids),
            "mensaje": f"Funciona: @{p['usuario']} ({p['nombre']}), {len(vids)} vídeos leídos.", "que_hacer": ""}


def detalle(url: str) -> dict:
    """Likes, comentarios, compartidos y guardados de un vídeo (yt-dlp, sin descargar nada)."""
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 30}
    with yt_dlp.YoutubeDL(opts) as y:
        i = y.extract_info(url, download=False)
    return {"vistas": i.get("view_count"), "likes": i.get("like_count"), "comentarios": i.get("comment_count"),
            "compartidos": i.get("repost_count"), "guardados": i.get("save_count"), "duracion": i.get("duration"),
            "texto": i.get("description") or i.get("title")}


def comentarios(vid: str, maximo: int = 50) -> list[dict]:
    out = []
    with httpx.Client(headers={"User-Agent": UA, "Referer": "https://www.tiktok.com/"}, follow_redirects=True,
                      timeout=30) as c:
        try:
            c.get("https://www.tiktok.com/")   # cookie de visitante
        except httpx.HTTPError:
            pass
        cursor = 0
        while len(out) < maximo:
            r = c.get("https://www.tiktok.com/api/comment/list/",
                      params={"aid": 1988, "count": 50, "aweme_id": vid, "cursor": cursor})
            try:
                d = r.json()
            except ValueError:
                break
            for x in d.get("comments") or []:
                us = x.get("user") or {}
                out.append({"id": f"tt_{x.get('cid')}", "autor": us.get("unique_id") or "", "texto": x.get("text") or "",
                            "likes": x.get("digg_count") or 0,
                            "creado": datetime.fromtimestamp(x.get("create_time") or 0, timezone.utc).isoformat()})
            if not d.get("has_more"):
                break
            cursor = d.get("cursor") or cursor + 50
            time.sleep(1.5 + random.random())
    return out[:maximo]

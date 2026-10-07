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
    pass


def limpiar_usuario(u: str) -> str:
    u = (u or "").strip()
    m = re.search(r"tiktok\.com/@([\w.\-]+)", u)
    if m:
        u = m.group(1)
    return u.lstrip("@").strip().lower()


def fecha_de_id(vid: str) -> str | None:
    """Los id de TikTok llevan la fecha dentro: los 32 bits altos son los segundos desde 1970."""
    try:
        return datetime.fromtimestamp(int(vid) >> 32, timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        return None


def _get(cliente: httpx.Client, url: str, **kw) -> httpx.Response:
    espera = 3
    for intento in range(3):
        try:
            r = cliente.get(url, **kw)
            if r.status_code == 200 and r.text:
                return r
            if r.status_code in (403, 404):
                return r
        except httpx.HTTPError as e:
            log.info("TikTok %s: %s", url, e)
        time.sleep(espera + random.random())
        espera *= 2
    raise ErrorTikTok("TikTok no responde ahora mismo. Se reintentará en la próxima actualización.")


def perfil(usuario: str) -> dict:
    u = limpiar_usuario(usuario)
    if not u:
        raise ErrorTikTok("Usuario de TikTok vacío")
    with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"}, follow_redirects=True,
                      timeout=30) as c:
        r = _get(c, f"https://www.tiktok.com/embed/@{u}")
    if r.status_code == 404:
        raise ErrorTikTok(f"No existe la cuenta @{u} en TikTok")
    m = re.search(r'<script id="__FRONTITY_CONNECT_STATE__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        raise ErrorTikTok("TikTok ha cambiado la página pública del perfil; no se pudieron leer los vídeos.")
    data = json.loads(m.group(1)).get("source", {}).get("data", {})
    bloque = next((v for k, v in data.items() if k.lower().endswith(f"@{u}")), None) or next(iter(data.values()), {})
    info = bloque.get("userInfo") or {}
    if info.get("privateAccount"):
        raise ErrorTikTok(f"@{u} es una cuenta privada")
    videos = []
    for v in bloque.get("videoList") or []:
        vid = str(v.get("id") or "")
        if not vid or v.get("privateItem"):
            continue
        videos.append({"vid": vid, "url": f"https://www.tiktok.com/@{u}/video/{vid}", "texto": v.get("desc") or "",
                       "portada": v.get("coverUrl") or v.get("originCoverUrl"), "publicado": fecha_de_id(vid),
                       "vistas": v.get("playCount")})
    return {"usuario": u, "nombre": info.get("nickname") or u, "seguidores": info.get("followerCount"),
            "videos": videos}


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

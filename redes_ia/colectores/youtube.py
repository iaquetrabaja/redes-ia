"""YouTube Shorts (opcional): vídeos y vistas de un canal con yt-dlp, sin descargar nada y sin clave."""
import re


class ErrorYouTube(Exception):
    pass


def limpiar_canal(c: str) -> str:
    c = (c or "").strip()
    m = re.search(r"youtube\.com/(@[\w.\-]+|channel/[\w\-]+|c/[\w\-]+)", c)
    if m:
        return m.group(1)
    return c if c.startswith("@") else "@" + c.lstrip("@")


def perfil(canal: str, maximo: int = 15) -> dict:
    import yt_dlp
    c = limpiar_canal(canal)
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True, "playlistend": maximo,
            "socket_timeout": 30}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            i = y.extract_info(f"https://www.youtube.com/{c}/shorts", download=False)
    except Exception as e:  # noqa: BLE001
        raise ErrorYouTube(f"No se pudo leer {c} en YouTube: {str(e)[:150]}") from e
    videos = [{"vid": e.get("id"), "url": e.get("url") or f"https://www.youtube.com/shorts/{e.get('id')}",
               "texto": e.get("title") or "", "portada": (e.get("thumbnails") or [{}])[-1].get("url"),
               "publicado": None, "vistas": e.get("view_count")} for e in (i.get("entries") or []) if e.get("id")]
    return {"usuario": c.lstrip("@").lower(), "nombre": i.get("channel") or i.get("title") or c,
            "seguidores": i.get("channel_follower_count"), "videos": videos}

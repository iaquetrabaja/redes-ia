"""Instagram con la API oficial («API de Instagram con inicio de sesión de Instagram»).

Solo TU cuenta profesional (creador o empresa): perfil, seguidores, publicaciones con métricas, estadísticas
(insights) y comentarios. El token de larga duración dura 60 días y se renueva solo desde aquí.

La competencia: Instagram no da datos de cuentas ajenas con este tipo de token. Opciones:
- añadir sus vídeos a mano o por CSV (Ajustes → Competencia), o
- «Business Discovery», que necesita un token de Facebook (página vinculada a la cuenta de Instagram).
"""
import time

import httpx

from .. import ajustes as A

IG = "https://graph.instagram.com/v23.0"
FB = "https://graph.facebook.com/v23.0"


class ErrorInstagram(Exception):
    pass


def _get(url: str, params: dict) -> dict:
    r = httpx.get(url, params=params, timeout=30)
    try:
        d = r.json()
    except ValueError as e:
        raise ErrorInstagram(f"Instagram respondió algo raro ({r.status_code})") from e
    if r.status_code >= 400 or "error" in d:
        msg = (d.get("error") or {}).get("message") or r.text[:200]
        if r.status_code in (400, 401, 190) and "token" in msg.lower():
            raise ErrorInstagram("El token de Instagram no es válido o ha caducado. Genera uno nuevo (Ajustes → Redes).")
        raise ErrorInstagram(f"Instagram: {msg}")
    return d


def token() -> str:
    t = A.get("ig_token")
    if not t:
        raise ErrorInstagram("Falta el token de Instagram (Ajustes → Redes).")
    return t


def perfil() -> dict:
    return _get(f"{IG}/me", {"fields": "user_id,username,name,followers_count,follows_count,media_count,biography",
                              "access_token": token()})


def renovar_token() -> str:
    """Los tokens de larga duración caducan a los 60 días; se renuevan si tienen más de 24 h."""
    t = token()
    d = _get("https://graph.instagram.com/refresh_access_token", {"grant_type": "ig_refresh_token",
                                                                   "access_token": t})
    if d.get("access_token"):
        A.set("ig_token", d["access_token"])
        A.set("ig_token_renovado", str(int(time.time())))
        return "renovado"
    return "sin cambios"


def publicaciones(maximo: int = 30) -> list[dict]:
    d = _get(f"{IG}/me/media", {"fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,"
                                          "comments_count,thumbnail_url,media_url", "limit": min(50, maximo),
                                "access_token": token()})
    out = []
    for m in d.get("data", [])[:maximo]:
        out.append({"vid": m["id"], "url": m.get("permalink"), "texto": m.get("caption") or "",
                    "portada": m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") == "IMAGE" else None),
                    "publicado": m.get("timestamp"), "likes": m.get("like_count"),
                    "comentarios": m.get("comments_count"), "tipo": m.get("media_product_type") or m.get("media_type")})
    return out


def estadisticas(media_id: str, tipo: str = "") -> dict:
    """Vistas, alcance, guardados y compartidos (si la publicación los da; los reels sí)."""
    metricas = "views,reach,saved,shares" if (tipo or "").upper() in ("REELS", "VIDEO", "CLIPS") else "reach,saved,shares"
    try:
        d = _get(f"{IG}/{media_id}/insights", {"metric": metricas, "access_token": token()})
    except ErrorInstagram:
        return {}
    out = {}
    for x in d.get("data", []):
        v = (x.get("values") or [{}])[0].get("value")
        out[x.get("name")] = v if v is not None else x.get("total_value", {}).get("value")
    return {"vistas": out.get("views"), "alcance": out.get("reach"), "guardados": out.get("saved"),
            "compartidos": out.get("shares")}


def comentarios(media_id: str, maximo: int = 50) -> list[dict]:
    d = _get(f"{IG}/{media_id}/comments", {"fields": "id,text,timestamp,like_count,from,username",
                                            "limit": min(50, maximo), "access_token": token()})
    return [{"id": f"ig_{c['id']}", "autor": (c.get("from") or {}).get("username") or c.get("username") or "",
             "texto": c.get("text") or "", "likes": c.get("like_count") or 0, "creado": c.get("timestamp") or ""}
            for c in d.get("data", [])]


def business_discovery(usuario: str) -> dict:
    """Competencia por Business Discovery (opcional): necesita token de Facebook y el id de tu cuenta de IG."""
    fb, ig_id = A.get("fb_token"), A.get("fb_ig_id")
    if not (fb and ig_id):
        raise ErrorInstagram("Para leer otras cuentas de Instagram hace falta el token de Facebook (Ajustes → Redes).")
    campos = (f"business_discovery.username({usuario}){{username,name,followers_count,media.limit(25)"
              "{id,caption,permalink,timestamp,like_count,comments_count,media_type,media_product_type}}")
    d = _get(f"{FB}/{ig_id}", {"fields": campos, "access_token": fb}).get("business_discovery", {})
    vids = [{"vid": m["id"], "url": m.get("permalink"), "texto": m.get("caption") or "", "portada": None,
             "publicado": m.get("timestamp"), "likes": m.get("like_count"), "comentarios": m.get("comments_count")}
            for m in (d.get("media") or {}).get("data", [])]
    return {"usuario": usuario, "nombre": d.get("name") or usuario, "seguidores": d.get("followers_count"),
            "videos": vids}

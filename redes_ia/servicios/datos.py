"""Actualizar cuentas: guarda vídeos, una foto diaria de sus métricas y los seguidores."""
import csv
import io
import logging
import time
from datetime import date

from .. import ajustes as A
from ..colectores import instagram, tiktok, youtube
from ..db import ex, q

log = logging.getLogger("datos")
REDES = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube Shorts"}


def _guardar_video(cuenta_id: int, red: str, v: dict) -> int:
    ex("""INSERT INTO videos(cuenta_id, red, vid, url, texto, portada, publicado, duracion) VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(red, vid) DO UPDATE SET url=excluded.url, texto=COALESCE(NULLIF(excluded.texto,''), texto),
          portada=COALESCE(excluded.portada, portada), publicado=COALESCE(excluded.publicado, publicado),
          duracion=COALESCE(excluded.duracion, duracion)""",
       (cuenta_id, red, v["vid"], v.get("url"), v.get("texto") or "", v.get("portada"), v.get("publicado"),
        v.get("duracion")))
    return q("SELECT id FROM videos WHERE red=? AND vid=?", (red, v["vid"]), one=True)["id"]


def _guardar_metricas(video_id: int, m: dict) -> None:
    hoy = date.today().isoformat()
    ex("""INSERT INTO metricas(video_id, fecha, vistas, likes, comentarios, compartidos, guardados, alcance)
          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(video_id, fecha) DO UPDATE SET
          vistas=COALESCE(excluded.vistas, vistas), likes=COALESCE(excluded.likes, likes),
          comentarios=COALESCE(excluded.comentarios, comentarios), compartidos=COALESCE(excluded.compartidos, compartidos),
          guardados=COALESCE(excluded.guardados, guardados), alcance=COALESCE(excluded.alcance, alcance)""",
       (video_id, hoy, m.get("vistas"), m.get("likes"), m.get("comentarios"), m.get("compartidos"),
        m.get("guardados"), m.get("alcance")))


def _guardar_comentarios(red: str, video_id: int, cs: list[dict]) -> int:
    n = 0
    for c in cs:
        if not c.get("texto"):
            continue
        ex("INSERT OR IGNORE INTO comentarios(id, red, video_id, autor, texto, likes, creado) VALUES(?,?,?,?,?,?,?)",
           (c["id"], red, video_id, c.get("autor"), c["texto"], c.get("likes"), c.get("creado")))
        n += 1
    return n


def actualizar_cuenta(c: dict) -> str:
    red, mia = c["red"], bool(c["mia"])
    try:
        if red == "tiktok":
            p = tiktok.perfil(c["usuario"])
        elif red == "youtube":
            p = youtube.perfil(c["usuario"])
        elif red == "instagram":
            if mia:
                pf = instagram.perfil()
                p = {"nombre": pf.get("name") or pf.get("username"), "seguidores": pf.get("followers_count"),
                     "videos": instagram.publicaciones()}
            else:
                p = instagram.business_discovery(c["usuario"])
        else:
            return "red desconocida"
        n = 0
        for v in p["videos"]:
            vid_id = _guardar_video(c["id"], red, v)
            m = {"vistas": v.get("vistas"), "likes": v.get("likes"), "comentarios": v.get("comentarios")}
            if red == "instagram" and mia:
                m.update({k: val for k, val in instagram.estadisticas(v["vid"], v.get("tipo", "")).items()
                          if val is not None})
            if red == "tiktok" and mia:       # mis vídeos: detalle completo (likes, compartidos, guardados)
                try:
                    m.update({k: val for k, val in tiktok.detalle(v["url"]).items()
                              if val is not None and k != "texto" and k != "duracion"})
                    time.sleep(1.5)
                except Exception as e:  # noqa: BLE001
                    log.info("detalle TikTok %s: %s", v["vid"], e)
            _guardar_metricas(vid_id, m)
            n += 1
        if mia:   # comentarios de mis 5 vídeos más recientes
            recientes = q("SELECT id, vid FROM videos WHERE cuenta_id=? ORDER BY publicado DESC LIMIT 5", (c["id"],))
            for r in recientes:
                try:
                    cs = tiktok.comentarios(r["vid"]) if red == "tiktok" else (
                        instagram.comentarios(r["vid"]) if red == "instagram" else [])
                    _guardar_comentarios(red, r["id"], cs)
                except Exception as e:  # noqa: BLE001
                    log.info("comentarios %s: %s", r["vid"], e)
        ex("UPDATE cuentas SET nombre=COALESCE(?, nombre), seguidores=COALESCE(?, seguidores), ultimo=?, error=NULL "
           "WHERE id=?", (p.get("nombre"), p.get("seguidores"), time.strftime("%Y-%m-%d %H:%M"), c["id"]))
        if p.get("seguidores") is not None:
            ex("INSERT OR REPLACE INTO seguidores(cuenta_id, fecha, seguidores) VALUES(?,?,?)",
               (c["id"], date.today().isoformat(), p["seguidores"]))
        return f"{n} vídeos"
    except Exception as e:  # noqa: BLE001
        ex("UPDATE cuentas SET error=? WHERE id=?", (str(e)[:300], c["id"]))
        log.info("Cuenta %s/%s: %s", red, c["usuario"], e)
        return f"error: {e}"


def actualizar_todo() -> dict:
    res = {}
    if A.tiene("ig_token"):
        try:
            renov = int(A.get("ig_token_renovado") or 0)
            if time.time() - renov > 7 * 86400:
                instagram.renovar_token()
        except Exception as e:  # noqa: BLE001
            log.info("Renovar token IG: %s", e)
    for c in q("SELECT * FROM cuentas WHERE activa=1 AND demo=0 ORDER BY mia DESC, id"):
        if c["red"] == "instagram" and not c["mia"] and not A.tiene("fb_token"):
            continue   # competencia de Instagram sin Business Discovery: solo datos manuales/CSV
        res[f"{c['red']}/@{c['usuario']}"] = actualizar_cuenta(c)
        time.sleep(2)
    return res


def anadir_cuenta(red: str, usuario: str, mia: bool) -> int:
    u = tiktok.limpiar_usuario(usuario) if red == "tiktok" else (
        youtube.limpiar_canal(usuario).lstrip("@").lower() if red == "youtube" else usuario.strip().lstrip("@").lower())
    if not u:
        raise ValueError("Escribe el usuario")
    ex("INSERT OR IGNORE INTO cuentas(red, usuario, mia) VALUES(?,?,?)", (red, u, int(mia)))
    ex("UPDATE cuentas SET mia=?, activa=1 WHERE red=? AND usuario=?", (int(mia), red, u))
    return q("SELECT id FROM cuentas WHERE red=? AND usuario=?", (red, u), one=True)["id"]


def importar_csv(texto: str) -> int:
    """Vídeos de la competencia a mano: columnas cuenta, url, texto, vistas[, likes, fecha]. Separador , o ;"""
    muestra = texto[:2000]
    dialect = csv.Sniffer().sniff(muestra, delimiters=",;\t") if muestra.strip() else csv.excel
    filas = list(csv.DictReader(io.StringIO(texto), dialect=dialect))
    n = 0
    for f in filas:
        f = {(k or "").strip().lower(): (v or "").strip() for k, v in f.items()}
        cuenta, url = f.get("cuenta", "").lstrip("@").lower(), f.get("url", "")
        if not cuenta or not url:
            continue
        cid = anadir_cuenta("instagram", cuenta, False)
        vid = url.rstrip("/").split("/")[-1] or url
        v_id = _guardar_video(cid, "instagram", {"vid": vid, "url": url, "texto": f.get("texto", ""),
                                                 "publicado": f.get("fecha") or None})
        _guardar_metricas(v_id, {"vistas": _num(f.get("vistas")), "likes": _num(f.get("likes"))})
        n += 1
    return n


def _num(s: str | None):
    if not s:
        return None
    s = s.lower().replace(" ", "")
    mult = 1000 if s.endswith("k") or s.endswith("mil") else (1_000_000 if s.endswith("m") else 1)
    s = s.rstrip("kmil").replace(".", "").replace(",", ".")
    try:
        return int(float(s) * mult)
    except ValueError:
        return None

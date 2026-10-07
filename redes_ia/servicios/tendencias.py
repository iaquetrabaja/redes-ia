"""Tendencias de tu nicho: repos nuevos de GitHub, Hacker News y Reddit. Fuentes públicas sin clave; si una falla,
se sigue con las demás. Los temas se cambian en Ajustes (por defecto, IA práctica)."""
import html
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from .. import ajustes as A
from ..db import ex, q

log = logging.getLogger("tendencias")
UA = {"User-Agent": "redes-ia/1.0 (+https://github.com/iaquetrabaja/redes-ia)"}
DEFECTO_TEMAS = "IA, LLM, agentes, automatización, ChatGPT, Claude, Gemini, código abierto"
DEFECTO_SUBREDDITS = "artificial, ChatGPT, LocalLLaMA"


def temas() -> list[str]:
    return [t.strip() for t in (A.get("temas") or DEFECTO_TEMAS).split(",") if t.strip()]


def subreddits() -> list[str]:
    return [t.strip().lstrip("r/") for t in (A.get("subreddits") or DEFECTO_SUBREDDITS).split(",") if t.strip()]


def _guardar(url, titulo, resumen, fuente, metrica, etiqueta, creada):
    if not url or not titulo:
        return
    ahora = datetime.now(timezone.utc).isoformat(timespec="minutes")
    ex("""INSERT INTO tendencias(url,titulo,resumen,fuente,metrica,etiqueta,creada,vista) VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(url) DO UPDATE SET metrica=excluded.metrica, vista=excluded.vista""",
       (url, titulo[:200], (resumen or "")[:400] or None, fuente, int(metrica or 0), etiqueta, creada, ahora))


def github(dias: int = 14) -> int:
    desde = (date.today() - timedelta(days=dias)).isoformat()
    n = 0
    for t in temas()[:6]:
        try:
            r = httpx.get("https://api.github.com/search/repositories", headers={**UA, "Accept": "application/vnd.github+json"},
                          params={"q": f"{t} created:>{desde} stars:>30", "sort": "stars", "order": "desc",
                                  "per_page": 8}, timeout=20)
            if r.status_code == 403:
                break
            r.raise_for_status()
            for it in r.json().get("items", []):
                _guardar(it["html_url"], it["full_name"], it.get("description"), "github", it["stargazers_count"],
                         f"{it['stargazers_count']} estrellas", it["created_at"][:10])
                n += 1
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            log.info("GitHub '%s': %s", t, e)
    return n


def hacker_news(horas: int = 48) -> int:
    desde = int(time.time()) - horas * 3600
    n = 0
    for t in temas()[:6]:
        try:
            r = httpx.get("https://hn.algolia.com/api/v1/search", headers=UA, timeout=20,
                          params={"query": t, "tags": "story", "numericFilters": f"created_at_i>{desde},points>60",
                                  "hitsPerPage": 10})
            r.raise_for_status()
            for h in r.json().get("hits", []):
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
                _guardar(url, h["title"], f"Hacker News · {h.get('num_comments', 0)} comentarios", "hackernews",
                         h.get("points"), f"{h.get('points')} puntos", (h.get("created_at") or "")[:10])
                n += 1
        except Exception as e:  # noqa: BLE001
            log.info("HN '%s': %s", t, e)
    return n


def reddit() -> int:
    n = 0
    for sub in subreddits()[:5]:
        try:
            r = httpx.get(f"https://www.reddit.com/r/{sub}/top/.rss", params={"t": "day"}, timeout=20,
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141 Safari/537.36"})
            if r.status_code != 200:
                continue
            for i, e in enumerate(re.findall(r"<entry>(.*?)</entry>", r.text, re.S)[:8]):
                tit = re.search(r"<title>(.*?)</title>", e, re.S)
                link = re.search(r'<link href="([^"]+)"', e)
                upd = re.search(r"<(?:published|updated)>([^<]+)<", e)
                if tit and link:
                    _guardar(link.group(1), html.unescape(tit.group(1)).strip(), None, f"reddit/{sub}", 100 - i * 5,
                             f"top {i + 1} del día en r/{sub}", (upd.group(1) if upd else "")[:10])
                    n += 1
        except Exception as e:  # noqa: BLE001
            log.info("Reddit r/%s: %s", sub, e)
    return n


def actualizar() -> dict:
    res = {"github": github(), "hackernews": hacker_news(), "reddit": reddit()}
    ex("DELETE FROM tendencias WHERE vista < ?", ((date.today() - timedelta(days=21)).isoformat(),))
    return res


def recientes(limite: int = 24, dias: int = 5) -> list[dict]:
    desde = (date.today() - timedelta(days=dias)).isoformat()
    rows = q("SELECT * FROM tendencias WHERE vista >= ? ORDER BY metrica DESC", (desde,))
    por: dict[str, list] = {}
    for r in rows:
        por.setdefault(r["fuente"].split("/")[0], []).append(r)
    cada = max(4, limite // max(1, len(por)))
    return [r for lst in por.values() for r in lst[:cada]][:limite]

"""Miniaturas con IA: portadas para TikTok, Reels y YouTube con TU cara, a partir de la idea del vídeo.

Cómo funciona:
1. Subes 3-10 fotos tuyas (de frente, buena luz). Se guardan solo en tu ordenador (datos/caras).
2. La IA de texto propone el texto de la miniatura (corto, que se entienda solo) y la escena.
3. La IA de imagen crea la miniatura usando tus fotos como referencia de identidad. En cada versión se usa una mezcla
   distinta de tus fotos y un gesto, un ángulo y una ropa distintos, para que no salgas siempre igual.

Generar imágenes no es gratis en ningún proveedor (céntimos por imagen). Proveedores: Gemini, OpenAI u OpenRouter.
"""
import base64
import io
import json
import random
import uuid

import httpx

from .. import ajustes as A
from .. import llm
from ..db import DATOS, ex, q

CARAS = DATOS / "caras"
MINIS = DATOS / "miniaturas"
TAMANO = {"9:16": (1080, 1920), "16:9": (1920, 1080)}

PROVEEDORES_IMAGEN = {
    "gemini": {"nombre": "Google Gemini", "clave": "clave_gemini", "defecto": "gemini-2.5-flash-image"},
    "openai": {"nombre": "OpenAI", "clave": "clave_openai", "defecto": "gpt-image-1"},
    "openrouter": {"nombre": "OpenRouter", "clave": "clave_openrouter", "defecto": "google/gemini-2.5-flash-image"},
}

ESTILOS = {
    "impacto": {
        "nombre": "Impacto",
        "desc": "Texto enorme a dos colores, tú con expresión fuerte y, como mucho, un objeto del tema.",
        "brief": "Texto muy impactante en mayúsculas. Sin decorado: la persona sobre un fondo liso y oscuro.",
        "look": ("High-impact thumbnail. The person (real photo, chest-up, expressive) on a plain dark backdrop with "
                 "a subtle texture. Huge headline in a heavy condensed UPPERCASE sans-serif (like Anton), lines of "
                 "similar width forming a compact block, using only white and yellow (#FFD400), with a thick black "
                 "outline and a soft drop shadow."),
    },
    "estudio": {
        "nombre": "Estudio",
        "desc": "Retrato limpio sobre fondo liso de color apagado, texto grande en el centro.",
        "brief": "Retrato limpio, fondo liso, la cara transmite la emoción del vídeo.",
        "look": ("Real studio portrait photograph on a plain seamless backdrop in one muted solid colour (warm sand, "
                 "sage green, slate blue or off-white; choose what suits the topic). Soft natural key light."),
    },
    "editorial": {
        "nombre": "Editorial",
        "desc": "Estética de revista: fondo claro, tipografía negra y una palabra en naranja.",
        "brief": "Sobrio, tipo portada de revista. Una sola palabra destacada.",
        "look": ("Magazine-cover style real photograph: off-white or light grey background, the person in natural "
                 "daylight, black headline type with exactly one highlighted word in burnt orange (#D24D1E). "
                 "Generous white space, refined and calm."),
    },
    "escena": {
        "nombre": "Escena real",
        "desc": "Tú en un sitio real relacionado con el tema (oficina, tienda, taller…).",
        "brief": "La escena cuenta el tema del vídeo sin necesidad de leer.",
        "look": ("Candid documentary photograph in a real location that matches the topic, 35mm lens, natural light. "
                 "The background is slightly darker and softer so the white headline reads perfectly."),
    },
    "objeto": {
        "nombre": "Objeto",
        "desc": "El objeto o la pantalla clave del vídeo en primer plano y tu reacción.",
        "brief": "Un único objeto protagonista (móvil, portátil, factura…) y la reacción de la persona.",
        "look": ("Real photograph with one hero object related to the topic in the foreground (a phone screen, a "
                 "laptop, a document…) and the person reacting next to it. Clean background, natural light."),
    },
}

POSES = [
    "looking straight into the camera, mouth slightly open in surprise, eyebrows raised",
    "three-quarter view, head turned slightly, confident half smile",
    "leaning towards the camera, pointing at the headline with one hand",
    "laughing naturally, eyes a bit squinted, relaxed shoulders",
    "serious, focused look, chin slightly down, arms crossed",
    "sceptical look, one eyebrow raised, head tilted",
    "excited, both hands open at chest height, big genuine smile",
    "shot from slightly below, hand on chin, thinking",
    "shrugging with palms up, amused expression",
]
ROPA = ["plain black t-shirt", "grey hoodie", "white t-shirt", "navy overshirt", "dark green sweater",
        "denim shirt", "black crewneck sweatshirt"]

EVITAR = ("Avoid anything that looks AI-generated: no glossy plastic skin, no over-smoothing, no HDR, no glow, no neon, "
          "no lens flares, no sparkles, no holograms, no robots, no brains or circuit patterns, no watermark, no extra "
          "text, no misspelled letters. The headline is the ONLY text in the image.")

SISTEMA = ("Eres el diseñador de miniaturas de un canal de vídeos cortos en español. Escribes textos de miniatura cortos "
           "que generan curiosidad sin ser clickbait falso. Respondes solo con JSON.")


class ErrorMiniatura(Exception):
    pass


def _carpetas():
    CARAS.mkdir(parents=True, exist_ok=True)
    MINIS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- proveedor de imagen
def proveedor_imagen() -> str:
    p = A.get("img_proveedor")
    if p in PROVEEDORES_IMAGEN and A.tiene(PROVEEDORES_IMAGEN[p]["clave"]):
        return p
    for k, v in PROVEEDORES_IMAGEN.items():   # el primero que tenga clave
        if A.tiene(v["clave"]):
            return k
    return ""


def modelo_imagen() -> str:
    p = proveedor_imagen()
    return A.get("img_modelo") or (PROVEEDORES_IMAGEN[p]["defecto"] if p else "")


def _mime(b: bytes) -> str:
    return "image/png" if b[:4] == b"\x89PNG" else "image/webp" if b[8:12] == b"WEBP" else "image/jpeg"


def generar_imagen(prompt: str, refs: list[bytes], formato: str) -> bytes:
    p = proveedor_imagen()
    if not p:
        raise ErrorMiniatura("Para crear imágenes hace falta una clave de Gemini, OpenAI u OpenRouter (Ajustes → IA).")
    m = modelo_imagen()
    clave = A.get(PROVEEDORES_IMAGEN[p]["clave"])
    nombre = PROVEEDORES_IMAGEN[p]["nombre"]
    if p == "gemini":
        partes = [{"inline_data": {"mime_type": _mime(b), "data": base64.b64encode(b).decode()}} for b in refs[:4]]
        partes.append({"text": prompt})
        body = {"contents": [{"role": "user", "parts": partes}],
                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": formato}}}
        r = llm._post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", json=body,
                      headers={"x-goog-api-key": clave})
        if r.status_code >= 400:
            raise ErrorMiniatura(_explica(nombre, r))
        for parte in (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", []):
            d = parte.get("inline_data") or parte.get("inlineData")
            if d:
                return base64.b64decode(d["data"])
        raise ErrorMiniatura(f"{nombre} no devolvió imagen (puede que haya rechazado el texto: prueba otra idea).")
    if p == "openai":
        size = "1536x1024" if formato == "16:9" else "1024x1536"
        h = {"Authorization": f"Bearer {clave}"}
        if refs:
            files = [("image[]", (f"ref{i}.png", b, _mime(b))) for i, b in enumerate(refs[:4])]
            extra = {"input_fidelity": "high"} if m.startswith("gpt-image-1") else {}
            r = httpx.post("https://api.openai.com/v1/images/edits", headers=h, files=files,
                           data={"model": m, "prompt": prompt, "size": size, "quality": "high", **extra},
                           timeout=llm.TIMEOUT)
        else:
            r = httpx.post("https://api.openai.com/v1/images/generations", headers=h, timeout=llm.TIMEOUT,
                           json={"model": m, "prompt": prompt, "size": size, "quality": "high"})
        if r.status_code >= 400:
            raise ErrorMiniatura(_explica(nombre, r))
        return base64.b64decode(r.json()["data"][0]["b64_json"])
    # openrouter: chat completions con salida de imagen
    contenido = [{"type": "image_url", "image_url": {"url": f"data:{_mime(b)};base64,{base64.b64encode(b).decode()}"}}
                 for b in refs[:4]] + [{"type": "text", "text": prompt}]
    r = llm._post("https://openrouter.ai/api/v1/chat/completions",
                  headers={"Authorization": f"Bearer {clave}", "HTTP-Referer": "https://github.com/iaquetrabaja/redes-ia",
                           "X-Title": "Redes IA"},
                  json={"model": m, "modalities": ["image", "text"], "messages": [{"role": "user", "content": contenido}],
                        "image_config": {"aspect_ratio": formato}})
    if r.status_code >= 400:
        raise ErrorMiniatura(_explica(nombre, r))
    msg = r.json()["choices"][0]["message"]
    for im in msg.get("images") or []:
        url = (im.get("image_url") or {}).get("url", "")
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
    raise ErrorMiniatura(f"{nombre} no devolvió imagen con el modelo {m}: elige uno que genere imágenes.")


def _explica(nombre: str, r: httpx.Response) -> str:
    t = r.text[:300]
    if r.status_code in (401, 403):
        return f"{nombre} rechaza la clave ({r.status_code}). Revísala en Ajustes → IA."
    if r.status_code == 429 or "quota" in t.lower() or "billing" in t.lower():
        return (f"{nombre} no deja crear imágenes con esta clave ({r.status_code}): las imágenes suelen necesitar "
                "tener la facturación activada. Mira la guía, apartado Miniaturas.")
    return f"{nombre} {r.status_code}: {t}"


# ---------------------------------------------------------------- caras
def guardar_cara(data: bytes) -> str:
    from PIL import Image, ImageOps
    _carpetas()
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as e:  # noqa: BLE001
        raise ErrorMiniatura("Ese archivo no es una imagen válida.") from e
    im.thumbnail((1280, 1280))
    nombre = f"{uuid.uuid4().hex[:12]}.jpg"
    im.save(CARAS / nombre, "JPEG", quality=90)
    ex("INSERT INTO caras(archivo, principal) VALUES(?, (SELECT COUNT(*)=0 FROM caras))", (nombre,))
    return nombre


def borrar_cara(cid: int) -> None:
    c = q("SELECT * FROM caras WHERE id=?", (cid,), one=True)
    if c:
        (CARAS / c["archivo"]).unlink(missing_ok=True)
        ex("DELETE FROM caras WHERE id=?", (cid,))
        if c["principal"]:
            ex("UPDATE caras SET principal=1 WHERE id=(SELECT id FROM caras ORDER BY id DESC LIMIT 1)")


def _refs(n: int = 3) -> list[bytes]:
    """La foto principal + otras al azar: cada miniatura ve una mezcla distinta y no sales siempre igual."""
    filas = [c for c in q("SELECT archivo, principal FROM caras ORDER BY principal DESC, id DESC")
             if (CARAS / c["archivo"]).exists()]
    if not filas:
        return []
    elegidas = [filas[0]] + random.sample(filas[1:], min(len(filas) - 1, n - 1))
    random.shuffle(elegidas)
    return [(CARAS / c["archivo"]).read_bytes() for c in elegidas]


# ---------------------------------------------------------------- generar
def _conceptos(idea: str, estilo: str, n: int, texto_fijo: str) -> list[dict]:
    e = ESTILOS[estilo]
    fijo = f'Usa EXACTAMENTE este texto en todas: "{texto_fijo}".' if texto_fijo else "Propón un texto distinto en cada una."
    prompt = f"""Canal: {A.get('contexto')}

Idea o guion del vídeo:
\"\"\"{idea[:5000]}\"\"\"

Estilo: {e['nombre']}: {e['brief']}

Diseña {n} miniaturas DISTINTAS. Reglas del texto:
- En español de España, de 3 a 7 palabras, máximo 2 líneas. Sin emojis, comillas ni hashtags.
- Se tiene que entender solo: el tema concreto + el beneficio o el giro (gratis, en 5 minutos, sin pagar…).
- Nada de metáforas sin contexto («la bestia») ni frases que dependan de otra («y encima…»).
- La persona no sale siempre igual: cambia la expresión, el gesto y el encuadre en cada una.
- {fijo}

Devuelve JSON: {{"miniaturas": [{{"texto": "...", "destacar": "una palabra del texto o vacío",
"escena": "qué se ve, en inglés, 1-2 frases", "expresion": "expresión y gesto, en inglés",
"por_que": "por qué funciona, en español, 1 frase"}}]}}"""
    d = llm.generar_json(prompt, SISTEMA)
    lista = d.get("miniaturas") if isinstance(d, dict) else d
    out = [c for c in (lista or []) if isinstance(c, dict) and c.get("texto")]
    if not out:
        raise ErrorMiniatura("La IA no propuso ninguna miniatura. Prueba otra vez.")
    for c in out:
        if texto_fijo:
            c["texto"] = texto_fijo
    return out[:n]


def _prompt(c: dict, estilo: str, formato: str, n_caras: int) -> str:
    e = ESTILOS[estilo]
    fmt = "vertical 9:16 cover for TikTok and Instagram Reels" if formato == "9:16" else "horizontal 16:9 YouTube thumbnail"
    caras = (f"Reference images 1-{n_caras} are photos of the real person (the channel host). Use them ONLY for identity: "
             "same face shape, eyes, nose, hair, facial hair and skin tone; do not beautify or change age. Do NOT copy "
             "the pose, expression, head angle, framing, clothing or lighting of those photos." if n_caras else
             "There is no reference person: show a natural-looking adult that fits the topic.")
    destacar = (f' The word "{c["destacar"]}" can be in the accent colour.' if c.get("destacar") else "")
    zona = ("Keep the text clear of the bottom 20% and the right 15% (platform buttons)." if formato == "9:16"
            else "Keep the text away from the bottom-right corner.")
    return " ".join([
        f"Create a {fmt}.", caras, f"Style: {e['look']}",
        f"Scene: {c.get('escena', '')}. Expression: {c.get('expresion', '')}.",
        f"Pose: {random.choice(POSES)}. Wearing a {random.choice(ROPA)}.",
        f'Headline text, spelled exactly: "{c["texto"]}". Very large, at most two lines, centred, in a heavy condensed '
        f"sans-serif, strong contrast.{destacar} {zona}",
        "The face is fully visible and never covered by the text. It must look like a real photo taken with a camera.",
        EVITAR,
    ])


def _ajustar(data: bytes, formato: str) -> bytes:
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im = ImageOps.fit(im, TAMANO[formato], Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92, optimize=True)
    return out.getvalue()


def crear_encargo(idea: str, estilo: str, formato: str, n: int, texto_fijo: str = "") -> str:
    if estilo not in ESTILOS:
        estilo = "impacto"
    formatos = ["9:16", "16:9"] if formato == "ambos" else [formato if formato in TAMANO else "9:16"]
    encargo = uuid.uuid4().hex[:10]
    for v in range(max(1, min(int(n), 4))):
        for f in formatos:
            ex("INSERT INTO miniaturas(encargo, variante, estilo, formato, idea, estado) VALUES(?,?,?,?,?, 'pendiente')",
               (encargo, v, estilo, f, idea[:5000]))
    A.set("mini_texto_fijo_" + encargo, texto_fijo[:80])
    return encargo


def generar(encargo: str) -> int:
    """Genera todas las miniaturas pendientes de un encargo. Devuelve cuántas salieron bien."""
    _carpetas()
    filas = q("SELECT * FROM miniaturas WHERE encargo=? ORDER BY id", (encargo,))
    if not filas:
        return 0
    fijo = A.get("mini_texto_fijo_" + encargo)
    n = max(f["variante"] for f in filas) + 1
    try:
        conceptos = _conceptos(filas[0]["idea"], filas[0]["estilo"], n, fijo)
    except Exception as e:  # noqa: BLE001
        ex("UPDATE miniaturas SET estado='error', error=? WHERE encargo=? AND estado='pendiente'", (str(e)[:300], encargo))
        return 0
    bien = 0
    for f in filas:
        c = conceptos[f["variante"] % len(conceptos)]
        ex("UPDATE miniaturas SET texto=?, por_que=? WHERE id=?", (c["texto"], c.get("por_que", ""), f["id"]))
        refs = _refs()
        try:
            img = _ajustar(generar_imagen(_prompt(c, f["estilo"], f["formato"], len(refs)), refs, f["formato"]),
                           f["formato"])
            nombre = f"{uuid.uuid4().hex[:12]}.jpg"
            (MINIS / nombre).write_bytes(img)
            ex("UPDATE miniaturas SET estado='ok', archivo=? WHERE id=?", (nombre, f["id"]))
            bien += 1
        except Exception as e:  # noqa: BLE001
            ex("UPDATE miniaturas SET estado='error', error=? WHERE id=?", (str(e)[:300], f["id"]))
    return bien


def galeria(limite: int = 60) -> list[list[dict]]:
    filas = q("SELECT * FROM miniaturas ORDER BY id DESC LIMIT ?", (limite,))
    grupos, orden = {}, []
    for f in filas:
        if f["encargo"] not in grupos:
            grupos[f["encargo"]] = []
            orden.append(f["encargo"])
        grupos[f["encargo"]].append(f)
    return [sorted(grupos[e], key=lambda x: (x["variante"], x["formato"])) for e in orden]


def borrar(mid: int) -> None:
    f = q("SELECT * FROM miniaturas WHERE id=?", (mid,), one=True)
    if f:
        if f["archivo"] and not f["archivo"].startswith("demo/"):
            (MINIS / f["archivo"]).unlink(missing_ok=True)
        ex("DELETE FROM miniaturas WHERE id=?", (mid,))


def resumen_json() -> str:
    """Para el servidor MCP: las últimas miniaturas, sin las imágenes."""
    return json.dumps([{k: f[k] for k in ("id", "estilo", "formato", "texto", "estado")}
                       for g in galeria(20) for f in g], ensure_ascii=False)

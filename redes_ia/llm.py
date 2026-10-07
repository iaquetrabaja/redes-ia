"""Cliente de IA propio (REST con httpx) para cinco proveedores: Gemini (gratis), OpenAI, Anthropic (Claude),
OpenRouter y Ollama (local, sin clave). Misma interfaz para todos: generar_texto y generar_json."""
import json
import re
import time

import httpx

from . import ajustes as A

PROVEEDORES = {
    "gemini": {"nombre": "Google Gemini", "clave": "clave_gemini", "gratis": True,
               "donde": "https://aistudio.google.com/apikey", "defecto": "gemini-2.5-flash"},
    "openai": {"nombre": "OpenAI (ChatGPT)", "clave": "clave_openai", "gratis": False,
               "donde": "https://platform.openai.com/api-keys", "defecto": "gpt-4o-mini"},
    "anthropic": {"nombre": "Anthropic (Claude)", "clave": "clave_anthropic", "gratis": False,
                  "donde": "https://console.anthropic.com/settings/keys", "defecto": "claude-3-5-haiku-latest"},
    "openrouter": {"nombre": "OpenRouter (muchos modelos)", "clave": "clave_openrouter", "gratis": False,
                   "donde": "https://openrouter.ai/keys", "defecto": "google/gemini-2.5-flash"},
    "ollama": {"nombre": "Ollama (en tu ordenador)", "clave": None, "gratis": True,
               "donde": "https://ollama.com/download", "defecto": "llama3.1"},
}
TIMEOUT = httpx.Timeout(240, connect=20)


class ErrorIA(Exception):
    pass


def proveedor() -> str:
    return A.get("proveedor") or ""


def configurado() -> bool:
    p = proveedor()
    if p not in PROVEEDORES:
        return False
    return p == "ollama" or A.tiene(PROVEEDORES[p]["clave"])


def _clave(p: str) -> str:
    k = A.get(PROVEEDORES[p]["clave"]) if PROVEEDORES[p]["clave"] else ""
    if PROVEEDORES[p]["clave"] and not k:
        raise ErrorIA(f"Falta la clave de {PROVEEDORES[p]['nombre']}. Ponla en Ajustes → IA.")
    return k


def _post(url: str, **kw) -> httpx.Response:
    """POST con reintentos suaves ante límites (429) y errores temporales del proveedor."""
    espera = 4
    for intento in range(4):
        try:
            r = httpx.post(url, timeout=TIMEOUT, **kw)
        except httpx.HTTPError as e:
            if intento == 3:
                raise ErrorIA(f"No se pudo conectar con la IA: {e}") from e
            time.sleep(espera)
            espera *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504) and intento < 3:
            time.sleep(espera)
            espera *= 2
            continue
        return r
    return r


def _fallo(nombre: str, r: httpx.Response) -> ErrorIA:
    txt = r.text[:300]
    if r.status_code in (401, 403) or (r.status_code == 400 and re.search(r"API.?key|API_KEY_INVALID|invalid.{0,10}key",
                                                                           txt, re.I)):
        return ErrorIA(f"{nombre} rechaza la clave ({r.status_code}). Revísala en Ajustes → IA.")
    if r.status_code == 429:
        return ErrorIA(f"{nombre} dice que has llegado al límite de uso (429). Espera un poco o cambia de modelo.")
    return ErrorIA(f"{nombre} {r.status_code}: {txt}")


# ---------------------------------------------------------------- modelos
def listar_modelos(p: str | None = None) -> list[str]:
    p = p or proveedor()
    try:
        if p == "gemini":
            r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200},
                          headers={"x-goog-api-key": _clave(p)}, timeout=30)
            r.raise_for_status()
            out = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
                   if "generateContent" in m.get("supportedGenerationMethods", [])]
            out = [m for m in out if not re.search(r"embedding|aqa|tts|audio|live|image|vision|learnlm|gemma", m)]
            return sorted(out, key=_orden_gemini)
        if p in ("openai", "openrouter"):
            base = "https://api.openai.com/v1" if p == "openai" else "https://openrouter.ai/api/v1"
            r = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {_clave(p)}"}, timeout=30)
            r.raise_for_status()
            ids = [m["id"] for m in r.json().get("data", [])]
            if p == "openai":
                ids = [i for i in ids if re.match(r"^(gpt-|o\d|chatgpt)", i)
                       and not re.search(r"image|audio|realtime|transcribe|tts|search|embedding|instruct", i)]
            return sorted(ids)
        if p == "anthropic":
            r = httpx.get("https://api.anthropic.com/v1/models", headers={"x-api-key": _clave(p),
                                                                          "anthropic-version": "2023-06-01"}, timeout=30)
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]
        if p == "ollama":
            r = httpx.get(A.get("ollama_url").rstrip("/") + "/api/tags", timeout=10)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except ErrorIA:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorIA(f"No se pudieron listar los modelos de {PROVEEDORES.get(p, {}).get('nombre', p)}: {e}") from e
    return []


def _orden_gemini(m: str):
    """Primero los flash estables más nuevos (gratis y rápidos); los «lite», «preview» y «exp» al final."""
    v = re.search(r"(\d+(?:\.\d+)?)", m)
    ver = float(v.group(1)) if v else 0
    return (0 if "flash" in m else 1, 1 if re.search(r"lite|preview|exp|thinking", m) else 0, -ver, m)


def modelo_por_defecto(p: str) -> str:
    try:
        ms = listar_modelos(p)
    except ErrorIA:
        ms = []
    if p == "gemini" and ms:
        return ms[0]
    if p == "openai" and ms:
        for pref in ("gpt-4.1-mini", "gpt-4o-mini"):
            if pref in ms:
                return pref
        minis = [m for m in ms if "mini" in m]
        return minis[-1] if minis else ms[-1]
    if p == "anthropic" and ms:
        haiku = [m for m in ms if "haiku" in m] or [m for m in ms if "sonnet" in m]
        return haiku[0] if haiku else ms[0]
    if p == "ollama" and ms:
        return ms[0]
    return PROVEEDORES[p]["defecto"]


def modelo() -> str:
    return A.get("modelo") or PROVEEDORES.get(proveedor(), {}).get("defecto", "")


# ---------------------------------------------------------------- texto
def generar_texto(prompt: str, sistema: str = "", json_mode: bool = False, p: str | None = None,
                  m: str | None = None) -> str:
    p = p or proveedor()
    if p not in PROVEEDORES:
        raise ErrorIA("Elige un proveedor de IA en Ajustes → IA (Gemini es gratis).")
    m = m or modelo()
    nombre = PROVEEDORES[p]["nombre"]
    if p == "gemini":
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if sistema:
            body["systemInstruction"] = {"parts": [{"text": sistema}]}
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", json=body,
                  headers={"x-goog-api-key": _clave(p)})
        if r.status_code >= 400:
            raise _fallo(nombre, r)
        cand = (r.json().get("candidates") or [{}])[0]
        parts = cand.get("content", {}).get("parts", [])
        txt = "".join(x.get("text", "") for x in parts)
        if not txt:
            raise ErrorIA(f"{nombre} no devolvió texto ({cand.get('finishReason', 'sin motivo')}).")
        return txt
    if p in ("openai", "openrouter"):
        base = "https://api.openai.com/v1" if p == "openai" else "https://openrouter.ai/api/v1"
        msgs = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": prompt}]
        body = {"model": m, "messages": msgs}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        h = {"Authorization": f"Bearer {_clave(p)}"}
        if p == "openrouter":
            h.update({"HTTP-Referer": "https://github.com/iaquetrabaja/redes-ia", "X-Title": "Redes IA"})
        r = _post(f"{base}/chat/completions", json=body, headers=h)
        if r.status_code == 400 and json_mode:   # algunos modelos no aceptan response_format
            body.pop("response_format", None)
            r = _post(f"{base}/chat/completions", json=body, headers=h)
        if r.status_code >= 400:
            raise _fallo(nombre, r)
        return r.json()["choices"][0]["message"]["content"] or ""
    if p == "anthropic":
        body = {"model": m, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
        if sistema or json_mode:
            body["system"] = (sistema + ("\nResponde solo con JSON válido, sin texto alrededor." if json_mode else "")).strip()
        r = _post("https://api.anthropic.com/v1/messages", json=body,
                  headers={"x-api-key": _clave(p), "anthropic-version": "2023-06-01"})
        if r.status_code >= 400:
            raise _fallo(nombre, r)
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    # ollama
    body = {"model": m, "stream": False,
            "messages": ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": prompt}]}
    if json_mode:
        body["format"] = "json"
    try:
        r = httpx.post(A.get("ollama_url").rstrip("/") + "/api/chat", json=body, timeout=httpx.Timeout(600, connect=10))
    except httpx.HTTPError as e:
        raise ErrorIA("No encuentro Ollama. ¿Está abierto? Instálalo desde ollama.com y descarga un modelo.") from e
    if r.status_code >= 400:
        raise _fallo(nombre, r)
    return r.json().get("message", {}).get("content", "")


def extraer_json(raw: str):
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", raw, re.S)
        if m:
            return json.loads(m.group(1))
        raise ErrorIA("La IA no devolvió un JSON válido. Prueba otra vez o con otro modelo.")


def generar_json(prompt: str, sistema: str = "", **kw):
    return extraer_json(generar_texto(prompt, sistema, json_mode=True, **kw))


def probar(p: str, m: str | None = None) -> str:
    """Prueba de conexión: devuelve la respuesta corta del modelo."""
    return generar_texto("Responde solo con la palabra: funciona", p=p, m=m or None).strip()[:60]

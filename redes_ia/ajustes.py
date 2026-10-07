"""Ajustes y claves. Las claves se guardan solo en tu ordenador (datos/, fuera de git) y algo ofuscadas para que
no se lean de un vistazo si alguien abre la base de datos. No es cifrado fuerte: protege tu ordenador como tal."""
import base64
import hashlib
import os

from .db import DATOS, ex, q

SECRETOS = {"clave_gemini", "clave_openai", "clave_anthropic", "clave_openrouter", "ig_token", "fb_token"}

DEFECTO = {
    "proveedor": "",
    "modelo": "",
    "ollama_url": "http://127.0.0.1:11434",
    "hora_diaria": "6",
    "contexto": "Canal sobre IA práctica: herramientas, automatizaciones y trucos que ahorran tiempo, en español.",
    "voz": "",
    "dias_resumen": "7",
}


def _llave() -> bytes:
    f = DATOS / ".llave"
    if not f.exists():
        DATOS.mkdir(parents=True, exist_ok=True)
        f.write_bytes(os.urandom(32))
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
    return f.read_bytes()


def _xor(data: bytes) -> bytes:
    k = hashlib.sha256(_llave()).digest()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))


def get(clave: str, defecto: str | None = None) -> str:
    r = q("SELECT valor FROM ajustes WHERE clave=?", (clave,), one=True)
    if not r or r["valor"] is None:
        return DEFECTO.get(clave, "") if defecto is None else defecto
    v = r["valor"]
    if clave in SECRETOS and v.startswith("x:"):
        try:
            return _xor(base64.b64decode(v[2:])).decode("utf-8")
        except Exception:  # noqa: BLE001
            return ""
    return v


def set(clave: str, valor: str) -> None:  # noqa: A001
    v = valor or ""
    if clave in SECRETOS and v:
        v = "x:" + base64.b64encode(_xor(v.encode("utf-8"))).decode()
    ex("INSERT INTO ajustes(clave,valor) VALUES(?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (clave, v))


def tiene(clave: str) -> bool:
    return bool(get(clave))


def oculta(v: str) -> str:
    return (v[:4] + "…" + v[-4:]) if v and len(v) > 12 else ("•••" if v else "")

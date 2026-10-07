"""SQLite local en ./datos/redes.db. Todo vive en tu ordenador."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from . import RAIZ

DATOS = Path(os.environ.get("REDES_IA_DATOS") or (RAIZ / "datos"))
_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS cuentas (
  id INTEGER PRIMARY KEY, red TEXT NOT NULL, usuario TEXT NOT NULL, mia INTEGER DEFAULT 0, activa INTEGER DEFAULT 1,
  nombre TEXT, seguidores INTEGER, ultimo TEXT, error TEXT, demo INTEGER DEFAULT 0,
  creada TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(red, usuario));
CREATE TABLE IF NOT EXISTS seguidores (cuenta_id INTEGER, fecha TEXT, seguidores INTEGER, PRIMARY KEY(cuenta_id, fecha));
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY, cuenta_id INTEGER NOT NULL, red TEXT, vid TEXT NOT NULL, url TEXT, texto TEXT, portada TEXT,
  publicado TEXT, duracion REAL, visto TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(red, vid));
CREATE TABLE IF NOT EXISTS metricas (
  video_id INTEGER, fecha TEXT, vistas INTEGER, likes INTEGER, comentarios INTEGER, compartidos INTEGER,
  guardados INTEGER, alcance INTEGER, PRIMARY KEY(video_id, fecha));
CREATE TABLE IF NOT EXISTS comentarios (
  id TEXT PRIMARY KEY, red TEXT, video_id INTEGER, autor TEXT, texto TEXT, likes INTEGER, creado TEXT,
  categoria TEXT, motivo TEXT, borrador TEXT, estado TEXT DEFAULT 'pendiente', analizado TEXT);
CREATE TABLE IF NOT EXISTS tendencias (
  id INTEGER PRIMARY KEY, url TEXT UNIQUE, titulo TEXT, resumen TEXT, fuente TEXT, metrica INTEGER, etiqueta TEXT,
  creada TEXT, vista TEXT);
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY, creada TEXT DEFAULT CURRENT_TIMESTAMP, tipo TEXT, titulo TEXT, por_que TEXT, como TEXT,
  gancho TEXT, nota REAL, motivo_nota TEXT, video_id INTEGER, tendencia_id INTEGER, fuentes TEXT, detalle TEXT,
  estado TEXT DEFAULT 'nueva');
CREATE TABLE IF NOT EXISTS tareas (
  id INTEGER PRIMARY KEY, tipo TEXT, inicio TEXT DEFAULT CURRENT_TIMESTAMP, fin TEXT, estado TEXT, detalle TEXT);
CREATE INDEX IF NOT EXISTS idx_videos_cuenta ON videos(cuenta_id);
CREATE INDEX IF NOT EXISTS idx_ideas_creada ON ideas(creada);
"""


def ruta_db() -> Path:
    DATOS.mkdir(parents=True, exist_ok=True)
    return DATOS / "redes.db"


def _conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None or getattr(_local, "ruta", None) != str(ruta_db()):
        c = sqlite3.connect(ruta_db(), timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.c, _local.ruta = c, str(ruta_db())
    return c


def iniciar():
    c = _conn()
    c.executescript(SCHEMA)
    c.commit()


def q(sql: str, params=(), one: bool = False):
    rows = [dict(r) for r in _conn().execute(sql, params).fetchall()]
    return (rows[0] if rows else None) if one else rows


def ex(sql: str, params=()) -> int:
    c = _conn()
    cur = c.execute(sql, params)
    c.commit()
    return cur.lastrowid


@contextmanager
def transaccion():
    c = _conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise

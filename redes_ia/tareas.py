"""Tareas programadas mientras la app está abierta: datos e ideas cada día, automatizaciones los lunes."""
import logging
import threading
import time

from . import ajustes as A
from . import llm
from .db import ex, q

log = logging.getLogger("tareas")
_cerrojos: dict[str, threading.Lock] = {}
_planificador = None


def ejecutar(tipo: str, fn, *args) -> bool:
    """Lanza una tarea en segundo plano y la deja registrada. False si ya estaba en marcha."""
    lock = _cerrojos.setdefault(tipo, threading.Lock())
    if not lock.acquire(blocking=False):
        return False

    def run():
        tid = ex("INSERT INTO tareas(tipo, estado) VALUES(?, 'en curso')", (tipo,))
        try:
            res = fn(*args)
            ex("UPDATE tareas SET fin=CURRENT_TIMESTAMP, estado='ok', detalle=? WHERE id=?", (str(res)[:500], tid))
        except Exception as e:  # noqa: BLE001
            log.exception("tarea %s", tipo)
            ex("UPDATE tareas SET fin=CURRENT_TIMESTAMP, estado='error', detalle=? WHERE id=?", (str(e)[:500], tid))
        finally:
            lock.release()
    threading.Thread(target=run, daemon=True).start()
    return True


def en_marcha() -> set[str]:
    return {k for k, v in _cerrojos.items() if v.locked()}


def ultimas(n: int = 6) -> list[dict]:
    return q("SELECT * FROM tareas ORDER BY id DESC LIMIT ?", (n,))


def diaria():
    from .servicios import datos, estudio, ideas
    out = {"datos": datos.actualizar_todo()}
    if llm.configurado():
        try:
            out["ideas"] = ideas.generar()
        except Exception as e:  # noqa: BLE001
            out["ideas"] = f"error: {e}"
        try:
            out["comentarios"] = estudio.clasificar_comentarios()
        except Exception as e:  # noqa: BLE001
            out["comentarios"] = f"error: {e}"
    return out


def semanal():
    from .servicios import automatizaciones
    if llm.configurado():
        return automatizaciones.generar()
    return "sin IA configurada"


def iniciar():
    global _planificador
    if _planificador or A.get("modo_demo") == "1":
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    hora = int(A.get("hora_diaria") or 6) % 24
    _planificador = BackgroundScheduler()
    _planificador.add_job(lambda: ejecutar("diaria", diaria), CronTrigger(hour=hora, minute=5), id="diaria",
                          coalesce=True, misfire_grace_time=6 * 3600)
    _planificador.add_job(lambda: ejecutar("automatizaciones", semanal), CronTrigger(day_of_week="mon", hour=hora,
                                                                                      minute=30),
                          id="semanal", coalesce=True, misfire_grace_time=12 * 3600)
    _planificador.start()
    # Si el ordenador estaba apagado a la hora de la tarea, se hace al abrir (una vez al día como mucho).
    ult = q("SELECT inicio FROM tareas WHERE tipo='diaria' AND estado='ok' ORDER BY id DESC LIMIT 1", one=True)
    if q("SELECT 1 FROM cuentas WHERE demo=0", one=True) and (not ult or ult["inicio"][:10] < time.strftime("%Y-%m-%d")):
        ejecutar("diaria", diaria)


def reprogramar():
    global _planificador
    if _planificador:
        _planificador.shutdown(wait=False)
        _planificador = None
    iniciar()

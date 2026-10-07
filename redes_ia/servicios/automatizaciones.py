"""Ideas semanales de AUTOMATIZACIÓN con IA para trabajadores corrientes: una tarea que sirve a varios oficios a la
vez, fácil de montar sin programar, con guion por escenas para que el vídeo no sea solo pantalla."""
import json
import random

from .. import llm
from ..db import ex, q
from .ideas import parecida

POR_SEMANA = 3
SISTEMA = ("Eres guionista y estratega de vídeos cortos en español de España, especializado en automatizaciones con IA "
           "que cualquiera puede copiar. Todo lo que propones se puede montar de verdad hoy. Respondes solo con JSON.")
OFICIOS = ["albañil o reformista", "fontanero o electricista", "pequeño empresario con empleados",
           "dependiente de tienda o supermercado", "farmacia", "recepción de hotel", "bar o restaurante",
           "peluquería o estética", "fisioterapia o consulta pequeña", "transportista o repartidor", "inmobiliaria",
           "administrativo de oficina", "profesor", "sanitario a turnos", "comercial", "taller mecánico",
           "limpieza o mantenimiento", "autónomo que hace sus facturas"]
REGLAS = """Reglas:
- UNA tarea que sirve a muchos oficios a la vez; el título habla de la tarea («Deja de escribir los partes por la
  noche»), no de un oficio. En el vídeo se ve aplicada en 2-3 oficios distintos.
- Fácil: 30-60 minutos, sin programar, con lo que ya tiene todo el mundo (WhatsApp, notas de voz, ChatGPT/Gemini/
  Claude, Google Forms/Sheets/Calendar, Atajos o Rutinas del móvil).
- Resultado visible en los 2 primeros segundos; no solo pantalla (persona en su sitio, móvil en primer plano, antes y
  después, cronómetro, esquema de 3 cajas).
- Ahorro concreto y creíble; coste real; honesto con datos personales y revisar lo que escribe la IA.
- Cierre con una palabra clave para pedir la guía por comentario."""


def recientes(n: int = 12) -> list[str]:
    return [r["titulo"] for r in q("SELECT titulo FROM ideas WHERE tipo='automatizacion' AND estado!='descartada' "
                                   "ORDER BY id DESC LIMIT ?", (n,))]


def generar(n: int = POR_SEMANA) -> dict:
    prev = recientes()
    oficios = random.sample(OFICIOS, 9)
    prompt = f"""Quiero {n} ideas de vídeo corto sobre automatizaciones con IA para que trabajadores corrientes
trabajen menos horas. Inspírate en estos trabajadores (cada idea debe servir al menos a 3): {', '.join(oficios)}.
{REGLAS}
Ya propuestas (no las repitas):
{chr(10).join('- ' + t for t in prev) or '(ninguna)'}
Campos: "titulo" (máx 80), "gancho", "oficios" (lista de 3-5), "que_automatiza" (antes y después), "ahorro",
"herramientas" (lista de {{"nombre","coste","para_que"}}), "dificultad" ("fácil"), "tiempo_montaje", "momento_wow",
"guion" (5-7 escenas {{"plano","texto"}}), "pasos" (4-6), "limites", "palabra", "por_que", "nota" (0-10),
"motivo_nota". Responde SOLO JSON: {{"ideas": [ ... ]}}"""
    data = llm.generar_json(prompt, SISTEMA)
    hechas = []
    for it in (data.get("ideas") or [])[: n + 2]:
        t = (it.get("titulo") or "").strip()
        if not t or parecida(t, prev + hechas):
            continue
        try:
            nota = max(0.0, min(10.0, round(float(it.get("nota")), 1)))
        except (TypeError, ValueError):
            nota = None
        det = {k: it.get(k) for k in ("oficios", "que_automatiza", "ahorro", "herramientas", "dificultad",
                                      "tiempo_montaje", "momento_wow", "guion", "limites", "palabra")}
        como = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(it.get("pasos") or []))
        ex("INSERT INTO ideas(tipo,titulo,por_que,como,gancho,nota,motivo_nota,fuentes,detalle) "
           "VALUES('automatizacion',?,?,?,?,?,?,'[]',?)",
           (t, it.get("por_que"), como, it.get("gancho"), nota, it.get("motivo_nota"),
            json.dumps({"automatizacion": det}, ensure_ascii=False)))
        hechas.append(t)
        if len(hechas) >= n:
            break
    return {"ideas": len(hechas), "titulos": hechas}

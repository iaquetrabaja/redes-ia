"""Datos de demostración (marcados como demo) para ver el panel sin conectar nada. Se guardan en datos/demo/."""
import json
import random
from datetime import date, datetime, timedelta, timezone

from .. import ajustes as A
from ..db import ex, q
from . import estudio

MIA = "tu_cuenta_demo"
COMPETENCIA = [("tiktok", "ia_al_dia_demo", 4200), ("tiktok", "trucos_ia_demo", 18000),
               ("instagram", "negocio_y_ia_demo", 9100)]
TEMAS = [
    "Cómo respondo 200 correos a la semana sin escribirlos yo",
    "3 trucos de ChatGPT que uso cada día en mi negocio",
    "Esta IA gratis lee tus facturas y las pasa a Excel",
    "Le pido a una IA mi plan de contenido de la semana",
    "Probé 5 IAs para hacer presupuestos: esta es la que gana",
    "Automatizo las citas de mi peluquería con un formulario",
    "Cómo hago miniaturas en 2 minutos con IA",
    "La IA que resume tus notas de voz en tareas",
    "Así preparo un vídeo entero con IA en una tarde",
    "Deja de copiar y pegar: conecta tus apps sin programar",
    "Hice una web en 10 minutos con IA y esto pasó",
    "El prompt que uso para no sonar a robot",
]


def cargar(seed: int = 7) -> None:
    rnd = random.Random(seed)
    if q("SELECT 1 FROM cuentas WHERE demo=1", one=True):
        return
    A.set("modo_demo", "1")
    A.set("contexto", "Canal de demostración sobre IA práctica para autónomos y pequeños negocios.")
    A.set("voz", "### Quién soy\nCreador de demostración que enseña IA práctica a autónomos.\n\n### Tono\nCercano, "
                 "directo, sin humo.\n\n### Nunca uso\n«revolucionario», «game changer», «literalmente» de relleno.")
    hoy = date.today()
    cuentas = []
    for red, seg in (("tiktok", 3150), ("instagram", 2280)):
        cid = ex("INSERT INTO cuentas(red,usuario,mia,nombre,seguidores,ultimo,demo) VALUES(?,?,?,?,?,?,1)",
                 (red, MIA, 1, "Tu cuenta (demo)", seg, datetime.now().strftime("%Y-%m-%d %H:%M")))
        cuentas.append((cid, red, True, seg, 2400 if red == "tiktok" else 1500))
        for d in range(30, -1, -1):
            ex("INSERT OR REPLACE INTO seguidores VALUES(?,?,?)",
               (cid, (hoy - timedelta(days=d)).isoformat(), seg - d * rnd.randint(4, 14)))
    for red, u, seg in COMPETENCIA:
        cid = ex("INSERT INTO cuentas(red,usuario,mia,nombre,seguidores,ultimo,demo) VALUES(?,?,0,?,?,?,1)",
                 (red, u, u.replace("_demo", "").replace("_", " ").title() + " (demo)", seg,
                  datetime.now().strftime("%Y-%m-%d %H:%M")))
        cuentas.append((cid, red, False, seg, seg // 3))
    n = 0
    for cid, red, mia, seg, base in cuentas:
        for i in range(12):
            dias = i * 2 + rnd.randint(0, 1)
            pub = (datetime.now(timezone.utc) - timedelta(days=dias, hours=rnd.randint(0, 20))).isoformat(timespec="seconds")
            mult = rnd.choice([0.4, 0.6, 0.8, 1, 1, 1.2, 1.5, 2.5, 6]) if i != 3 else 9
            vistas = int(base * mult)
            tema = TEMAS[(i + n) % len(TEMAS)] if mia else rnd.choice(TEMAS).replace("mi ", "tu ")
            n += 1
            vid = f"demo{cid}{i}"
            v_id = ex("INSERT INTO videos(cuenta_id,red,vid,url,texto,portada,publicado,duracion) VALUES(?,?,?,?,?,?,?,?)",
                      (cid, red, vid, f"https://example.com/demo/{vid}", tema + ". Comenta GUIA y te la mando.", None,
                       pub, rnd.randint(25, 70)))
            ex("INSERT INTO metricas VALUES(?,?,?,?,?,?,?,?)",
               (v_id, hoy.isoformat(), vistas, int(vistas * rnd.uniform(.04, .09)), int(vistas * rnd.uniform(.002, .01)),
                int(vistas * rnd.uniform(.002, .02)), int(vistas * rnd.uniform(.004, .04)), int(vistas * .8)))
    mios = q("SELECT v.id, v.red FROM videos v JOIN cuentas c ON c.id=v.cuenta_id WHERE c.mia=1 ORDER BY v.publicado DESC LIMIT 4")
    coms = [("cliente", "Tengo una clínica y perdemos horas con las citas, ¿me lo montarías?", "Claro, escríbeme por privado y me cuentas cómo las gestionáis ahora."),
            ("pregunta", "¿Funciona también con Outlook o solo con Gmail?", "Con Outlook también: se conecta igual desde la misma herramienta."),
            ("pregunta", "¿Cuánto cuesta al mes?", "La versión que enseño es gratis; solo pagarías si pasas de 100 tareas al mes."),
            ("idea", "Haz uno de cómo pasar notas de voz a tareas en Trello", "Apuntado para la semana que viene."),
            ("queja", "Esto con datos de clientes no lo veo nada claro…", "Buen punto: en el vídeo quito nombres antes de pasarlo a la IA, y lo explicaré mejor."),
            ("apoyo", "Muy útil, me lo guardo 🙌", "")]
    for k, (cat, txt, borr) in enumerate(coms):
        v = mios[k % len(mios)]
        ex("INSERT INTO comentarios(id,red,video_id,autor,texto,likes,creado,categoria,motivo,borrador,analizado) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
           (f"demo_c{k}", v["red"], v["id"], f"persona_demo_{k}", txt, rnd.randint(0, 12),
            (datetime.now(timezone.utc) - timedelta(hours=k * 5)).isoformat(), cat, "ejemplo de demostración", borr,
            datetime.now().strftime("%Y-%m-%d %H:%M")))
    for k, (fu, t, et) in enumerate([("github", "ejemplo/agente-facturas", "1.240 estrellas"),
                                     ("hackernews", "Un modelo abierto que corre en el portátil", "412 puntos"),
                                     ("reddit/ChatGPT", "Cómo uso la IA para mi pequeño negocio", "top 1 del día")]):
        ex("INSERT INTO tendencias(url,titulo,resumen,fuente,metrica,etiqueta,creada,vista) VALUES(?,?,?,?,?,?,?,?)",
           (f"https://example.com/tendencia/{k}", t, "Tendencia de demostración", fu, 1000 - k * 100, et,
            hoy.isoformat(), hoy.isoformat()))
    comp = q("SELECT v.id FROM videos v JOIN cuentas c ON c.id=v.cuenta_id WHERE c.mia=0 LIMIT 2")
    ideas = [("competencia", "Paso mis facturas a Excel con una foto: prueba real con 30 tickets",
              "Un competidor hizo 9 veces su media con un tema parecido; los guardados indican utilidad.",
              "Gancho con el montón de tickets, prueba en directo, resultado en la hoja y límites.",
              "30 tickets, una foto cada uno y la hoja se rellena sola.", 8.7, comp[0]["id"] if comp else None),
             ("tendencia", "Un agente de código abierto que ordena tu correo: lo pruebo una semana",
              "Tendencia fuerte en GitHub y encaja con tu público de autónomos.",
              "Antes y después de la bandeja, 3 reglas que crea solo y qué falla.", "Mi bandeja tenía 1.200 correos. Ahora, 14.", 8.2, None),
             ("combinada", "Lo que le pregunto a la IA cada lunes para planificar la semana",
              "Tus vídeos de rutina con IA superan tu media x2,5.", "Pantalla partida: lunes caótico vs. lunes con plan.",
              "Cada lunes le hago 3 preguntas a la IA. Esta es la segunda.", 7.6, None)]
    for tipo, t, pq, como, g, nota, vid in ideas:
        ex("INSERT INTO ideas(tipo,titulo,por_que,como,gancho,nota,motivo_nota,video_id,fuentes) VALUES(?,?,?,?,?,?,?,?,'[]')",
           (tipo, t, pq, como, g, nota, "Idea de demostración", vid))
    auto = {"oficios": ["fontanería", "recepción de hotel", "pequeña empresa"],
            "que_automatiza": "Antes: escribir el parte de trabajo por la noche. Después: lo dictas al salir y la IA lo ordena.",
            "ahorro": "≈ 1-2 h/semana", "herramientas": [{"nombre": "Notas de voz del móvil", "coste": "gratis", "para_que": "dictar"},
                                                         {"nombre": "Gemini", "coste": "gratis", "para_que": "ordenar el parte"}],
            "dificultad": "fácil", "tiempo_montaje": "15 minutos", "momento_wow": "La nota de voz se convierte en un parte limpio.",
            "guion": [{"plano": "Móvil en primer plano", "texto": "20 segundos hablando y el parte está hecho."}],
            "limites": "Revisa el texto antes de enviarlo y no metas datos personales.", "palabra": "PARTE"}
    ex("INSERT INTO ideas(tipo,titulo,por_que,como,gancho,nota,motivo_nota,fuentes,detalle) VALUES(?,?,?,?,?,?,?,'[]',?)",
       ("automatizacion", "Deja de escribir los partes de trabajo por la noche",
        "Le pasa a miles de autónomos y se entiende en un segundo.", "1. Graba una nota de voz.\n2. Pégala en Gemini con la instrucción.\n3. Revisa y envía.",
        "20 segundos hablando y el parte está hecho.", 8.4, "Idea de demostración",
        json.dumps({"automatizacion": auto}, ensure_ascii=False)))
    # Un guion ya preparado, pasado por las herramientas de verdad (sin IA)
    borrador = {"ganchos": [{"texto": "30 tickets, una foto cada uno y la hoja se rellena sola.", "formula": "La demostración"},
                            {"texto": "Hola, hoy os enseño una herramienta de facturas", "formula": "—"},
                            {"texto": "Pasé 2 horas con facturas. Ahora tardo 5 minutos.", "formula": "Antes y después"}],
                "guion": [{"texto": "30 tickets, una foto cada uno y la hoja se rellena sola.", "pantalla": "Montón de tickets", "rotulo": "30 tickets"},
                          {"texto": "Le hago una foto a cada uno con el móvil.", "pantalla": "Móvil", "rotulo": ""},
                          {"texto": "La IA saca fecha, importe y tienda, y lo pone en una fila.", "pantalla": "Hoja de cálculo", "rotulo": "Fecha, importe, tienda"},
                          {"texto": "Antes tardaba dos horas al mes. Ahora, cinco minutos.", "pantalla": "Cronómetro", "rotulo": "2 h → 5 min"},
                          {"texto": "Si un ticket está borroso, me avisa para revisarlo.", "pantalla": "Aviso", "rotulo": ""},
                          {"texto": "Comenta GUIA y te mando cómo montarlo. Son 30 tickets, ¿cuántos tienes tú?", "pantalla": "Cara", "rotulo": "Comenta GUIA"}],
                "pie_instagram": "30 tickets en una hoja de cálculo sin escribir nada. Así lo hago con una foto.\n\nComenta GUIA y te mando el paso a paso.\n\n#ia #autonomos #facturas",
                "descripcion_tiktok": "30 tickets a Excel con una foto #ia #autonomos #facturas", "palabra": "GUIA"}
    res = estudio._evaluar(borrador)
    res.update({"versiones": 1, "creado": datetime.now().strftime("%Y-%m-%d %H:%M"), "demo": True})
    i1 = q("SELECT id FROM ideas WHERE tipo='competencia' LIMIT 1", one=True)
    if i1:
        ex("UPDATE ideas SET detalle=?, estado='guardada' WHERE id=?", (json.dumps({"guion": res}, ensure_ascii=False), i1["id"]))
    A.set("auditoria", json.dumps({
        "funciona": ["Las demostraciones con un número delante (x9 tu media en «facturas a Excel»).",
                     "Los vídeos con recurso descargable se guardan el doble (30 guardados por 1.000 vistas)."],
        "no_funciona": ["Las listas genéricas de herramientas se quedan por debajo de tu media (x0,6)."],
        "repetir": ["«Facturas a Excel» con otra herramienta y comparando tiempos."],
        "dejar": ["Empezar con «hola, hoy os enseño»."],
        "siguiente": "Una demostración por semana con cifra real en el primer segundo.",
        "actualizado": datetime.now().strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False))
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    A.set("plan", json.dumps({"foco": "Demostraciones con una cifra real delante (plan de demostración).",
                              "creado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                              "dias": [{"dia": d, "tipo": "video" if k in (0, 2, 4) else "tarea",
                                        "titulo": TEMAS[k] if k in (0, 2, 4) else "Responder comentarios de clientes",
                                        "hora": "19:30" if k in (0, 2, 4) else "12:00", "formato": "vertical 35 s" if k in (0, 2, 4) else "",
                                        "gancho": "Una cifra real en el primer segundo" if k in (0, 2, 4) else "",
                                        "palabra": "GUIA" if k == 0 else None, "nota": ""} for k, d in enumerate(dias)]},
                             ensure_ascii=False))

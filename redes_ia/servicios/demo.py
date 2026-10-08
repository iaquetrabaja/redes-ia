"""Datos de demostración (marcados como demo) para ver el panel sin conectar nada. Se guardan en datos/demo/."""
import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from .. import ajustes as A
from ..db import ex, q, transaccion
from . import estudio

# Cambia este número si cambian los datos de ejemplo: la demo se vuelve a generar sola al arrancar.
VERSION = "5"
MIA = "tu_cuenta_demo"
# Tus cuentas: red, seguidores hoy, vistas de un vídeo típico, días entre vídeos, engagement base (%)
MIAS = [("tiktok", 12480, 2600, 2.4, 9.5), ("instagram", 5230, 1700, 3.5, 8.0), ("youtube", 1940, 950, 4.5, 6.5)]
# Competencia: red, usuario, seguidores hoy, vistas típicas, vídeos por semana, engagement base (%), crecimiento/día
COMPETENCIA = [
    ("tiktok", "la_ia_en_casa_demo", 95200, 21000, 6.0, 4.1, 0.0016),
    ("tiktok", "ia_al_dia_demo", 41800, 8800, 4.5, 5.8, 0.0012),
    ("tiktok", "trucos_ia_demo", 18300, 5200, 3.5, 7.4, 0.0021),
    ("tiktok", "autonomo_digital_demo", 7800, 2300, 2.5, 8.6, 0.0009),
    ("instagram", "marketing_con_ia_demo", 26400, 6100, 4.0, 4.9, 0.0010),
    ("instagram", "negocio_y_ia_demo", 9100, 2800, 3.0, 6.3, 0.0014),
    ("instagram", "pymes_digitales_demo", 4300, 1250, 1.5, 7.1, 0.0006),
    ("youtube", "ia_explicada_demo", 31000, 7200, 3.0, 3.8, 0.0011),
    ("youtube", "herramientas_ia_demo", 12500, 3100, 2.0, 4.6, 0.0008),
    ("youtube", "tutoriales_rapidos_demo", 5600, 1500, 4.0, 5.2, 0.0017),
]
DIAS_HISTORIA = 190
TONOS = ["#e9e4dc", "#dde5e3", "#e6e0ea", "#e3e8dc", "#ece2dc", "#dfe3ea"]
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


def portada(texto: str, k: int) -> str:
    """Miniatura vertical de ejemplo (SVG en línea): fondo suave y el título, como una portada sencilla."""
    palabras, lineas, l = texto.split(), [], ""
    for w in palabras:
        if len(l) + len(w) > 14 and l:
            lineas.append(l)
            l = w
        else:
            l = (l + " " + w).strip()
    lineas = (lineas + [l])[:5]
    y0 = 160 - len(lineas) * 13
    txt = "".join(f'<text x="18" y="{y0 + i * 27}" font-family="Roboto,Arial,sans-serif" font-size="21" '
                  f'font-weight="500" fill="#1d1d1b">{t.replace("&", "y").replace("<", "")}</text>'
                  for i, t in enumerate(lineas))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 320"><rect width="180" height="320" '
           f'fill="{TONOS[k % len(TONOS)]}"/><rect x="18" y="{y0 - 34}" width="26" height="3" fill="#d24d1e"/>{txt}</svg>')
    return "data:image/svg+xml," + quote(svg)


def _borrar_demo() -> None:
    ids = [r["id"] for r in q("SELECT id FROM cuentas WHERE demo=1")]
    with transaccion() as c:
        for cid in ids:
            c.execute("DELETE FROM metricas WHERE video_id IN (SELECT id FROM videos WHERE cuenta_id=?)", (cid,))
            c.execute("DELETE FROM comentarios WHERE video_id IN (SELECT id FROM videos WHERE cuenta_id=?)", (cid,))
            c.execute("DELETE FROM videos WHERE cuenta_id=?", (cid,))
            c.execute("DELETE FROM seguidores WHERE cuenta_id=?", (cid,))
            c.execute("DELETE FROM cuentas WHERE id=?", (cid,))
        if not q("SELECT 1 FROM cuentas WHERE demo=0", one=True):   # base solo de demo: fuera también lo demás
            for t in ("ideas", "tendencias", "comentarios", "tareas"):
                c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM miniaturas WHERE archivo LIKE 'demo/%'")


def _seguidores(c, cid: int, hoy_n: int, ritmo: float, rnd: random.Random, saltos=()) -> None:
    """Historia diaria de seguidores hacia atrás desde hoy, con algo de ruido y algún salto (un vídeo que funcionó)."""
    n, filas = float(hoy_n), []
    for d in range(DIAS_HISTORIA + 1):
        filas.append((cid, (date.today() - timedelta(days=d)).isoformat(), int(n)))
        baja = n * ritmo * rnd.uniform(0.2, 1.8) + (n * 0.012 if d in saltos else 0)
        n = max(10, n - baja)
    c.executemany("INSERT OR REPLACE INTO seguidores VALUES(?,?,?)", filas)


def _metricas(vistas: int, er: float, rnd: random.Random) -> tuple:
    """Me gusta, comentarios, compartidos y guardados que suman más o menos el engagement pedido."""
    inter = vistas * er / 100
    reparto = [rnd.uniform(.62, .72), rnd.uniform(.05, .09), rnd.uniform(.08, .14)]
    reparto.append(max(0.05, 1 - sum(reparto)))
    return tuple(int(inter * r) for r in reparto)


def cargar(seed: int = 7) -> None:
    """Carga los datos de ejemplo. Si ya estaban de otra versión o de otro día, los rehace (para que las gráficas
    lleguen siempre hasta hoy)."""
    rnd = random.Random(seed)
    marca = f"{VERSION}:{date.today().isoformat()}"
    if q("SELECT 1 FROM cuentas WHERE demo=1", one=True):
        if A.get("demo_version") == marca:
            return
        _borrar_demo()
    A.set("demo_version", marca)
    A.set("modo_demo", "1")
    A.set("contexto", "Canal de demostración sobre IA práctica para autónomos y pequeños negocios.")
    A.set("voz", "### Quién soy\nCreador de demostración que enseña IA práctica a autónomos.\n\n### Tono\nCercano, "
                 "directo, sin humo.\n\n### Nunca uso\n«revolucionario», «game changer», «literalmente» de relleno.")
    hoy = date.today()
    ahora = datetime.now(timezone.utc)
    ultimo = datetime.now().strftime("%Y-%m-%d %H:%M")
    n = 0
    with transaccion() as c:
        for red, seg, base, cada, er in MIAS:
            cid = c.execute("INSERT INTO cuentas(red,usuario,mia,nombre,seguidores,ultimo,demo) VALUES(?,?,1,?,?,?,1)",
                            (red, MIA, "Tu cuenta (demo)", seg, ultimo)).lastrowid
            saltos, filas_m = [], []
            k, edad_d = 0, rnd.uniform(0.3, 1.5)
            while edad_d < DIAS_HISTORIA - 5:
                # vas a mejor: los vídeos recientes rinden algo más que los de hace tres meses
                tendencia = 1 + 0.45 * (1 - edad_d / DIAS_HISTORIA)
                mult = rnd.choice([0.45, 0.6, 0.75, 0.9, 1, 1, 1.1, 1.3, 1.6, 2.2]) if k % 11 != 1 else rnd.choice([5.5, 8.5])
                final = int(base * tendencia * mult * rnd.uniform(0.9, 1.1))
                if mult > 4:
                    saltos += [int(edad_d), int(edad_d) - 1]
                tema = TEMAS[(k + n) % len(TEMAS)]
                pub = ahora - timedelta(days=edad_d)
                vid = f"demo{cid}_{k}"
                v_id = c.execute("INSERT INTO videos(cuenta_id,red,vid,url,texto,portada,publicado,duracion) "
                                 "VALUES(?,?,?,?,?,?,?,?)",
                                 (cid, red, vid, f"https://example.com/demo/{vid}", tema + ". Comenta GUIA y te la mando.",
                                  portada(tema, k + n), pub.isoformat(timespec="seconds"), rnd.randint(22, 65))).lastrowid
                v_er = er * rnd.uniform(0.75, 1.3) * (1.15 if mult > 1.5 else 1)
                tau = rnd.uniform(1.2, 3.5)
                # una foto por día desde que se publicó: así salen las vistas ganadas por día
                for d in range(int(edad_d), -1, -1):
                    t = edad_d - d + 0.6
                    vistas = int(final * (1 - math.exp(-t / tau)))
                    filas_m.append((v_id, (hoy - timedelta(days=d)).isoformat(), vistas,
                                    *_metricas(vistas, v_er, rnd), int(vistas * .8)))
                k += 1
                n += 1
                edad_d += cada * rnd.uniform(0.6, 1.4)
            c.executemany("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?,?,?,?,?)", filas_m)
            _seguidores(c, cid, seg, 0.0028, rnd, saltos)
        for red, u, seg, base, por_semana, er, ritmo in COMPETENCIA:
            cid = c.execute("INSERT INTO cuentas(red,usuario,mia,nombre,seguidores,ultimo,demo) VALUES(?,?,0,?,?,?,1)",
                            (red, u, u.replace("_demo", "").replace("_", " ").capitalize() + " (demo)", seg,
                             ultimo)).lastrowid
            filas_m, k, edad_d = [], 0, rnd.uniform(0.2, 2)
            while edad_d < 95:
                mult = rnd.choice([0.4, 0.55, 0.7, 0.85, 1, 1, 1.15, 1.4, 1.8, 2.6]) if k % 9 != 4 else rnd.choice([4.5, 7])
                vistas = int(base * mult * rnd.uniform(0.9, 1.1))
                tema = rnd.choice(TEMAS).replace("mi ", "tu ").replace("Mi ", "Tu ")
                vid = f"demo{cid}_{k}"
                v_id = c.execute("INSERT INTO videos(cuenta_id,red,vid,url,texto,portada,publicado,duracion) "
                                 "VALUES(?,?,?,?,?,?,?,?)",
                                 (cid, red, vid, f"https://example.com/demo/{vid}", tema, portada(tema, n),
                                  (ahora - timedelta(days=edad_d)).isoformat(timespec="seconds"),
                                  rnd.randint(18, 75))).lastrowid
                v_er = er * rnd.uniform(0.7, 1.35) * (1.2 if mult > 2 else 1)
                filas_m.append((v_id, hoy.isoformat(), vistas, *_metricas(vistas, v_er, rnd), int(vistas * .8)))
                k += 1
                n += 1
                edad_d += 7 / por_semana * rnd.uniform(0.5, 1.5)
            c.executemany("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?,?,?,?,?)", filas_m)
            _seguidores(c, cid, seg, ritmo, rnd)
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
    _miniaturas_demo()


# Miniaturas de ejemplo (imágenes reales hechas con la propia herramienta, en web/static/demo/).
MINIS_DEMO = [
    ("impacto", "COMMUNITY MANAGER CON IA GRATIS", "mini-1.jpg",
     "Dice el tema y el beneficio en 5 palabras; los logos dejan claro que va de redes."),
    ("impacto", "IA QUE HACE DE COMMUNITY MANAGER GRATIS", "mini-2.jpg",
     "Señalar la pantalla lleva la mirada al resultado."),
    ("objeto", "COMMUNITY MANAGER CON IA GRATIS", "mini-3.jpg", "El portátil con el panel es la prueba de lo que promete."),
    ("estudio", "GESTIONA TUS REDES CON IA GRATIS", "mini-4.jpg", "Gesto de «así de fácil» y texto que se entiende solo."),
]


def _miniaturas_demo() -> None:
    from ..db import ex as _ex
    if q("SELECT 1 FROM miniaturas WHERE archivo LIKE 'demo/%'", one=True):
        return
    idea = "Vídeo: he creado una IA que hace el trabajo de un community manager, gratis y en tu ordenador."
    for k, (estilo, texto, archivo, por_que) in enumerate(MINIS_DEMO):
        _ex("INSERT INTO miniaturas(encargo, variante, estilo, formato, idea, texto, por_que, archivo, estado) "
            "VALUES(?,?,?,?,?,?,?,?, 'ok')", ("demo", k, estilo, "9:16", idea, texto, por_que, "demo/" + archivo))

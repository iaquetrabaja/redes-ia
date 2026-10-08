"""Pruebas de Redes IA (sin red ni IA de verdad: todo simulado). Ejecuta: python -m unittest discover -s tests"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["REDES_IA_DATOS"] = tempfile.mkdtemp(prefix="redes-ia-test-")

from redes_ia import ajustes as A  # noqa: E402
from redes_ia import llm  # noqa: E402
from redes_ia.db import ex, iniciar, q  # noqa: E402

iniciar()


class Resp:
    def __init__(self, data=None, status=200, text=None):
        self._data, self.status_code = data, status
        self.text = text if text is not None else json.dumps(data or {})
        self.content = self.text.encode()

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class TestLLM(unittest.TestCase):
    def setUp(self):
        A.set("clave_gemini", "AIza-prueba")
        A.set("clave_openai", "sk-prueba")
        A.set("clave_anthropic", "sk-ant-prueba")

    def test_gemini_texto_y_json(self):
        A.set("proveedor", "gemini")
        A.set("modelo", "gemini-2.5-flash")
        r = Resp({"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})
        with mock.patch("redes_ia.llm.httpx.post", return_value=r) as p:
            self.assertEqual(llm.generar_json("hola"), {"ok": True})
            body = p.call_args.kwargs["json"]
            self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")

    def test_openai_y_anthropic(self):
        with mock.patch("redes_ia.llm.httpx.post",
                        return_value=Resp({"choices": [{"message": {"content": "funciona"}}]})):
            self.assertEqual(llm.generar_texto("x", p="openai", m="gpt-4o-mini"), "funciona")
        with mock.patch("redes_ia.llm.httpx.post",
                        return_value=Resp({"content": [{"type": "text", "text": "```json\n{\"a\": 1}\n```"}]})):
            self.assertEqual(llm.generar_json("x", p="anthropic", m="claude"), {"a": 1})

    def test_ollama_sin_clave(self):
        with mock.patch("redes_ia.llm.httpx.post", return_value=Resp({"message": {"content": "hola"}})):
            self.assertEqual(llm.generar_texto("x", p="ollama", m="llama3.1"), "hola")

    def test_clave_mala_da_mensaje_claro(self):
        A.set("proveedor", "gemini")
        with mock.patch("redes_ia.llm.httpx.post", return_value=Resp({"error": "x"}, status=403)):
            with self.assertRaises(llm.ErrorIA) as e:
                llm.generar_texto("x")
            self.assertIn("rechaza la clave", str(e.exception))

    def test_json_con_texto_alrededor(self):
        self.assertEqual(llm.extraer_json('Aquí tienes: {"x": [1, 2]} ¡listo!'), {"x": [1, 2]})

    def test_claves_ofuscadas_en_la_base(self):
        A.set("clave_openai", "sk-secreta-123")
        crudo = q("SELECT valor FROM ajustes WHERE clave='clave_openai'", one=True)["valor"]
        self.assertNotIn("secreta", crudo)
        self.assertEqual(A.get("clave_openai"), "sk-secreta-123")


class TestColectores(unittest.TestCase):
    def test_tiktok_perfil_desde_la_pagina_publica(self):
        from redes_ia.colectores import tiktok
        estado = {"source": {"data": {"/embed/@cuenta": {
            "userInfo": {"nickname": "Cuenta", "followerCount": 1234, "privateAccount": False},
            "videoList": [{"id": "7693912477498658051", "desc": "Hola", "coverUrl": "c", "playCount": 900}]}}}}
        html = f'<script id="__FRONTITY_CONNECT_STATE__" type="application/json">{json.dumps(estado)}</script>'
        with mock.patch("redes_ia.colectores.tiktok.httpx.Client.get", return_value=Resp(None, 200, html)):
            p = tiktok.perfil("https://www.tiktok.com/@Cuenta")
        self.assertEqual(p["seguidores"], 1234)
        self.assertEqual(p["videos"][0]["vistas"], 900)
        self.assertTrue(p["videos"][0]["publicado"].startswith("2026-"))

    def test_tiktok_fecha_de_id(self):
        from redes_ia.colectores import tiktok
        self.assertTrue(tiktok.fecha_de_id("7693912477498658051").startswith("2026-10"))
        self.assertIsNone(tiktok.fecha_de_id("abc"))

    def test_instagram_publicaciones(self):
        from redes_ia.colectores import instagram
        A.set("ig_token", "IGQ-prueba")
        data = {"data": [{"id": "1", "caption": "Texto", "media_type": "VIDEO", "media_product_type": "REELS",
                          "permalink": "https://instagram.com/reel/1", "timestamp": "2026-10-01T10:00:00+0000",
                          "like_count": 50, "comments_count": 3}]}
        with mock.patch("redes_ia.colectores.instagram.httpx.get", return_value=Resp(data)):
            pubs = instagram.publicaciones()
        self.assertEqual(pubs[0]["likes"], 50)
        self.assertEqual(pubs[0]["tipo"], "REELS")

    def test_instagram_token_caducado(self):
        from redes_ia.colectores import instagram
        A.set("ig_token", "IGQ-prueba")
        with mock.patch("redes_ia.colectores.instagram.httpx.get",
                        return_value=Resp({"error": {"message": "Invalid OAuth access token"}}, status=400)):
            with self.assertRaises(instagram.ErrorInstagram) as e:
                instagram.perfil()
        self.assertIn("token", str(e.exception).lower())

    def test_importar_csv_competencia(self):
        from redes_ia.servicios import datos
        n = datos.importar_csv("cuenta;url;texto;vistas;likes\notra;https://www.instagram.com/reel/AB1/;Gancho;12k;800\n")
        self.assertEqual(n, 1)
        v = q("SELECT m.vistas FROM videos v JOIN metricas m ON m.video_id=v.id WHERE v.vid='AB1'", one=True)
        self.assertEqual(v["vistas"], 12000)


def _pagina_embed(usuario, info, videos):
    estado = {"source": {"data": {f"/embed/@{usuario}": {"userInfo": info, "videoList": videos}}}}
    return f'<script id="__FRONTITY_CONNECT_STATE__" type="application/json">{json.dumps(estado)}</script>'


class TestComprobarTikTok(unittest.TestCase):
    """La comprobación al añadir una cuenta: cada caso con su mensaje y qué hacer. Sin internet (respuestas simuladas)."""

    def _comprobar(self, usuario, respuestas):
        from redes_ia.colectores import tiktok

        def get(url, **kw):
            for trozo, resp in respuestas.items():
                if trozo in url:
                    return resp
            return Resp(None, 404, "")
        with mock.patch("redes_ia.colectores.tiktok.httpx.Client.get", side_effect=get), \
                mock.patch("redes_ia.colectores.tiktok.time.sleep"):
            return tiktok.comprobar(usuario)

    def test_ok_con_enlace_del_perfil(self):
        html = _pagina_embed("mi_cuenta", {"nickname": "Mi Cuenta", "followerCount": 3150, "privateAccount": False},
                             [{"id": "7693912477498658051", "desc": "Mi vídeo", "playCount": 900}])
        r = self._comprobar("https://www.tiktok.com/@Mi_Cuenta?lang=es", {"/embed/@mi_cuenta": Resp(None, 200, html)})
        self.assertTrue(r["ok"])
        self.assertEqual(r["tipo"], "ok")
        self.assertEqual((r["usuario"], r["nombre"], r["seguidores"]), ("mi_cuenta", "Mi Cuenta", 3150))
        self.assertEqual(r["videos"][0]["vistas"], 900)

    def test_privada(self):
        html = _pagina_embed("privada_x", {"nickname": "P", "followerCount": 10, "privateAccount": True}, [])
        r = self._comprobar("@privada_x", {"/embed/@privada_x": Resp(None, 200, html)})
        self.assertFalse(r["ok"])
        self.assertEqual(r["tipo"], "privada")
        self.assertIn("Cuenta privada", r["que_hacer"])

    def test_no_existe(self):
        r = self._comprobar("no_existe_x", {"/embed/@no_existe_x": Resp(None, 500, "Internal Server Error"),
                                            "tiktok.com/@no_existe_x": Resp(None, 200, '{"statusCode":10221}')})
        self.assertFalse(r["ok"])
        self.assertEqual(r["tipo"], "no_existe")
        self.assertIn("bien escrito", r["que_hacer"])

    def test_sin_videos(self):
        html = _pagina_embed("nueva_x", {"nickname": "Nueva", "followerCount": 0, "privateAccount": False}, [])
        r = self._comprobar("nueva_x", {"/embed/@nueva_x": Resp(None, 200, html)})
        self.assertTrue(r["ok"])
        self.assertEqual(r["tipo"], "sin_videos")
        self.assertEqual(r["videos"], [])

    def test_tiktok_frena_y_sin_conexion(self):
        import httpx
        r = self._comprobar("lenta_x", {"/embed/@lenta_x": Resp(None, 429, ""), "tiktok.com/@lenta_x": Resp(None, 429, "")})
        self.assertEqual(r["tipo"], "frena")
        self.assertIn("minutos", r["que_hacer"])
        from redes_ia.colectores import tiktok
        with mock.patch("redes_ia.colectores.tiktok.httpx.Client.get", side_effect=httpx.ConnectError("sin red")), \
                mock.patch("redes_ia.colectores.tiktok.time.sleep"):
            self.assertEqual(tiktok.comprobar("alguien")["tipo"], "sin_conexion")

    def test_formato_y_vacio_sin_peticiones(self):
        from redes_ia.colectores import tiktok
        with mock.patch("redes_ia.colectores.tiktok.httpx.Client.get") as g:
            self.assertEqual(tiktok.comprobar("mi cuenta")["tipo"], "formato")
            self.assertEqual(tiktok.comprobar("  ")["tipo"], "vacio")
            g.assert_not_called()
        self.assertEqual(tiktok.limpiar_usuario("https://www.tiktok.com/@Pepe.Ruiz/video/123"), "pepe.ruiz")
        self.assertEqual(tiktok.limpiar_usuario(" @Pepe_Ruiz "), "pepe_ruiz")


class TestMetricasComparativa(unittest.TestCase):
    def test_engagement(self):
        from redes_ia.servicios.metricas import engagement
        self.assertEqual(engagement({"vistas": 1000, "likes": 50, "comentarios": 5, "compartidos": 10, "guardados": 15}), 8.0)
        self.assertIsNone(engagement({"vistas": 1000}))       # sin interacciones no es 0 %, es «no se sabe»
        self.assertIsNone(engagement({"vistas": 0, "likes": 3}))

    def test_estadisticas_de_una_cuenta(self):
        from datetime import date, timedelta
        from redes_ia.servicios.metricas import estadisticas
        hoy = date.today()
        vids = [{"publicado": (hoy - timedelta(days=d)).isoformat(), "vistas": v, "er": er, "multiplo": m}
                for d, v, er, m in [(1, 1000, 5.0, 1.0), (3, 3000, 7.0, 3.0), (5, 500, None, 0.5), (20, 900, 4.0, 0.9)]]
        s = estadisticas(vids, 7)
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["mediana"], 1000)
        self.assertEqual(s["engagement"], 6.0)
        self.assertEqual(s["sobre2"], 1)
        self.assertEqual(s["mejor"]["vistas"], 3000)
        self.assertEqual(s["frecuencia"], 3.0)
        # solo hay vídeos de las últimas 3 semanas: la frecuencia de 90 días se calcula sobre esas 3 semanas
        self.assertEqual(estadisticas(vids, 90)["frecuencia"], round(4 * 7 / 21, 1))

    def test_conclusion(self):
        from redes_ia.servicios.metricas import conclusion
        filas = [{"clave": "mediana", "suf": "", "tu": 2000, "mediana": 4000, "diferencia": -50},
                 {"clave": "engagement", "suf": "%", "tu": 9.0, "mediana": 6.0, "diferencia": 50},
                 {"clave": "frecuencia", "suf": "", "tu": 3.0, "mediana": 3.1, "diferencia": -3},
                 {"clave": "crecimiento", "suf": "%", "tu": 1.0, "mediana": 1.0, "diferencia": 0.0}]
        t = conclusion(filas, "TikTok")
        self.assertIn("tu engagement es un 50 % mayor", t)
        self.assertIn("pero tu mediana de vistas es un 50 % menor (2.000 frente a 4.000 vistas)", t)
        self.assertIn("Lo primero a mejorar", t)
        self.assertNotIn("publicas", t)          # una diferencia del 3 % no se menciona
        self.assertIn("a la par", conclusion([{**f, "diferencia": 0} for f in filas], "TikTok"))


class TestGuion(unittest.TestCase):
    def test_bucle_generar_puntuar_corregir(self):
        from redes_ia.servicios import estudio
        iid = ex("INSERT INTO ideas(tipo,titulo,gancho,estado,fuentes) VALUES('propia','Facturas a Excel con una foto','',"
                 "'guardada','[]')")
        flojo = {"ganchos": [{"texto": "Hola chicos, en el vídeo de hoy os enseño una herramienta", "formula": "x"}],
                 "guion": [{"texto": "Hola chicos, en el vídeo de hoy os enseño una herramienta muy interesante "
                                     "que sirve para muchas cosas diferentes y que os va a encantar seguro.", "pantalla": "",
                            "rotulo": ""}],
                 "pie_instagram": "Mira esto " + "#ia " * 8, "descripcion_tiktok": "Mira esto", "palabra": None}
        bueno = {"ganchos": [{"texto": "30 tickets. Una foto. La hoja se rellena sola.", "formula": "Demostración"}],
                 "guion": [{"texto": "30 tickets. Una foto. La hoja se rellena sola.", "pantalla": "tickets", "rotulo": "30 tickets"},
                           {"texto": "Le hago una foto a cada uno con el móvil.", "pantalla": "móvil", "rotulo": ""},
                           {"texto": "La IA saca fecha, importe y tienda.", "pantalla": "hoja", "rotulo": ""},
                           {"texto": "Antes, 2 horas al mes. Ahora, 5 minutos.", "pantalla": "cronómetro", "rotulo": ""},
                           {"texto": "Comenta GUIA y te lo mando. 30 tickets, una foto.", "pantalla": "cara", "rotulo": ""}],
                 "pie_instagram": "30 tickets a Excel con una foto.\n\nComenta GUIA y te mando el paso a paso.\n\n#ia #facturas",
                 "descripcion_tiktok": "30 tickets a Excel con una foto #ia #facturas", "palabra": "GUIA"}
        with mock.patch("redes_ia.servicios.estudio.llm.generar_json", side_effect=[flojo, bueno, bueno]) as g:
            res = estudio.preparar_guion(iid, vueltas=2)
        self.assertGreaterEqual(g.call_count, 2)
        self.assertGreaterEqual(res["versiones"], 2)
        self.assertEqual(res["ganchos"][0]["texto"], "30 tickets. Una foto. La hoja se rellena sola.")
        self.assertIn("ritmo", res)
        guardado = json.loads(q("SELECT detalle FROM ideas WHERE id=?", (iid,), one=True)["detalle"])
        self.assertIn("guion", guardado)

    def test_ideas_sin_repetir(self):
        from redes_ia.servicios import ideas
        self.assertTrue(ideas.parecida("Paso mis facturas a Excel con una foto",
                                       ["Paso mis facturas a Excel con una foto: prueba real"]))
        self.assertFalse(ideas.parecida("Un agente que ordena tu correo", ["Facturas a Excel con una foto"]))


class TestRutasDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from redes_ia.servicios import demo
        demo.cargar()
        from fastapi.testclient import TestClient
        from redes_ia.web.app import app
        cls.c = TestClient(app)

    def test_todas_las_paginas(self):
        for u in ["/", "/?dias=3", "/?dias=90&red=tiktok", "/?dias=30&red=youtube", "/competencia",
                  "/competencia?dias=90&red=instagram", "/competencia?dias=3&red=youtube", "/ideas", "/ideas?estado=todas&orden=nota", "/automatizaciones",
                  "/estudio", "/estudio?tab=comentarios", "/estudio?tab=plan", "/estudio?tab=voz", "/herramientas",
                  "/herramientas?h=ritmo", "/ajustes", "/ajustes?tab=redes", "/ajustes?tab=general",
                  "/ajustes?tab=claude", "/bienvenida", "/api/estado"]:
            r = self.c.get(u)
            self.assertEqual(r.status_code, 200, u)
            self.assertNotIn("Traceback", r.text, u)

    def test_herramientas_desde_el_panel(self):
        r = self.c.post("/herramientas", data={"h": "gancho", "texto": "Hola chicos, en el vídeo de hoy\n30 tickets y listo"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("FLOJO", r.text)

    def test_ficha_de_cada_cuenta(self):
        for c in q("SELECT id, usuario FROM cuentas WHERE demo=1"):
            for d in (7, 90):
                r = self.c.get(f"/competencia/{c['id']}?dias={d}")
                self.assertEqual(r.status_code, 200, c)
                self.assertIn("@" + c["usuario"], r.text)
        self.assertEqual(self.c.get("/competencia/999999", follow_redirects=False).status_code, 303)

    def test_competencia_resalta_lo_tuyo_y_compara(self):
        r = self.c.get("/competencia?dias=7")
        self.assertIn("fila-mia", r.text)
        self.assertIn("Tú contra tu competencia", r.text)
        self.assertIn("Frente a la mediana de tu competencia", r.text)
        self.assertIn("Engagement", self.c.get("/").text)

    def test_demo_completa(self):
        from redes_ia.servicios import metricas as M
        for red in ("tiktok", "instagram", "youtube"):
            n = q("SELECT COUNT(*) n FROM cuentas WHERE demo=1 AND mia=0 AND red=?", (red,), one=True)["n"]
            self.assertGreaterEqual(n, 3, red)
        r = M.resumen(90)
        self.assertGreater(sum(v for _, v in r["grafica"]["ganadas"]["TikTok"]), 0)
        self.assertGreater(len(r["grafica"]["seguidores"]), 1)
        self.assertIsNotNone(r["k"]["act"]["engagement"])

    def test_con_prefijo_de_url(self):
        from redes_ia.web import app as appmod
        with mock.patch.object(appmod, "BASE", "/x"), mock.patch.dict(appmod.plantillas.env.globals, {"B": "/x"}):
            cid = q("SELECT id FROM cuentas WHERE demo=1 AND mia=0 LIMIT 1", one=True)["id"]
            for u in ["/", "/competencia", f"/competencia/{cid}"]:
                r = self.c.get(u)
                self.assertEqual(r.status_code, 200, u)
                self.assertIn('href="/x/competencia', r.text, u)
                self.assertIn('src="/x/static/', r.text, u)
                self.assertNotIn('href="/competencia', r.text, u)
                self.assertNotIn('action="/competencia', r.text, u)
            r = self.c.post("/competencia/cuenta", data={"red": "tiktok", "usuario": "x"}, follow_redirects=False)
            self.assertTrue(r.headers["location"].startswith("/x/competencia"))

    def test_anadir_cuenta_comprueba_antes(self):
        from redes_ia.servicios import datos
        A.set("modo_demo", "0")
        try:
            malo = {"ok": False, "tipo": "no_existe", "mensaje": "No existe ninguna cuenta @nadie_x en TikTok.",
                    "que_hacer": "Revisa que esté bien escrito.", "usuario": "nadie_x", "videos": []}
            with mock.patch.object(datos, "comprobar_cuenta", return_value=malo):
                r = self.c.post("/competencia/cuenta", data={"red": "tiktok", "usuario": "@nadie_x"},
                                follow_redirects=False)
            self.assertIn("err=", r.headers["location"])
            self.assertIsNone(q("SELECT 1 FROM cuentas WHERE usuario='nadie_x'", one=True))
            frena = {**malo, "tipo": "frena", "mensaje": "TikTok no responde ahora mismo.", "usuario": "lento_x"}
            with mock.patch.object(datos, "comprobar_cuenta", return_value=frena):
                r = self.c.post("/competencia/cuenta", data={"red": "tiktok", "usuario": "lento_x"},
                                follow_redirects=False)
            self.assertIn("ok=", r.headers["location"])
            cid = q("SELECT id FROM cuentas WHERE usuario='lento_x'", one=True)["id"]
            self.c.post(f"/competencia/cuenta/{cid}/borrar")
            self.assertIsNone(q("SELECT 1 FROM cuentas WHERE usuario='lento_x'", one=True))
        finally:
            A.set("modo_demo", "1")

    def test_post_desde_otra_web_bloqueado(self):
        r = self.c.post("/ideas/nueva", data={"titulo": "x"}, headers={"origin": "https://malo.example"})
        self.assertEqual(r.status_code, 403)


class TestMCP(unittest.TestCase):
    def test_lista_y_ejecuta(self):
        from redes_ia.mcp_server import mcp

        async def go():
            tools = await mcp.list_tools()
            r = await mcp.call_tool("puntuar_gancho", {"gancho": "Hola chicos, en el vídeo de hoy"})
            return tools, r
        tools, r = asyncio.run(go())
        nombres = {t.name for t in tools}
        for n in ("puntuar_gancho", "hoja_de_ritmo", "revisar_pie", "humanizar", "ranking_viral", "ideas_recientes",
                  "auditoria", "preparar_guion"):
            self.assertIn(n, nombres)
        texto = r.content[0].text if hasattr(r, "content") else str(r)
        self.assertIn("FLOJO", texto)


if __name__ == "__main__":
    unittest.main()

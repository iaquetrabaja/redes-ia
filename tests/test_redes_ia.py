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
        for u in ["/", "/?dias=3", "/?dias=90&red=tiktok", "/ideas", "/ideas?estado=todas&orden=nota", "/automatizaciones",
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

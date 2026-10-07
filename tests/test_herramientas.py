"""Pruebas de las herramientas. Sin dependencias:  python -m unittest discover -s tests"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "redes"))

from herramientas import (clasificar_formula, formulas, hoja_de_ritmo, humanizar, puntuar,  # noqa: E402
                          puntuar_gancho, ranking, ranking_viral, revisar_pie, rubrica_perfil)


class Ganchos(unittest.TestCase):
    def test_gancho_malo_puntua_bajo(self):
        r = puntuar_gancho("Hola chicos, en el vídeo de hoy os voy a enseñar algo de marketing")
        self.assertLess(r["score"], 30)
        self.assertEqual(r["nivel"], "FLOJO")
        self.assertTrue(any("Saludo" in x for x in r["rompe_tratos"]))
        self.assertTrue(any("Preámbulo" in x for x in r["rompe_tratos"]))

    def test_gancho_concreto_puntua_alto(self):
        r = puntuar_gancho("18.000 euros me costó no poner una cláusula en el contrato.")
        self.assertGreaterEqual(r["score"], 70)
        self.assertEqual(r["nivel"], "FUERTE")
        self.assertEqual(r["formula"]["id"], 1)

    def test_numeros_dichos_cuentan(self):
        r = puntuar_gancho("Perdí veinte mil euros con un solo cliente.")
        self.assertGreaterEqual(r["propiedades"]["CONCRECION"]["score"], 70)

    def test_ranking_ordena(self):
        filas = ranking(["Hola, ¿qué tal?", "Deja de publicar tres veces al día.", ""])
        self.assertEqual(len(filas), 2)
        self.assertGreaterEqual(filas[0]["score"], filas[1]["score"])
        self.assertTrue(filas[0]["gancho"].startswith("Deja"))

    def test_cada_formula_reconoce_su_ejemplo(self):
        for f in formulas():
            c = clasificar_formula(f["ejemplo"])
            self.assertIsNotNone(c, f["nombre"])
            self.assertEqual(c["id"], f["id"], f["nombre"])

    def test_hay_26_formulas_completas(self):
        fs = formulas()
        self.assertEqual(len(fs), 26)
        for f in fs:
            for clave in ("plantilla", "ejemplo", "en_pantalla", "para_que", "trampa", "match"):
                self.assertTrue(f[clave], (f["id"], clave))

    def test_sin_formula_devuelve_none(self):
        self.assertIsNone(clasificar_formula("me gusta el café por las mañanas"))

    def test_es_json(self):
        json.dumps(puntuar_gancho("Nadie te cuenta que tus primeros 30 vídeos tienen que fracasar."))


class Ritmo(unittest.TestCase):
    GUION = ("Los presupuestos me llevaban cinco horas. Ahora, veinte minutos.\n"
             "Dicto la visita en una nota de voz al salir.\n"
             "ChatGPT me lo deja en Gmail con mis precios.\n"
             "Comenta PRESU y te paso la plantilla: cinco horas menos.")

    def test_estructura(self):
        r = hoja_de_ritmo(self.GUION, objetivo_s=20)
        self.assertEqual(len(r["beats"]), 4)
        self.assertEqual(r["beats"][0]["tipo"], "GANCHO")
        self.assertIn("CTA", r["beats"][-1]["tipo"])
        self.assertTrue(r["vuelve_al_inicio"])
        self.assertAlmostEqual(r["total_s"], r["total_palabras"] / (170 / 60), places=1)

    def test_gancho_largo_avisa(self):
        r = hoja_de_ritmo("Hoy quería contaros una cosa que me pasó la semana pasada con un cliente muy pesado de Valencia.\nFin.")
        self.assertTrue(r["beats"][0]["avisos"])
        self.assertTrue(any("La línea 1 tarda" in a for a in r["avisos"]))

    def test_vacio(self):
        r = hoja_de_ritmo("   \n ")
        self.assertEqual(r["beats"], [])


class Pie(unittest.TestCase):
    MALO = ("Hola a todos! En este vídeo os cuento cosas.\nSígueme y guárdalo.\n"
            "#ia #viral #fyp #parati #negocios #autonomos #emprendedores")
    BUENO = ("Perdí 3 clientes en un mes por contestar tarde. Esto es lo que cambié.\n\n"
             "Ahora el WhatsApp contesta solo las preguntas de siempre y yo solo miro los presupuestos.\n\n"
             "Comenta PRESU y te mando la plantilla.\n\n#autonomos #whatsapp #presupuestos")

    def test_malo_instagram(self):
        r = revisar_pie(self.MALO, red="instagram")
        estados = {c["check"]: c["estado"] for c in r["checks"]}
        self.assertEqual(estados["PRIMERA LÍNEA"], "FAIL")
        self.assertEqual(estados["HASHTAGS"], "FAIL")
        self.assertEqual(r["veredicto"], "ARREGLAR")

    def test_tiktok_sin_tope_duro(self):
        r = revisar_pie(self.MALO, red="tiktok")
        estados = {c["check"]: c["estado"] for c in r["checks"]}
        self.assertEqual(estados["HASHTAGS"], "WARN")
        self.assertEqual(r["corte"], 90)

    def test_bueno(self):
        r = revisar_pie(self.BUENO, palabras_clave=["presupuestos"])
        self.assertEqual(r["llamadas"], ["comentar una palabra clave"])
        self.assertLessEqual(len(r["lo_que_se_ve"]), 125)
        self.assertNotEqual(r["veredicto"], "ARREGLAR")


class Humanizar(unittest.TestCase):
    def test_invisibles_y_tipografia(self):
        r = humanizar("Hola​ mundo — esto es “raro”…")
        self.assertNotIn("​", r["texto"])
        self.assertNotIn("—", r["texto"])
        self.assertNotIn("“", r["texto"])
        self.assertIn("...", r["texto"])
        tipos = {c["tipo"] for c in r["cambios"]}
        self.assertTrue({"invisible", "tipografia"} <= tipos)

    def test_muletillas_y_mayusculas(self):
        r = humanizar("Sin embargo, es importante destacar que funciona. Cabe destacar que es gratis.")
        self.assertTrue(r["texto"].startswith("Pero funciona."), r["texto"])
        self.assertIn("Es gratis.", r["texto"])

    def test_sin_tildes_tambien(self):
        r = humanizar("Sigueme para mas trucos.")
        self.assertNotIn("Sigueme", r["texto"])

    def test_respeta_enlaces(self):
        r = humanizar("Mira https://ejemplo.com/sin-embargo-cabe-destacar ahora.")
        self.assertIn("https://ejemplo.com/sin-embargo-cabe-destacar", r["texto"])

    def test_senales(self):
        r = humanizar("No es solo una herramienta, es una forma de vida. #a #b #c #d #e #f #g")
        ids = {s["id"] for s in r["senales"]}
        self.assertIn("no-es-solo", ids)
        self.assertIn("muro-hashtags", ids)

    def test_respeta_espanol(self):
        r = humanizar("¿Te pasa? ¡Pues «esto» lo arregla!")
        self.assertEqual(r["texto"], "¿Te pasa? ¡Pues «esto» lo arregla!")


class Detectar(unittest.TestCase):
    MAQUINA = ("En el mundo actual, la inteligencia artificial juega un papel fundamental en las empresas. "
               "Sin embargo, es importante destacar que su implementación requiere una planificación cuidadosa. "
               "En primer lugar, las organizaciones deben identificar los procesos clave de su actividad. "
               "En segundo lugar, deben formar a sus equipos de manera adecuada y constante. "
               "En conclusión, la inteligencia artificial representa una oportunidad única para todos.")
    PERSONA = ("Ayer perdí dos horas con un presupuesto. Dos. ¿Sabes por qué? Porque copiaba los precios a mano "
               "desde un Excel de 2019. Hoy lo he cambiado: dicto la visita, ChatGPT me lo monta con mis precios y "
               "yo solo lo reviso. Me lleva 10 minutos. Vale, no es magia, pero a las 21:00 ya estoy cenando "
               "con mi familia en Murcia y no delante del portátil.")

    def test_maquina_vs_persona(self):
        m, p = puntuar(self.MAQUINA), puntuar(self.PERSONA)
        self.assertLess(m["human_score"], p["human_score"])
        self.assertEqual(m["veredicto"], "MARCADO")
        self.assertIn(p["veredicto"], ("PASA", "REVISAR"))
        self.assertEqual(set(m["checks"]), {"burstiness", "especificidad", "muletillas", "huella", "voz"})

    def test_humanizar_sube_nota(self):
        antes = puntuar(self.MAQUINA)["human_score"]
        despues = puntuar(humanizar(self.MAQUINA)["texto"])["human_score"]
        self.assertGreater(despues, antes)


class Viral(unittest.TestCase):
    FILAS = [
        {"cuenta": "@a", "seguidores": "48000", "mediana": "11000", "vistas": "412.000",
         "gancho": "Nadie te cuenta que tus primeros 30 vídeos van a fracasar"},
        {"cuenta": "@b", "seguidores": "2M", "mediana": "900k", "vistas": "1,2 M",
         "gancho": "en este vídeo os enseño mi rutina de mañana"},
        {"cuenta": "@c", "seguidores": "4000", "mediana": "3000", "vistas": "180000",
         "gancho": "Copia este mensaje de seguimiento, me costó dos años"},
        {"cuenta": "@d", "seguidores": "10000", "vistas": "", "gancho": "fila sin vistas"},
    ]

    def test_orden_por_multiplo(self):
        r = ranking_viral(self.FILAS)
        self.assertEqual(r["n"], 3)
        self.assertEqual(r["base"], "mediana de la cuenta")
        self.assertEqual(r["videos"][0]["cuenta"], "@c")
        self.assertEqual(r["videos"][0]["formula_id"], 9)
        self.assertEqual(r["videos"][-1]["cuenta"], "@b")
        self.assertAlmostEqual(r["videos"][-1]["multiplo"], 1.33, places=2)
        self.assertEqual(r["sin_clasificar"], 1)
        json.dumps(r)


class Rubrica(unittest.TestCase):
    def test_suma_100(self):
        d = rubrica_perfil()
        self.assertEqual(sum(i["puntos"] for i in d["items"]), 100)
        self.assertEqual(len(d["items"]), 12)


if __name__ == "__main__":
    unittest.main()

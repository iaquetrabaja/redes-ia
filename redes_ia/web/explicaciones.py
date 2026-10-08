"""Textos de «¿Qué es esto?» de cada sección. Explican qué ves, de dónde sale y cómo usarlo.

Están pensados para quien abre Redes IA por primera vez (y para enseñarlo en un vídeo). Cada entrada es
(título, [párrafos o viñetas]). Las viñetas empiezan por «- » y se pintan como lista.
"""

EXPLICACIONES: dict[str, tuple[str, list[str]]] = {
    "resumen": ("Tus números de un vistazo", [
        "Aquí ves cómo les va a tus vídeos en el periodo que elijas (3, 7, 30 o 90 días) y si vas a mejor o a peor "
        "que en el periodo anterior del mismo tamaño.",
        "- **Vistas, me gusta y comentarios**: lo básico. Las vistas dicen cuánta gente lo vio; no si le gustó.",
        "- **Compartidos y guardados**: lo que más pesa para que TikTok e Instagram enseñen tu vídeo a más gente. "
        "Un vídeo que se guarda es útil; uno que se comparte, se recomienda solo.",
        "- **Seguidores**: la evolución día a día en cada red.",
        "- **Tus vídeos del periodo**: con la columna «× tu media», que compara cada vídeo con tu vídeo típico. "
        "x3 significa que tuvo el triple de vistas que tu mediana. Así sabes qué funcionó de verdad, sin que te "
        "engañe un día bueno.",
        "Los datos se actualizan solos cada día (o con «Actualizar datos»). Todo se guarda en tu ordenador.",
    ]),
    "ideas": ("Ideas de vídeo con nota", [
        "Redes IA busca qué está funcionando y te lo convierte en ideas para tu canal, cada una con una nota del 0 "
        "al 10. Mira cuatro sitios:",
        "- **Tu competencia**: los vídeos que superan la media de su propia cuenta. No mira las vistas brutas (una "
        "cuenta grande con un día flojo no te enseña nada); mira lo que sorprendió a su propia audiencia.",
        "- **Tus mejores vídeos**: para proponerte una segunda parte cuando en los comentarios hay dudas reales.",
        "- **Tendencias**: lo nuevo en GitHub, Hacker News y Reddit que encaja con tu nicho.",
        "- **Tus comentarios**: lo que te preguntan o piden (sin contar los que solo son la palabra clave de un "
        "mensaje automático).",
        "La **nota** pondera la demanda demostrada, la actualidad, el encaje con tu canal y lo fácil que es grabarlo "
        "esta semana. La etiqueta **«Gancho NN»** es la nota (0-100) de la primera frase propuesta.",
        "Guarda las que te gusten, marca las que ya hiciste y descarta el resto: no se repiten ideas parecidas. "
        "Con **«Preparar guion»** tienes el vídeo listo para grabar.",
    ]),
    "guion": ("Qué hace «Preparar guion»", [
        "- **3 ganchos** (la frase de los 2 primeros segundos) con 26 fórmulas probadas, cada uno con su nota. El "
        "mejor abre el vídeo.",
        "- **El guion frase a frase** con el segundo en que empieza cada una (a unas 170 palabras por minuto), el "
        "texto en pantalla y lo que se ve.",
        "- **Avisos de ritmo**: frases de más de 4 segundos (ahí la gente se va), tramos sin nada concreto, si "
        "vuelve al principio para que se vea dos veces.",
        "- **El texto del post** de Instagram y TikTok, revisado: lo que se ve antes del «… más», máximo de "
        "hashtags, una sola llamada a la acción.",
        "- **«Suena humano»**: quita las muletillas típicas de la IA y puntúa el texto.",
        "Si algo flojea, la IA lo corrige sola con esos avisos (hasta dos vueltas) y se queda con la mejor versión.",
    ]),
    "automatizaciones": ("Ideas de automatizaciones para trabajadores corrientes", [
        "Cada lunes, 3 ideas de vídeo sobre una tarea que la IA hace sola y que sirve a muchos oficios a la vez "
        "(el fontanero, la recepcionista, quien tiene empleados…): partes de trabajo, citas, mensajes repetidos, "
        "presupuestos.",
        "Cada idea trae: qué automatiza (antes y después), para quién sirve, cuánto tiempo ahorra, qué herramientas "
        "usa (gratis o de pago), el guion por escenas pensado para que no sea solo grabar la pantalla, los pasos "
        "para montarla y la palabra clave para mandar la guía por mensaje.",
        "Son siempre fáciles: desde el móvil o el ordenador, sin programar, en 30-60 minutos.",
    ]),
    "estudio.auditoria": ("Auditoría: qué de lo que publicas funciona", [
        "Tus vídeos de los últimos 90 días ordenados por **cuánto superan tu propia media** (× tu media), no por "
        "vistas. La barra verde marca el tercio de arriba.",
        "- **Compartidos / 1.000** y **guardados / 1.000**: por cada mil vistas, cuántas personas lo compartieron "
        "o guardaron. Permite comparar un vídeo pequeño con uno grande.",
        "- **Fórmula del gancho**: qué tipo de primera frase usaste (Nadie te cuenta, Tiempo comprimido, La cifra…).",
        "Con **«Sacar conclusiones con IA»** te dice qué patrones funcionan, cuáles no, qué repetirías con otro "
        "ángulo y cuál es tu siguiente apuesta, siempre con el dato que lo demuestra.",
    ]),
    "estudio.comentarios": ("Comentarios que merecen respuesta", [
        "Lee los comentarios de tus últimos vídeos y los ordena para que no se te escape nada importante:",
        "- **Cliente potencial**: alguien con un negocio o un problema que podrías resolver.",
        "- **Pregunta**: una duda concreta.",
        "- **Idea de vídeo**: te piden un tema.",
        "- **Queja o crítica**, **Apoyo** y **Ruido**.",
        "Cada uno trae un **borrador de respuesta** con tu voz, listo para copiar. Nada se publica solo: respondes "
        "tú y lo marcas como «Respondido». Los comentarios que solo son la palabra clave de un mensaje automático "
        "no aparecen.",
    ]),
    "estudio.plan": ("Plan de la semana", [
        "Un plan de 7 días hecho con tus ideas guardadas, las mejores de la semana y lo que dice la auditoría: qué "
        "publicar cada día, en qué formato, a qué hora, con qué gancho y con qué palabra clave. Los días sin vídeo "
        "propone una tarea corta (responder comentarios, grabar en bloque…).",
    ]),
    "estudio.voz": ("La voz de tu canal", [
        "Cómo hablas tú: a quién te diriges, tu tono, tus frases, las palabras que nunca dirías y cómo cierras un "
        "vídeo. La usan las ideas, los guiones y los borradores de respuesta para que todo suene a ti y no a una IA.",
        "Puedes escribirla a mano o pulsar «Escribirla a partir de mis vídeos» y corregirla.",
    ]),
    "herramientas.gancho": ("Puntuar ganchos", [
        "Pega varias primeras frases (una por línea) y te las ordena de mejor a peor con una nota de 0 a 100. Mira "
        "cinco cosas: que sea corta, que tenga algo concreto (una cifra, un nombre), que cree tensión, que lo "
        "importante vaya delante y a quién le habla. También avisa de lo que hunde un gancho (saludar, «en el vídeo "
        "de hoy», «deja de hacer scroll») y dice qué fórmula usa.",
        "Sirve para descartar los ganchos flojos antes de grabar; el que gana entre dos buenos lo decide tu vídeo.",
    ]),
    "herramientas.ritmo": ("Ritmo del guion", [
        "Pega el guion (una frase por línea) y te dice cuánto dura al decirlo en voz alta, en qué segundo empieza "
        "cada frase y dónde se te va a ir la gente: un gancho de más de 3 segundos, frases de más de 4, tramos sin "
        "nada concreto, o un final que no vuelve al principio.",
    ]),
    "herramientas.pie": ("Revisar el texto del post", [
        "Te enseña exactamente lo que se ve en el feed antes del «… más» (unos 125 caracteres en Instagram) y "
        "revisa la longitud, si la primera línea engancha, el número de hashtags (máximo 5 en Instagram), que haya "
        "una sola llamada a la acción y que estén tus palabras de búsqueda.",
    ]),
    "herramientas.humanizar": ("Humanizar", [
        "Quita lo que delata un texto escrito con IA: caracteres invisibles, rayas largas, muletillas («cabe "
        "destacar», «en el mundo actual», «sígueme para más»…), y te avisa de las estructuras típicas («no es solo "
        "X, es Y», listas de tres). Te da una nota de lo humano que suena antes y después.",
    ]),
    "herramientas.viral": ("Ranking viral", [
        "Pega una tabla de vídeos (cuenta, vistas, mediana de la cuenta o seguidores, y el gancho) y los ordena por "
        "cuánto superaron a su propia cuenta. Te dice qué fórmulas de gancho se repiten arriba y qué separa a los "
        "que funcionaron de los que no.",
    ]),
    "ajustes.ia": ("Qué IA usar", [
        "Redes IA no trae una IA dentro: usa la tuya con tu propia clave. **Gemini es gratis** (con límites diarios) "
        "y es lo recomendado para empezar. OpenAI, Claude y OpenRouter cobran por uso (céntimos al día con este "
        "panel). Ollama funciona en tu ordenador sin internet si tienes un equipo potente. La clave solo se guarda "
        "en tu ordenador.",
    ]),
    "ajustes.redes": ("Tus cuentas y tu competencia", [
        "- **TikTok y YouTube**: pon tu @ y el de las cuentas que quieras vigilar. Se leen los datos públicos, sin "
        "contraseña.",
        "- **Instagram**: tu cuenta profesional con la API oficial (la guía explica cómo sacar el token). La "
        "competencia de Instagram se añade a mano o con un CSV, porque Instagram no da datos de cuentas ajenas.",
    ]),
    "ajustes.general": ("Horarios y preferencias", [
        "A qué hora se actualizan los datos y se buscan ideas cada día, y el contexto de tu canal (de qué hablas y "
        "para quién), que usa la IA en todo lo que genera.",
    ]),
    "ajustes.claude": ("Usarlo desde Claude, Cursor y similares", [
        "Redes IA trae un **servidor MCP**: conecta Claude Desktop, Claude Code o Cursor y pídeles en el chat "
        "«puntúame estos ganchos», «¿qué ideas tengo guardadas?» o «prepárame el guion de la idea 4». Usan las "
        "mismas herramientas y tus datos locales. También trae una **skill** en español con 13 modos.",
    ]),
}


def clave(ruta: str, params) -> str:
    """Qué explicación toca según la página y la pestaña."""
    p = (ruta or "/").rstrip("/") or "/"
    if p == "/":
        return "resumen"
    base = p.strip("/").split("/")[0]
    if base == "estudio":
        return "estudio." + (params.get("tab") or "auditoria")
    if base == "herramientas":
        return "herramientas." + (params.get("h") or "gancho")
    if base == "ajustes":
        return "ajustes." + (params.get("tab") or "ia")
    return base

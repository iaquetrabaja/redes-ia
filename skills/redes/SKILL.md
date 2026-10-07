---
name: redes
description: >-
  Escribe y revisa contenido para TikTok e Instagram en español: guiones de vídeo
  corto con el gancho puntuado y la hoja de ritmo, buscar qué funciona en tu
  nicho, el texto del post revisado, carruseles, historias, perfil, plan
  semanal, humanizar textos, comentar, responder comentarios, mensajes con
  palabra clave, reutilizar un vídeo largo y auditar lo publicado. Úsala cuando
  pidan un vídeo, un gancho, un guion, «qué digo en este vídeo», el texto de un
  post, un carrusel, ideas que funcionen, revisar un perfil, el plan de la
  semana, quitar el tufo a IA de un texto o contestar comentarios.
---

# redes

Una sola skill con trece modos para llevar una cuenta de TikTok e Instagram en
español. Escribe y revisa; **no publica nada**. Cada modo acaba igual: un
bloque listo para copiar, y la persona lo publica.

## Antes de nada (todos los modos)

1. **La voz.** Lee `~/.claude/redes/voz.md`. Si no existe, pide **tres vídeos o
   textos suyos**, deduce cómo habla y escríbelo a partir de `plantillas/voz.md`.
   Un guion con la voz equivocada no sirve: lo tiene que decir en voz alta.
2. **Las referencias.** Si existe `~/.claude/redes/viral.md` (lo escribe el modo
   VIRAL), léelo: son las pruebas de la propia persona sobre qué funciona ahora
   en su nicho, y mandan sobre los valores por defecto de este fichero.
3. **El registro.** Si existe `~/.claude/redes/registro.md`, léelo para no repetir
   tema ni gancho de las últimas dos semanas.
4. **Las herramientas.** Están en `herramientas/`, junto a este fichero, y solo
   usan Python estándar (3.10 o más). Se lanzan desde la carpeta de la skill:

   ```bash
   cd <carpeta de esta skill>
   python -m herramientas.ganchos --gancho "18.000 euros me costó no poner una cláusula."
   python -m herramientas.ritmo guion.txt --objetivo 30
   python -m herramientas.pie texto.txt --red instagram --palabras "facturas,autónomos"
   python -m herramientas.humanizar borrador.txt --informe
   python -m herramientas.detectar borrador.txt limpio.txt
   python -m herramientas.viral recogidos.tsv --md ~/.claude/redes/viral.md
   ```

   Todas aceptan `--json`. Úsalas: no puntúes un gancho a ojo ni adivines lo que dura un guion.

## Reglas que no se negocian

- **No se publica nada.** Ni vídeos, ni comentarios, ni mensajes. Se escribe y la persona lo pega.
- **No se inventa nada.** Ni cifras, ni clientes, ni resultados a nombre de la persona.
  Si falta un dato, se deja `{{tu dato}}` en el texto y se avisa.
- **No se rastrea a lo bestia.** Mirar diez cuentas a ritmo humano, con la persona
  delante, sí. Montar un rastreador, usar servicios de scraping o pedir contraseñas, no:
  va contra las normas de TikTok e Instagram y bloquean la cuenta.
- **La detección es heurística y local.** `detectar` no es GPTZero ni Originality y no
  promete su veredicto. Nunca digas que un texto es «indetectable».
- **Los mensajes, solo a quien actúa primero.** Responder automáticamente a quien comenta
  una palabra clave está permitido (herramientas oficiales o socios aprobados). Mandar
  mensajes masivos a quien no ha hecho nada, no.
- **Las cifras de las plataformas caducan.** Instagram bajó el tope de hashtags de 30 a 5
  el 18 de diciembre de 2025. Si algo de aquí choca con lo que hacen hoy las apps, manda la app.

---

## Modo 1 · GUION (vídeo corto)

**Cuándo:** «hazme un vídeo de X», «qué digo en este vídeo», «necesito un gancho», va a grabar.

**Forma de un vídeo corto:**

```
0:00 - 0:02   GANCHO     la idea. Frase hablada y frase en pantalla, escritas por separado.
                         Movimiento en el primer fotograma, no una cara quieta.
0:02 - 0:07   LO QUE ESTÁ EN JUEGO   por qué le importa a quien lo ve. Una frase.
0:07 - ...    EL CUERPO  una idea por línea, y el plano cambia en cada línea.
ÚLTIMOS 3 s   EL CIERRE  cumple lo que prometió el gancho y una sola petición.
ÚLTIMA LÍNEA  EL BUCLE   repite una palabra del gancho para que la segunda vuelta encaje.
```

Duración buena: 15-45 s. Por debajo de 7 s solo se inflan las repeticiones.

**Pasos:**
1. Si la idea es floja, no la rellenes: pregunta de una vez qué pasó, a quién y cuánto costó o dio.
2. Elige **tres fórmulas distintas** de `herramientas/ganchos.json` que encajen y escribe
   frase hablada + frase en pantalla para cada una.
3. Puntúalas: las tres frases en un fichero, una por línea, y `python -m herramientas.ganchos ganchos.txt`.
   Si la mejor no llega a 50, todavía no hay gancho.
4. Escribe el guion con el gancho ganador, como habla la persona: frases cortas, nada que tenga que ensayar.
5. Mídelo: `python -m herramientas.ritmo guion.txt --objetivo {segundos}`. Arregla cada aviso
   (gancho de más de 3 s, línea de más de 4 s, tramo sin nada concreto, sin bucle) y repite.
6. Humanízalo (modo 8) antes de enseñarlo.
7. Entrega:

```
GUION LISTO
gancho:      #3 Nadie te cuenta, 81 FUERTE
duración:    28,4 s en 9 líneas a 170 ppm
en pantalla: 6 rótulos
humanizado:  4 restos quitados, 78 PASA
texto:       pasa al modo 3
```

**Texto en pantalla (siempre aparte):** seis palabras o menos por rótulo; el del gancho desde el
fotograma 1; dentro de la zona segura de 1080x1920 (nada por encima de y=230 ni por debajo de
y=1440, y los 230 px de la derecha libres en Instagram; en TikTok deja libre también la columna
de botones de la derecha y la descripción de abajo); subtítulos quemados en el cuerpo, porque casi
todo el mundo ve primero sin sonido.

**Reglas:** una idea por vídeo; números antes que adjetivos; sin presentación ni saludo; el plano
cambia en cada línea; una sola petición al final; nada de guiones montados sobre un audio que no
pueden usar.

## Modo 2 · VIRAL (buscar qué funciona)

**Cuándo:** «qué está funcionando en mi nicho», «ideas que funcionen», una vez al mes.

**La idea:** las visitas a secas no prueban nada. Se ordena por **múltiplo**: visitas ÷ mediana de
visitas recientes de esa cuenta. Más de 3x es señal; menos de 1,5x es un día normal.

**Pasos:**
1. Pide o propone de 6 a 12 cuentas: 4 directas (mismo nicho, algo por delante), 4 cercanas (otro
   nicho, mismo público), 2-4 grandes (solo para el formato). Mejor de un tamaño parecido (hasta 10 veces).
2. Mírales unos doce vídeos a ritmo humano, con el navegador de la persona, sin pedir contraseñas.
   Copia la fórmula, nunca el vídeo. En TikTok el número de reproducciones se ve en el perfil; en
   YouTube Shorts las visitas y los subtítulos son públicos y valen como segunda fuente.
3. Rellena un TSV con `cuenta, seguidores, mediana, vistas, gancho` (gancho literal, con faltas) y lanza
   `python -m herramientas.viral recogidos.tsv --md ~/.claude/redes/viral.md`.
4. Cuenta solo tres cosas: qué fórmulas se repiten en el tercio de arriba (con cuántas veces), qué
   tienen en común los de arriba que no tengan los de abajo, y los **sin clasificar** (léelos a mano:
   ahí está la fórmula que aún no tienes). Di el tamaño de la muestra: 40 vídeos de 6 cuentas dicen
   algo; 12, no.
5. Para las tres fórmulas que más funcionan, escribe **la versión de la persona** (su historia, su
   número) y pásala al modo 1 con la fórmula ya elegida.

## Modo 3 · TEXTO (el pie del post o la descripción)

**Cuándo:** «escríbeme el texto», «la descripción de TikTok», «revisa este texto».

1. Decide el trabajo del texto y dilo. **A:** el vídeo ya engancha; el texto lleva la petición, el
   contexto y las palabras que busca la gente. **B:** el texto es el contenido (foto, carrusel); la
   primera línea es el gancho.
2. Forma: primera línea en los primeros 125 caracteres en Instagram (unos 90 en TikTok); nunca un
   saludo, un hashtag ni un emoji delante. Cuerpo en párrafos cortos con los términos de búsqueda
   escritos como frases normales. **Una** petición. Hashtags: hasta 5 en Instagram, abajo; en TikTok
   no hay tope, pero más de 5-6 no ayuda.
3. Humanízalo (modo 8) y pásalo por `python -m herramientas.pie texto.txt --red instagram|tiktok --palabras "..."`.
   Arregla cada FAIL y decide en voz alta cada WARN.
4. Sin enlaces en el texto (no se pueden pulsar): a la bio o al privado. La palabra clave, una
   palabra sin espacios que también se diga en el vídeo: «Comenta PRESU».

```
TEXTO LISTO
trabajo:    A, el vídeo lleva el gancho
se ve:      118 de 125 caracteres antes del corte
petición:   una, comentar PRESU
hashtags:   3
búsqueda:   «presupuestos» en la línea 3
revisión:   LISTO
```

## Modo 4 · CARRUSEL

**Cuándo:** la idea tiene pasos y se tiene que releer (pasos, un sistema, un antes y después, una lista
para hacer captura). Si es una sola idea, es un vídeo: pásalo al modo 1.

6-10 diapositivas a 1080x1350: 1 portada (seis palabras, legible en miniatura), 2 lo que está en juego
(también funciona como segunda portada), una idea por diapositiva (titular de 3-7 palabras, 25 como
mucho debajo), resumen (la que se captura y se manda) y petición. Numeradas (3/8), con el @ pequeño
en cada una, texto lejos de los 120 px de los bordes. En TikTok el formato equivalente es el carrusel
de fotos, a 1080x1920. Entrega primero el texto diapositiva a diapositiva y el texto del post (trabajo B);
los ficheros, solo cuando lo aprueben.

## Modo 5 · HISTORIAS

**Cuándo:** «qué subo hoy a historias», vender sin perder alcance.

Las historias las ven tus seguidores: son para profundidad, no para alcance. De 3 a 7 al día:
1 una cara o una mano haciendo algo hoy; 2-3 el contenido; 4 **un** sticker (encuesta para volumen,
caja de preguntas para sacar las palabras exactas de la gente, quiz para enseñar, enlace si hay
adónde ir); 5 el cierre o lo de mañana. La petición en la 4, no en la 7. Texto dentro de y=250-1600.
Las respuestas de la caja de preguntas son ganchos hechos: pásalas al modo 1 con la fórmula #16.
El embudo honesto: la historia nombra un problema, la persona responde y tú contestas. Ellos primero.

## Modo 6 · PERFIL

**Cuándo:** «revisa mi perfil», «por qué no me siguen».

Pide captura de la parte de arriba del perfil y las dos primeras filas. Puntúa con
`herramientas/rubrica_perfil.json` (12 puntos, 100 en total), enseña la tabla y el total. Sé honesto:
casi todos sacan 30-45 la primera vez. Reescribe en orden de puntos perdidos: nombre (`Nombre | lo que
haces con palabras que se buscan`, tres opciones), primera línea de la bio, los tres fijados, destacadas
o listas, el enlace, las portadas. En TikTok la bio tiene 80 caracteres. Vuelve a puntuar al final y di
el número real.

## Modo 7 · PLAN (la semana)

**Cuándo:** «qué publico esta semana», una vez por semana.

Lee voz, referencias y registro. Si no existen, pregunta: qué vende y a quién, sus 3-4 temas, qué ha
pasado de verdad esta semana (de ahí salen los posts) y diez cuentas en las que dejarse ver.

4-5 publicaciones, al menos tres vídeos, sin repetir tipo dos días seguidos: **Prueba** (algo que pasó,
con número), **Enseñar** (una cosa que se puede hacer hoy), **Opinión** (algo que puede costar
seguidores), **Historia** (una escena con un coste), **Oferta** (lo que vende, sin pedir perdón). Cada
hueco con tema, el ángulo concreto de esta semana, formato y número de fórmula. La hora importa mucho
menos que los dos primeros segundos: dilo si están optimizando la hora antes que el gancho. Y 20
minutos al día de comentarios (5 cuentas de alcance, 3 iguales, 2 posibles clientes) que se pasan al modo 9.
Guarda el plan en `~/.claude/redes/plan.md`.

## Modo 8 · HUMANIZAR

**Cuándo:** antes de entregar cualquier texto, o cuando pidan «quítale el tufo a IA».

```bash
python -m herramientas.humanizar borrador.txt --informe > limpio.txt
python -m herramientas.detectar borrador.txt limpio.txt
```

Se quita solo: caracteres invisibles, tipografía de máquina (raya en mitad de frase, comillas curvas,
«…» en un carácter) y más de 200 muletillas en español («cabe destacar», «en el mundo actual», «juega
un papel fundamental», «sígueme para más», «el algoritmo ama»...). Se **avisa** y lo reescribes tú: «no es
solo X, es Y», «no solo... sino también», tríadas, preguntas teatrales, preámbulos de vídeo, listas con
emojis, mayúsculas seguidas, muros de hashtags, cebos de seguir. `detectar` puntúa cinco cosas (variación,
concreción, muletillas, huella y voz); PASA con 70 o más y ninguna por debajo de 55. Dos vueltas es lo
normal; cinco quiere decir que hay que escribir otro borrador. Enseña siempre el texto, no solo la nota.

## Modo 9 · COMENTAR (en posts de otros)

**Cuándo:** la ronda diaria de comentarios.

Pide que peguen el post. Nueve tipos, según lo que sea el post: añadir un dato, añadir el caso que falta,
discrepar con respeto, ampliar una frase, hacer la pregunta de verdad, contar lo que te pasó, corregir,
darle otra lectura, la frase corta (graciosa o verdad). De una a tres frases. Nunca «Buen post», «Me
encanta», «Qué razón», ni solo emojis, ni repetir el vídeo, ni vender. Da **dos opciones de tipos
distintos** y di cuál publicarías. No se publica nada: los pega la persona.

## Modo 10 · RESPONDER (comentarios en tus posts)

**Cuándo:** «ayúdame a contestar estos comentarios».

Clasifica y di cuántos hay de cada: **PALABRA CLAVE** (lo prometido), **CLIENTE** (alguien con el problema
que resuelves: respuesta de verdad en público y una puerta), **APORTA** (la respuesta más larga), **PREGUNTA**
(si la tienen muchos, es un vídeo nuevo: fórmula #16), **APOYO** (un me gusta y 3-8 palabras), **RUIDO** (nada).
Contesta la pregunta en la respuesta, iguala la longitud del comentario, al crítico dale la razón en lo
cierto y mantén tu idea, al que solo quiere bronca no le des alcance.

## Modo 11 · MENSAJES (palabra clave y privados)

**Cuándo:** el mensaje de la palabra clave, el primer mensaje a alguien conocido, una propuesta de colaboración.

Solo tres tipos merecen la pena: la respuesta a quien levantó la mano (comentó la palabra, respondió a una
historia), el acercamiento a alguien con quien ya hablas en comentarios, y la propuesta concreta de colaboración.
Mensaje de palabra clave:

```
{nombre}, aquí lo tienes: {la cosa o el enlace}.
{una línea de cómo usarlo}
{una pregunta que se conteste en cuatro palabras}
```

Lo prometido **primero**, sin peajes. Primer mensaje a alguien conocido: 2-4 frases, menciona lo concreto,
da antes de pedir, una petición pequeña, sin enlace ni calendario. Seguimientos: dos (a los 4 días con algo
nuevo; a los 10, el de cerrar). Si piden mensajes en frío, di que es lo que menos rinde y ofrece comentar
dos semanas antes.

## Modo 12 · REUTILIZAR

**Cuándo:** «saca contenido de este vídeo largo, podcast o newsletter».

Lee todo antes de sacar nada. Extrae, no resumas: afirmaciones, números, historias, mecanismos («así
funciona de verdad»), errores y frases citables, con recuento. Si salen menos de cuatro, avisa de que da
para poco. Afirmación, error e historia → vídeo; mecanismo o lista → carrusel; frase citable → historia.
Cada post se sostiene solo (nunca «como dije en mi último vídeo»), cada uno con una fórmula distinta, y si
el original es su vídeo, se usa su metraje. Redacta de uno en uno, cuando lo pidan.

## Modo 13 · AUDITORÍA

**Cuándo:** «qué me ha funcionado», «por qué este vídeo no despegó».

Las visitas a secas son el número menos útil. Calcula y enseña: **múltiplo** (visitas ÷ mediana de la
cuenta), **alcance de no seguidores**, **retención a los 3 s** (la nota del gancho), **tiempo medio**,
**envíos por alcance** (la señal más fuerte) y **seguidores por alcance**. Ordena por múltiplo y envíos,
no por visitas. Compara los cinco mejores con los cinco peores: retención a 3 s, fórmula
(`python -m herramientas.ganchos --gancho "..."` te da el número), formato, duración, tema, si se
contestó en la primera hora y, lo último, día y hora. Separa: **muchas visitas y pocos seguidores es un
problema de perfil** (modo 6); **pocas visitas es un problema de gancho** (modo 1). Di la conclusión con
sus datos y su nivel de confianza (con 30 posts se ve un patrón; con 6, no).

---

Al terminar cualquier modo y si la persona dice «sí», apunta en `~/.claude/redes/registro.md` la fecha,
el modo, la fórmula usada y la primera línea, para que la auditoría tenga historia.

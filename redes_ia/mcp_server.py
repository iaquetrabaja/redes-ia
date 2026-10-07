"""Servidor MCP (stdio) de Redes IA para Claude Desktop, Claude Code, Cursor y cualquier cliente MCP.

Herramientas de la skill (funcionan sin IA ni internet) y acceso de solo lectura a tu panel local (ideas, auditoría,
comentarios, voz, plan). preparar_guion sí usa la IA que tengas configurada en el panel.

Arranque: python -m redes_ia.mcp_server   (o python mcp_redes.py desde cualquier carpeta)
"""
import json

try:   # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:   # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

import herramientas as H

from .db import iniciar, q

mcp = _Server("redes-ia", instructions=(
    "Herramientas para crear contenido de TikTok e Instagram en español: puntuar ganchos, cronometrar guiones, revisar "
    "el texto del post, humanizar textos de IA y rankear vídeos virales; y leer las ideas, la auditoría, los "
    "comentarios, la voz y el plan del panel local Redes IA. No publica nada en ninguna red."))


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False, indent=1, default=str)


@mcp.tool()
def puntuar_gancho(gancho: str) -> str:
    """Puntúa un gancho (primeros 2 segundos de un vídeo) de 0 a 100: longitud, concreción, tensión, lo importante
    delante y a quién habla. Devuelve nota, nivel (FUERTE/VALE/FLOJO), punto débil, fórmula y lo que lo rompe."""
    return _j(H.puntuar_gancho(gancho))


@mcp.tool()
def ranking_ganchos(ganchos: list[str]) -> str:
    """Ordena varias opciones de gancho de mejor a peor con su nota."""
    return _j(H.ranking(ganchos))


@mcp.tool()
def formulas_gancho() -> str:
    """Las 26 fórmulas de gancho en español: nombre, plantilla, ejemplo, texto en pantalla, para qué sirve y la trampa."""
    return _j([{k: f.get(k) for k in ("id", "nombre", "plantilla", "ejemplo", "en_pantalla", "para_que", "trampa")}
               for f in H.formulas()])


@mcp.tool()
def hoja_de_ritmo(guion: str, objetivo_segundos: float = 30) -> str:
    """Cronometra un guion (una frase por línea): cuándo empieza cada frase, cuánto dura y avisos (gancho largo, frases
    de más de 4 s, tramos sin nada concreto, si vuelve al principio)."""
    return _j(H.hoja_de_ritmo(guion, objetivo_s=objetivo_segundos))


@mcp.tool()
def revisar_pie(texto: str, red: str = "instagram", palabras_clave: list[str] | None = None) -> str:
    """Revisa el texto de un post (instagram) o la descripción (tiktok): lo que se ve antes de «más», hashtags,
    llamadas a la acción, longitud y palabras de búsqueda. Devuelve comprobaciones PASS/WARN/FAIL y veredicto."""
    return _j(H.revisar_pie(texto, palabras_clave or [], red=red))


@mcp.tool()
def humanizar(texto: str) -> str:
    """Limpia un texto escrito con IA: caracteres invisibles, rayas largas, muletillas típicas. Devuelve el texto,
    los cambios y las señales que conviene reescribir a mano."""
    return _j(H.humanizar(texto))


@mcp.tool()
def detectar_ia(texto: str) -> str:
    """Cinco comprobaciones locales de lo «humano» que suena un texto (0-100). Heurística, no un detector externo."""
    return _j(H.puntuar(texto))


@mcp.tool()
def ranking_viral(videos: list[dict]) -> str:
    """Ordena vídeos por cuántas veces superan la mediana de su propia cuenta y clasifica la fórmula del gancho.
    Cada vídeo: {"cuenta", "mediana" o "seguidores", "vistas", "gancho"}. Acepta «12k» o «1,2 M»."""
    return _j(H.ranking_viral(videos))


# ---------------------------------------------------------------- datos del panel local
@mcp.tool()
def ideas_recientes(estado: str = "activas", limite: int = 15) -> str:
    """Ideas de vídeo del panel (nota, gancho, por qué, cómo). estado: activas, guardada, hecha o todas."""
    from .servicios import ideas
    rows = ideas.listar("todas" if estado == "todas" else estado)[:limite]
    return _j([{k: r.get(k) for k in ("id", "tipo", "titulo", "gancho", "nota", "por_que", "como", "estado", "creada")}
               for r in rows])


@mcp.tool()
def auditoria(red: str = "") -> str:
    """Tus vídeos ordenados por múltiplo sobre tu propia mediana, con compartidos y guardados por 1.000 vistas, la
    fórmula del gancho y las conclusiones guardadas."""
    from .servicios import estudio
    a = estudio.auditoria(red or None)
    return _j({"videos": a["videos"][:40], "medianas": a["medianas"], "conclusiones": a["conclusiones"]})


@mcp.tool()
def comentarios_pendientes(categoria: str = "") -> str:
    """Comentarios de tus vídeos clasificados (cliente, pregunta, idea, queja, apoyo) con borrador de respuesta."""
    from .servicios import estudio
    return _j([{k: c.get(k) for k in ("id", "red", "autor", "texto", "categoria", "motivo", "borrador", "v_url")}
               for c in estudio.comentarios(categoria)][:60])


@mcp.tool()
def voz_del_canal() -> str:
    """La voz del canal (cómo habla el creador) y el contexto. Úsala antes de escribir guiones o respuestas."""
    from . import ajustes as A
    return _j({"voz": A.get("voz"), "contexto": A.get("contexto")})


@mcp.tool()
def plan_semanal() -> str:
    """El último plan de la semana guardado en el panel."""
    from .servicios import estudio
    return _j(estudio.plan_actual() or {"aviso": "Aún no hay plan. Créalo en el panel: Estudio → Plan de la semana."})


@mcp.tool()
def preparar_guion(idea_id: int) -> str:
    """Prepara el guion de una idea con la IA configurada en el panel: 3 ganchos puntuados, guion con tiempos, texto
    de Instagram y descripción de TikTok revisados, y lo corrige hasta 2 veces con los avisos de las herramientas."""
    from .servicios import estudio
    return _j(estudio.preparar_guion(idea_id))


def main():
    iniciar()
    mcp.run()


if __name__ == "__main__":
    main()

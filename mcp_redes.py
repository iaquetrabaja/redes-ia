"""Arranca el servidor MCP de Redes IA desde cualquier carpeta (para Claude Desktop, Claude Code o Cursor).

Uso en la configuración del cliente MCP:  <python de tu instalación> <ruta>/redes-ia/mcp_redes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from redes_ia.mcp_server import main  # noqa: E402

main()

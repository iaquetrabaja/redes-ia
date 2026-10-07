"""Redes IA: panel local de contenido para TikTok e Instagram, con tu propia clave de IA."""
import sys
from pathlib import Path

__version__ = "1.0.0"

RAIZ = Path(__file__).resolve().parent.parent
# Las herramientas de la skill viven en skills/redes/herramientas (así la skill se copia tal cual a Claude).
_SKILL = RAIZ / "skills" / "redes"
if str(_SKILL) not in sys.path:
    sys.path.insert(0, str(_SKILL))

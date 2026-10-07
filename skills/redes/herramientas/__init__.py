"""Herramientas de la skill de redes: solo librería estándar.

Cada módulo funciona como orden (python -m herramientas.X) y como funciones
que devuelven dicts listos para pasar a JSON:

    from herramientas import puntuar_gancho, hoja_de_ritmo, revisar_pie, humanizar, puntuar, ranking_viral
"""

import warnings

# «python -m herramientas.X» importa antes este paquete, que ya ha cargado X; el
# aviso de runpy por eso es inofensivo y solo ensucia la salida.
warnings.filterwarnings("ignore", category=RuntimeWarning,
                        message=r".*found in sys\.modules after import of package 'herramientas'.*")

from .detectar import puntuar  # noqa: E402
from .ganchos import clasificar_formula, formulas, puntuar_gancho, ranking  # noqa: E402
from .humanizar import humanizar  # noqa: E402
from .pie import revisar_pie  # noqa: E402
from .ritmo import hoja_de_ritmo  # noqa: E402
from .viral import ranking_viral  # noqa: E402

__all__ = ["puntuar_gancho", "clasificar_formula", "ranking", "formulas", "hoja_de_ritmo",
           "revisar_pie", "humanizar", "puntuar", "ranking_viral", "rubrica_perfil"]


def rubrica_perfil():
    """La rúbrica de perfil de 100 puntos (dict)."""
    from ._comun import cargar_json
    return cargar_json("rubrica_perfil.json")

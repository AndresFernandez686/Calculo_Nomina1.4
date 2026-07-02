"""Utilidades para manejo de dinero con ``decimal.Decimal``.

Todos los cálculos monetarios del módulo de liquidaciones usan ``Decimal``
para evitar los errores de redondeo propios de ``float``. El redondeo final
se hace con ``ROUND_HALF_UP`` a 2 decimales, salvo indicación contraria.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

CENTAVOS = Decimal("0.01")


def D(valor: Any) -> Decimal:
    """Convierte cualquier valor numérico a ``Decimal`` de forma segura.

    Se pasa por ``str`` para evitar arrastrar la imprecisión binaria de los
    ``float`` (por ejemplo ``Decimal(0.1)`` != ``Decimal("0.1")``).
    """
    if isinstance(valor, Decimal):
        return valor
    if valor is None:
        return Decimal("0")
    if isinstance(valor, float):
        return Decimal(str(valor))
    try:
        return Decimal(str(valor).strip() or "0")
    except Exception:  # pragma: no cover - entrada inválida
        return Decimal("0")


def q(valor: Any, decimales: int = 2) -> Decimal:
    """Cuantiza un valor monetario a ``decimales`` con ``ROUND_HALF_UP``."""
    cuantia = Decimal(1).scaleb(-decimales)  # 10^-decimales
    return D(valor).quantize(cuantia, rounding=ROUND_HALF_UP)


def money(valor: Any) -> Decimal:
    """Redondeo estándar a 2 decimales (guaraníes con centavos)."""
    return D(valor).quantize(CENTAVOS, rounding=ROUND_HALF_UP)

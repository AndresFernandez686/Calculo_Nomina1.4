"""Concepto de liquidación con desglose auditable y metadata legal.

Cada concepto calculado expone: ``nombre``, ``monto`` (``Decimal``),
``articulo_legal``, ``detalle_calculo`` (paso a paso), ``aplica`` y
``motivo_no_aplicacion``. La bandera ``remunerativo`` indica si el concepto
está sujeto al aporte IPS del 9%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .montos import money


@dataclass
class Concepto:
    """Un concepto de la liquidación (salario pendiente, aguinaldo, etc.)."""

    nombre: str
    articulo_legal: str
    monto: Decimal = Decimal("0")
    detalle_calculo: list[str] = field(default_factory=list)
    aplica: bool = True
    motivo_no_aplicacion: str | None = None
    remunerativo: bool = False

    def __post_init__(self) -> None:
        self.monto = money(self.monto)
        if not self.aplica:
            self.monto = Decimal("0.00")

    @classmethod
    def no_aplica(
        cls,
        nombre: str,
        articulo_legal: str,
        motivo: str,
        *,
        remunerativo: bool = False,
    ) -> "Concepto":
        """Construye un concepto que no aplica, documentando el motivo legal."""
        return cls(
            nombre=nombre,
            articulo_legal=articulo_legal,
            monto=Decimal("0.00"),
            detalle_calculo=[f"No aplica — {motivo}"],
            aplica=False,
            motivo_no_aplicacion=motivo,
            remunerativo=remunerativo,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa el concepto a un diccionario apto para JSON."""
        return {
            "nombre": self.nombre,
            "monto": str(self.monto),
            "monto_float": float(self.monto),
            "articulo_legal": self.articulo_legal,
            "detalle_calculo": list(self.detalle_calculo),
            "aplica": self.aplica,
            "motivo_no_aplicacion": self.motivo_no_aplicacion,
            "remunerativo": self.remunerativo,
        }

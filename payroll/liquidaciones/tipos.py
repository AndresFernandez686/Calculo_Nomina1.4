"""Tipos de liquidación (herencia + polimorfismo).

:class:`LiquidacionBase` define el algoritmo común (plantilla): calcula los
conceptos declarados por cada subclase, aplica el aporte IPS sobre los
remunerativos y arma un resultado auditable. Cada subclase declara, mediante
polimorfismo, qué conceptos la componen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .concepto import Concepto
from .conceptos import (
    CalculadorAguinaldo,
    CalculadorAporteIPS,
    CalculadorConcepto,
    CalculadorDescuentoFaltaPreaviso,
    CalculadorIndemnizacion,
    CalculadorPreaviso,
    CalculadorSalarioPendiente,
    CalculadorVacaciones,
)
from .contexto import ContextoLiquidacion
from .montos import money


@dataclass
class ResultadoLiquidacion:
    """Resultado auditable de una liquidación."""

    tipo: str
    articulo_legal: str
    conceptos: list[Concepto] = field(default_factory=list)
    aporte_patronal: Concepto | None = None

    @property
    def total_neto(self) -> Decimal:
        return money(sum((c.monto for c in self.conceptos if c.aplica), Decimal("0")))

    @property
    def total_remunerativo(self) -> Decimal:
        return money(
            sum(
                (c.monto for c in self.conceptos if c.aplica and c.remunerativo),
                Decimal("0"),
            )
        )

    def concepto(self, nombre: str) -> Concepto | None:
        return next((c for c in self.conceptos if c.nombre == nombre), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "articulo_legal": self.articulo_legal,
            "conceptos": [c.to_dict() for c in self.conceptos],
            "aporte_patronal": self.aporte_patronal.to_dict() if self.aporte_patronal else None,
            "total_neto": str(self.total_neto),
            "total_neto_float": float(self.total_neto),
        }


class LiquidacionBase(ABC):
    """Plantilla de cálculo común a todos los tipos de liquidación."""

    tipo: str = "base"
    articulo_legal: str = "Código del Trabajo de Paraguay"

    def __init__(self, contexto: ContextoLiquidacion) -> None:
        self.contexto = contexto

    @abstractmethod
    def calculadores(self) -> list[CalculadorConcepto]:
        """Conceptos que componen este tipo de liquidación (polimorfismo)."""
        raise NotImplementedError

    def calcular(self) -> ResultadoLiquidacion:
        conceptos = [calc.calcular(self.contexto) for calc in self.calculadores()]

        ips = CalculadorAporteIPS()
        conceptos.append(ips.calcular_sobre(self.contexto, conceptos))
        patronal = ips.aporte_patronal(self.contexto, conceptos)

        return ResultadoLiquidacion(
            tipo=self.tipo,
            articulo_legal=self.articulo_legal,
            conceptos=conceptos,
            aporte_patronal=patronal,
        )


class RenunciaVoluntaria(LiquidacionBase):
    tipo = "renuncia-voluntaria"
    articulo_legal = "Arts. 234 y 243 CT"

    def calculadores(self) -> list[CalculadorConcepto]:
        return [
            CalculadorSalarioPendiente(),
            CalculadorAguinaldo(),
            CalculadorVacaciones(),
        ]


class DespidoSinCausa(LiquidacionBase):
    tipo = "despido-sin-causa"
    articulo_legal = "Arts. 87, 91 y 243 CT"

    def calculadores(self) -> list[CalculadorConcepto]:
        return [
            CalculadorSalarioPendiente(),
            CalculadorAguinaldo(),
            CalculadorVacaciones(),
            CalculadorPreaviso(),
            CalculadorIndemnizacion(),
        ]


class DespidoConCausa(LiquidacionBase):
    tipo = "despido-con-causa"
    articulo_legal = "Arts. 81 y 243 CT"

    def calculadores(self) -> list[CalculadorConcepto]:
        return [
            CalculadorSalarioPendiente(),
            CalculadorAguinaldo(),
            CalculadorVacaciones(),
        ]


class AbandonoTrabajo(LiquidacionBase):
    tipo = "abandono-trabajo"
    articulo_legal = "Arts. 87 y 243 CT"

    def calculadores(self) -> list[CalculadorConcepto]:
        return [
            CalculadorSalarioPendiente(),
            CalculadorAguinaldo(),
            CalculadorVacaciones(),
            CalculadorDescuentoFaltaPreaviso(),
        ]


class MutuoAcuerdo(LiquidacionBase):
    tipo = "mutuo-acuerdo"
    articulo_legal = "Art. 78 CT"

    def calculadores(self) -> list[CalculadorConcepto]:
        return [
            CalculadorSalarioPendiente(),
            CalculadorAguinaldo(),
            CalculadorVacaciones(),
        ]

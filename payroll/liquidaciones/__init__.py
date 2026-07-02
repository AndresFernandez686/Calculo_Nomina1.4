"""Módulo de liquidaciones laborales (Paraguay, Código del Trabajo).

Arquitectura POO con desglose auditable, metadata legal por concepto y
manejo monetario con ``decimal.Decimal`` (ROUND_HALF_UP, 2 decimales).

Uso típico::

    from payroll.liquidaciones import (
        ContextoLiquidacion, RegistroDiario, ParametrosLegales, crear_liquidacion,
    )

    contexto = ContextoLiquidacion(
        fecha_ingreso=date(2020, 1, 1),
        fecha_salida=date(2026, 6, 30),
        registros=[RegistroDiario(...), ...],
        calificacion="no_calificado",
        vacaciones_usadas_dias=0,
    )
    resultado = crear_liquidacion("despido-sin-causa", contexto).calcular()
    print(resultado.to_dict())
"""

from .concepto import Concepto
from .conceptos import (
    CalculadorAguinaldo,
    CalculadorAporteIPS,
    CalculadorDescuentoFaltaPreaviso,
    CalculadorIndemnizacion,
    CalculadorPreaviso,
    CalculadorSalarioPendiente,
    CalculadorVacaciones,
)
from .contexto import ContextoLiquidacion, RegistroDiario
from .factory import (
    crear_liquidacion,
    normalizar_tipo,
    tipos_disponibles,
)
from .montos import D, money, q
from .parametros_legales import ParametrosLegales, TramoEscala
from .tipos import (
    AbandonoTrabajo,
    DespidoConCausa,
    DespidoSinCausa,
    LiquidacionBase,
    MutuoAcuerdo,
    RenunciaVoluntaria,
    ResultadoLiquidacion,
)

__all__ = [
    "Concepto",
    "ContextoLiquidacion",
    "RegistroDiario",
    "ParametrosLegales",
    "TramoEscala",
    "ResultadoLiquidacion",
    "LiquidacionBase",
    "RenunciaVoluntaria",
    "DespidoSinCausa",
    "DespidoConCausa",
    "AbandonoTrabajo",
    "MutuoAcuerdo",
    "crear_liquidacion",
    "normalizar_tipo",
    "tipos_disponibles",
    "CalculadorSalarioPendiente",
    "CalculadorAguinaldo",
    "CalculadorVacaciones",
    "CalculadorPreaviso",
    "CalculadorIndemnizacion",
    "CalculadorDescuentoFaltaPreaviso",
    "CalculadorAporteIPS",
    "D",
    "money",
    "q",
]

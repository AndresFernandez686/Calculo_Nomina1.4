"""Contexto de entrada para el cálculo de una liquidación.

Reúne los datos del trabajador y su historial de jornadas, y expone los
cálculos derivados reutilizados por los conceptos: promedio de los últimos
6 meses (art. 92 inc. b CT), total devengado en el año calendario
(art. 243 CT), antigüedad y período de prueba (art. 58 CT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .montos import D, money
from .parametros_legales import ParametrosLegales


@dataclass
class RegistroDiario:
    """Una jornada trabajada del historial del empleado (jornalero)."""

    fecha: date
    horas_normales: Decimal = Decimal("0")
    horas_especiales: Decimal = Decimal("0")  # recargo +30%
    horas_feriado: Decimal = Decimal("0")  # recargo x2
    valor_hora: Decimal = Decimal("0")
    bonificacion: Decimal = Decimal("0")  # remunerativa (comisiones, extras)
    remunerativo: bool = True

    def __post_init__(self) -> None:
        self.horas_normales = D(self.horas_normales)
        self.horas_especiales = D(self.horas_especiales)
        self.horas_feriado = D(self.horas_feriado)
        self.valor_hora = D(self.valor_hora)
        self.bonificacion = D(self.bonificacion)

    def monto(self, parametros: ParametrosLegales) -> Decimal:
        """Monto remunerativo devengado en la jornada (jornalero).

        (h_normales × valor) + (h_especiales × valor × 1.3)
        + (h_feriado × valor × 2) + bonificación
        """
        normal = self.horas_normales * self.valor_hora
        especial = self.horas_especiales * self.valor_hora * parametros.multiplicador_hora_especial
        feriado = self.horas_feriado * self.valor_hora * parametros.multiplicador_feriado
        return money(normal + especial + feriado + self.bonificacion)


def _restar_meses(referencia: date, meses: int) -> date:
    """Devuelve la fecha ``meses`` antes de ``referencia`` (día 1 del mes)."""
    total = referencia.year * 12 + (referencia.month - 1) - meses
    anio, mes = divmod(total, 12)
    return date(anio, mes + 1, 1)


@dataclass
class ContextoLiquidacion:
    """Todos los datos necesarios para calcular una liquidación."""

    fecha_ingreso: date
    fecha_salida: date
    registros: list[RegistroDiario] = field(default_factory=list)
    calificacion: str = "no_calificado"
    vacaciones_usadas_dias: Decimal = Decimal("0")
    parametros: ParametrosLegales = field(default_factory=ParametrosLegales)

    def __post_init__(self) -> None:
        self.vacaciones_usadas_dias = D(self.vacaciones_usadas_dias)
        self.registros = sorted(self.registros, key=lambda r: r.fecha)

    # ------------------------------------------------------------------ #
    # Antigüedad y período de prueba
    # ------------------------------------------------------------------ #
    @property
    def antiguedad_dias(self) -> int:
        return max((self.fecha_salida - self.fecha_ingreso).days, 0)

    @property
    def antiguedad_anios_completos(self) -> int:
        return self.antiguedad_dias // 365

    @property
    def antiguedad_meses(self) -> Decimal:
        return D(self.antiguedad_dias) / D("30")

    def anios_indemnizables(self) -> int:
        """Años de servicio para indemnización: fracción > 6 meses = 1 año."""
        dias = self.antiguedad_dias
        anios = dias // 365
        resto_dias = dias % 365
        resto_meses = D(resto_dias) / D("30")
        if resto_meses > D(self.parametros.fraccion_anio_indemnizable_meses):
            anios += 1
        return max(anios, 0)

    @property
    def periodo_prueba_dias(self) -> int:
        return self.parametros.periodo_prueba_dias(self.calificacion)

    def supero_periodo_prueba(self) -> bool:
        return self.antiguedad_dias > self.periodo_prueba_dias

    def tiene_estabilidad(self) -> bool:
        """Estabilidad laboral (art. 94 CT): antigüedad ≥ 10 años."""
        return self.antiguedad_anios_completos >= self.parametros.anios_estabilidad

    # ------------------------------------------------------------------ #
    # Promedios y devengados
    # ------------------------------------------------------------------ #
    def registros_ultimos_meses(self, meses: int) -> list[RegistroDiario]:
        desde = _restar_meses(self.fecha_salida.replace(day=1), meses - 1)
        return [
            r for r in self.registros
            if r.remunerativo and desde <= r.fecha <= self.fecha_salida
        ]

    def promedio_diario_6meses(self) -> tuple[Decimal, dict]:
        """Salario diario promedio de los últimos 6 meses (art. 92 inc. b).

        promedio_mensual = total_devengado_6m / meses_con_datos
        valor_dia = promedio_mensual / 30
        """
        meses = self.parametros.meses_promedio
        regs = self.registros_ultimos_meses(meses)
        total = sum((r.monto(self.parametros) for r in regs), Decimal("0"))
        claves_mes = {(r.fecha.year, r.fecha.month) for r in regs}
        meses_con_datos = max(len(claves_mes), 1)
        promedio_mensual = D(total) / D(meses_con_datos)
        valor_dia = money(promedio_mensual / self.parametros.dias_mes)
        auditoria = {
            "meses_considerados": meses,
            "meses_con_datos": meses_con_datos,
            "total_devengado": money(total),
            "promedio_mensual": money(promedio_mensual),
            "valor_dia": valor_dia,
        }
        return valor_dia, auditoria

    def devengado_anual(self) -> tuple[Decimal, dict]:
        """Total devengado en el año calendario (art. 243 CT).

        Desde el 01/01 (o desde la fecha de ingreso si es posterior) hasta la
        fecha de salida.
        """
        inicio_anio = date(self.fecha_salida.year, 1, 1)
        desde = max(inicio_anio, self.fecha_ingreso)
        regs = [r for r in self.registros if r.remunerativo and desde <= r.fecha <= self.fecha_salida]
        total = sum((r.monto(self.parametros) for r in regs), Decimal("0"))
        auditoria = {
            "desde": desde.isoformat(),
            "hasta": self.fecha_salida.isoformat(),
            "registros": len(regs),
            "total_devengado": money(total),
        }
        return money(total), auditoria

    def registros_pendientes(self) -> list[RegistroDiario]:
        """Jornadas del último período (mes de salida) aún no cobradas."""
        return [
            r for r in self.registros
            if r.fecha.year == self.fecha_salida.year
            and r.fecha.month == self.fecha_salida.month
            and r.fecha <= self.fecha_salida
        ]

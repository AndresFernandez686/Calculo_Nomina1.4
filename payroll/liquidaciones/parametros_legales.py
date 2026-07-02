"""Parámetros legales configurables de la liquidación (Paraguay).

Ninguna tasa, día o escala está *hardcodeada* en la lógica de cálculo: todo
se lee desde esta clase. Puede instanciarse con valores por defecto (Código
del Trabajo de Paraguay, Ley N° 213/93 y modificaciones) o sobreescribirse
desde un archivo de configuración externo mediante :meth:`desde_dict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from .montos import D


@dataclass(frozen=True)
class TramoEscala:
    """Un tramo de una escala legal por antigüedad.

    ``limite_dias`` es el límite superior (inclusive) del tramo en días de
    antigüedad. ``None`` representa "sin límite" (último tramo).
    """

    limite_dias: int | None
    valor: int
    descripcion: str


# Escala de preaviso (art. 87 CT), medida en días de antigüedad una vez
# superado el período de prueba.
_ESCALA_PREAVISO_DEFAULT: tuple[TramoEscala, ...] = (
    TramoEscala(365, 30, "Superado el período de prueba hasta 1 año"),
    TramoEscala(5 * 365, 45, "Más de 1 año hasta 5 años"),
    TramoEscala(10 * 365, 60, "Más de 5 años hasta 10 años"),
    TramoEscala(None, 90, "Más de 10 años"),
)

# Escala de vacaciones (arts. 218 y 221 CT), medida en años de antigüedad.
_ESCALA_VACACIONES_DEFAULT: tuple[TramoEscala, ...] = (
    TramoEscala(5, 12, "1 a 5 años"),
    TramoEscala(10, 18, "5 a 10 años"),
    TramoEscala(None, 30, "Más de 10 años"),
)


@dataclass(frozen=True)
class ParametrosLegales:
    """Contenedor inmutable de todos los parámetros legales del cálculo."""

    # --- Aportes IPS (Ley 98/92) ---
    aporte_ips_trabajador: Decimal = Decimal("0.09")
    aporte_ips_patronal: Decimal = Decimal("0.165")

    # --- Recargos de jornada (jornalero) ---
    multiplicador_hora_especial: Decimal = Decimal("1.30")  # +30%
    multiplicador_feriado: Decimal = Decimal("2.00")  # x2

    # --- Bases de cálculo ---
    dias_mes: Decimal = Decimal("30")
    divisor_aguinaldo: Decimal = Decimal("12")
    meses_promedio: int = 6  # promedio últimos 6 meses (art. 92 inc. b)

    # --- Indemnización (art. 91 CT) ---
    dias_indemnizacion_por_anio: Decimal = Decimal("15")
    antiguedad_minima_indemnizacion_meses: int = 6
    fraccion_anio_indemnizable_meses: int = 6  # fracción > 6 meses = 1 año

    # --- Estabilidad laboral (art. 94 CT) ---
    anios_estabilidad: int = 10
    dias_indemnizacion_estabilidad_por_anio: Decimal = Decimal("30")

    # --- Período de prueba (art. 58 CT) ---
    periodo_prueba_no_calificado_dias: int = 30
    periodo_prueba_calificado_dias: int = 60
    periodo_prueba_alta_direccion_dias: int = 180

    # --- Abandono de trabajo (art. 87 CT) ---
    # Descuento al trabajador por falta de preaviso: mitad del preaviso legal.
    fraccion_descuento_preaviso_trabajador: Decimal = Decimal("0.5")

    # --- Redondeo ---
    decimales: int = 2

    # --- Escalas ---
    escala_preaviso: tuple[TramoEscala, ...] = _ESCALA_PREAVISO_DEFAULT
    escala_vacaciones: tuple[TramoEscala, ...] = _ESCALA_VACACIONES_DEFAULT

    # ------------------------------------------------------------------ #
    # Métodos de consulta de escalas
    # ------------------------------------------------------------------ #
    def dias_preaviso(self, antiguedad_dias: int) -> tuple[int, str]:
        """Días de preaviso y descripción del tramo según antigüedad."""
        for tramo in self.escala_preaviso:
            if tramo.limite_dias is None or antiguedad_dias <= tramo.limite_dias:
                return tramo.valor, tramo.descripcion
        ultimo = self.escala_preaviso[-1]
        return ultimo.valor, ultimo.descripcion

    def dias_vacaciones_anuales(self, antiguedad_anios: int) -> tuple[int, str]:
        """Días hábiles de vacaciones por año y descripción según antigüedad."""
        for tramo in self.escala_vacaciones:
            if tramo.limite_dias is None or antiguedad_anios <= tramo.limite_dias:
                return tramo.valor, tramo.descripcion
        ultimo = self.escala_vacaciones[-1]
        return ultimo.valor, ultimo.descripcion

    def periodo_prueba_dias(self, calificacion: str) -> int:
        """Duración del período de prueba según la calificación del trabajador."""
        mapa = {
            "no_calificado": self.periodo_prueba_no_calificado_dias,
            "calificado": self.periodo_prueba_calificado_dias,
            "tecnico": self.periodo_prueba_calificado_dias,
            "alta_direccion": self.periodo_prueba_alta_direccion_dias,
            "gerencia": self.periodo_prueba_alta_direccion_dias,
        }
        return mapa.get(calificacion, self.periodo_prueba_no_calificado_dias)

    # ------------------------------------------------------------------ #
    # Fábrica desde configuración externa
    # ------------------------------------------------------------------ #
    @classmethod
    def desde_dict(cls, datos: dict[str, Any] | None) -> "ParametrosLegales":
        """Crea parámetros a partir de un diccionario de configuración.

        Solo se sobreescriben las claves presentes; el resto usa el default
        legal. Los porcentajes y montos se convierten a ``Decimal``.
        """
        base = cls()
        if not datos:
            return base

        campos_decimal = {
            "aporte_ips_trabajador",
            "aporte_ips_patronal",
            "multiplicador_hora_especial",
            "multiplicador_feriado",
            "dias_mes",
            "divisor_aguinaldo",
            "dias_indemnizacion_por_anio",
            "dias_indemnizacion_estabilidad_por_anio",
            "fraccion_descuento_preaviso_trabajador",
        }
        cambios: dict[str, Any] = {}
        for clave, valor in datos.items():
            if not hasattr(base, clave):
                continue
            cambios[clave] = D(valor) if clave in campos_decimal else valor
        return replace(base, **cambios)

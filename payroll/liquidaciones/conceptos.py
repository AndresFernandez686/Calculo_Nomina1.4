"""Calculadores de conceptos de liquidación (una clase por concepto, SRP).

Cada calculador recibe el :class:`ContextoLiquidacion` y devuelve un
:class:`Concepto` con su monto (``Decimal``), artículo legal y desglose
auditable. El aporte IPS se calcula aparte, sobre los conceptos remunerativos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .concepto import Concepto
from .contexto import ContextoLiquidacion
from .montos import D, money


class CalculadorConcepto(ABC):
    """Contrato común de todos los calculadores de concepto."""

    nombre: str = "Concepto"
    articulo_legal: str = ""

    @abstractmethod
    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        raise NotImplementedError


class CalculadorSalarioPendiente(CalculadorConcepto):
    """Salario devengado y no cobrado del último período (jornalero)."""

    nombre = "Salario pendiente"
    articulo_legal = "Arts. 227 y 231 CT"

    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        params = contexto.parametros
        registros = contexto.registros_pendientes()
        if not registros:
            return Concepto.no_aplica(
                self.nombre,
                self.articulo_legal,
                "no hay jornadas pendientes en el período de salida",
                remunerativo=True,
            )

        detalle: list[str] = []
        total = Decimal("0")
        horas_n = horas_e = horas_f = Decimal("0")
        for r in registros:
            monto = r.monto(params)
            total += monto
            horas_n += r.horas_normales
            horas_e += r.horas_especiales
            horas_f += r.horas_feriado

        detalle.append(f"Jornadas pendientes: {len(registros)}")
        detalle.append(
            f"Horas normales {horas_n} × valor hora = "
            f"{money(horas_n * (registros[0].valor_hora if registros else 0))}"
        )
        detalle.append(
            f"Horas especiales {horas_e} × valor hora × {params.multiplicador_hora_especial} (+30%)"
        )
        detalle.append(
            f"Horas feriado {horas_f} × valor hora × {params.multiplicador_feriado} (x2)"
        )
        detalle.append(f"Total salario pendiente = {money(total)}")
        return Concepto(
            nombre=self.nombre,
            articulo_legal=self.articulo_legal,
            monto=money(total),
            detalle_calculo=detalle,
            remunerativo=True,
        )


class CalculadorAguinaldo(CalculadorConcepto):
    """Aguinaldo proporcional: total devengado en el año / 12 (art. 243 CT)."""

    nombre = "Aguinaldo proporcional"
    articulo_legal = "Art. 243 CT"

    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        params = contexto.parametros
        total_anual, aud = contexto.devengado_anual()
        monto = money(total_anual / params.divisor_aguinaldo)
        detalle = [
            f"Devengado del {aud['desde']} al {aud['hasta']} = {aud['total_devengado']}",
            f"Aguinaldo = {aud['total_devengado']} / {params.divisor_aguinaldo} = {monto}",
        ]
        if monto <= 0:
            return Concepto.no_aplica(
                self.nombre,
                self.articulo_legal,
                "no hay salarios devengados en el año calendario",
                remunerativo=True,
            )
        return Concepto(
            nombre=self.nombre,
            articulo_legal=self.articulo_legal,
            monto=monto,
            detalle_calculo=detalle,
            remunerativo=True,
        )


class CalculadorVacaciones(CalculadorConcepto):
    """Vacaciones no gozadas (arts. 218 y 221 CT), base art. 92 inc. b."""

    nombre = "Vacaciones no gozadas"
    articulo_legal = "Arts. 218 y 221 CT"

    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        params = contexto.parametros
        anios = contexto.antiguedad_anios_completos
        dias_anuales, tramo = params.dias_vacaciones_anuales(max(anios, 1))
        valor_dia, aud_prom = contexto.promedio_diario_6meses()

        # Proporcional: (días_del_año × meses_trabajados_en_período) / 12
        meses_periodo = min(D(contexto.antiguedad_dias) / params.dias_mes, D("12"))
        dias_generados = D(dias_anuales) * meses_periodo / params.divisor_aguinaldo
        dias_pendientes = dias_generados - contexto.vacaciones_usadas_dias
        if dias_pendientes < 0:
            dias_pendientes = Decimal("0")

        monto = money(dias_pendientes * valor_dia)
        detalle = [
            f"Antigüedad: {anios} años ({tramo}) → {dias_anuales} días/año",
            f"Proporcional = {dias_anuales} × {money(meses_periodo)} meses / 12 = {money(dias_generados)} días",
            f"Días usados: {money(contexto.vacaciones_usadas_dias)}",
            f"Días pendientes: {money(dias_pendientes)}",
            f"Valor día (promedio 6m / 30) = {valor_dia}",
            f"Monto = {money(dias_pendientes)} × {valor_dia} = {monto}",
        ]
        if dias_pendientes <= 0:
            return Concepto.no_aplica(
                self.nombre,
                self.articulo_legal,
                "no hay días de vacaciones pendientes",
                remunerativo=True,
            )
        return Concepto(
            nombre=self.nombre,
            articulo_legal=self.articulo_legal,
            monto=monto,
            detalle_calculo=detalle,
            remunerativo=True,
        )


class CalculadorPreaviso(CalculadorConcepto):
    """Preaviso (art. 87 CT). Solo si se superó el período de prueba."""

    nombre = "Preaviso"
    articulo_legal = "Art. 87 CT"

    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        params = contexto.parametros
        if not contexto.supero_periodo_prueba():
            return Concepto.no_aplica(
                self.nombre,
                "Arts. 87 y 58 CT",
                f"no se superó el período de prueba ({contexto.periodo_prueba_dias} días)",
            )

        dias, tramo = params.dias_preaviso(contexto.antiguedad_dias)
        valor_dia, _ = contexto.promedio_diario_6meses()
        monto = money(D(dias) * valor_dia)
        detalle = [
            f"Antigüedad: {contexto.antiguedad_dias} días ({tramo}) → {dias} días de preaviso",
            f"Valor día (promedio 6m / 30) = {valor_dia}",
            f"Monto = {dias} × {valor_dia} = {monto}",
        ]
        return Concepto(
            nombre=self.nombre,
            articulo_legal=self.articulo_legal,
            monto=monto,
            detalle_calculo=detalle,
            remunerativo=False,  # indemnizatorio: no aporta IPS
        )


class CalculadorIndemnizacion(CalculadorConcepto):
    """Indemnización por despido injustificado (art. 91 CT) y estabilidad (art. 94)."""

    nombre = "Indemnización por despido"
    articulo_legal = "Art. 91 CT"

    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        params = contexto.parametros
        if contexto.antiguedad_meses <= D(params.antiguedad_minima_indemnizacion_meses):
            return Concepto.no_aplica(
                self.nombre,
                self.articulo_legal,
                f"antigüedad ≤ {params.antiguedad_minima_indemnizacion_meses} meses, art. 91 CT",
            )

        anios = contexto.anios_indemnizables()
        valor_dia, _ = contexto.promedio_diario_6meses()

        estabilidad = contexto.tiene_estabilidad()
        if estabilidad:
            dias_por_anio = params.dias_indemnizacion_estabilidad_por_anio
            articulo = "Art. 94 CT (estabilidad laboral)"
        else:
            dias_por_anio = params.dias_indemnizacion_por_anio
            articulo = "Art. 91 CT"

        dias_totales = dias_por_anio * D(anios)
        monto = money(dias_totales * valor_dia)
        detalle = [
            f"Años de servicio (fracción > {params.fraccion_anio_indemnizable_meses} meses = 1 año): {anios}",
            f"Días por año: {dias_por_anio}"
            + (" (doble por estabilidad ≥ 10 años, art. 94 CT)" if estabilidad else ""),
            f"Días totales = {dias_por_anio} × {anios} = {dias_totales}",
            f"Valor día (promedio 6m / 30) = {valor_dia}",
            f"Monto = {dias_totales} × {valor_dia} = {monto}",
        ]
        return Concepto(
            nombre=self.nombre,
            articulo_legal=articulo,
            monto=monto,
            detalle_calculo=detalle,
            remunerativo=False,  # indemnizatorio: no aporta IPS
        )


class CalculadorDescuentoFaltaPreaviso(CalculadorConcepto):
    """Descuento al trabajador por falta de preaviso (abandono, art. 87 CT).

    Equivale a la mitad del preaviso que le habría correspondido. Se expresa
    como un concepto de monto negativo (descuento).
    """

    nombre = "Descuento por falta de preaviso del trabajador"
    articulo_legal = "Art. 87 CT"

    def calcular(self, contexto: ContextoLiquidacion) -> Concepto:
        params = contexto.parametros
        if not contexto.supero_periodo_prueba():
            return Concepto.no_aplica(
                self.nombre,
                "Arts. 87 y 58 CT",
                "no se superó el período de prueba, no corresponde descuento",
            )
        dias, _ = params.dias_preaviso(contexto.antiguedad_dias)
        valor_dia, _ = contexto.promedio_diario_6meses()
        dias_descuento = D(dias) * params.fraccion_descuento_preaviso_trabajador
        monto = money(dias_descuento * valor_dia)
        detalle = [
            f"Preaviso omitido por el trabajador: {dias} días",
            f"Descuento = {params.fraccion_descuento_preaviso_trabajador} × {dias} días = {dias_descuento} días",
            f"Monto descontado = {dias_descuento} × {valor_dia} = -{monto}",
        ]
        return Concepto(
            nombre=self.nombre,
            articulo_legal=self.articulo_legal,
            monto=-monto,
            detalle_calculo=detalle,
            remunerativo=False,
        )


class CalculadorAporteIPS:
    """Aporte IPS del trabajador (9%) sobre conceptos remunerativos (Ley 98/92)."""

    nombre = "Aporte IPS trabajador (9%)"
    articulo_legal = "Ley 98/92"

    def calcular_sobre(
        self, contexto: ContextoLiquidacion, conceptos: list[Concepto]
    ) -> Concepto:
        params = contexto.parametros
        base = sum(
            (c.monto for c in conceptos if c.aplica and c.remunerativo),
            Decimal("0"),
        )
        monto = money(D(base) * params.aporte_ips_trabajador)
        nombres = [c.nombre for c in conceptos if c.aplica and c.remunerativo]
        detalle = [
            f"Base remunerativa (IPS): {', '.join(nombres) or 'ninguno'} = {money(base)}",
            f"Aporte trabajador = {money(base)} × {params.aporte_ips_trabajador} = -{monto}",
            "Preaviso e indemnización NO integran la base (son indemnizatorios).",
        ]
        if monto <= 0:
            return Concepto.no_aplica(
                self.nombre,
                self.articulo_legal,
                "no hay conceptos remunerativos sujetos a aporte",
            )
        return Concepto(
            nombre=self.nombre,
            articulo_legal=self.articulo_legal,
            monto=-monto,
            detalle_calculo=detalle,
            remunerativo=False,
        )

    def aporte_patronal(
        self, contexto: ContextoLiquidacion, conceptos: list[Concepto]
    ) -> Concepto:
        """Aporte patronal (16,5%), informativo (no descuenta al trabajador)."""
        params = contexto.parametros
        base = sum(
            (c.monto for c in conceptos if c.aplica and c.remunerativo),
            Decimal("0"),
        )
        monto = money(D(base) * params.aporte_ips_patronal)
        return Concepto(
            nombre="Aporte IPS patronal (16,5%)",
            articulo_legal="Ley 98/92",
            monto=monto,
            detalle_calculo=[
                f"Base remunerativa = {money(base)}",
                f"Aporte patronal = {money(base)} × {params.aporte_ips_patronal} = {monto}",
            ],
            aplica=monto > 0,
            remunerativo=False,
        )

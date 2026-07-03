"""Tests unitarios del módulo de liquidaciones (Paraguay).

Cubre cada concepto y cada tipo de liquidación, verificando montos con
``Decimal``, aplicación/no aplicación de conceptos y metadata legal.

Ejecutar con:  pytest -q
"""

from datetime import date
from decimal import Decimal

import pytest

from payroll.liquidaciones import (
    AbandonoTrabajo,
    ContextoLiquidacion,
    DespidoConCausa,
    DespidoSinCausa,
    MutuoAcuerdo,
    ParametrosLegales,
    RegistroDiario,
    RenunciaVoluntaria,
    crear_liquidacion,
    normalizar_tipo,
)
from payroll.liquidaciones.conceptos import (
    CalculadorAguinaldo,
    CalculadorIndemnizacion,
    CalculadorPreaviso,
    CalculadorSalarioPendiente,
    CalculadorVacaciones,
)

VALOR_HORA = Decimal("10000")


def _registros_mensuales(
    inicio: date,
    fin: date,
    horas_por_dia: Decimal = Decimal("8"),
    valor_hora: Decimal = VALOR_HORA,
    dias_por_mes: int = 22,
):
    """Genera registros: ``dias_por_mes`` jornadas por mes entre dos fechas."""
    registros: list[RegistroDiario] = []
    anio, mes = inicio.year, inicio.month
    while (anio, mes) <= (fin.year, fin.month):
        for dia in range(1, dias_por_mes + 1):
            try:
                f = date(anio, mes, dia)
            except ValueError:
                continue
            if f > fin:
                break
            registros.append(
                RegistroDiario(
                    fecha=f,
                    horas_normales=horas_por_dia,
                    valor_hora=valor_hora,
                )
            )
        mes += 1
        if mes > 12:
            mes = 1
            anio += 1
    return registros


@pytest.fixture
def contexto_5anios():
    ingreso = date(2021, 1, 1)
    salida = date(2026, 6, 30)
    registros = _registros_mensuales(date(2025, 7, 1), salida)
    return ContextoLiquidacion(
        fecha_ingreso=ingreso,
        fecha_salida=salida,
        registros=registros,
        calificacion="no_calificado",
        vacaciones_usadas_dias=Decimal("0"),
    )


# --------------------------------------------------------------------------- #
# Parámetros / configuración
# --------------------------------------------------------------------------- #
def test_parametros_desde_dict_sobreescribe_solo_lo_indicado():
    params = ParametrosLegales.desde_dict({"aporte_ips_trabajador": "0.10"})
    assert params.aporte_ips_trabajador == Decimal("0.10")
    assert params.aporte_ips_patronal == Decimal("0.165")  # default intacto


def test_escala_preaviso():
    p = ParametrosLegales()
    assert p.dias_preaviso(300)[0] == 30
    assert p.dias_preaviso(2 * 365)[0] == 45
    assert p.dias_preaviso(7 * 365)[0] == 60
    assert p.dias_preaviso(11 * 365)[0] == 90


def test_escala_vacaciones():
    p = ParametrosLegales()
    assert p.dias_vacaciones_anuales(3)[0] == 12
    assert p.dias_vacaciones_anuales(8)[0] == 18
    assert p.dias_vacaciones_anuales(15)[0] == 30


# --------------------------------------------------------------------------- #
# Conceptos individuales
# --------------------------------------------------------------------------- #
def test_salario_pendiente_usa_formula_jornalero():
    salida = date(2026, 6, 15)
    registros = [
        RegistroDiario(date(2026, 6, 10), horas_normales=Decimal("8"), valor_hora=VALOR_HORA),
        RegistroDiario(date(2026, 6, 11), horas_especiales=Decimal("2"), valor_hora=VALOR_HORA),
        RegistroDiario(date(2026, 6, 12), horas_feriado=Decimal("8"), valor_hora=VALOR_HORA),
    ]
    ctx = ContextoLiquidacion(date(2020, 1, 1), salida, registros)
    concepto = CalculadorSalarioPendiente().calcular(ctx)
    # 8*10000 + 2*10000*1.3 + 8*10000*2 = 80000 + 26000 + 160000 = 266000
    assert concepto.monto == Decimal("266000.00")
    assert concepto.aplica is True
    assert concepto.remunerativo is True


def test_aguinaldo_toma_todo_el_ano_no_solo_ultimo_mes():
    salida = date(2026, 6, 30)
    registros = _registros_mensuales(date(2026, 1, 1), salida)
    ctx = ContextoLiquidacion(date(2020, 1, 1), salida, registros)
    concepto = CalculadorAguinaldo().calcular(ctx)
    total_anual, _ = ctx.devengado_anual()
    assert concepto.monto == (total_anual / Decimal("12")).quantize(Decimal("0.01"))
    assert concepto.articulo_legal == "Art. 243 CT"


def test_preaviso_no_aplica_en_periodo_de_prueba():
    salida = date(2026, 1, 20)
    ctx = ContextoLiquidacion(date(2026, 1, 1), salida, [])  # 19 días
    concepto = CalculadorPreaviso().calcular(ctx)
    assert concepto.aplica is False
    assert concepto.monto == Decimal("0.00")
    assert concepto.motivo_no_aplicacion is not None
    assert "período de prueba" in concepto.motivo_no_aplicacion


def test_indemnizacion_no_aplica_si_antiguedad_menor_6_meses():
    salida = date(2026, 5, 1)
    ctx = ContextoLiquidacion(date(2026, 1, 1), salida, [])  # 4 meses
    concepto = CalculadorIndemnizacion().calcular(ctx)
    assert concepto.aplica is False
    assert concepto.motivo_no_aplicacion is not None
    assert "art. 91" in concepto.motivo_no_aplicacion.lower()


def test_indemnizacion_estabilidad_doble_10_anios(contexto_5anios):
    ingreso = date(2010, 1, 1)
    salida = date(2026, 6, 30)  # 16 años
    registros = _registros_mensuales(date(2025, 7, 1), salida)
    ctx = ContextoLiquidacion(ingreso, salida, registros)
    concepto = CalculadorIndemnizacion().calcular(ctx)
    assert "94" in concepto.articulo_legal
    valor_dia, _ = ctx.promedio_diario_6meses()
    anios = ctx.anios_indemnizables()
    esperado = (Decimal("30") * anios * valor_dia).quantize(Decimal("0.01"))
    assert concepto.monto == esperado


def test_vacaciones_resta_dias_usados():
    ingreso = date(2023, 1, 1)
    salida = date(2026, 6, 30)
    registros = _registros_mensuales(date(2025, 7, 1), salida)
    ctx = ContextoLiquidacion(ingreso, salida, registros, vacaciones_usadas_dias=Decimal("5"))
    concepto = CalculadorVacaciones().calcular(ctx)
    assert concepto.aplica is True
    assert any("Días usados" in linea for linea in concepto.detalle_calculo)


# --------------------------------------------------------------------------- #
# Tipos de liquidación (polimorfismo)
# --------------------------------------------------------------------------- #
def test_renuncia_no_incluye_preaviso_ni_indemnizacion(contexto_5anios):
    resultado = RenunciaVoluntaria(contexto_5anios).calcular()
    nombres = [c.nombre for c in resultado.conceptos]
    assert "Preaviso" not in nombres
    assert "Indemnización por despido" not in nombres
    assert any("IPS" in n for n in nombres)


def test_despido_sin_causa_incluye_preaviso_e_indemnizacion(contexto_5anios):
    resultado = DespidoSinCausa(contexto_5anios).calcular()
    nombres = [c.nombre for c in resultado.conceptos]
    assert "Preaviso" in nombres
    assert "Indemnización por despido" in nombres


def test_despido_con_causa_sin_preaviso_ni_indemnizacion(contexto_5anios):
    resultado = DespidoConCausa(contexto_5anios).calcular()
    nombres = [c.nombre for c in resultado.conceptos]
    assert "Preaviso" not in nombres
    assert "Indemnización por despido" not in nombres


def test_abandono_incluye_descuento_por_falta_preaviso(contexto_5anios):
    resultado = AbandonoTrabajo(contexto_5anios).calcular()
    descuento = resultado.concepto("Descuento por falta de preaviso del trabajador")
    assert descuento is not None
    assert descuento.monto < 0  # es un descuento


def test_ips_solo_sobre_conceptos_remunerativos(contexto_5anios):
    resultado = DespidoSinCausa(contexto_5anios).calcular()
    ips = next(c for c in resultado.conceptos if "IPS trabajador" in c.nombre)
    base = sum(
        c.monto for c in resultado.conceptos if c.aplica and c.remunerativo
    )
    esperado = (base * Decimal("0.09")).quantize(Decimal("0.01"))
    assert ips.monto == -esperado
    # Preaviso e indemnización NO son remunerativos
    preaviso = resultado.concepto("Preaviso")
    assert preaviso is not None
    assert preaviso.remunerativo is False


def test_total_neto_descuenta_ips(contexto_5anios):
    resultado = RenunciaVoluntaria(contexto_5anios).calcular()
    suma = sum((c.monto for c in resultado.conceptos if c.aplica), Decimal("0"))
    assert resultado.total_neto == suma.quantize(Decimal("0.01"))
    ips = next(c for c in resultado.conceptos if "IPS trabajador" in c.nombre)
    assert ips.monto <= 0


def test_todos_los_conceptos_tienen_metadata_legal(contexto_5anios):
    resultado = DespidoSinCausa(contexto_5anios).calcular()
    for c in resultado.conceptos:
        assert c.articulo_legal, f"{c.nombre} sin artículo legal"
        assert isinstance(c.monto, Decimal)
        assert c.detalle_calculo, f"{c.nombre} sin desglose auditable"


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("renuncia", "renuncia-voluntaria"),
        ("despido", "despido-sin-causa"),
        ("despido-con-causa", "despido-con-causa"),
        ("fin-de-contrato", "mutuo-acuerdo"),
        ("desconocido", "renuncia-voluntaria"),
    ],
)
def test_normalizar_tipo(entrada, esperado):
    assert normalizar_tipo(entrada) == esperado


def test_factory_crea_clase_correcta(contexto_5anios):
    assert isinstance(crear_liquidacion("despido-sin-causa", contexto_5anios), DespidoSinCausa)
    assert isinstance(crear_liquidacion("mutuo-acuerdo", contexto_5anios), MutuoAcuerdo)

"""Cálculos y consultas utilizados por la liquidación de empleados.

Este módulo no depende de la aplicación Flask ni registra rutas.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import cast

from sqlalchemy import desc, text

from payroll.configuracion import VALOR_POR_HORA_DEFAULT
from payroll.models import CalculationRun, Employee, EmployeePayroll, HistorialSalarios, Liquidacion, db
from payroll.periodos import _agrupar_registros_por_mes, _mes_es

def _parse_fecha_form(valor):
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return None


def _formatear_fecha_iso(valor: date | None) -> str:
    return valor.isoformat() if valor else ""


def _fmt_hhmm(h: float) -> str:
    """Convierte horas decimales a formato HH:MM (ej. 14.90 -> '14:54')."""
    hrs = int(h)
    mins = int(round((h - hrs) * 60))
    return f"{hrs}:{mins:02d}"


def _obtener_valor_hora_vigente(empleado_id: int, fecha: date | None = None) -> float:
    """Devuelve el valor por hora vigente del historial salarial para un empleado.

    Busca el registro en ``historial_salarios`` donde:
    ``fecha_inicio <= fecha`` y ``(fecha_fin IS NULL OR fecha_fin >= fecha)``.
    Si no existe historial registrado, devuelve el valor por defecto global.
    """
    if fecha is None:
        fecha = date.today()
    fecha_str = fecha.isoformat()
    historial = (
        HistorialSalarios.query
        .filter(
            text(
                "empleado_id = :eid "
                "AND fecha_inicio <= :fs "
                "AND (fecha_fin IS NULL OR fecha_fin >= :fs)"
            ).bindparams(eid=empleado_id, fs=fecha_str)
        )
        .order_by(desc(HistorialSalarios.fecha_inicio))
        .first()
    )
    return float(historial.valor_hora) if historial else VALOR_POR_HORA_DEFAULT


def _obtener_fecha_ingreso_empleado(empleado: Employee, registros: list[EmployeePayroll]) -> date | None:
    if getattr(empleado, "hire_date", None):
        fecha = _parse_fecha_form(empleado.hire_date)
        if fecha:
            return fecha

    fechas = []
    for registro in registros:
        fecha = _parse_fecha_form(getattr(registro, "fecha", None))
        if fecha:
            fechas.append(fecha)

    if not fechas:
        return None

    fecha_ingreso = min(fechas)
    empleado.hire_date = fecha_ingreso.isoformat()
    return fecha_ingreso


def _obtener_ultimos_periodos(registros: list[EmployeePayroll], fecha_limite: date | None, cantidad: int = 6) -> list[dict]:
    meses = sorted(
        _agrupar_registros_por_mes(registros),
        key=lambda mes: (int(mes.get("year") or 0), int(mes.get("month") or 0)),
    )
    meses_filtrados = []
    for mes in meses:
        year = int(mes.get("year") or 0)
        month = int(mes.get("month") or 0)
        if not year or not month:
            continue
        if fecha_limite and (year, month) > (fecha_limite.year, fecha_limite.month):
            continue
        meses_filtrados.append(mes)

    if cantidad > 0 and len(meses_filtrados) > cantidad:
        return meses_filtrados[-cantidad:]
    return meses_filtrados


def _calcular_salario_pendiente_liquidacion(
    registros: list[EmployeePayroll],
    fecha_salida: date | None,
    ultimo_sueldo_pagado: bool = False,
) -> dict:
    """Calcula el salario pendiente con desglose auditable de horas."""
    _SIN_DATOS: dict = {
        "dias": 0, "horas": 0.0, "horas_normales": 0.0, "horas_especiales": 0.0, "horas_feriado": 0.0,
        "valor_hora": VALOR_POR_HORA_DEFAULT, "monto": 0.0, "periodo": "Sin periodo",
        "fecha_inicio": "", "fecha_fin": fecha_salida.strftime("%d/%m/%Y") if fecha_salida else "",
        "modo": "sin_datos",
    }
    if not registros or not fecha_salida:
        return _SIN_DATOS

    periodo_registros = []
    for registro in registros:
        fecha = _parse_fecha_form(getattr(registro, "fecha", None))
        if not fecha:
            continue
        if fecha.year == fecha_salida.year and fecha.month == fecha_salida.month and fecha <= fecha_salida:
            periodo_registros.append(registro)

    dias_periodo = max(int(fecha_salida.day), 1)
    if not periodo_registros:
        meses_historicos = _agrupar_registros_por_mes(registros)
        if not meses_historicos:
            return _SIN_DATOS

        ultimo_mes: dict = cast(dict, next(iter(meses_historicos)))
        periodo_registros_ultimo = list(ultimo_mes.get("registros") or [])
        if not periodo_registros_ultimo:
            return _SIN_DATOS

        run_id = next((reg.run_id for reg in periodo_registros_ultimo if reg.run_id is not None), None)
        valor_hora = VALOR_POR_HORA_DEFAULT
        if run_id is not None:
            run = CalculationRun.query.get(int(run_id))
            if run and float(run.valor_por_hora or 0) > 0:
                valor_hora = float(run.valor_por_hora)

        horas_normales_mes   = sum(float(reg.horas_normales or 0)   for reg in periodo_registros_ultimo)
        horas_especiales_mes = sum(float(reg.horas_especiales or 0) for reg in periodo_registros_ultimo)
        horas_feriado_mes    = sum(float(getattr(reg, "horas_feriado", 0) or 0) for reg in periodo_registros_ultimo)
        horas_total_mes = horas_normales_mes + horas_especiales_mes + horas_feriado_mes
        monto_mes_completo = sum(float(reg.sueldo_final or 0) for reg in periodo_registros_ultimo)
        dias_registrados_mes = max(len(periodo_registros_ultimo), 1)

        fecha_ref = _parse_fecha_form(getattr(next(iter(periodo_registros_ultimo)), "fecha", None))
        mes_ref = (
            f"{_mes_es(fecha_ref.month)} {fecha_ref.year}"
            if fecha_ref and 1 <= fecha_ref.month <= 12
            else "último mes"
        )

        if not ultimo_sueldo_pagado:
            fecha_fin_mes = (
                date(fecha_ref.year, fecha_ref.month,
                     calendar.monthrange(fecha_ref.year, fecha_ref.month)[1])
                if fecha_ref else None
            )
            return {
                "dias": dias_registrados_mes,
                "horas": round(horas_total_mes, 2),
                "horas_normales":   round(horas_normales_mes, 2),
                "horas_especiales": round(horas_especiales_mes, 2),
                "horas_feriado":    round(horas_feriado_mes, 2),
                "valor_hora": round(valor_hora, 2),
                "monto": round(monto_mes_completo, 2),
                "periodo": f"Mes completo ({mes_ref})",
                "fecha_inicio": fecha_ref.strftime("%d/%m/%Y") if fecha_ref else "",
                "fecha_fin":    fecha_fin_mes.strftime("%d/%m/%Y") if fecha_fin_mes else "",
                "modo": "mes_completo",
            }
        else:
            dias_transcurridos = max((fecha_salida - date(fecha_salida.year, fecha_salida.month, 1)).days + 1, 1)
            monto_promedio_dia    = monto_mes_completo / dias_registrados_mes
            h_n_dia = horas_normales_mes   / dias_registrados_mes
            h_e_dia = horas_especiales_mes / dias_registrados_mes
            h_f_dia = horas_feriado_mes    / dias_registrados_mes
            return {
                "dias": dias_transcurridos,
                "horas": round((horas_total_mes / dias_registrados_mes) * dias_transcurridos, 2),
                "horas_normales":   round(h_n_dia * dias_transcurridos, 2),
                "horas_especiales": round(h_e_dia * dias_transcurridos, 2),
                "horas_feriado":    round(h_f_dia * dias_transcurridos, 2),
                "valor_hora": round(valor_hora, 2),
                "monto": round(monto_promedio_dia * dias_transcurridos, 2),
                "periodo": f"Días parciales en {_mes_es(fecha_salida.month)} {fecha_salida.year} (ref. {mes_ref})",
                "fecha_inicio": date(fecha_salida.year, fecha_salida.month, 1).strftime("%d/%m/%Y"),
                "fecha_fin":    fecha_salida.strftime("%d/%m/%Y"),
                "modo": "dias_parciales",
            }

    run_id = next((reg.run_id for reg in periodo_registros if reg.run_id is not None), None)
    valor_hora = VALOR_POR_HORA_DEFAULT
    if run_id is not None:
        run = CalculationRun.query.get(int(run_id))
        if run and float(run.valor_por_hora or 0) > 0:
            valor_hora = float(run.valor_por_hora)

    fecha_periodo = _parse_fecha_form(getattr(next(iter(periodo_registros)), "fecha", None))

    horas_normales   = sum(float(reg.horas_normales or 0)   for reg in periodo_registros)
    horas_especiales = sum(float(reg.horas_especiales or 0) for reg in periodo_registros)
    horas_feriado    = sum(float(getattr(reg, "horas_feriado", 0) or 0) for reg in periodo_registros)
    horas_total = horas_normales + horas_especiales + horas_feriado
    monto = sum(float(reg.sueldo_final or 0) for reg in periodo_registros)
    return {
        "dias": min(len(periodo_registros), dias_periodo),
        "horas": round(horas_total, 2),
        "horas_normales":   round(horas_normales, 2),
        "horas_especiales": round(horas_especiales, 2),
        "horas_feriado":    round(horas_feriado, 2),
        "valor_hora": round(valor_hora, 2),
        "monto": round(monto, 2),
        "periodo": f"{fecha_periodo.strftime('%d/%m/%Y') if fecha_periodo else ''} al {fecha_salida.strftime('%d/%m/%Y')}",
        "fecha_inicio": fecha_periodo.strftime("%d/%m/%Y") if fecha_periodo else "",
        "fecha_fin":    fecha_salida.strftime("%d/%m/%Y"),
        "modo": "periodo_actual",
    }


def _calcular_aguinaldo_proporcional(
    registros: list[EmployeePayroll],
    fecha_salida: date | None,
    fecha_ingreso: date | None = None,
) -> dict:
    periodos = _obtener_ultimos_periodos(registros, fecha_salida, cantidad=6)

    # Mapa (year, month) -> total sueldo del mes
    meses_con_datos_map: dict[tuple[int, int], float] = {
        (int(mes.get("year") or 0), int(mes.get("month") or 0)): float(mes.get("total_sueldos") or 0)
        for mes in periodos
        if mes.get("year") and mes.get("month")
    }

    total_salarios = sum(meses_con_datos_map.values())
    aguinaldo = round(total_salarios / 12, 2)

    # Período considerado: desde el 01/01 del año de salida (o fecha_ingreso si es posterior)
    fecha_inicio_periodo: date | None = None
    if fecha_salida:
        inicio_anio = date(fecha_salida.year, 1, 1)
        fecha_inicio_periodo = (
            fecha_ingreso
            if fecha_ingreso and fecha_ingreso > inicio_anio
            else inicio_anio
        )

    # Lista de todos los meses del período (con o sin datos)
    detalle_meses: list[dict] = []
    if fecha_inicio_periodo and fecha_salida:
        cy, cm = fecha_inicio_periodo.year, fecha_inicio_periodo.month
        while (cy, cm) <= (fecha_salida.year, fecha_salida.month):
            monto = meses_con_datos_map.get((cy, cm))
            detalle_meses.append({
                "mes": f"{_mes_es(cm)} {cy}",
                "monto": monto,
                "tiene_datos": monto is not None,
            })
            cm += 1
            if cm > 12:
                cm = 1
                cy += 1

    meses_con_datos = len(meses_con_datos_map)
    meses_esperados = len(detalle_meses) if detalle_meses else (fecha_salida.month if fecha_salida else 12)
    meses_faltantes = sum(1 for m in detalle_meses if not m["tiene_datos"])

    periodo_texto = (
        f"{fecha_inicio_periodo.strftime('%d/%m/%Y')} al {fecha_salida.strftime('%d/%m/%Y')}"
        if fecha_inicio_periodo and fecha_salida
        else (" - ".join(m.get("mes_nombre", "") for m in periodos) or "Sin periodo")
    )

    return {
        "periodo": periodo_texto,
        "total_salarios": round(total_salarios, 2),
        "aguinaldo": aguinaldo,
        "meses_con_datos": meses_con_datos,
        "meses_esperados": meses_esperados,
        "meses_faltantes": meses_faltantes,
        "alerta_meses_incompletos": meses_faltantes > 0,
        "detalle_meses": detalle_meses,
        "fecha_inicio_periodo": fecha_inicio_periodo.strftime("%d/%m/%Y") if fecha_inicio_periodo else "",
        "fecha_fin_periodo": fecha_salida.strftime("%d/%m/%Y") if fecha_salida else "",
    }


def _dias_anuales_por_antiguedad(anios_cumplidos: int) -> int:
    if anios_cumplidos <= 5:
        return 12
    if anios_cumplidos <= 10:
        return 18
    return 30


def _calcular_vacaciones_por_liquidacion(
    empleado: Employee,
    registros: list[EmployeePayroll],
    fecha_salida: date | None,
    vacaciones_usadas: float,
) -> dict:
    fecha_ingreso = _obtener_fecha_ingreso_empleado(empleado, registros)
    if not fecha_ingreso or not fecha_salida:
        return {
            "fecha_ingreso": _formatear_fecha_iso(fecha_ingreso),
            "dias_generados": 0.0,
            "dias_usados": round(vacaciones_usadas, 2),
            "dias_pendientes": 0.0,
            "promedio_diario": 0.0,
            "promedio_mensual": 0.0,
            "monto": 0.0,
            "dias_antiguedad": 0,
            "periodo_promedio": "Sin periodo",
            "meses_detalle": [],
        }

    dias_antiguedad = max((fecha_salida - fecha_ingreso).days, 0)
    meses_periodo = _obtener_ultimos_periodos(registros, fecha_salida, cantidad=6)

    # Construir detalle mensual
    meses_detalle = [
        {"nombre": mes.get("mes_nombre", ""), "total": float(mes.get("total_sueldos") or 0)}
        for mes in meses_periodo
        if mes.get("mes_nombre")
    ]

    total_salarios = sum(m["total"] for m in meses_detalle)
    cant_meses = max(len(meses_detalle), 1)

    # Fórmula art. 92 inc. b CT: promedio mensual = total / meses; promedio diario = mensual / 30
    promedio_mensual = round(total_salarios / cant_meses, 2) if total_salarios else 0.0
    promedio_diario = round(promedio_mensual / 30, 2)

    periodo_promedio = " - ".join(m["nombre"] for m in meses_detalle)

    anios_completos = dias_antiguedad // 365
    dias_restantes = dias_antiguedad % 365
    dias_generados = 0.0
    for anio in range(1, anios_completos + 1):
        dias_generados += _dias_anuales_por_antiguedad(anio)
    if dias_restantes > 0:
        dias_generados += (dias_restantes / 365) * _dias_anuales_por_antiguedad(anios_completos + 1)

    dias_pendientes = round(max(dias_generados - vacaciones_usadas, 0.0), 2)
    monto = round(dias_pendientes * promedio_diario, 2)
    return {
        "fecha_ingreso": _formatear_fecha_iso(fecha_ingreso),
        "dias_generados": round(dias_generados, 2),
        "dias_usados": round(vacaciones_usadas, 2),
        "dias_pendientes": dias_pendientes,
        "promedio_diario": promedio_diario,
        "promedio_mensual": promedio_mensual,
        "monto": monto,
        "dias_antiguedad": dias_antiguedad,
        "periodo_promedio": periodo_promedio or "Sin periodo",
        "meses_detalle": meses_detalle,
    }


def _calcular_preaviso_e_indemnizacion(tipo_liquidacion: str, dias_antiguedad: int, promedio_diario: float) -> dict:
    if tipo_liquidacion != "despido-sin-causa":
        return {"preaviso": 0.0, "indemnizacion": 0.0, "preaviso_dias": 0, "indemnizacion_dias": 0}

    # Escala de preaviso: art. 87 CT (4 tramos)
    if dias_antiguedad <= 365:
        preaviso_dias = 30
    elif dias_antiguedad <= 5 * 365:
        preaviso_dias = 45
    elif dias_antiguedad <= 10 * 365:
        preaviso_dias = 60
    else:
        preaviso_dias = 90  # art. 87 CT: más de 10 años → 90 días

    # Indemnización: art. 91 CT — 15 días por año; fracción > 6 meses = 1 año
    anios_completos = dias_antiguedad // 365
    meses_fraccion = (dias_antiguedad % 365) // 30
    anios = anios_completos + (1 if meses_fraccion >= 6 else 0)
    anios = max(anios, 1)  # mínimo 1 año si ya superó los 6 meses (art. 91)
    indemnizacion_dias = 15 * anios
    return {
        "preaviso": round(preaviso_dias * promedio_diario, 2),
        "indemnizacion": round(indemnizacion_dias * promedio_diario, 2),
        "preaviso_dias": preaviso_dias,
        "indemnizacion_dias": indemnizacion_dias,
    }


def _dias_inclusive(fecha_inicio: date | None, fecha_fin: date | None) -> float:
    if not fecha_inicio or not fecha_fin:
        return 0.0
    if fecha_fin < fecha_inicio:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio
    return float((fecha_fin - fecha_inicio).days + 1)


def _calcular_timeline_antiguedad(
    fecha_ingreso: date | None,
    fecha_salida: date | None,
    meses_aguinaldo: int,
) -> dict:
    if not fecha_ingreso or not fecha_salida:
        return {
            "fecha_ingreso": "N/D",
            "fecha_salida": "N/D",
            "periodos_completos": 0,
            "periodo_proporcional": 0.0,
            "meses_aguinaldo": max(0, min(int(meses_aguinaldo or 0), 12)),
            "aguinaldo_porcentaje": 0.0,
            "donut_gradient": "conic-gradient(#3b82f6 0 0%, #334155 0 100%)",
        }

    if fecha_salida < fecha_ingreso:
        fecha_ingreso, fecha_salida = fecha_salida, fecha_ingreso

    periodos_completos = 0
    periodo_proporcional = 0.0

    cursor = date(fecha_ingreso.year, fecha_ingreso.month, 1)
    limite = date(fecha_salida.year, fecha_salida.month, 1)

    while cursor <= limite:
        dias_mes = calendar.monthrange(cursor.year, cursor.month)[1]
        inicio_mes = cursor
        fin_mes = date(cursor.year, cursor.month, dias_mes)

        tramo_inicio = max(fecha_ingreso, inicio_mes)
        tramo_fin = min(fecha_salida, fin_mes)

        if tramo_inicio <= tramo_fin:
            if tramo_inicio == inicio_mes and tramo_fin == fin_mes:
                periodos_completos += 1
            else:
                dias_trabajados_mes = (tramo_fin - tramo_inicio).days + 1
                periodo_proporcional += dias_trabajados_mes / dias_mes

        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    meses_aguinaldo = max(0, min(int(meses_aguinaldo or 0), 12))
    aguinaldo_porcentaje = round((meses_aguinaldo / 12) * 100, 2)
    donut_gradient = (
        f"conic-gradient(#3b82f6 0 {aguinaldo_porcentaje:.2f}%, #334155 {aguinaldo_porcentaje:.2f}% 100%)"
    )

    return {
        "fecha_ingreso": _formatear_fecha_iso(fecha_ingreso),
        "fecha_salida": fecha_salida.strftime("%d/%m/%Y"),
        "periodos_completos": periodos_completos,
        "periodo_proporcional": round(periodo_proporcional, 2),
        "meses_aguinaldo": meses_aguinaldo,
        "aguinaldo_porcentaje": aguinaldo_porcentaje,
        "donut_gradient": donut_gradient,
    }


def _calcular_promedio_laboral(registros: list[EmployeePayroll], empleado_id: int) -> dict:
    fechas = []
    total_salarios = 0.0
    dias_trabajados = 0

    for registro in registros:
      fecha_texto = getattr(registro, "fecha", "")
      if fecha_texto:
          fechas.append(str(fecha_texto))
      total_salarios += float(getattr(registro, "sueldo_final", 0) or 0)
      dias_trabajados += 1

    if not dias_trabajados:
        return {
            "periodo": "Sin periodo",
            "total_salarios": 0.0,
            "dias_trabajados": 0,
            "promedio_diario": 0.0,
            "promedio_mensual": 0.0,
        }

    promedio_diario = round(total_salarios / dias_trabajados, 2)
    promedio_mensual = round(promedio_diario * 30, 2)
    periodo = f"{min(fechas)} a {max(fechas)}" if fechas else "Sin periodo"

    return {
        "periodo": periodo,
        "total_salarios": round(total_salarios, 2),
        "dias_trabajados": dias_trabajados,
        "promedio_diario": promedio_diario,
        "promedio_mensual": promedio_mensual,
    }


def _calcular_liquidacion_resumen(tipo_liquidacion: str, promedio: dict, vacaciones_pendientes: float) -> dict:
    promedio_diario = float(promedio.get("promedio_diario") or 0.0)
    promedio_mensual = float(promedio.get("promedio_mensual") or 0.0)

    salario_pendiente = round(promedio_mensual, 2)
    aguinaldo = round(float(promedio.get("total_salarios") or 0.0) / 12, 2)
    vacaciones = round(vacaciones_pendientes * promedio_diario, 2)

    if tipo_liquidacion == "despido-sin-causa":
        preaviso = round(promedio_mensual, 2)
        indemnizacion = round(promedio_mensual, 2)
    elif tipo_liquidacion == "fin-de-contrato":
        preaviso = 0.0
        indemnizacion = 0.0
    else:
        preaviso = 0.0
        indemnizacion = 0.0

    total_liquidacion = round(salario_pendiente + aguinaldo + vacaciones + preaviso + indemnizacion, 2)
    return {
        "salario_pendiente": salario_pendiente,
        "aguinaldo": aguinaldo,
        "vacaciones": vacaciones,
        "preaviso": preaviso,
        "indemnizacion": indemnizacion,
        "total_liquidacion": total_liquidacion,
    }


def _label_tipo_liquidacion(tipo: str | None) -> str:
    labels = {
        "renuncia-voluntaria": "Renuncia voluntaria",
        "despido-sin-causa": "Despido sin causa",
        "despido-con-causa": "Despido con causa",
        "fin-de-contrato": "Fin de contrato",
    }
    return labels.get((tipo or "").strip(), "Tipo no definido")


def _detalle_calculo_liquidacion_historial(liq: Liquidacion) -> dict:
    salario_pendiente = float(liq.salario_pendiente or 0)
    aguinaldo = float(liq.aguinaldo or 0)
    vacaciones = float(liq.vacaciones or 0)
    preaviso = float(liq.preaviso or 0)
    indemnizacion = float(liq.indemnizacion or 0)
    total = float(liq.total_liquidacion or 0)

    return {
        "salario_pendiente": (
            f"Salario pendiente: Gs. {salario_pendiente:,.0f}. "
            "Corresponde al tramo trabajado hasta la fecha de salida seleccionada."
        ),
        "aguinaldo": (
            f"Aguinaldo proporcional: Gs. {aguinaldo:,.0f}. "
            "Se calcula prorrateando los periodos salariales acumulados sobre 12 meses."
        ),
        "vacaciones": (
            f"Vacaciones no gozadas: Gs. {vacaciones:,.0f}. "
            "Resultado de días pendientes por promedio diario vigente en la liquidación."
        ),
        "preaviso": (
            f"Preaviso: Gs. {preaviso:,.0f}. "
            + (
                "Aplica según tipo de liquidación y antigüedad." if preaviso > 0 else "No aplica para este caso."
            )
        ),
        "indemnizacion": (
            f"Indemnización: Gs. {indemnizacion:,.0f}. "
            + (
                "Aplica cuando corresponde legalmente por tipo de desvinculación." if indemnizacion > 0 else "No aplica para este caso."
            )
        ),
        "total": f"Total liquidación: Gs. {total:,.0f}. Suma final de todos los conceptos aplicables.",
    }


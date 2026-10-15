"""Vista y registro de rutas de liquidación de empleados."""

from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import desc, text

from payroll.models import Employee, EmployeePayroll, Liquidacion, PromedioLaboral, db
from payroll.models_liquidacion import calcular_vacaciones_desde_historial
from payroll.periodos import _agrupar_registros_por_mes_key
from payroll.liquidaciones.servicios import (
    _parse_fecha_form,
    _formatear_fecha_iso,
    _fmt_hhmm,
    _obtener_ultimos_periodos,
    _calcular_salario_pendiente_liquidacion,
    _calcular_aguinaldo_proporcional,
    _calcular_vacaciones_por_liquidacion,
    _calcular_preaviso_e_indemnizacion,
    _dias_inclusive,
    _calcular_timeline_antiguedad,
    _calcular_promedio_laboral,
    _label_tipo_liquidacion,
    _detalle_calculo_liquidacion_historial,
)

def liquidaciones(empleado_id):
    """Muestra la vista de liquidaciones para un empleado."""
    empleado = db.session.get(Employee, empleado_id)
    if not empleado:
        abort(404)

    registros = (
        EmployeePayroll.query.filter_by(employee_id=empleado_id)
        .order_by(text("employee_payroll.fecha ASC"))
        .all()
    )

    historial_mensual = [{"fecha": r.fecha} for r in registros if getattr(r, "fecha", None)]
    periodos_registrados = len(_agrupar_registros_por_mes_key(registros))
    promedio_actual = _calcular_promedio_laboral(registros, empleado_id)
    active_tab = (request.args.get("tab") or "nueva").strip().lower()
    if active_tab not in {"nueva", "historial", "exportar"}:
        active_tab = "nueva"

    historial_liquidaciones_raw = (
        Liquidacion.query.filter_by(empleado_id=empleado_id)
        .order_by(desc(Liquidacion.created_at))
        .all()
    )
    fecha_ingreso_empleado = _parse_fecha_form(getattr(empleado, "hire_date", None))
    historial_liquidaciones = []
    for item in historial_liquidaciones_raw:
        fecha_salida_item = _parse_fecha_form(getattr(item, "fecha_salida", None))
        detalle_texto = _detalle_calculo_liquidacion_historial(item)
        periodo_trabajado_str = "N/D"
        if fecha_salida_item:
            if fecha_ingreso_empleado:
                inicio_periodo = max(date(fecha_salida_item.year, 1, 1), fecha_ingreso_empleado)
            else:
                inicio_periodo = date(fecha_salida_item.year, 1, 1)
            periodo_trabajado_str = (
                f"{inicio_periodo.strftime('%d/%m/%Y')} - {fecha_salida_item.strftime('%d/%m/%Y')}"
            )
        historial_liquidaciones.append(
            {
                "id": item.id,
                "tipo": _label_tipo_liquidacion(item.tipo),
                "tipo_key": (item.tipo or "").strip(),
                "fecha_registro": item.created_at.strftime("%d/%m/%Y %H:%M") if item.created_at else "N/D",
                "fecha_salida": fecha_salida_item.strftime("%d/%m/%Y") if fecha_salida_item else "N/D",
                "periodo_trabajado": periodo_trabajado_str,
                "salario_pendiente": float(item.salario_pendiente or 0),
                "aguinaldo": float(item.aguinaldo or 0),
                "vacaciones": float(item.vacaciones or 0),
                "preaviso": float(item.preaviso or 0),
                "indemnizacion": float(item.indemnizacion or 0),
                "total_liquidacion": float(item.total_liquidacion or 0),
                "detalle_texto": detalle_texto,
            }
        )

    ultima_liquidacion = (
        Liquidacion.query.filter_by(empleado_id=empleado_id)
        .order_by(desc(Liquidacion.created_at))
        .first()
    )
    ultima_fecha_salida = _parse_fecha_form(getattr(ultima_liquidacion, "fecha_salida", None)) if ultima_liquidacion else None
    # Prioridad: último registro de nómina cargado > última liquidación > hoy
    ultima_fecha_nomina = None
    if registros:
        ultima_fecha_nomina = _parse_fecha_form(getattr(next(reversed(registros)), "fecha", None))
    fecha_salida_default = ultima_fecha_nomina or ultima_fecha_salida or date.today()
    try:
        estado_vacaciones = calcular_vacaciones_desde_historial(historial_mensual=historial_mensual)
    except ValueError:
        estado_vacaciones = {
            "fecha_inicio": "",
            "fecha_fin": "",
            "dias_trabajados": 0,
            "dias_vacaciones": 0.0,
            "mensaje": "Sin datos suficientes para calcular vacaciones",
        }

    vacaciones_usadas = float(empleado.vacation_used_days or 0.0)
    fecha_salida = fecha_salida_default
    ultimo_sueldo_pagado = False  # GET: default a no pagado (más seguro)
    salario_pendiente_data = _calcular_salario_pendiente_liquidacion(registros, fecha_salida, ultimo_sueldo_pagado)
    aguinaldo_data = _calcular_aguinaldo_proporcional(registros, fecha_salida, fecha_ingreso_empleado)
    vacaciones_data = _calcular_vacaciones_por_liquidacion(
        empleado=empleado,
        registros=registros,
        fecha_salida=fecha_salida,
        vacaciones_usadas=vacaciones_usadas,
    )
    preaviso_indemnizacion = _calcular_preaviso_e_indemnizacion(
        empleado.liquidation_type or "renuncia-voluntaria",
        vacaciones_data["dias_antiguedad"],
        vacaciones_data["promedio_diario"],
    )

    vacaciones_generadas = float(vacaciones_data["dias_generados"] or estado_vacaciones.get("dias_vacaciones") or 0.0)
    vacaciones_pendientes = float(vacaciones_data["dias_pendientes"] or 0.0)
    monto_vacaciones_pendientes = float(vacaciones_data["monto"] or 0.0)
    salario_pendiente = float(salario_pendiente_data["monto"] or 0.0)
    aguinaldo = float(aguinaldo_data["aguinaldo"] or 0.0)
    preaviso = float(preaviso_indemnizacion["preaviso"] or 0.0)
    indemnizacion = float(preaviso_indemnizacion["indemnizacion"] or 0.0)
    total_liquidacion = round(salario_pendiente + aguinaldo + monto_vacaciones_pendientes + preaviso + indemnizacion, 2)

    if request.method == "POST":
        tipo_liquidacion = (request.form.get("liq_tipo") or "renuncia-voluntaria").strip()
        fecha_salida = _parse_fecha_form(request.form.get("liq_salida")) or fecha_salida_default
        ultimo_sueldo_pagado = request.form.get("ultimo_sueldo_pagado", "no") == "si"

        salario_pendiente_data = _calcular_salario_pendiente_liquidacion(registros, fecha_salida, ultimo_sueldo_pagado)
        aguinaldo_data = _calcular_aguinaldo_proporcional(registros, fecha_salida, fecha_ingreso_empleado)

        vacaciones_usadas = float(request.form.get("vacaciones_usadas") or 0.0)
        fecha_desde = _parse_fecha_form(request.form.get("vacaciones_desde"))
        fecha_hasta = _parse_fecha_form(request.form.get("vacaciones_hasta"))
        if vacaciones_usadas <= 0 and fecha_desde and fecha_hasta:
            vacaciones_usadas = _dias_inclusive(fecha_desde, fecha_hasta)

        vacaciones_data = _calcular_vacaciones_por_liquidacion(
            empleado=empleado,
            registros=registros,
            fecha_salida=fecha_salida,
            vacaciones_usadas=vacaciones_usadas,
        )
        preaviso_indemnizacion = _calcular_preaviso_e_indemnizacion(
            tipo_liquidacion,
            vacaciones_data["dias_antiguedad"],
            vacaciones_data["promedio_diario"],
        )

        salario_pendiente = salario_pendiente_data["monto"]
        aguinaldo = aguinaldo_data["aguinaldo"]
        vacaciones = vacaciones_data["monto"]
        preaviso = preaviso_indemnizacion["preaviso"]
        indemnizacion = preaviso_indemnizacion["indemnizacion"]
        total_liquidacion = round(salario_pendiente + aguinaldo + vacaciones + preaviso + indemnizacion, 2)

        resumen = {
            "salario_pendiente": salario_pendiente,
            "aguinaldo": aguinaldo,
            "vacaciones": vacaciones,
            "preaviso": preaviso,
            "indemnizacion": indemnizacion,
            "total_liquidacion": total_liquidacion,
        }

        promedio = PromedioLaboral()
        promedio.empleado_id = empleado.id
        promedio.periodo = aguinaldo_data["periodo"] or promedio_actual["periodo"]
        promedio.total_salarios = aguinaldo_data["total_salarios"] or promedio_actual["total_salarios"]
        promedio.dias_trabajados = vacaciones_data["dias_antiguedad"] or promedio_actual["dias_trabajados"]
        promedio.promedio_diario = vacaciones_data["promedio_diario"] or promedio_actual["promedio_diario"]
        promedio.promedio_mensual = round((promedio.promedio_diario or 0) * 30, 2)

        empleado.liquidation_type = tipo_liquidacion
        empleado.vacation_generated_days = vacaciones_generadas
        empleado.vacation_used_days = vacaciones_usadas
        empleado.vacation_pending_days = vacaciones_pendientes
        empleado.vacation_used_from = request.form.get("vacaciones_desde") or None
        empleado.vacation_used_to = request.form.get("vacaciones_hasta") or None

        liquidacion = Liquidacion()
        liquidacion.empleado_id = empleado.id
        liquidacion.tipo = tipo_liquidacion
        liquidacion.fecha_salida = _formatear_fecha_iso(fecha_salida)
        liquidacion.salario_pendiente = resumen["salario_pendiente"]
        liquidacion.aguinaldo = resumen["aguinaldo"]
        liquidacion.vacaciones = resumen["vacaciones"]
        liquidacion.preaviso = resumen["preaviso"]
        liquidacion.indemnizacion = resumen["indemnizacion"]
        liquidacion.total_liquidacion = resumen["total_liquidacion"]
        db.session.add(promedio)
        db.session.add(liquidacion)
        db.session.commit()

        flash("La liquidación se guardó con las vacaciones actualizadas.", "success")
        return redirect(url_for("liquidaciones", empleado_id=empleado_id, tab="historial"))

    ultimo_promedio = (
        PromedioLaboral.query.filter_by(empleado_id=empleado_id)
        .order_by(desc(PromedioLaboral.created_at))
        .first()
    )

    detalle_vacaciones = (
        f"Vacaciones generadas: {vacaciones_generadas:.2f} días · "
        f"Vacaciones utilizadas: {vacaciones_usadas:.2f} días · "
        f"Vacaciones pendientes: {vacaciones_pendientes:.2f} días"
    )
    _sp = salario_pendiente_data
    _lineas_sp: list[str] = []
    if _sp.get("fecha_inicio") and _sp.get("fecha_fin"):
        _lineas_sp.append(f"Período pendiente: {_sp['fecha_inicio']} al {_sp['fecha_fin']}")
    _lineas_sp.append(f"Horas normales: <strong>{_fmt_hhmm(_sp.get('horas_normales', 0.0))}</strong>")
    _lineas_sp.append(f"Horas especiales: <strong>{_fmt_hhmm(_sp.get('horas_especiales', 0.0))}</strong>")
    if _sp.get("horas_feriado", 0.0) > 0:
        _lineas_sp.append(f"Horas feriado: <strong>{_fmt_hhmm(_sp.get('horas_feriado', 0.0))}</strong> (×2)")
    _lineas_sp.append(f"Valor hora: <strong>Gs. {_sp.get('valor_hora', 0.0):,.0f}</strong>")
    _lineas_sp.append(f"Total: <strong>Gs. {salario_pendiente:,.0f}</strong>")
    detalle_salario_pendiente = "\n".join(_lineas_sp)
    meses_aguinaldo = len(_obtener_ultimos_periodos(registros, fecha_salida_default, 12))
    # Desglose mes a mes del aguinaldo (auditable)
    _lineas_ag = [f"Período: {aguinaldo_data['fecha_inicio_periodo']} al {aguinaldo_data['fecha_fin_periodo']}"]
    for _m in aguinaldo_data.get("detalle_meses", []):
        if _m["tiene_datos"]:
            _lineas_ag.append(f"{_m['mes']}: <strong>Gs. {_m['monto']:,.0f}</strong>")
        else:
            _lineas_ag.append(f"{_m['mes']}: <em>sin registros</em>")
    _lineas_ag.append(f"Total salarios: <strong>Gs. {aguinaldo_data['total_salarios']:,.0f}</strong>")
    _lineas_ag.append(
        f"Aguinaldo = Gs. {aguinaldo_data['total_salarios']:,.0f} / 12 = "
        f"<strong>Gs. {aguinaldo_data['aguinaldo']:,.0f}</strong>"
    )
    detalle_aguinaldo = "\n".join(_lineas_ag)
    aguinaldo_alerta = aguinaldo_data.get("alerta_meses_incompletos", False)
    aguinaldo_meses_con_datos = aguinaldo_data.get("meses_con_datos", meses_aguinaldo)
    aguinaldo_meses_esperados = aguinaldo_data.get("meses_esperados", 12)
    aguinaldo_meses_faltantes = aguinaldo_data.get("meses_faltantes", 0)
    detalle_vacaciones = (
        f"{detalle_vacaciones} · {vacaciones_data['dias_pendientes']:.2f} días × Gs. {vacaciones_data['promedio_diario']:,.0f}"
    )
    detalle_preaviso = (
        f"{preaviso_indemnizacion['preaviso_dias']} días × Gs. {vacaciones_data['promedio_diario']:,.0f}"
        if preaviso > 0
        else "No aplica"
    )
    detalle_indemnizacion = (
        f"{preaviso_indemnizacion['indemnizacion_dias']} días × Gs. {vacaciones_data['promedio_diario']:,.0f}"
        if indemnizacion > 0
        else "No aplica"
    )
    timeline_antiguedad = _calcular_timeline_antiguedad(
        _parse_fecha_form(vacaciones_data.get("fecha_ingreso")),
        fecha_salida_default,
        meses_aguinaldo,
    )

    composicion_base = [
        {
            "label": "Salario pendiente",
            "amount": float(salario_pendiente or 0),
            "color": "#4f83ff",
            "dot_class": "dot-blue",
        },
        {
            "label": "Aguinaldo proporcional",
            "amount": float(aguinaldo or 0),
            "color": "#22c55e",
            "dot_class": "dot-green",
        },
        {
            "label": "Vacaciones no gozadas",
            "amount": float(monto_vacaciones_pendientes or 0),
            "color": "#facc15",
            "dot_class": "dot-yellow",
        },
    ]
    if float(indemnizacion or 0) > 0:
        composicion_base.append(
            {
                "label": "Indemnización",
                "amount": float(indemnizacion or 0),
                "color": "#fb923c",
                "dot_class": "dot-orange",
            }
        )
    if float(preaviso or 0) > 0:
        composicion_base.append(
            {
                "label": "Preaviso",
                "amount": float(preaviso or 0),
                "color": "#ef4444",
                "dot_class": "dot-red",
            }
        )

    composicion_liquidacion = []
    composicion_chart_gradient = "conic-gradient(#64748b 0 100%)"
    composicion_dominante_label = "Sin datos"
    composicion_dominante_porcentaje = 0.0
    total_composicion = float(total_liquidacion or 0)
    if total_composicion > 0:
        acumulado = 0.0
        segmentos = []
        for concepto in composicion_base:
            porcentaje = round((concepto["amount"] / total_composicion) * 100, 2)
            composicion_liquidacion.append(
                {
                    **concepto,
                    "percentage": porcentaje,
                }
            )
            inicio = acumulado
            acumulado = min(acumulado + porcentaje, 100.0)
            segmentos.append(f"{concepto['color']} {inicio:.2f}% {acumulado:.2f}%")

        if segmentos:
            composicion_chart_gradient = f"conic-gradient({', '.join(segmentos)})"
        dominante = max(composicion_liquidacion, key=lambda item: float(item.get("percentage") or 0))
        composicion_dominante_label = str(dominante.get("label") or "Sin datos")
        composicion_dominante_porcentaje = float(dominante.get("percentage") or 0)
    else:
        for concepto in composicion_base:
            composicion_liquidacion.append(
                {
                    **concepto,
                    "percentage": 0.0,
                }
            )

    return render_template(
        "liquidaciones.html",
        empleado=empleado,
        mensaje=estado_vacaciones["mensaje"],
        detalle_vacaciones=detalle_vacaciones,
        vacaciones_generadas=round(vacaciones_generadas, 2),
        vacaciones_usadas=round(vacaciones_usadas, 2),
        vacaciones_pendientes=round(vacaciones_pendientes, 2),
        monto_vacaciones_pendientes=monto_vacaciones_pendientes,
        vacaciones_desde=empleado.vacation_used_from or "",
        vacaciones_hasta=empleado.vacation_used_to or "",
        selected_liquidation_type=empleado.liquidation_type or "renuncia-voluntaria",
        promedio_laboral=ultimo_promedio,
        ultima_liquidacion=ultima_liquidacion,
        periodos_registrados=periodos_registrados,
        fecha_ingreso=vacaciones_data["fecha_ingreso"],
        vacaciones_dias_antiguedad=vacaciones_data["dias_antiguedad"],
        salario_pendiente=salario_pendiente,
        aguinaldo=aguinaldo,
        preaviso=preaviso,
        indemnizacion=indemnizacion,
        total_liquidacion=total_liquidacion,
        fecha_salida_default=_formatear_fecha_iso(fecha_salida_default),
        promedio_diario_vacaciones=vacaciones_data["promedio_diario"],
        promedio_mensual_vacaciones=vacaciones_data["promedio_mensual"],
        vacaciones_meses_promedio=vacaciones_data["meses_detalle"],
        vacaciones_periodo_promedio=vacaciones_data["periodo_promedio"],
        detalle_salario_pendiente=detalle_salario_pendiente,
        detalle_aguinaldo=detalle_aguinaldo,
        detalle_preaviso=detalle_preaviso,
        detalle_indemnizacion=detalle_indemnizacion,
        composicion_liquidacion=composicion_liquidacion,
        composicion_chart_gradient=composicion_chart_gradient,
        composicion_dominante_label=composicion_dominante_label,
        composicion_dominante_porcentaje=composicion_dominante_porcentaje,
        timeline_antiguedad=timeline_antiguedad,
        active_tab=active_tab,
        historial_liquidaciones=historial_liquidaciones,
        aguinaldo_alerta=aguinaldo_alerta,
        aguinaldo_meses_con_datos=aguinaldo_meses_con_datos,
        aguinaldo_meses_esperados=aguinaldo_meses_esperados,
        aguinaldo_meses_faltantes=aguinaldo_meses_faltantes,
        ultimo_sueldo_pagado=ultimo_sueldo_pagado,
        salario_modo=salario_pendiente_data.get("modo", ""),
    )


def registrar_rutas_liquidaciones(app):
    """Conserva el endpoint existente para enlaces y redirecciones."""
    app.add_url_rule(
        "/empleado/<int:empleado_id>/liquidaciones",
        endpoint="liquidaciones",
        view_func=liquidaciones,
        methods=["GET", "POST"],
    )

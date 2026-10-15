"""Utilidades de períodos de nómina compartidas por las vistas y liquidaciones."""

from datetime import datetime
from typing import Optional

import pandas as pd

from payroll.models import CalculationRun, db

MESES_ES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

def _mes_es(month: int) -> str:
    """Nombre del mes en español (1–12).

    Envuelve el acceso a ``MESES_ES`` para evitar el falso positivo de Pylance
    con Python 3.14 donde ``int`` no se reconoce como ``SupportsIndex``.
    """
    return MESES_ES[month - 1]  # type: ignore[index]

def _agrupar_registros_por_mes(registros):
    run_ids = {int(r.run_id) for r in registros if getattr(r, "run_id", None)}
    runs_by_id = {}
    if run_ids:
        runs = [db.session.get(CalculationRun, run_id) for run_id in run_ids]
        runs = [run for run in runs if run is not None]
        runs_by_id = {run.id: run for run in runs}

    meses = {}
    for registro in registros:
        fecha_str = getattr(registro, "fecha", "")
        try:
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue

        clave = (fecha_dt.year, fecha_dt.month)
        if clave not in meses:
            meses[clave] = {
                "year": fecha_dt.year,
                "month": fecha_dt.month,
                "mes_nombre": f"{_mes_es(fecha_dt.month)} {fecha_dt.year}",
                "registros": [],
                "dias_trabajados": 0,
                "total_horas_normales": 0.0,
                "total_horas_especiales": 0.0,
                "total_sueldos": 0.0,
                "total_salario_bruto": 0.0,
                "monto_horas_normales": 0.0,
                "monto_horas_especiales": 0.0,
                "monto_feriados": 0.0,
                "bonificacion": 0.0,
                "total_descuento_ips": 0.0,
                "total_aporte_empleador_ips": 0.0,
                "total_ips": 0.0,
                "total_salario_neto_ips": 0.0,
                "_run_ids_contados": set(),
            }

        meses[clave]["registros"].append(registro)
        horas_normales = float(registro.horas_normales or 0)
        horas_especiales = float(registro.horas_especiales or 0)

        if (horas_normales + horas_especiales) > 0:
            meses[clave]["dias_trabajados"] += 1

        meses[clave]["total_horas_normales"] += horas_normales
        meses[clave]["total_horas_especiales"] += horas_especiales
        meses[clave]["total_sueldos"] += float(registro.sueldo_final or 0)

        run_id = getattr(registro, "run_id", None)
        if run_id and run_id not in meses[clave]["_run_ids_contados"]:
            run = runs_by_id.get(int(run_id))
            if run:
                bruto = float(run.total_salario_bruto or 0)
                if bruto <= 0:
                    bruto = float(run.total_sueldos or 0)

                monto_normal = float(
                    run.total_monto_horas_normales
                    or (float(run.total_horas_normales or 0) * float(run.valor_por_hora or 0))
                )
                monto_especial = float(
                    run.total_monto_horas_especiales
                    or (
                        float(run.total_horas_especiales or 0)
                        * float(run.valor_por_hora or 0)
                        * 1.3
                    )
                )
                monto_feriados = float(
                    run.total_monto_feriados
                    if run.total_monto_feriados is not None
                    else max(0.0, bruto - monto_normal - monto_especial)
                )
                bonificacion = float(run.total_bonificacion or 0)

                if (not run.feriados and monto_feriados <= 0.01) or abs(monto_feriados) < 0.015:
                    monto_feriados = 0.0

                descuento_ips = float(run.total_descuento_ips or 0)
                aporte_empleador = float(run.total_aporte_empleador_ips or 0)
                total_ips = float(run.total_ips or (descuento_ips + aporte_empleador))
                neto = float(run.total_salario_neto_ips or (bruto - descuento_ips))

                meses[clave]["total_salario_bruto"] += bruto
                meses[clave]["monto_horas_normales"] += monto_normal
                meses[clave]["monto_horas_especiales"] += monto_especial
                meses[clave]["monto_feriados"] += monto_feriados
                meses[clave]["bonificacion"] += bonificacion
                meses[clave]["total_descuento_ips"] += descuento_ips
                meses[clave]["total_aporte_empleador_ips"] += aporte_empleador
                meses[clave]["total_ips"] += total_ips
                meses[clave]["total_salario_neto_ips"] += neto

            meses[clave]["_run_ids_contados"].add(run_id)

    salida = []
    for clave in sorted(meses.keys()):
        mes = meses[clave]
        if abs(mes["monto_feriados"]) < 0.015:
            mes["monto_feriados"] = 0.0
        if mes["total_salario_bruto"] <= 0:
            mes["total_salario_bruto"] = mes["total_sueldos"]
        if mes["total_salario_neto_ips"] <= 0:
            mes["total_salario_neto_ips"] = mes["total_salario_bruto"]
        mes.pop("_run_ids_contados", None)
        salida.append(mes)

    return salida

def _month_key_from_value(valor: object) -> Optional[str]:
    if valor is None:
        return None

    if isinstance(valor, datetime):
        return f"{valor.year:04d}-{valor.month:02d}"

    texto = str(valor).strip()
    if not texto:
        return None

    # Soporta fechas normalizadas del sistema (YYYY-MM-DD) sin ambiguedad.
    try:
        fecha_iso = datetime.strptime(texto[:10], "%Y-%m-%d")
        return f"{fecha_iso.year:04d}-{fecha_iso.month:02d}"
    except ValueError:
        pass

    # Soporta fechas de formularios/reportes en formato DD/MM/YYYY.
    try:
        fecha_latam = datetime.strptime(texto[:10], "%d/%m/%Y")
        return f"{fecha_latam.year:04d}-{fecha_latam.month:02d}"
    except ValueError:
        pass

    try:
        fecha = pd.to_datetime(texto, errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    if pd.isna(fecha):
        return None
    return f"{fecha.year:04d}-{fecha.month:02d}"

def _month_label_from_key(month_key: str) -> str:
    try:
        year_str, month_str = month_key.split("-", 1)
        year = int(year_str)
        month = int(month_str)
        return f"{_mes_es(month)} {year}"
    except (ValueError, IndexError):
        return month_key

def _agrupar_registros_por_mes_key(registros):
    meses = {}
    for registro in registros:
        month_key = _month_key_from_value(getattr(registro, "fecha", ""))
        if not month_key:
            continue

        if month_key not in meses:
            meses[month_key] = {
                "month_key": month_key,
                "mes_nombre": _month_label_from_key(month_key),
                "registros": [],
                "dias_trabajados": 0,
                "total_horas_normales": 0.0,
                "total_horas_especiales": 0.0,
                "total_sueldos": 0.0,
            }

        meses[month_key]["registros"].append(registro)
        horas_normales = float(getattr(registro, "horas_normales", 0) or 0)
        horas_especiales = float(getattr(registro, "horas_especiales", 0) or 0)
        if (horas_normales + horas_especiales) > 0:
            meses[month_key]["dias_trabajados"] += 1
        meses[month_key]["total_horas_normales"] += horas_normales
        meses[month_key]["total_horas_especiales"] += horas_especiales
        meses[month_key]["total_sueldos"] += float(getattr(registro, "sueldo_final", 0) or 0)

    return [meses[key] for key in sorted(meses.keys(), reverse=True)]

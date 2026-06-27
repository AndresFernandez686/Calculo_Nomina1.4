"""
Calculadora de Sueldos - Aplicación Flask.

Migración completa desde Streamlit a Flask manteniendo toda la lógica de negocio:
- Carga de archivos Excel o PDF (hasta 2 quincenas).
- Configuración de valor por hora y hasta 3 feriados (doble pago).
- Detección y corrección de registros incompletos y horarios ambiguos.
- Cálculo de horas normales / especiales (20:00-22:00 +30%) y feriados (x2).
- Resultados con resumen, descarga en Excel e historial persistido en BD.
"""
import io
import os
import pickle
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, cast

import pandas as pd
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import desc, inspect, text

from payroll.data_processor import procesar_datos_excel, validar_archivo_excel
from payroll.models import (
    CalculationRun,
    Employee,
    EmployeeAttendance,
    EmployeePayroll,
    EmployeeRecord,
    db,
)
from payroll.pdf_processor import (
    convertir_a_dataframe_estandar,  # noqa: F401  (import keeps API discoverable)
    detectar_horarios_ambiguos,
    detectar_registros_incompletos,
    filtrar_registros_sin_asistencia,
    procesar_pdf_a_dataframe,
    validar_datos_pdf,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
PENDING_DIR = os.path.join(INSTANCE_DIR, "pending")
os.makedirs(PENDING_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "calculadora-sueldos-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    INSTANCE_DIR, "sueldos.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB

db.init_app(app)

from payroll.calculations import calcular_horas_especiales, horas_a_horasminutos


@app.template_filter("hhmm")
def _hhmm_filter(value):
    """Convierte horas decimales a formato H:MM para las plantillas."""
    try:
        return horas_a_horasminutos(float(value))
    except (TypeError, ValueError):
        return "0:00"


VALOR_POR_HORA_DEFAULT = 13937.0


# --------------------------------------------------------------------------- #
# Utilidades                                                                   #
# --------------------------------------------------------------------------- #
def _parse_feriados(form):
    """Lee hasta 3 fechas de feriado del formulario y devuelve un set de dates."""
    fechas = set()
    for key in ("feriado_1", "feriado_2", "feriado_3"):
        valor = (form.get(key) or "").strip()
        if valor:
            try:
                fechas.add(datetime.strptime(valor, "%Y-%m-%d").date())
            except ValueError:
                pass
    return fechas


def _guardar_pendiente(df, config):
    """Persiste el DataFrame y la configuración en disco hasta confirmar correcciones."""
    token = uuid.uuid4().hex
    ruta = os.path.join(PENDING_DIR, f"{token}.pkl")
    with open(ruta, "wb") as fh:
        pickle.dump({"df": df, "config": config}, fh)
    return token


def _cargar_pendiente(token):
    ruta = os.path.join(PENDING_DIR, f"{token}.pkl")
    if not token or not os.path.exists(ruta):
        return None
    with open(ruta, "rb") as fh:
        return pickle.load(fh)


def _eliminar_pendiente(token):
    ruta = os.path.join(PENDING_DIR, f"{token}.pkl")
    if token and os.path.exists(ruta):
        os.remove(ruta)


def _df_incompletos_a_lista(df_incompletos):
    items = []
    for idx, row in df_incompletos.iterrows():
        items.append(
            {
                "idx": int(idx),
                "empleado": row["Empleado"],
                "fecha": _fecha_str(row["Fecha"]),
                "horario": str(row.get("Horario_Registrado", "")),
                "dato_faltante": row.get("Dato_Faltante", ""),
                "problema": row.get("Tipo_Problema", ""),
            }
        )
    return items


def _df_ambiguos_a_lista(df_ambiguos):
    items = []
    for idx, row in df_ambiguos.iterrows():
        items.append(
            {
                "idx": int(idx),
                "empleado": row["Empleado"],
                "fecha": _fecha_str(row["Fecha"]),
                "entrada": row["Entrada_Original"],
                "salida": row["Salida_Original"],
                "razon": row["Razon_Sospecha"],
            }
        )
    return items


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
                "mes_nombre": f"{MESES_ES[fecha_dt.month - 1]} {fecha_dt.year}",
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
                    or max(0.0, bruto - monto_normal - monto_especial)
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
    for clave in sorted(meses.keys(), reverse=True):
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


def _filtrar_registros_por_mes(registros, year, month):
    filtrados = []
    for registro in registros:
        fecha_str = getattr(registro, "fecha", "")
        try:
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        if fecha_dt.year == year and fecha_dt.month == month:
            filtrados.append(registro)
    return filtrados


def _fecha_str(valor):
    try:
        return pd.to_datetime(valor).strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001
        return str(valor)


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
        return f"{MESES_ES[month - 1]} {year}"
    except (ValueError, IndexError):
        return month_key


def _obtener_meses_df(df) -> set[str]:
    if "Fecha" not in df.columns:
        return set()
    meses: set[str] = set()
    for valor in df["Fecha"].tolist():
        month_key = _month_key_from_value(valor)
        if month_key:
            meses.add(month_key)
    return meses


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


def _obtener_conflictos_mes_empleado(employee_id: int, meses_objetivo: set[str]):
    if not meses_objetivo:
        return [], []

    registros = (
        EmployeePayroll.query.filter_by(employee_id=employee_id)
        .order_by(desc(EmployeePayroll.created_at))
        .all()
    )
    registros_conflictivos = []
    for registro in registros:
        month_key = _month_key_from_value(getattr(registro, "fecha", ""))
        if month_key in meses_objetivo:
            registros_conflictivos.append(registro)

    meses_conflictivos_set: set[str] = set()
    for registro in registros_conflictivos:
        month_key = _month_key_from_value(getattr(registro, "fecha", ""))
        if month_key:
            meses_conflictivos_set.add(month_key)

    meses_conflictivos = sorted(meses_conflictivos_set, reverse=True)
    return meses_conflictivos, registros_conflictivos


def _reemplazar_meses_existentes(employee_id: int, meses_objetivo: set[str]) -> None:
    if not meses_objetivo:
        return

    registros = EmployeePayroll.query.filter_by(employee_id=employee_id).all()
    registros_a_borrar = []
    run_ids: set[int] = set()
    for registro in registros:
        month_key = _month_key_from_value(getattr(registro, "fecha", ""))
        if month_key in meses_objetivo:
            registros_a_borrar.append(registro)
            if getattr(registro, "run_id", None):
                run_ids.add(int(registro.run_id))

    for registro in registros_a_borrar:
        db.session.delete(registro)

    if run_ids:
        for run_id in run_ids:
            EmployeeAttendance.query.filter_by(run_id=run_id).delete(
                synchronize_session=False
            )
            EmployeeRecord.query.filter_by(run_id=run_id).delete(
                synchronize_session=False
            )
            CalculationRun.query.filter_by(id=run_id).delete(
                synchronize_session=False
            )

    db.session.commit()


def _sanear_nombre_para_archivo(nombre: str) -> str:
    texto = re.sub(r"[^\w\-]+", "_", nombre.strip(), flags=re.UNICODE)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto or "empleado"


def _generar_df_desde_registros(registros):
    filas = []
    for r in registros:
        filas.append(
            {
                "Fecha": r.fecha,
                "Entrada": r.entrada,
                "Salida": r.salida,
                "Feriado": r.feriado,
                "Horas Trabajadas (h:mm)": r.horas_trabajadas,
                "Horas Normales": horas_a_horasminutos(r.horas_normales),
                "Horas Especiales": horas_a_horasminutos(r.horas_especiales),
                "Descuento Inventario": r.descuento_inventario,
                "Descuento Caja": r.descuento_caja,
                "Retiro": r.retiro,
                "Sueldo Final": r.sueldo_final,
            }
        )
    return pd.DataFrame(filas)


def _crear_pdf_desde_registros(registros, empleado_nombre, mes_nombre):
    df = _generar_df_desde_registros(registros)
    resumen = {
        "total_horas_normales": sum(float(r.horas_normales or 0) for r in registros),
        "total_horas_especiales": sum(float(r.horas_especiales or 0) for r in registros),
        "total_sueldos": sum(float(r.sueldo_final or 0) for r in registros),
    }

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"{empleado_nombre} — {mes_nombre}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    columnas = [
        "Fecha",
        "Entrada",
        "Salida",
        "Feriado",
        "Horas Normales",
        "Horas Especiales",
        "Desc. Inv.",
        "Desc. Caja",
        "Retiro",
        "Sueldo Final",
    ]
    datos = [columnas]
    for _, fila in df.iterrows():
        datos.append(
            [
                fila["Fecha"],
                fila["Entrada"] or "-",
                fila["Salida"] or "-",
                fila["Feriado"] or "-",
                fila["Horas Normales"],
                fila["Horas Especiales"],
                f"${fila['Descuento Inventario']:.0f}" if fila["Descuento Inventario"] else "-",
                f"${fila['Descuento Caja']:.0f}" if fila["Descuento Caja"] else "-",
                f"${fila['Retiro']:.0f}" if fila["Retiro"] else "-",
                f"${fila['Sueldo Final']:.0f}",
            ]
        )

    tabla = Table(datos, repeatRows=1, hAlign="LEFT")
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#3a485d")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7d7d7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7d7d7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(tabla)
    story.append(Spacer(1, 16))

    resumen_tabla = Table(
        [
            ["Total Horas Normales", f"{resumen['total_horas_normales']:.2f}"],
            ["Total Horas Especiales", f"{resumen['total_horas_especiales']:.2f}"],
            ["Sueldo Total", f"${resumen['total_sueldos']:.0f}"],
        ],
        hAlign="LEFT",
        colWidths=[150, 120],
    )
    resumen_tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7d7d7")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7d7d7")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    story.append(resumen_tabla)

    doc.build(story)
    output.seek(0)
    return output


def _crear_excel_desde_registros(registros, empleado_nombre, mes_nombre):
    df = _generar_df_desde_registros(registros)
    resumen = {
        "total_horas_normales": sum(float(r.horas_normales or 0) for r in registros),
        "total_horas_especiales": sum(float(r.horas_especiales or 0) for r in registros),
        "total_sueldos": sum(float(r.sueldo_final or 0) for r in registros),
    }
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sueldos")
        workbook = writer.book
        worksheet = writer.sheets["Sueldos"]

        fila_inicio = len(df) + 3
        bold = Font(bold=True)
        worksheet.cell(row=fila_inicio, column=1, value="Total Horas Normales").font = bold
        worksheet.cell(row=fila_inicio, column=2, value=resumen["total_horas_normales"]).font = bold
        worksheet.cell(row=fila_inicio + 1, column=1, value="Total Horas Especiales").font = bold
        worksheet.cell(row=fila_inicio + 1, column=2, value=resumen["total_horas_especiales"]).font = bold
        worksheet.cell(row=fila_inicio + 2, column=1, value="Sueldo Total").font = bold
        worksheet.cell(row=fila_inicio + 2, column=2, value=resumen["total_sueldos"]).font = bold

    output.seek(0)
    return output


def _hhmm_to_decimal(valor):
    if valor is None or pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except (TypeError, ValueError):
            return 0.0
    texto = str(valor).strip()
    if not texto or texto.lower() in {"nan", "nat", "none"}:
        return 0.0
    if ":" in texto:
        partes = texto.split(":", 1)
        try:
            horas = float(partes[0])
            minutos = float(partes[1])
            return horas + minutos / 60.0
        except ValueError:
            return 0.0
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _parsear_feriados_run(run: CalculationRun):
    fechas = set()
    if not run.feriados:
        return fechas
    for valor in str(run.feriados).split(","):
        texto = valor.strip()
        if not texto:
            continue
        try:
            fechas.add(datetime.strptime(texto, "%d/%m/%Y").date())
        except ValueError:
            continue
    return fechas


def _registro_tiene_horario_valido(record: EmployeeRecord) -> bool:
    entrada = str(record.entrada or "").strip()
    salida = str(record.salida or "").strip()
    invalidos = {"", "nan", "0:00", "00:00", "none"}
    return entrada.lower() not in invalidos and salida.lower() not in invalidos


def _run_necesita_recalculo(run: CalculationRun, records: list[EmployeeRecord]) -> bool:
    for record in records:
        if not _registro_tiene_horario_valido(record):
            continue
        observaciones = str(record.observaciones or "").strip().lower()
        if "entrada ajustada al inicio de la jornada laboral" in observaciones:
            return True
        if "salida ajustada al fin de la jornada laboral" in observaciones:
            return True
        if str(record.horas_trabajadas or "").strip() == "0:00" and record.sueldo_final == 0:
            return True
    return False


def _recalcular_run_legado(run: CalculationRun) -> None:
    records = cast(list[EmployeeRecord], list(getattr(run, "records", []) or []))
    if not records or not _run_necesita_recalculo(run, records):
        return

    filas = []
    for record in records:
        filas.append(
            {
                "Empleado": record.empleado,
                "Fecha": record.fecha,
                "Entrada": record.entrada,
                "Salida": record.salida,
                "Descuento Inventario": record.descuento_inventario,
                "Descuento Caja": record.descuento_caja,
                "Retiro": record.retiro,
            }
        )

    resultado = procesar_datos_excel(
        pd.DataFrame(filas),
        run.valor_por_hora,
        _parsear_feriados_run(run),
    )
    if len(resultado["resultados"]) != len(records):
        return

    payroll_rows = cast(
        list[EmployeePayroll],
        list(EmployeePayroll.query.filter_by(run_id=run.id).all()),
    )
    payroll_rows.sort(key=lambda row: row.id)

    for record, fila in zip(records, resultado["resultados"]):
        record.feriado = fila["Feriado"]
        record.horas_trabajadas = fila["Horas Trabajadas (h:mm)"]
        record.horas_normales = _hhmm_to_decimal(fila["Horas Normales"])
        record.horas_especiales = _hhmm_to_decimal(fila["Horas Especiales"])
        record.monto_horas_normales = float(fila.get("Monto Horas Normales") or 0)
        record.monto_horas_especiales = float(fila.get("Monto Horas Especiales") or 0)
        record.monto_feriado = float(fila.get("Monto Feriado") or 0)
        record.bonificacion = float(fila.get("Bonificacion") or 0)
        record.sueldo_bruto = float(fila.get("Sueldo Bruto") or 0)
        record.descuento_ips = float(fila.get("Descuento IPS") or 0)
        record.sueldo_final = float(fila["Sueldo Final"] or 0)
        record.observaciones = fila.get("Observaciones", "")

    for payroll, fila in zip(payroll_rows, resultado["resultados"]):
        payroll.feriado = fila["Feriado"]
        payroll.horas_trabajadas = fila["Horas Trabajadas (h:mm)"]
        payroll.horas_normales = _hhmm_to_decimal(fila["Horas Normales"])
        payroll.horas_especiales = _hhmm_to_decimal(fila["Horas Especiales"])
        payroll.monto_horas_normales = float(fila.get("Monto Horas Normales") or 0)
        payroll.monto_horas_especiales = float(fila.get("Monto Horas Especiales") or 0)
        payroll.monto_feriado = float(fila.get("Monto Feriado") or 0)
        payroll.bonificacion = float(fila.get("Bonificacion") or 0)
        payroll.sueldo_bruto = float(fila.get("Sueldo Bruto") or 0)
        payroll.descuento_ips = float(fila.get("Descuento IPS") or 0)
        payroll.sueldo_final = float(fila["Sueldo Final"] or 0)
        payroll.observaciones = fila.get("Observaciones", "")

    run.total_horas = resultado["total_horas"]
    run.total_horas_normales = resultado["total_horas_normales"]
    run.total_horas_especiales = resultado["total_horas_especiales"]
    run.total_monto_horas_normales = resultado["total_monto_horas_normales"]
    run.total_monto_horas_especiales = resultado["total_monto_horas_especiales"]
    run.total_monto_feriados = resultado["total_monto_feriados"]
    run.total_bonificacion = resultado["total_bonificacion"]
    run.total_sueldos = resultado["total_sueldos"]
    run.total_salario_bruto = resultado["total_salario_bruto"]
    run.total_descuento_ips = resultado["total_descuento_ips"]
    run.total_aporte_empleador_ips = resultado["total_aporte_empleador_ips"]
    run.total_ips = resultado["total_ips"]
    run.total_salario_neto_ips = resultado["total_salario_neto_ips"]
    run.total_registros = len(resultado["resultados"])
    db.session.commit()


def _normalizar_nombre(nombre: str) -> str:
    texto = str(nombre or "").strip().lower()
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    return " ".join(texto.split())


def _empleado_coincide(nombre_extraido: str, empleado: Employee) -> bool:
    nombre_extraido = _normalizar_nombre(nombre_extraido)
    nombre_empleado = _normalizar_nombre(empleado.nombre)
    if not nombre_extraido or not nombre_empleado:
        return False
    if nombre_extraido == nombre_empleado:
        return True

    tokens_extraido = nombre_extraido.split()
    tokens_empleado = nombre_empleado.split()

    if len(tokens_extraido) == 1 and tokens_empleado:
        return tokens_extraido[0] == tokens_empleado[0]
    if len(tokens_empleado) == 1 and tokens_extraido:
        return tokens_empleado[0] == tokens_extraido[0]

    return _tokens_consecutivos(tokens_extraido, tokens_empleado) or _tokens_consecutivos(
        tokens_empleado,
        tokens_extraido,
    )


def _tokens_consecutivos(tokens_base: list[str], tokens_objetivo: list[str]) -> bool:
    if len(tokens_objetivo) > len(tokens_base):
        return False
    for indice in range(len(tokens_base) - len(tokens_objetivo) + 1):
        if tokens_base[indice: indice + len(tokens_objetivo)] == tokens_objetivo:
            return True
    return False


def _desglose_horas(entrada_texto: str, salida_texto: str) -> dict:
    entrada_dt = datetime.strptime(entrada_texto, "%H:%M")
    salida_dt = datetime.strptime(salida_texto, "%H:%M")
    if salida_dt < entrada_dt:
        salida_dt += timedelta(days=1)

    horas_totales = (salida_dt - entrada_dt).total_seconds() / 3600.0
    horas_normales, horas_especiales = calcular_horas_especiales(entrada_dt, salida_dt)

    return {
        "entrada": entrada_texto,
        "salida": salida_texto,
        "horas_totales_decimal": round(horas_totales, 10),
        "horas_totales_hhmm": horas_a_horasminutos(horas_totales),
        "horas_normales_decimal": round(horas_normales, 10),
        "horas_normales_hhmm": horas_a_horasminutos(horas_normales),
        "horas_especiales_decimal": round(horas_especiales, 10),
        "horas_especiales_hhmm": horas_a_horasminutos(horas_especiales),
    }


def _calcular_y_guardar(df, config, employee: Employee):
    """Ejecuta el cálculo y guarda el resultado en la base de datos."""
    resultado = procesar_datos_excel(
        df,
        config["valor_por_hora"],
        set(config["feriados"]),
        ips_enabled=config.get("ips_enabled", False),
    )

    run = CalculationRun()
    run.employee_id = employee.id
    run.source_name = config.get("source_name")
    run.source_type = config.get("source_type", "excel")
    run.valor_por_hora = config["valor_por_hora"]
    run.feriados = (
        ", ".join(d.strftime("%d/%m/%Y") for d in sorted(config["feriados"]))
        if config["feriados"]
        else None
    )
    run.seguro_ips = "Sí" if config.get("ips_enabled", False) else "No"
    run.total_horas = resultado["total_horas"]
    run.total_horas_normales = resultado["total_horas_normales"]
    run.total_horas_especiales = resultado["total_horas_especiales"]
    run.total_monto_horas_normales = resultado["total_monto_horas_normales"]
    run.total_monto_horas_especiales = resultado["total_monto_horas_especiales"]
    run.total_monto_feriados = resultado["total_monto_feriados"]
    run.total_bonificacion = resultado["total_bonificacion"]
    run.total_sueldos = resultado["total_sueldos"]
    run.total_salario_bruto = resultado["total_salario_bruto"]
    run.total_descuento_ips = resultado["total_descuento_ips"]
    run.total_aporte_empleador_ips = resultado["total_aporte_empleador_ips"]
    run.total_ips = resultado["total_ips"]
    run.total_salario_neto_ips = resultado["total_salario_neto_ips"]
    run.total_registros = len(resultado["resultados"])

    db.session.add(run)
    db.session.flush()

    for fila in resultado["resultados"]:
        record = EmployeeRecord()
        record.run_id = run.id
        record.employee_id = employee.id
        record.empleado = fila["Empleado"]
        record.fecha = fila["Fecha"]
        record.entrada = fila["Entrada"]
        record.salida = fila["Salida"]
        record.feriado = fila["Feriado"]
        record.horas_trabajadas = fila["Horas Trabajadas (h:mm)"]
        record.horas_normales = _hhmm_to_decimal(fila["Horas Normales"])
        record.horas_especiales = _hhmm_to_decimal(fila["Horas Especiales"])
        record.monto_horas_normales = float(fila.get("Monto Horas Normales") or 0)
        record.monto_horas_especiales = float(fila.get("Monto Horas Especiales") or 0)
        record.monto_feriado = float(fila.get("Monto Feriado") or 0)
        record.bonificacion = float(fila.get("Bonificacion") or 0)
        record.sueldo_bruto = float(fila.get("Sueldo Bruto") or 0)
        record.descuento_inventario = float(fila["Descuento Inventario"] or 0)
        record.descuento_caja = float(fila["Descuento Caja"] or 0)
        record.retiro = float(fila["Retiro"] or 0)
        record.descuento_ips = float(fila["Descuento IPS"] or 0)
        record.sueldo_final = float(fila["Sueldo Final"] or 0)
        record.observaciones = fila.get("Observaciones", "")
        db.session.add(record)

        payroll = EmployeePayroll()
        payroll.employee_id = employee.id
        payroll.fecha = fila["Fecha"]
        payroll.entrada = fila["Entrada"]
        payroll.salida = fila["Salida"]
        payroll.feriado = fila["Feriado"]
        payroll.horas_trabajadas = fila["Horas Trabajadas (h:mm)"]
        payroll.horas_normales = _hhmm_to_decimal(fila["Horas Normales"])
        payroll.horas_especiales = _hhmm_to_decimal(fila["Horas Especiales"])
        payroll.monto_horas_normales = float(fila.get("Monto Horas Normales") or 0)
        payroll.monto_horas_especiales = float(fila.get("Monto Horas Especiales") or 0)
        payroll.monto_feriado = float(fila.get("Monto Feriado") or 0)
        payroll.bonificacion = float(fila.get("Bonificacion") or 0)
        payroll.sueldo_bruto = float(fila.get("Sueldo Bruto") or 0)
        payroll.descuento_inventario = float(fila["Descuento Inventario"] or 0)
        payroll.descuento_caja = float(fila["Descuento Caja"] or 0)
        payroll.descuento_ips = float(fila["Descuento IPS"] or 0)
        payroll.retiro = float(fila["Retiro"] or 0)
        payroll.sueldo_final = float(fila["Sueldo Final"] or 0)
        payroll.observaciones = fila.get("Observaciones", "")
        payroll.run_id = run.id
        db.session.add(payroll)

    attendance = EmployeeAttendance()
    attendance.employee_id = employee.id
    attendance.run_id = run.id
    attendance.source_name = run.source_name or "asistencia"
    attendance.source_type = run.source_type
    attendance.total_registros = len(resultado["resultados"])
    db.session.add(attendance)

    db.session.commit()
    return run.id, resultado


def _render_confirmacion_reemplazo(empleado: Employee, pendiente_token: str, meses_conflictivos: list[str], registros_conflictivos):
    return render_template(
        "confirm_replace_month.html",
        empleado=empleado,
        pending_token=pendiente_token,
        meses_conflictivos=meses_conflictivos,
        meses_conflictivos_label=[_month_label_from_key(m) for m in meses_conflictivos],
        registros_conflictivos_por_mes=_agrupar_registros_por_mes_key(registros_conflictivos),
    )


# --------------------------------------------------------------------------- #
# Rutas                                                                        #
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    selected_employee_id = request.args.get("empleado_id", type=int)
    empleados = Employee.query.order_by(Employee.nombre).all()
    selected_employee = None
    history_runs = []

    if selected_employee_id:
        selected_employee = db.session.get(Employee, selected_employee_id)
        if selected_employee:
            history_runs = (
                CalculationRun.query.filter_by(employee_id=selected_employee_id)
                .order_by(desc(CalculationRun.created_at))
                .limit(8)
                .all()
            )

    return render_template(
        "index.html",
        empleados=empleados,
        selected_employee=selected_employee,
        selected_employee_id=selected_employee_id,
        history_runs=history_runs,
        valor_default=VALOR_POR_HORA_DEFAULT,
        hoy=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/api/empleados", methods=["GET"])
def api_empleados():
    """Devuelve la lista de empleados en JSON."""
    empleados = Employee.query.order_by(Employee.nombre).all()
    return {
        "empleados": [{"id": e.id, "nombre": e.nombre} for e in empleados]
    }


@app.route("/api/empleados/crear", methods=["POST"])
def api_crear_empleado():
    """Crea un nuevo empleado."""
    datos = request.get_json()
    nombre = (datos.get("nombre") or "").strip()
    
    if not nombre:
        return {"success": False, "error": "El nombre es requerido"}, 400
    
    empleado_existente = Employee.query.filter_by(nombre=nombre).first()
    if empleado_existente:
        return {"success": False, "error": "El empleado ya existe"}, 400
    
    empleado = Employee(nombre=nombre)  # type: ignore[call-arg]
    db.session.add(empleado)
    db.session.commit()
    
    return {
        "success": True,
        "empleado": {"id": empleado.id, "nombre": empleado.nombre}
    }, 201


@app.route("/api/validar-horas", methods=["POST"])
def api_validar_horas():
    """Valida una resta de horas puntual usando la misma lógica del sistema."""
    datos = request.get_json(silent=True) or {}
    entrada = str(datos.get("entrada") or "").strip()
    salida = str(datos.get("salida") or "").strip()

    if not entrada or not salida:
        return {
            "success": False,
            "error": "Los campos entrada y salida son requeridos en formato HH:MM",
        }, 400

    try:
        desglose = _desglose_horas(entrada, salida)
    except ValueError:
        return {
            "success": False,
            "error": "Formato inválido. Usa HH:MM, por ejemplo 10:10 y 17:10",
        }, 400

    return {
        "success": True,
        "metodo": "resta_exacta_entrada_salida",
        "fuente_externa": {
            "url": "https://calculadorasonline.com/calculadora-de-horas-minutos-y-segundos-sumar-horas-restar-horas/",
            "api_publica_detectada": False,
            "nota": "La página pública no expone un endpoint API visible; esta respuesta replica la resta exacta usada para contrastar resultados.",
        },
        "resultado": desglose,
    }


@app.route("/empleado/<int:empleado_id>")
def ver_empleado(empleado_id):
    """Muestra la nómina de un empleado."""
    empleado = db.session.get(Employee, empleado_id)
    if not empleado:
        abort(404)
    
    registros = (
        EmployeePayroll.query.filter_by(employee_id=empleado_id)
        .order_by(desc(EmployeePayroll.created_at))
        .all()
    )
    registros_por_mes = _agrupar_registros_por_mes(registros)
    
    return render_template(
        "employee_payroll.html",
        empleado=empleado,
        registros=registros,
        registros_por_mes=registros_por_mes,
    )


@app.route("/empleado/<int:empleado_id>/descargar_mes/<int:year>/<int:month>")
def descargar_mes(empleado_id, year, month):
    empleado = db.session.get(Employee, empleado_id)
    if not empleado:
        abort(404)

    registros = (
        EmployeePayroll.query.filter_by(employee_id=empleado_id)
        .order_by(desc(EmployeePayroll.created_at))
        .all()
    )
    registros_mes = _filtrar_registros_por_mes(registros, year, month)
    if not registros_mes:
        abort(404)

    formato = request.args.get("format", "xlsx").lower()
    mes_nombre = f"{MESES_ES[month - 1]} {year}"
    base_nombre = _sanear_nombre_para_archivo(f"{empleado.nombre}_{mes_nombre}")

    if formato == "pdf":
        contenido = _crear_pdf_desde_registros(registros_mes, empleado.nombre, mes_nombre)
        mimetype = "application/pdf"
        nombre_archivo = f"{base_nombre}.pdf"
    else:
        contenido = _crear_excel_desde_registros(registros_mes, empleado.nombre, mes_nombre)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        nombre_archivo = f"{base_nombre}.xlsx"

    return send_file(
        contenido,
        mimetype=mimetype,
        as_attachment=True,
        download_name=nombre_archivo,
    )


@app.route("/empleado/<int:empleado_id>/eliminar", methods=["POST"])
def eliminar_empleado(empleado_id):
    empleado = db.session.get(Employee, empleado_id)
    if not empleado:
        flash("El empleado no existe o ya fue eliminado.", "error")
        return redirect(url_for("index"))

    db.session.delete(empleado)
    db.session.commit()
    flash(f"Empleado {empleado.nombre} y sus datos asociados fueron eliminados.", "success")
    return redirect(url_for("index"))


@app.route("/procesar", methods=["POST"])
def procesar():
    try:
        valor_por_hora = float(request.form.get("valor_por_hora", VALOR_POR_HORA_DEFAULT))
    except (TypeError, ValueError):
        valor_por_hora = VALOR_POR_HORA_DEFAULT

    employee_id = request.form.get("employee_id", type=int)
    if not employee_id:
        flash("Selecciona un empleado para asociar la carga de asistencia.", "error")
        return redirect(url_for("index"))

    empleado = db.session.get(Employee, employee_id)
    if not empleado:
        flash("El empleado seleccionado no existe.", "error")
        return redirect(url_for("index"))

    feriados = _parse_feriados(request.form)
    tipo_archivo = request.form.get("file_type", "excel")

    # --- Leer archivo(s) -------------------------------------------------- #
    try:
        if tipo_archivo == "pdf":
            archivos = request.files.getlist("pdf_files") or request.files.getlist("pdf_files[]")
            archivos = [a for a in archivos if a and a.filename]
            if not archivos:
                flash("No se cargó ningún archivo PDF.", "error")
                return redirect(url_for("index"))
            if len(archivos) > 2:
                flash("Máximo 2 archivos PDF permitidos (uno por quincena).", "error")
                return redirect(url_for("index"))

            dataframes, nombres = [], []
            for archivo in archivos:
                df_temp = procesar_pdf_a_dataframe(archivo)
                if df_temp.empty:
                    continue
                es_valido, _ = validar_datos_pdf(df_temp)
                if es_valido:
                    dataframes.append(df_temp)
                    nombres.append(archivo.filename)

            if not dataframes:
                flash(
                    "No se pudieron extraer datos de los PDF. Verifica el contenido.",
                    "error",
                )
                return redirect(url_for("index"))

            df = pd.concat(dataframes, ignore_index=True)
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            df = df.sort_values(["Fecha", "Empleado"]).reset_index(drop=True)
            source_name = (
                nombres[0] if len(nombres) == 1 else f"combinado_{len(nombres)}_pdfs"
            )
        else:
            archivo = request.files.get("excel_file")
            if not archivo or not archivo.filename:
                flash("No se cargó ningún archivo Excel.", "error")
                return redirect(url_for("index"))
            df = pd.read_excel(archivo)
            es_valido, faltantes = validar_archivo_excel(df)
            if not es_valido:
                flash(
                    "El Excel no contiene las columnas: " + ", ".join(faltantes),
                    "error",
                )
                return redirect(url_for("index"))
            source_name = archivo.filename
    except Exception as e:  # noqa: BLE001
        flash(f"Error al procesar el archivo: {e}", "error")
        return redirect(url_for("index"))

    # --- Filtrar sin asistencia y detectar problemas --------------------- #
    df_con_asistencia, df_sin_asistencia = filtrar_registros_sin_asistencia(df)
    df = df_con_asistencia.reset_index(drop=True)

    coincidencia = df["Empleado"].astype(str).apply(lambda x: _empleado_coincide(x, empleado))
    df = df[coincidencia].copy()
    if df.empty:
        flash(
            f"No se encontraron registros de asistencia para {empleado.nombre} en el archivo.",
            "error",
        )
        return redirect(url_for("index", empleado_id=employee_id))

    df.loc[:, "Empleado"] = empleado.nombre

    df_incompletos = detectar_registros_incompletos(df)
    df_ambiguos = detectar_horarios_ambiguos(df)

    ips_value = (request.form.get("seguro_ips", "No") or "No").strip().lower()
    ips_enabled = ips_value in ("sí", "si", "s", "yes", "true")

    config = {
        "valor_por_hora": valor_por_hora,
        "feriados": list(feriados),
        "source_name": source_name,
        "source_type": tipo_archivo,
        "excluidos": len(df_sin_asistencia),
        "employee_id": employee_id,
        "ips_enabled": ips_enabled,
    }

    meses_df = _obtener_meses_df(df)
    meses_conflictivos, registros_conflictivos = _obtener_conflictos_mes_empleado(
        employee_id,
        meses_df,
    )
    if meses_conflictivos:
        config["meses_conflictivos"] = meses_conflictivos
        token_reemplazo = _guardar_pendiente(df, config)
        session["replace_pending_token"] = token_reemplazo
        return _render_confirmacion_reemplazo(
            empleado,
            token_reemplazo,
            meses_conflictivos,
            registros_conflictivos,
        )

    if not df_incompletos.empty or not df_ambiguos.empty:
        token = _guardar_pendiente(df, config)
        session["pending_token"] = token
        return render_template(
            "corrections.html",
            incompletos=_df_incompletos_a_lista(df_incompletos),
            ambiguos=_df_ambiguos_a_lista(df_ambiguos),
            excluidos=len(df_sin_asistencia),
        )

    run_id, _ = _calcular_y_guardar(df, config, empleado)
    return redirect(url_for("resultado", run_id=run_id))


@app.route("/correcciones", methods=["POST"])
def correcciones():
    token = session.get("pending_token")
    pendiente = _cargar_pendiente(token)
    if not pendiente:
        flash("La sesión de corrección expiró. Vuelve a subir el archivo.", "error")
        return redirect(url_for("index"))

    df = pendiente["df"].copy()
    config = pendiente["config"]
    employee_id = config.get("employee_id")
    empleado = db.session.get(Employee, employee_id)
    if not empleado:
        flash("El empleado asociado a la corrección ya no existe.", "error")
        return redirect(url_for("index"))

    # Registros incompletos: el admin indica si la marca fue Entrada o Salida
    # y aporta el horario faltante.
    df = _aplicar_correcciones_incompletos(df, pendiente["df"], request.form)

    # Horarios ambiguos: intercambiar entrada <-> salida
    for key in request.form:
        if key.startswith("intercambiar_"):
            idx = int(key.split("_", 1)[1])
            entrada = df.at[idx, "Entrada"]
            df.at[idx, "Entrada"] = df.at[idx, "Salida"]
            df.at[idx, "Salida"] = entrada

    _eliminar_pendiente(token)
    session.pop("pending_token", None)

    meses_df = _obtener_meses_df(df)
    meses_conflictivos, registros_conflictivos = _obtener_conflictos_mes_empleado(
        employee_id,
        meses_df,
    )
    if meses_conflictivos:
        config["meses_conflictivos"] = meses_conflictivos
        token_reemplazo = _guardar_pendiente(df, config)
        session["replace_pending_token"] = token_reemplazo
        return _render_confirmacion_reemplazo(
            empleado,
            token_reemplazo,
            meses_conflictivos,
            registros_conflictivos,
        )

    run_id, _ = _calcular_y_guardar(df, config, empleado)
    return redirect(url_for("resultado", run_id=run_id))


@app.route("/actualizar-mes", methods=["POST"])
def actualizar_mes():
    token = request.form.get("pending_token") or session.get("replace_pending_token")
    pendiente = _cargar_pendiente(token)
    if not pendiente:
        flash("La solicitud de actualización expiró. Vuelve a cargar el archivo.", "error")
        return redirect(url_for("index"))

    df = pendiente["df"].copy()
    config = pendiente["config"]
    employee_id = config.get("employee_id")
    empleado = db.session.get(Employee, employee_id)
    if not empleado:
        flash("El empleado asociado a la actualización ya no existe.", "error")
        return redirect(url_for("index"))

    meses_df = _obtener_meses_df(df)
    _reemplazar_meses_existentes(employee_id, meses_df)

    _eliminar_pendiente(token)
    session.pop("replace_pending_token", None)

    run_id, _ = _calcular_y_guardar(df, config, empleado)
    flash("Se actualizó el mes y se reemplazaron los registros anteriores.", "success")
    return redirect(url_for("resultado", run_id=run_id))


def _aplicar_correcciones_incompletos(df, df_original, form):
    """
    Completa registros incompletos respetando el horario realmente registrado.
    El administrador indica si la marca registrada fue Entrada o Salida y aporta
    el horario faltante.
    """
    for key in list(form.keys()):
        if not key.startswith("tipo_"):
            continue
        idx = int(key.split("_", 1)[1])
        tipo = form.get(key)
        hora_faltante = (form.get(f"hora_{idx}") or "").strip()
        if not hora_faltante:
            continue

        ent_orig = str(df_original.at[idx, "Entrada"]).strip()
        sal_orig = str(df_original.at[idx, "Salida"]).strip()
        registrado = sal_orig if ent_orig in ("", "nan", "0:00", "00:00") else ent_orig

        if tipo == "Entrada":
            df.at[idx, "Entrada"] = registrado
            df.at[idx, "Salida"] = hora_faltante
        else:
            df.at[idx, "Entrada"] = hora_faltante
            df.at[idx, "Salida"] = registrado

    return df


@app.route("/resultado/<int:run_id>")
def resultado(run_id):
    run = db.session.get(CalculationRun, run_id)
    if not run:
        abort(404)
    _recalcular_run_legado(run)
    records = cast(list[EmployeeRecord], list(getattr(run, "records", []) or []))
    return render_template("results.html", run=run, records=records)


@app.route("/descargar/<int:run_id>")
def descargar(run_id):
    run = db.session.get(CalculationRun, run_id)
    if not run:
        abort(404)

    _recalcular_run_legado(run)
    records = cast(list[EmployeeRecord], list(getattr(run, "records", []) or []))
    filas = []
    for r in records:
        filas.append(
            {
                "Empleado": r.empleado,
                "Fecha": r.fecha,
                "Entrada": r.entrada,
                "Salida": r.salida,
                "Feriado": r.feriado,
                "Horas Trabajadas (h:mm)": r.horas_trabajadas,
                "Horas Normales": horas_a_horasminutos(r.horas_normales),
                "Horas Especiales": horas_a_horasminutos(r.horas_especiales),
                "Descuento Inventario": r.descuento_inventario,
                "Descuento Caja": r.descuento_caja,
                "Retiro": r.retiro,
                "Sueldo Final": r.sueldo_final,
            }
        )

    df = pd.DataFrame(filas)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sueldos")
    output.seek(0)

    base = (run.source_name or "sueldos").replace(".pdf", "").replace(".xlsx", "")
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{base}_calculado.xlsx",
    )


@app.route("/plantilla")
def plantilla():
    ruta = os.path.join(BASE_DIR, "plantilla_sueldos_feriados_dias.xlsx")
    if not os.path.exists(ruta):
        abort(404)
    return send_file(
        ruta,
        as_attachment=True,
        download_name="plantilla_sueldo.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/eliminar/<int:run_id>", methods=["POST"])
def eliminar(run_id):
    run = db.session.get(CalculationRun, run_id)
    if run:
        db.session.delete(run)
        db.session.commit()
        flash("Cálculo eliminado del historial.", "success")
    return redirect(url_for("index"))


def _ensure_missing_employee_columns():
    engine = db.engine
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    def ensure_column(table_name: str, column_name: str, ddl: str) -> None:
        if table_name not in table_names:
            return
        current_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if column_name in current_columns:
            return
        with engine.begin() as connection:
            connection.execute(text(ddl))
        app.logger.info("Added missing %s column to %s table", column_name, table_name)

    ensure_column(
        "calculation_runs",
        "employee_id",
        "ALTER TABLE calculation_runs ADD COLUMN employee_id INTEGER",
    )
    ensure_column(
        "calculation_runs",
        "seguro_ips",
        "ALTER TABLE calculation_runs ADD COLUMN seguro_ips VARCHAR(5) NOT NULL DEFAULT 'No'",
    )
    ensure_column(
        "calculation_runs",
        "total_salario_bruto",
        "ALTER TABLE calculation_runs ADD COLUMN total_salario_bruto FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_descuento_ips",
        "ALTER TABLE calculation_runs ADD COLUMN total_descuento_ips FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_aporte_empleador_ips",
        "ALTER TABLE calculation_runs ADD COLUMN total_aporte_empleador_ips FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_ips",
        "ALTER TABLE calculation_runs ADD COLUMN total_ips FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_salario_neto_ips",
        "ALTER TABLE calculation_runs ADD COLUMN total_salario_neto_ips FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_monto_horas_normales",
        "ALTER TABLE calculation_runs ADD COLUMN total_monto_horas_normales FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_monto_horas_especiales",
        "ALTER TABLE calculation_runs ADD COLUMN total_monto_horas_especiales FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_monto_feriados",
        "ALTER TABLE calculation_runs ADD COLUMN total_monto_feriados FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "calculation_runs",
        "total_bonificacion",
        "ALTER TABLE calculation_runs ADD COLUMN total_bonificacion FLOAT NOT NULL DEFAULT 0",
    )

    ensure_column(
        "employee_records",
        "employee_id",
        "ALTER TABLE employee_records ADD COLUMN employee_id INTEGER",
    )
    ensure_column(
        "employee_records",
        "descuento_ips",
        "ALTER TABLE employee_records ADD COLUMN descuento_ips FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_records",
        "monto_horas_normales",
        "ALTER TABLE employee_records ADD COLUMN monto_horas_normales FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_records",
        "monto_horas_especiales",
        "ALTER TABLE employee_records ADD COLUMN monto_horas_especiales FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_records",
        "monto_feriado",
        "ALTER TABLE employee_records ADD COLUMN monto_feriado FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_records",
        "bonificacion",
        "ALTER TABLE employee_records ADD COLUMN bonificacion FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_records",
        "sueldo_bruto",
        "ALTER TABLE employee_records ADD COLUMN sueldo_bruto FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_payroll",
        "descuento_ips",
        "ALTER TABLE employee_payroll ADD COLUMN descuento_ips FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_payroll",
        "monto_horas_normales",
        "ALTER TABLE employee_payroll ADD COLUMN monto_horas_normales FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_payroll",
        "monto_horas_especiales",
        "ALTER TABLE employee_payroll ADD COLUMN monto_horas_especiales FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_payroll",
        "monto_feriado",
        "ALTER TABLE employee_payroll ADD COLUMN monto_feriado FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_payroll",
        "bonificacion",
        "ALTER TABLE employee_payroll ADD COLUMN bonificacion FLOAT NOT NULL DEFAULT 0",
    )
    ensure_column(
        "employee_payroll",
        "sueldo_bruto",
        "ALTER TABLE employee_payroll ADD COLUMN sueldo_bruto FLOAT NOT NULL DEFAULT 0",
    )


with app.app_context():
    db.create_all()
    _ensure_missing_employee_columns()

    # Crear empleados iniciales solo si la tabla de empleados está vacía.
    # Esto evita que un empleado eliminado vuelva a aparecer al reiniciar la aplicación.
    if Employee.query.count() == 0:
        empleados_iniciales = ["Paz", "Yanina Gomez"]
        for nombre in empleados_iniciales:
            empleado = Employee(nombre=nombre)  # type: ignore[call-arg]
            db.session.add(empleado)
        db.session.commit()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

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
import uuid
from datetime import datetime
from typing import cast

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

from payroll.data_processor import procesar_datos_excel, validar_archivo_excel
from payroll.models import CalculationRun, Employee, EmployeePayroll, EmployeeRecord, db
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

from payroll.calculations import horas_a_horasminutos


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


def _fecha_str(valor):
    try:
        return pd.to_datetime(valor).strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001
        return str(valor)


def _calcular_y_guardar(df, config):
    """Ejecuta el cálculo y guarda el resultado en la base de datos."""
    resultado = procesar_datos_excel(df, config["valor_por_hora"], set(config["feriados"]))

    run = CalculationRun()
    run.source_name = config.get("source_name")
    run.source_type = config.get("source_type", "excel")
    run.valor_por_hora = config["valor_por_hora"]
    run.feriados = (
        ", ".join(d.strftime("%d/%m/%Y") for d in sorted(config["feriados"]))
        if config["feriados"]
        else None
    )
    run.total_horas = resultado["total_horas"]
    run.total_horas_normales = resultado["total_horas_normales"]
    run.total_horas_especiales = resultado["total_horas_especiales"]
    run.total_sueldos = resultado["total_sueldos"]
    run.total_registros = len(resultado["resultados"])

    for fila in resultado["resultados"]:
        record = EmployeeRecord()
        record.empleado = fila["Empleado"]
        record.fecha = fila["Fecha"]
        record.entrada = fila["Entrada"]
        record.salida = fila["Salida"]
        record.feriado = fila["Feriado"]
        record.horas_trabajadas = fila["Horas Trabajadas (h:mm)"]
        record.horas_normales = fila["Horas Normales"]
        record.horas_especiales = fila["Horas Especiales"]
        record.descuento_inventario = float(fila["Descuento Inventario"] or 0)
        record.descuento_caja = float(fila["Descuento Caja"] or 0)
        record.retiro = float(fila["Retiro"] or 0)
        record.sueldo_final = float(fila["Sueldo Final"] or 0)
        record.observaciones = fila.get("Observaciones", "")
        run.records.append(record)

        # Guardar también en la tabla de nómina individual del empleado
        empleado_nombre = fila["Empleado"]
        empleado = Employee.query.filter_by(nombre=empleado_nombre).first()
        if not empleado:
            empleado = Employee(nombre=empleado_nombre)  # type: ignore[call-arg]
            db.session.add(empleado)
            db.session.flush()

        payroll = EmployeePayroll()
        payroll.employee_id = empleado.id
        payroll.fecha = fila["Fecha"]
        payroll.entrada = fila["Entrada"]
        payroll.salida = fila["Salida"]
        payroll.feriado = fila["Feriado"]
        payroll.horas_trabajadas = fila["Horas Trabajadas (h:mm)"]
        payroll.horas_normales = float(fila["Horas Normales"] or 0)
        payroll.horas_especiales = float(fila["Horas Especiales"] or 0)
        payroll.descuento_inventario = float(fila["Descuento Inventario"] or 0)
        payroll.descuento_caja = float(fila["Descuento Caja"] or 0)
        payroll.retiro = float(fila["Retiro"] or 0)
        payroll.sueldo_final = float(fila["Sueldo Final"] or 0)
        payroll.observaciones = fila.get("Observaciones", "")
        payroll.run_id = run.id
        db.session.add(payroll)

    db.session.add(run)
    db.session.commit()
    return run.id, resultado


# --------------------------------------------------------------------------- #
# Rutas                                                                        #
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    runs = (
        CalculationRun.query.order_by(CalculationRun.created_at.desc()).limit(8).all()  # type: ignore[attr-defined]
    )
    empleados = Employee.query.order_by(Employee.nombre).all()
    return render_template(
        "index.html",
        runs=runs,
        empleados=empleados,
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


@app.route("/empleado/<int:empleado_id>")
def ver_empleado(empleado_id):
    """Muestra la nómina de un empleado."""
    empleado = db.session.get(Employee, empleado_id)
    if not empleado:
        abort(404)
    
    registros = (
        EmployeePayroll.query.filter_by(employee_id=empleado_id)
        .order_by(EmployeePayroll.created_at.desc())  # type: ignore[attr-defined]
        .all()
    )
    
    return render_template(
        "employee_payroll.html",
        empleado=empleado,
        registros=registros
    )


@app.route("/procesar", methods=["POST"])
def procesar():
    try:
        valor_por_hora = float(request.form.get("valor_por_hora", VALOR_POR_HORA_DEFAULT))
    except (TypeError, ValueError):
        valor_por_hora = VALOR_POR_HORA_DEFAULT

    feriados = _parse_feriados(request.form)
    tipo_archivo = request.form.get("file_type", "excel")

    # --- Leer archivo(s) -------------------------------------------------- #
    try:
        if tipo_archivo == "pdf":
            archivos = request.files.getlist("pdf_files")
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

    df_incompletos = detectar_registros_incompletos(df)
    df_ambiguos = detectar_horarios_ambiguos(df)

    config = {
        "valor_por_hora": valor_por_hora,
        "feriados": list(feriados),
        "source_name": source_name,
        "source_type": tipo_archivo,
        "excluidos": len(df_sin_asistencia),
    }

    if not df_incompletos.empty or not df_ambiguos.empty:
        token = _guardar_pendiente(df, config)
        session["pending_token"] = token
        return render_template(
            "corrections.html",
            incompletos=_df_incompletos_a_lista(df_incompletos),
            ambiguos=_df_ambiguos_a_lista(df_ambiguos),
            excluidos=len(df_sin_asistencia),
        )

    run_id, _ = _calcular_y_guardar(df, config)
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

    run_id, _ = _calcular_y_guardar(df, config)
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
    records = cast(list[EmployeeRecord], list(getattr(run, "records", []) or []))
    return render_template("results.html", run=run, records=records)


@app.route("/descargar/<int:run_id>")
def descargar(run_id):
    run = db.session.get(CalculationRun, run_id)
    if not run:
        abort(404)

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
                "Horas Normales": r.horas_normales,
                "Horas Especiales": r.horas_especiales,
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


with app.app_context():
    db.create_all()
    
    # Crear empleados iniciales si no existen
    empleados_iniciales = ["Paz Tatiana", "Yanina Gomez"]
    for nombre in empleados_iniciales:
        empleado_existente = Employee.query.filter_by(nombre=nombre).first()
        if not empleado_existente:
            empleado = Employee(nombre=nombre)  # type: ignore[call-arg]
            db.session.add(empleado)
    db.session.commit()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

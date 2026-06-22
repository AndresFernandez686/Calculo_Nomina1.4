"""
Módulo de procesamiento de datos (versión Flask, sin Streamlit).

Contiene la lógica de negocio para validar y calcular sueldos a partir de
un DataFrame de pandas. Todas las funciones devuelven datos (no renderizan UI).
"""
from datetime import datetime, timedelta

import pandas as pd

from .calculations import calcular_horas_especiales, horas_a_horasminutos

REQUIRED_COLS = [
    "Empleado",
    "Fecha",
    "Entrada",
    "Salida",
    "Descuento Inventario",
    "Descuento Caja",
    "Retiro",
]


def detectar_y_resolver_marcaciones_duplicadas(df):
    """
    Detecta cuando un empleado marcó 3 veces en un mismo día y selecciona
    automáticamente solo 2 marcas, eliminando duplicados cercanos (10-20 min).

    Returns:
        tuple: (DataFrame procesado, lista de strings con duplicados resueltos)
    """
    df_procesado = df.copy()
    registros_procesados = []
    empleados_con_duplicados = []

    for (empleado, fecha), grupo in df_procesado.groupby(["Empleado", "Fecha"]):
        if len(grupo) == 3:
            empleados_con_duplicados.append(f"{empleado} - {fecha}")

            marcaciones = []
            for idx, row in grupo.iterrows():
                try:
                    entrada = pd.to_datetime(str(row["Entrada"])).time()
                    salida = pd.to_datetime(str(row["Salida"])).time()
                    fecha_dt = pd.to_datetime(row["Fecha"])

                    entrada_dt = datetime.combine(fecha_dt, entrada)
                    salida_dt = datetime.combine(fecha_dt, salida)

                    marcaciones.append(
                        {"index": idx, "entrada": entrada_dt, "salida": salida_dt, "row": row}
                    )
                except Exception:
                    marcaciones.append(
                        {"index": idx, "entrada": None, "salida": None, "row": row}
                    )

            # Crear marcación óptima: entrada más temprana + salida más tardía
            entrada_mas_temprana = min(marcaciones, key=lambda x: x["entrada"])
            salida_mas_tardia = max(marcaciones, key=lambda x: x["salida"])

            marcacion_principal = entrada_mas_temprana["row"].copy()
            marcacion_principal["Entrada"] = entrada_mas_temprana["entrada"].strftime("%H:%M")
            marcacion_principal["Salida"] = salida_mas_tardia["salida"].strftime("%H:%M")
            registros_procesados.append(marcacion_principal)

            segunda_marcacion = None
            for marc in marcaciones:
                diff_entrada = abs(
                    (marc["entrada"] - entrada_mas_temprana["entrada"]).total_seconds() / 60
                )
                diff_salida = abs(
                    (marc["salida"] - salida_mas_tardia["salida"]).total_seconds() / 60
                )
                if diff_entrada > 20 or diff_salida > 20:
                    segunda_marcacion = marc["row"]
                    break

            if segunda_marcacion is not None:
                registros_procesados.append(segunda_marcacion)
            elif len(marcaciones) >= 2:
                marcaciones_ordenadas = sorted(marcaciones, key=lambda x: x["entrada"])
                registros_procesados.append(marcaciones_ordenadas[1]["row"])
        else:
            for idx, row in grupo.iterrows():
                registros_procesados.append(row)

    df_resultado = pd.DataFrame(registros_procesados)
    return df_resultado, empleados_con_duplicados


def validar_archivo_excel(df):
    """Valida que el DataFrame contenga las columnas necesarias."""
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    return len(missing_cols) == 0, missing_cols


def procesar_datos_excel(df, valor_por_hora, fechas_feriados):
    """
    Procesa los datos y calcula los sueldos.

    Returns:
        dict con: resultados, total_horas, total_sueldos, total_horas_normales,
        total_horas_especiales, duplicados, errores.
    """
    df_procesado, duplicados = detectar_y_resolver_marcaciones_duplicadas(df)

    resultados = []
    total_horas = 0.0
    total_sueldos = 0.0
    total_horas_normales = 0.0
    total_horas_especiales = 0.0
    errores = []

    for idx, row in df_procesado.iterrows():
        try:
            resultado_fila = _procesar_fila(row, idx, valor_por_hora, fechas_feriados)
            if resultado_fila:
                resultados.append(resultado_fila["datos"])
                total_horas += resultado_fila["horas"]
                total_sueldos += resultado_fila["sueldo"]
                total_horas_normales += resultado_fila.get("horas_normales", 0)
                total_horas_especiales += resultado_fila.get("horas_especiales", 0)
        except Exception as e:  # noqa: BLE001
            if isinstance(idx, int):
                fila_num = idx + 2
            elif isinstance(idx, str) and idx.isdigit():
                fila_num = int(idx) + 2
            else:
                fila_num = 0
            errores.append(f"Error en la fila {fila_num}: {e}")

    return {
        "resultados": resultados,
        "total_horas": total_horas,
        "total_sueldos": total_sueldos,
        "total_horas_normales": total_horas_normales,
        "total_horas_especiales": total_horas_especiales,
        "duplicados": duplicados,
        "errores": errores,
    }


def _procesar_fila(row, idx, valor_por_hora, fechas_feriados):
    """
    Procesa una fila individual:
    - Validación de horario laboral (10:30 - 22:00)
    - Horas normales x tarifa
    - Horas especiales (20:00-22:00) x tarifa x 1.3
    - Factor de feriado x2 si aplica
    """
    fecha = pd.to_datetime(row["Fecha"])
    entrada = pd.to_datetime(str(row["Entrada"])).time()
    salida = pd.to_datetime(str(row["Salida"])).time()

    entrada_dt = datetime.combine(fecha, entrada)
    salida_dt = datetime.combine(fecha, salida)
    if salida_dt < entrada_dt:
        salida_dt += timedelta(days=1)

    hora_inicio_laboral = datetime.combine(fecha, datetime.strptime("10:30", "%H:%M").time())
    hora_fin_laboral = datetime.combine(fecha, datetime.strptime("22:00", "%H:%M").time())

    if entrada_dt < hora_inicio_laboral or entrada_dt > hora_fin_laboral:
        return {
            "datos": {
                "Empleado": row["Empleado"],
                "Fecha": fecha.strftime("%Y-%m-%d"),
                "Entrada": entrada.strftime("%H:%M"),
                "Salida": salida.strftime("%H:%M"),
                "Feriado": "No",
                "Horas Trabajadas (h:mm)": "0:00",
                "Horas Normales": "0:00",
                "Horas Especiales": "0:00",
                "Descuento Inventario": 0,
                "Descuento Caja": 0,
                "Retiro": 0,
                "Sueldo Final": 0,
                "Observaciones": "Fuera de horario laboral (10:30-22:00)",
            },
            "horas": 0,
            "sueldo": 0,
            "horas_normales": 0,
            "horas_especiales": 0,
        }

    if salida_dt > hora_fin_laboral + timedelta(
        days=1 if salida_dt.date() > entrada_dt.date() else 0
    ):
        salida_dt = hora_fin_laboral

    horas_trabajadas_decimal = (salida_dt - entrada_dt).total_seconds() / 3600
    horas_normales, horas_especiales = calcular_horas_especiales(entrada_dt, salida_dt)

    es_feriado = fecha.date() in fechas_feriados
    factor_feriado = 2 if es_feriado else 1

    sueldo_normal = horas_normales * valor_por_hora
    sueldo_especial = horas_especiales * valor_por_hora * 1.3
    sueldo_bruto = (sueldo_normal + sueldo_especial) * factor_feriado

    descuento_inventario = (
        row["Descuento Inventario"] if not pd.isnull(row["Descuento Inventario"]) else 0
    )
    descuento_caja = row["Descuento Caja"] if not pd.isnull(row["Descuento Caja"]) else 0
    retiro = row["Retiro"] if not pd.isnull(row["Retiro"]) else 0

    sueldo_final = sueldo_bruto - descuento_inventario - descuento_caja - retiro

    datos_fila = {
        "Empleado": row["Empleado"],
        "Fecha": fecha.strftime("%Y-%m-%d"),
        "Entrada": entrada.strftime("%H:%M"),
        "Salida": salida.strftime("%H:%M"),
        "Feriado": "Sí" if es_feriado else "No",
        "Horas Trabajadas (h:mm)": horas_a_horasminutos(horas_trabajadas_decimal),
        "Horas Normales": horas_a_horasminutos(horas_normales),
        "Horas Especiales": horas_a_horasminutos(horas_especiales),
        "Descuento Inventario": descuento_inventario,
        "Descuento Caja": descuento_caja,
        "Retiro": retiro,
        "Sueldo Final": round(sueldo_final, 2),
        "Observaciones": "",
    }

    return {
        "datos": datos_fila,
        "horas": horas_trabajadas_decimal,
        "sueldo": sueldo_final,
        "horas_normales": horas_normales,
        "horas_especiales": horas_especiales,
    }

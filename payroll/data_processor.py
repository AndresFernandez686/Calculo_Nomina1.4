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


def procesar_datos_excel(df, valor_por_hora, fechas_feriados, ips_enabled=False):
    """
    Procesa los datos y calcula los sueldos.

    Returns:
        dict con: resultados, total_horas, total_sueldos, total_horas_normales,
        total_horas_especiales, total_salario_bruto, total_descuento_ips,
        total_aporte_empleador_ips, total_ips, total_salario_neto_ips,
        duplicados, errores.
    """
    df_procesado, duplicados = detectar_y_resolver_marcaciones_duplicadas(df)

    resultados = []
    total_horas = 0.0
    total_sueldos = 0.0
    total_horas_normales = 0.0
    total_horas_especiales = 0.0
    total_monto_horas_normales = 0.0
    total_monto_horas_especiales = 0.0
    total_monto_feriados = 0.0
    total_bonificacion = 0.0
    total_salario_bruto = 0.0
    total_descuento_ips = 0.0
    total_aporte_empleador_ips = 0.0
    total_ips = 0.0
    total_salario_neto_ips = 0.0
    errores = []

    for idx, row in df_procesado.iterrows():
        try:
            resultado_fila = _procesar_fila(row, idx, valor_por_hora, fechas_feriados, ips_enabled)
            if resultado_fila:
                resultados.append(resultado_fila["datos"])
                total_horas += resultado_fila["horas"]
                total_sueldos += resultado_fila["sueldo"]
                total_horas_normales += resultado_fila.get("horas_normales", 0)
                total_horas_especiales += resultado_fila.get("horas_especiales", 0)
                total_monto_horas_normales += resultado_fila.get("monto_horas_normales", 0)
                total_monto_horas_especiales += resultado_fila.get("monto_horas_especiales", 0)
                total_monto_feriados += resultado_fila.get("monto_feriado", 0)
                total_bonificacion += resultado_fila.get("bonificacion", 0)
                total_salario_bruto += resultado_fila.get("salario_bruto", 0)
                total_descuento_ips += resultado_fila.get("descuento_ips", 0)
                total_aporte_empleador_ips += resultado_fila.get("aporte_empleador_ips", 0)
                total_ips += resultado_fila.get("total_ips", 0)
                total_salario_neto_ips += resultado_fila.get("salario_neto_ips", 0)
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
        "total_monto_horas_normales": total_monto_horas_normales,
        "total_monto_horas_especiales": total_monto_horas_especiales,
        "total_monto_feriados": total_monto_feriados,
        "total_bonificacion": total_bonificacion,
        "total_salario_bruto": total_salario_bruto,
        "total_descuento_ips": total_descuento_ips,
        "total_aporte_empleador_ips": total_aporte_empleador_ips,
        "total_ips": total_ips,
        "total_salario_neto_ips": total_salario_neto_ips,
        "duplicados": duplicados,
        "errores": errores,
    }


def _procesar_fila(row, idx, valor_por_hora, fechas_feriados, ips_enabled=False):
    """
    Procesa una fila individual:
    - Horas normales x tarifa
    - Horas especiales (20:00-22:00) x tarifa x 1.3
    - Factor de feriado x2 si aplica
    - Aportes de IPS cuando corresponde
    """
    fecha = pd.to_datetime(row["Fecha"])
    entrada = pd.to_datetime(str(row["Entrada"])).time()
    salida = pd.to_datetime(str(row["Salida"])).time()

    entrada_dt = datetime.combine(fecha, entrada)
    salida_dt = datetime.combine(fecha, salida)
    if salida_dt < entrada_dt:
        salida_dt += timedelta(days=1)

    if salida_dt <= entrada_dt:
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
                "Monto Horas Normales": 0,
                "Monto Horas Especiales": 0,
                "Monto Feriado": 0,
                "Bonificacion": 0,
                "Descuento Inventario": 0,
                "Descuento Caja": 0,
                "Retiro": 0,
                "Sueldo Bruto": 0,
                "Descuento IPS": 0,
                "Aporte Empleador IPS": 0,
                "Total IPS": 0,
                "Salario Neto IPS": 0,
                "Sueldo Final": 0,
                "Observaciones": "Horario sin duracion valida",
            },
            "horas": 0,
            "sueldo": 0,
            "horas_normales": 0,
            "horas_especiales": 0,
            "monto_horas_normales": 0,
            "monto_horas_especiales": 0,
            "monto_feriado": 0,
            "bonificacion": 0,
        }

    horas_trabajadas_decimal = (salida_dt - entrada_dt).total_seconds() / 3600
    horas_normales, horas_especiales = calcular_horas_especiales(entrada_dt, salida_dt)

    es_feriado = fecha.date() in fechas_feriados
    factor_feriado = 2 if es_feriado else 1

    monto_horas_normales = round(horas_normales * valor_por_hora, 2)
    monto_horas_especiales = round(horas_especiales * valor_por_hora * 1.3, 2)
    monto_base = round(monto_horas_normales + monto_horas_especiales, 2)
    monto_feriado = round(monto_base, 2) if es_feriado else 0.0
    bonificacion = 0.0
    sueldo_bruto = round(monto_base + monto_feriado + bonificacion, 2)

    descuento_ips = round(sueldo_bruto * 0.09, 2) if ips_enabled else 0.0
    aporte_empleador_ips = round(sueldo_bruto * 0.165, 2) if ips_enabled else 0.0
    total_ips = round(descuento_ips + aporte_empleador_ips, 2)
    salario_neto_ips = round(sueldo_bruto - descuento_ips, 2)

    descuento_inventario = (
        row["Descuento Inventario"] if not pd.isnull(row["Descuento Inventario"]) else 0
    )
    descuento_caja = row["Descuento Caja"] if not pd.isnull(row["Descuento Caja"]) else 0
    retiro = row["Retiro"] if not pd.isnull(row["Retiro"]) else 0

    sueldo_final = round(
        sueldo_bruto - descuento_ips - descuento_inventario - descuento_caja - retiro,
        2,
    )

    datos_fila = {
        "Empleado": row["Empleado"],
        "Fecha": fecha.strftime("%Y-%m-%d"),
        "Entrada": entrada.strftime("%H:%M"),
        "Salida": salida.strftime("%H:%M"),
        "Feriado": "Sí" if es_feriado else "No",
        "Horas Trabajadas (h:mm)": horas_a_horasminutos(horas_trabajadas_decimal),
        "Horas Normales": horas_a_horasminutos(horas_normales),
        "Horas Especiales": horas_a_horasminutos(horas_especiales),
        "Monto Horas Normales": monto_horas_normales,
        "Monto Horas Especiales": monto_horas_especiales,
        "Monto Feriado": monto_feriado,
        "Bonificacion": bonificacion,
        "Descuento Inventario": descuento_inventario,
        "Descuento Caja": descuento_caja,
        "Retiro": retiro,
        "Sueldo Bruto": sueldo_bruto,
        "Descuento IPS": descuento_ips,
        "Aporte Empleador IPS": aporte_empleador_ips,
        "Total IPS": total_ips,
        "Salario Neto IPS": salario_neto_ips,
        "Sueldo Final": sueldo_final,
        "Observaciones": "",
    }

    return {
        "datos": datos_fila,
        "horas": horas_trabajadas_decimal,
        "sueldo": sueldo_final,
        "horas_normales": horas_normales,
        "horas_especiales": horas_especiales,
        "monto_horas_normales": monto_horas_normales,
        "monto_horas_especiales": monto_horas_especiales,
        "monto_feriado": monto_feriado,
        "bonificacion": bonificacion,
        "salario_bruto": sueldo_bruto,
        "descuento_ips": descuento_ips,
        "aporte_empleador_ips": aporte_empleador_ips,
        "total_ips": total_ips,
        "salario_neto_ips": salario_neto_ips,
    }

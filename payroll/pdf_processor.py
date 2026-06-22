"""
Módulo para procesamiento inteligente de PDFs (versión Flask, sin Streamlit).

Convierte PDFs con formatos diversos a la estructura estándar usada por el
sistema de cálculo de sueldos.
"""
import re
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd


PATRON_FECHA_HORA = re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?")


def procesar_pdf_a_dataframe(archivo_pdf) -> pd.DataFrame:
    """Procesa un archivo PDF y extrae datos de empleados y horarios."""
    try:
        texto_pdf = extraer_texto_pdf(archivo_pdf)
        lineas = texto_pdf.split("\n")

        estructura = analizar_estructura_pdf(lineas)
        datos_brutos = extraer_datos_segun_estructura(lineas, estructura)
        datos_procesados = procesar_datos_inteligente(datos_brutos)
        df_final = convertir_a_dataframe_estandar(datos_procesados)
        return df_final
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def extraer_texto_pdf(archivo_pdf) -> str:
    """Extrae texto del PDF usando pdfplumber."""
    import pdfplumber

    lineas_documento: List[str] = []
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            lineas_tabulares = _extraer_lineas_tabulares(pagina)
            if lineas_tabulares:
                lineas_documento.extend(lineas_tabulares)
                continue

            texto_pagina = pagina.extract_text()
            if texto_pagina:
                lineas_documento.extend(texto_pagina.splitlines())
    return "\n".join(lineas_documento)


def _extraer_lineas_tabulares(pagina) -> List[str]:
    """Convierte tablas del PDF a líneas tabuladas para conservar columnas."""
    lineas = []
    for tabla in pagina.extract_tables() or []:
        for fila in tabla:
            if not fila:
                continue

            celdas = [re.sub(r"\s+", " ", str(celda or "")).strip() for celda in fila]
            celdas_no_vacias = [celda for celda in celdas if celda]
            if len(celdas_no_vacias) < 2:
                continue

            linea = "\t".join(celdas)
            if _parece_fila_asistencia(linea) or _parece_encabezado_tabla(celdas_no_vacias):
                lineas.append(linea)
    return lineas


def _parece_fila_asistencia(linea: str) -> bool:
    return bool(PATRON_FECHA_HORA.search(linea))


def _parece_encabezado_tabla(celdas: List[str]) -> bool:
    encabezados = " ".join(celdas).lower()
    return "nombre" in encabezados and "hora" in encabezados


def analizar_estructura_pdf(lineas: List[str]) -> Dict:
    """Analiza la estructura del PDF para identificar patrones."""
    estructura = {
        "tipo": "desconocido",
        "patron_empleado": None,
        "patron_fecha_hora": None,
        "columnas_detectadas": [],
        "separador": None,
    }

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        if re.match(r"Empleado:", linea, re.IGNORECASE):
            estructura["patron_empleado"] = "empleado_prefijo"
        if re.search(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}:\d{2}", linea):
            estructura["patron_fecha_hora"] = "fecha_hora_completa"
        if re.search(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", linea):
            estructura["patron_fecha_hora"] = "fecha_hora_separada"
        if re.search(r"\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}", linea):
            estructura["patron_fecha_hora"] = "fecha_hora_barras"
        if "\t" in linea or "|" in linea or "  " in linea:
            estructura["tipo"] = "tabular"

    return estructura


def extraer_datos_segun_estructura(lineas: List[str], estructura: Dict) -> List[Dict]:
    """Extrae datos según la estructura identificada usando el parser inteligente."""
    from .smart_parser import EntradaSalidaDetector, SmartTimeParser

    parser = SmartTimeParser()
    detector = EntradaSalidaDetector()

    datos = []
    empleado_actual = None
    posibles_nombres = _buscar_nombres_en_documento(lineas)

    for i, linea in enumerate(lineas):
        linea = linea.strip()
        if not linea:
            continue

        empleado_en_linea = _extraer_nombre_de_linea_tabular(linea)

        if re.match(r"Empleado:", linea, re.IGNORECASE):
            empleado_actual = linea.split(":", 1)[1].strip()
            continue
        elif re.match(r"Nombre:", linea, re.IGNORECASE):
            empleado_actual = linea.split(":", 1)[1].strip()
            continue
        elif re.match(r"^[A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+.*$", linea):
            if not any(char.isdigit() for char in linea) and len(linea.split()) >= 2:
                empleado_actual = linea.strip()
                continue
        elif re.match(r"^[A-ZÁÉÍÓÚ][a-záéíóúñ]+$", linea):
            if len(linea.strip()) >= 2 and linea.strip().isalpha():
                empleado_actual = linea.strip()
                continue
        elif re.match(r"^[A-ZÁÉÍÓÚÑ ]+$", linea) and len(linea.split()) >= 1:
            palabras_excluir = {
                "FECHA", "ENTRADA", "SALIDA", "TOTAL", "REPORTE", "ASISTENCIA", "NOMBRE",
                "EMPLEADO", "HORA", "DE", "DEL", "PAGOS", "DNI",
            }
            if linea not in palabras_excluir and any(v in linea for v in "AEIOUÁÉÍÓÚ"):
                empleado_actual = linea.strip().title()
                continue

        if empleado_en_linea:
            empleado_actual = empleado_en_linea

        fechas_horas = parser.extraer_fecha_hora(linea)
        for fh in fechas_horas:
            if empleado_en_linea:
                nombre_empleado = empleado_en_linea
            elif not empleado_actual and posibles_nombres:
                nombre_empleado = posibles_nombres[0]
            else:
                nombre_empleado = empleado_actual if empleado_actual else "Empleado 1"

            contexto = lineas[max(0, i - 2): i + 3] if i > 0 else [linea]
            tipo = detector.detectar_tipo(linea, fh["hora"], contexto)

            datos.append(
                {
                    "empleado": nombre_empleado,
                    "fecha": fh["fecha"],
                    "hora": fh["hora"],
                    "tipo": tipo,
                    "linea_original": linea,
                    "confianza": _calcular_confianza(linea, fh),
                }
            )

    return datos


def _buscar_nombres_en_documento(lineas: List[str]) -> List[str]:
    """Busca posibles nombres de empleados en todo el documento."""
    nombres_encontrados = []
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        if re.match(r"(Nombre|Empleado):", linea, re.IGNORECASE):
            nombre = linea.split(":", 1)[1].strip()
            if nombre and nombre not in nombres_encontrados:
                nombres_encontrados.append(nombre)
        elif re.match(r"^[A-ZÁÉÍÓÚ][a-záéíóúñ]+$", linea):
            if len(linea) >= 2 and linea not in nombres_encontrados:
                palabras_excluir = [
                    "Hora", "Fecha", "Entrada", "Salida", "Total", "Reporte", "Asistencia",
                ]
                if linea not in palabras_excluir:
                    nombres_encontrados.append(linea)
        elif re.match(r"^[A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+.*$", linea):
            if not any(char.isdigit() for char in linea) and linea not in nombres_encontrados:
                nombres_encontrados.append(linea)
        elif re.match(r"^[A-ZÁÉÍÓÚÑ ]+$", linea) and len(linea.split()) >= 1:
            palabras_excluir = {
                "FECHA", "ENTRADA", "SALIDA", "TOTAL", "REPORTE", "ASISTENCIA", "NOMBRE",
                "EMPLEADO", "HORA", "DE", "DEL", "PAGOS", "DNI",
            }
            if linea not in palabras_excluir and any(v in linea for v in "AEIOUÁÉÍÓÚ"):
                nombre = linea.title()
                if nombre and nombre not in nombres_encontrados:
                    nombres_encontrados.append(nombre)

    return nombres_encontrados


def _calcular_confianza(linea: str, fecha_hora: Dict) -> float:
    """Calcula la confianza de la extracción."""
    confianza = 0.5
    if any(p in linea.lower() for p in ["entrada", "salida", "entry", "exit"]):
        confianza += 0.3
    if re.match(r"\d{4}-\d{2}-\d{2}", fecha_hora["fecha"]):
        confianza += 0.2
    return min(confianza, 1.0)


def _extraer_nombre_de_linea_tabular(linea: str) -> str:
    """Extrae un nombre de empleado de una línea tabular del PDF."""
    columnas = re.split(r"\s{2,}|\t|\|", linea)
    columnas = [col.strip() for col in columnas if col.strip()]
    if len(columnas) < 2:
        return _extraer_nombre_de_fila_aplanada(linea)

    # Buscar la columna de nombre en la segunda posición cuando hay un identificador antes
    posible_nombre = columnas[1]
    if _es_nombre_de_empleado(posible_nombre):
        return posible_nombre.title()

    # Si la primera columna no es ID sino nombre, devolverla
    posible_nombre = columnas[0]
    if _es_nombre_de_empleado(posible_nombre):
        return posible_nombre.title()

    return _extraer_nombre_de_fila_aplanada(linea)


def _extraer_nombre_de_fila_aplanada(linea: str) -> str:
    """Respaldo para PDFs donde la tabla se extrae como texto corrido."""
    match = PATRON_FECHA_HORA.search(linea)
    if not match:
        return ""

    prefijo = linea[:match.start()].strip()
    if not prefijo:
        return ""

    tokens = prefijo.split()
    if not tokens:
        return ""

    if re.fullmatch(r"['`´]?\d+", tokens[0]):
        tokens = tokens[1:]

    if not tokens:
        return ""

    candidatos = []
    for indice, token in enumerate(tokens):
        token_limpio = token.strip(".,;:-_/\\")
        if not token_limpio or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", token_limpio):
            break

        siguiente = tokens[indice + 1] if indice + 1 < len(tokens) else ""
        if candidatos and siguiente and siguiente[:1].islower():
            break

        candidatos.append(token_limpio)
        if len(candidatos) == 3:
            break

    if not candidatos:
        return ""

    return " ".join(candidatos).title()


def _es_nombre_de_empleado(texto: str) -> bool:
    texto = texto.strip()
    if not texto:
        return False
    if re.search(r"\d", texto):
        return False
    palabras = texto.upper().split()
    encabezados_invalidos = {
        "FECHA", "ENTRADA", "SALIDA", "TOTAL", "REPORTE", "ASISTENCIA",
        "NOMBRE", "EMPLEADO", "HORA", "ID", "DNI", "DOCUMENTO", "PERSONA",
        "TIPO", "OTRO", "CODIGO", "CÓDIGO", "LEGAJO",
    }
    if any(palabra in encabezados_invalidos for palabra in palabras):
        return False
    if len(texto) < 2 or len(texto) > 60:
        return False
    palabras = texto.split()
    if len(palabras) == 1:
        return bool(re.match(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$", palabras[0]))
    if len(palabras) == 2:
        return bool(re.match(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$", texto))
    return all(re.match(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$", parte) for parte in palabras if parte)


def procesar_datos_inteligente(datos_brutos: List[Dict]) -> List[Dict]:
    """Procesa los datos de manera inteligente usando el DataGrouper."""
    from .smart_parser import DataGrouper

    if not datos_brutos:
        return []

    datos_confiables = [d for d in datos_brutos if d.get("confianza", 0) > 0.6]
    if not datos_confiables:
        datos_confiables = datos_brutos

    grouper = DataGrouper()
    return grouper.agrupar_por_empleado_fecha(datos_confiables)


def convertir_a_dataframe_estandar(datos_procesados: List[Dict]) -> pd.DataFrame:
    """Convierte los datos procesados al formato estándar del sistema."""
    if not datos_procesados:
        return pd.DataFrame()

    df = pd.DataFrame(datos_procesados)
    df = df.rename(
        columns={
            "empleado": "Empleado",
            "fecha": "Fecha",
            "entrada": "Entrada",
            "salida": "Salida",
        }
    )

    df["Descuento Inventario"] = 0
    df["Descuento Caja"] = 0
    df["Retiro"] = 0
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df


def validar_datos_pdf(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Valida los datos extraídos del PDF.
    Permite entrada o salida faltante (incluyendo 0:00) para corrección manual.
    """
    errores = []

    if df.empty:
        errores.append("No se pudieron extraer datos del PDF")
        return False, errores

    columnas_requeridas = ["Empleado", "Fecha", "Entrada", "Salida"]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append(f"Falta la columna: {col}")

    for idx, row in df.iterrows():
        entrada_str = str(row["Entrada"]).strip()
        if pd.notna(row["Entrada"]) and entrada_str != "" and entrada_str not in ["0:00", "00:00"]:
            try:
                datetime.strptime(entrada_str, "%H:%M")
            except Exception:  # noqa: BLE001
                if isinstance(idx, int):
                    fila_num = idx + 1
                elif isinstance(idx, str) and idx.isdigit():
                    fila_num = int(idx) + 1
                else:
                    fila_num = 0
                errores.append(
                    f"Formato de hora de entrada inválido en fila {fila_num}: {row['Entrada']}"
                )

        salida_str = str(row["Salida"]).strip()
        if pd.notna(row["Salida"]) and salida_str != "" and salida_str not in ["0:00", "00:00"]:
            try:
                datetime.strptime(salida_str, "%H:%M")
            except Exception:  # noqa: BLE001
                if isinstance(idx, int):
                    fila_num = idx + 1
                elif isinstance(idx, str) and idx.isdigit():
                    fila_num = int(idx) + 1
                else:
                    fila_num = 0
                errores.append(
                    f"Formato de hora de salida inválido en fila {fila_num}: {row['Salida']}"
                )

    return len(errores) == 0, errores


def detectar_registros_incompletos(df: pd.DataFrame) -> pd.DataFrame:
    """Detecta registros con entrada o salida faltante (pero no ambos)."""
    entrada_faltante = (
        df["Entrada"].isna()
        | (df["Entrada"] == "")
        | (df["Entrada"] == "nan")
        | (df["Entrada"].astype(str).str.strip() == "0:00")
        | (df["Entrada"].astype(str).str.strip() == "00:00")
    )
    salida_faltante = (
        df["Salida"].isna()
        | (df["Salida"] == "")
        | (df["Salida"] == "nan")
        | (df["Salida"].astype(str).str.strip() == "0:00")
        | (df["Salida"].astype(str).str.strip() == "00:00")
    )

    necesita_correccion = (entrada_faltante & ~salida_faltante) | (
        ~entrada_faltante & salida_faltante
    )
    df_incompletos = pd.DataFrame(df[necesita_correccion].copy())

    df_incompletos["Dato_Faltante"] = ""
    df_incompletos["Horario_Registrado"] = ""
    df_incompletos["Tipo_Problema"] = ""

    for idx in df_incompletos.index:
        row = df_incompletos.loc[idx]
        if entrada_faltante.loc[idx]:
            df_incompletos.loc[idx, "Dato_Faltante"] = "Entrada"
            df_incompletos.loc[idx, "Horario_Registrado"] = str(row["Salida"])
            df_incompletos.loc[idx, "Tipo_Problema"] = "Solo marcó salida"
        elif salida_faltante.loc[idx]:
            df_incompletos.loc[idx, "Dato_Faltante"] = "Salida"
            df_incompletos.loc[idx, "Horario_Registrado"] = str(row["Entrada"])
            df_incompletos.loc[idx, "Tipo_Problema"] = "Solo marcó entrada"

    return df_incompletos


def detectar_horarios_ambiguos(df: pd.DataFrame) -> pd.DataFrame:
    """Detecta registros con horarios que podrían estar mal asignados."""
    horarios_ambiguos = []

    for idx, row in df.iterrows():
        try:
            if pd.isna(row["Entrada"]) or pd.isna(row["Salida"]):
                continue

            entrada_str = str(row["Entrada"]).strip()
            salida_str = str(row["Salida"]).strip()

            if entrada_str in ["", "nan", "0:00", "00:00"] or salida_str in ["", "nan", "0:00", "00:00"]:
                continue

            entrada = datetime.strptime(entrada_str, "%H:%M").time()
            salida = datetime.strptime(salida_str, "%H:%M").time()

            entrada_decimal = entrada.hour + entrada.minute / 60
            salida_decimal = salida.hour + salida.minute / 60

            sospechoso = False
            razon = ""

            if entrada_decimal >= 20:
                sospechoso = True
                razon = f"Entrada registrada a las {entrada_str} (muy tarde - ¿podría ser salida?)"
            elif salida_decimal <= 10:
                sospechoso = True
                razon = f"Salida registrada a las {salida_str} (muy temprano - ¿podría ser entrada?)"
            elif entrada_decimal > salida_decimal:
                sospechoso = True
                razon = f"Entrada ({entrada_str}) después de salida ({salida_str}) - posible error de asignación"

            if sospechoso:
                row_dict = row.to_dict()
                row_dict["Razon_Sospecha"] = razon
                row_dict["Entrada_Original"] = entrada_str
                row_dict["Salida_Original"] = salida_str
                horarios_ambiguos.append(row_dict)
        except Exception:  # noqa: BLE001
            continue

    return pd.DataFrame(horarios_ambiguos) if horarios_ambiguos else pd.DataFrame()


def filtrar_registros_sin_asistencia(df: pd.DataFrame) -> tuple:
    """Separa registros donde el empleado no trabajó (sin entrada ni salida)."""
    entrada_faltante = (
        df["Entrada"].isna()
        | (df["Entrada"] == "")
        | (df["Entrada"] == "nan")
        | (df["Entrada"].astype(str).str.strip() == "0:00")
        | (df["Entrada"].astype(str).str.strip() == "00:00")
    )
    salida_faltante = (
        df["Salida"].isna()
        | (df["Salida"] == "")
        | (df["Salida"] == "nan")
        | (df["Salida"].astype(str).str.strip() == "0:00")
        | (df["Salida"].astype(str).str.strip() == "00:00")
    )

    sin_asistencia = entrada_faltante & salida_faltante
    df_sin_asistencia = df[sin_asistencia].copy()
    df_con_asistencia = df[~sin_asistencia].copy()
    return df_con_asistencia, df_sin_asistencia

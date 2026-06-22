from payroll.pdf_processor import (
    analizar_estructura_pdf,
    extraer_datos_segun_estructura,
    procesar_datos_inteligente,
    convertir_a_dataframe_estandar,
    validar_datos_pdf,
    filtrar_registros_sin_asistencia,
    detectar_registros_incompletos,
    detectar_horarios_ambiguos,
)
from app import _empleado_coincide
from payroll.models import Employee

texto_pdf = """
ID de persona    Nombre    Otra
15    Paz    Otro texto
2026-06-01 08:00
2026-06-01 17:00
2026-06-02 08:10
2026-06-02 17:05
"""
lineas = [l for l in texto_pdf.split("\n") if l.strip()]
estructura = analizar_estructura_pdf(lineas)
datos_brutos = extraer_datos_segun_estructura(lineas, estructura)
datos_procesados = procesar_datos_inteligente(datos_brutos)
df = convertir_a_dataframe_estandar(datos_procesados)

print("=== ESTRUCTURA DETECTADA ===")
print(estructura)
print("\n=== DATOS BRUTOS EXTRAÍDOS ===")
for item in datos_brutos:
    print(item)
print("\n=== DATAFRAME ESTANDARIZADO ===")
print(df.to_string(index=False))

valido, errores = validar_datos_pdf(df)
print("\n=== VALIDACIÓN PDF ===")
print("válido=", valido)
print("errores=", errores)

empleado_prueba = Employee()
empleado_prueba.nombre = 'Paz Tatiana'
calce = df.apply(lambda row: _empleado_coincide(row['Empleado'], empleado_prueba), axis=1)
print("\n=== COINCIDENCIAS CON empleado Paz Tatiana ===")
print(calce.tolist())
print("\n=== FILAS COINCIDENTES ===")
print(df[calce].to_string(index=False))

con_asistencia, sin_asistencia = filtrar_registros_sin_asistencia(df)
print("\n=== FILTRAR REGISTROS SIN ASISTENCIA ===")
print("con_asistencia rows=", len(con_asistencia))
print("sin_asistencia rows=", len(sin_asistencia))

print("\n=== REGISTROS INCOMPLETOS ===")
print(detectar_registros_incompletos(con_asistencia).to_string(index=False))

print("\n=== HORARIOS AMBIGUOS ===")
print(detectar_horarios_ambiguos(con_asistencia).to_string(index=False))

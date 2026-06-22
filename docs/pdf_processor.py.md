# pdf_processor.py

## Rol
Transforma archivos PDF de asistencia en un DataFrame compatible con el motor de calculo.

## Responsabilidades
- Extraer texto de PDF (`pdfplumber`).
- Detectar estructura del documento por patrones.
- Extraer eventos de fecha/hora y asociarlos a empleado.
- Normalizar a formato estandar con columnas esperadas.
- Validar calidad minima de datos.
- Detectar registros incompletos, ambiguos y sin asistencia.

## Flujo interno
1. `procesar_pdf_a_dataframe` llama a extraccion de texto.
2. Analiza estructura y extrae datos con apoyo de `smart_parser.py`.
3. Filtra y agrupa datos por empleado/fecha.
4. Convierte a DataFrame estandar y agrega columnas de descuentos.
5. Devuelve DataFrame listo para pipeline de `main.py`.

## Dependencias
- `smart_parser.py` (`SmartTimeParser`, `EntradaSalidaDetector`, `DataGrouper`).
- `pdfplumber` (dinamico), `pandas`, `streamlit`, `re`, `datetime`.

## Supuestos
- Si falta `pdfplumber`, se usa texto de ejemplo para no romper flujo.
- La deteccion de entrada/salida usa heuristicas por palabras y hora.
- Valores `0:00`/`00:00` se consideran faltantes.

## Vacios y riesgos
- Hay dos funciones con nombre `validar_datos_pdf`; la segunda reemplaza la primera.
- Heuristicas de nombres y horarios pueden fallar en formatos no latinos o layouts complejos.
- En caso de baja confianza, el sistema usa todos los datos y puede introducir ruido.

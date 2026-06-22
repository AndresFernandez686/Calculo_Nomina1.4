# Arquitectura general

## Resumen del proyecto
Aplicacion Streamlit para calcular sueldos desde registros de asistencia en Excel o PDF.

Capacidades clave:
- Calculo de horas normales y horas especiales (20:00-22:00 con recargo).
- Multiplicador por feriado seleccionado manualmente.
- Descuentos por inventario, caja y retiro.
- Correccion administrativa de registros incompletos.
- Deteccion de horarios ambiguos para confirmar intercambio entrada/salida.

## Puntos de entrada
- Entrada principal de aplicacion: `main.py` (Streamlit).
- Entrada operativa en Windows: `run_app.bat` y `test_run.bat`.

## Componentes y responsabilidades
- `main.py`: orquesta UI, carga de archivos y secuencia de procesamiento.
- `ui_components.py`: widgets, formularios y flujo de correcciones manuales.
- `data_processor.py`: validacion de estructura, reglas de calculo, agregados y exportacion.
- `calculations.py`: funciones puras de horas y conversiones.
- `pdf_processor.py`: parser de PDFs y conversion a formato estandar.
- `smart_parser.py`: deteccion de fechas/horas y agrupacion por empleado/fecha.
- `loading_components.py`: componentes visuales de espera/progreso.
- `styles.css`: look and feel de la interfaz.

## Flujo funcional end-to-end
1. Usuario configura valor por hora y feriados.
2. Usuario sube archivo Excel o uno/dos PDFs.
3. Sistema valida estructura y datos.
4. Sistema filtra registros sin asistencia (sin entrada y sin salida).
5. Sistema detecta registros incompletos (solo entrada o solo salida) y solicita correccion admin.
6. Sistema detecta horarios ambiguos y permite intercambiar entrada/salida.
7. Se ejecuta calculo de sueldos.
8. Se muestran metricas y se exporta Excel final.

## Dependencias externas principales
- `streamlit`, `pandas`, `openpyxl`.
- `pdfplumber` para extraccion PDF (con fallback en caso de ausencia).

## Supuestos de negocio identificados
- Horario laboral valido: 10:30 a 22:00.
- Horas especiales: solo tramo 20:00 a 22:00.
- Feriado aplica multiplicador x2 sobre sueldo normal+especial.
- Registros con entrada y salida faltante se excluyen (no trabajo).

## Vacios de informacion
- No hay especificacion formal de reglas para turnos nocturnos extendidos mas alla de ajustes basicos.
- No hay suite de tests automatizados para validar regresiones.
- No hay contrato de formato PDF soportado con versionado.

## Riesgos de mantenimiento
- Doble definicion de funciones en `pdf_processor.py` puede inducir errores de lectura del codigo.
- Mezcla de logica de negocio y presentacion Streamlit en varios modulos incrementa acoplamiento.
- Uso intensivo de indices de DataFrame para correcciones depende de que no cambie el indice entre pasos.

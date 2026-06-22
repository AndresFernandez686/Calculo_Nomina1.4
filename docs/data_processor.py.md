# data_processor.py

## Rol
Implementa reglas de negocio para transformar registros de asistencia en sueldos finales.

## Funciones clave
- `detectar_y_resolver_marcaciones_duplicadas(df)`:
  - Detecta grupos de 3 marcaciones por empleado/fecha.
  - Construye una marcacion principal con entrada mas temprana y salida mas tardia.
  - Intenta conservar segunda marcacion no duplicada.
- `validar_archivo_excel(df)`:
  - Verifica columnas requeridas.
- `procesar_datos_excel(...)`:
  - Ejecuta pipeline de fila por fila con acumulados generales.
- `_procesar_fila(...)`:
  - Valida horario laboral.
  - Calcula horas normales/especiales.
  - Aplica feriado y descuentos.
- `mostrar_resultados(...)`:
  - Renderiza tabla/metricas y habilita descarga en Excel.

## Reglas de negocio detectadas
- Horario permitido: 10:30 a 22:00.
- Si la salida es menor que entrada, asume cruce de medianoche.
- Horas especiales: calculadas por `calculations.py` en rango 20:00-22:00.
- Feriado: factor x2 sobre sueldo bruto.
- Descuentos: inventario, caja y retiro se restan al final.

## Dependencias
- `calculations.py` para formulas base.
- `streamlit` para feedback de errores y visualizacion.
- `pandas`, `openpyxl`, `io` para manejo/exportacion de datos.

## Entradas y salidas
- Entrada: DataFrame estandar con columnas esperadas y parametros de negocio.
- Salida: lista de filas procesadas, totales agregados, y archivo Excel descargable.

## Supuestos
- Los valores de descuento pueden venir nulos y se tratan como cero.
- La columna `Fecha` es parseable a datetime.

## Vacios y riesgos
- El manejo de duplicados para exactamente 3 marcaciones no cubre explicitamente 4+ marcaciones.
- La validacion de horario laboral puede descartar casos validos de turnos especiales no contemplados.
- Mezcla de capa de negocio y capa de presentacion en `mostrar_resultados`.

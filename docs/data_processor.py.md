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
  - Recibe `ips_enabled` para activar o desactivar calculos IPS.
- `_procesar_fila(...)`:
  - Valida horario laboral.
  - Calcula horas normales/especiales.
  - Aplica feriado y descuentos.
  - Cuando IPS esta habilitado, calcula y retorna `Descuento IPS` por fila.
- `mostrar_resultados(...)`:
  - Renderiza tabla/metricas y habilita descarga en Excel.

## Reglas de negocio detectadas
- Horario permitido: 10:30 a 22:00.
- Si la salida es menor que entrada, asume cruce de medianoche.
- Horas especiales: calculadas por `calculations.py` en rango 20:00-22:00.
- Feriado: factor x2 sobre sueldo bruto.
- Descuentos: inventario, caja y retiro se restan al final.
- IPS opcional:
  - Descuento empleado: 9% del salario bruto.
  - Aporte empleador: 16.5% del salario bruto.
  - Total IPS = descuento empleado + aporte empleador.
  - Salario neto IPS = salario bruto - descuento empleado.

## Dependencias
- `calculations.py` para formulas base.
- `streamlit` para feedback de errores y visualizacion.
- `pandas`, `openpyxl`, `io` para manejo/exportacion de datos.

## Entradas y salidas
- Entrada: DataFrame estandar con columnas esperadas y parametros de negocio.
- Salida: lista de filas procesadas, totales agregados, y archivo Excel descargable.
- Totales agregados actuales (cuando aplica IPS):
  - total_horas
  - total_horas_normales
  - total_horas_especiales
  - total_sueldos
  - total_salario_bruto
  - total_descuento_ips
  - total_aporte_empleador_ips
  - total_ips
  - total_salario_neto_ips

## Funcionamiento de meses repetidos (integracion con app.py)
- La validacion de mes repetido se ejecuta en [app.py](app.py) antes de guardar nuevos resultados.
- Regla aplicada: un empleado no debe tener duplicado el mismo mes-anio.
- Flujo:
  - Se detectan los meses del archivo de entrada usando la columna Fecha.
  - Se comparan contra registros existentes de ese empleado en employee_payroll.
  - Si hay conflicto de mes-anio, se muestra pantalla de confirmacion con detalle del mes existente.
  - Si el usuario confirma actualizar:
    - Se eliminan registros previos de ese mes para el empleado.
    - Se eliminan datos asociados del run anterior (asistencia, detalle y cabecera de calculo).
    - Se recalcula y guarda el nuevo resultado (por ejemplo, mismo mes con IPS ahora habilitado).
  - Si el usuario cancela, no se modifica la base.
- Efecto final: se mantiene un solo resultado por empleado y mes-anio.

## Supuestos
- Los valores de descuento pueden venir nulos y se tratan como cero.
- La columna `Fecha` es parseable a datetime.

## Vacios y riesgos
- El manejo de duplicados para exactamente 3 marcaciones no cubre explicitamente 4+ marcaciones.
- La validacion de horario laboral puede descartar casos validos de turnos especiales no contemplados.
- Mezcla de capa de negocio y capa de presentacion en `mostrar_resultados`.

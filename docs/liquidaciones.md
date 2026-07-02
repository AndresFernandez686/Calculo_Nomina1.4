# Liquidaciones

## Objetivo

Documentar la estructura y el flujo de cálculo de liquidaciones por empleado.

## Flujo de cálculo

Empleado -> historial de nóminas -> cálculo por conceptos -> promedio laboral -> persistencia -> liquidación final.

Flujo de UI actual:

Nueva liquidación -> Generar liquidación -> guardado en BD -> redirección automática a Historial.

## Tabla `liquidaciones`

Campos principales:

- `id`
- `empleado_id`
- `tipo` (`RENUNCIA`, `DESPIDO`, `FIN_CONTRATO`)
- `fecha_salida`
- `salario_pendiente`
- `aguinaldo`
- `vacaciones`
- `preaviso`
- `indemnizacion`
- `total_liquidacion`
- `created_at`

Uso:

- Guarda cada liquidación generada como historial consultable.
- Permite auditar el resultado final y recalcular si cambian los datos.
- Alimenta la pestaña Historial con detalle por concepto y total de cada liquidación.

## Tabla `promedios_laborales`

Campos principales:

- `id`
- `empleado_id`
- `periodo`
- `total_salarios`
- `dias_trabajados`
- `promedio_diario`
- `promedio_mensual`
- `created_at`

Uso:

- Guarda el promedio salarial calculado desde la nómina histórica.
- Sirve como base para vacaciones y liquidaciones.

## Regla funcional actual

- Fórmula base:
  - `LIQUIDACIÓN FINAL = salario_pendiente + aguinaldo + vacaciones + preaviso + indemnización`
- Salario pendiente:
  - Si hay registros del mes de salida, usa los registros hasta la fecha de salida.
  - Si no hay registros del mes de salida, prorratea solo los días transcurridos del mes de salida con base en el último mes registrado.
- Aguinaldo proporcional:
  - Se calcula sobre periodos históricos previos (ventana configurable por la lógica del backend).
  - El detalle de meses en UI se muestra en orden cronológico.
- Vacaciones:
  - Vacaciones generadas: antigüedad + regla legal.
  - Vacaciones utilizadas: editable por el usuario.
  - Vacaciones pendientes: `generadas - utilizadas`.
  - Monto vacaciones: `dias_pendientes * promedio_diario`.
- Preaviso e indemnización:
  - Se aplican según tipo de liquidación y antigüedad.

## Estado en UI

- La pantalla de liquidaciones muestra:
  - Tabs ordenadas: `Nueva liquidación`, `Historial`, `Exportar PDF`.
  - Pestaña `Historial` con registros persistidos reales de la tabla `liquidaciones`.
  - Tabla de historial con: fecha de registro, fecha de salida, tipo, salario pendiente, aguinaldo, vacaciones, preaviso, indemnización y total.
  - Resumen por concepto con detalle de fórmula aplicada.
  - Estado de vacaciones (generadas, usadas, pendientes).
  - Períodos registrados (meses realmente cargados para ese empleado).
  - Tarjeta `Composición de la liquidación (%)` (donut):
    - Segmentos por concepto sobre el total a pagar.
    - Centro del donut con el concepto dominante y su porcentaje.
    - Total a pagar destacado debajo.
  - Tarjeta `Línea de tiempo de antigüedad y derechos` (donut + leyenda):
    - Fecha de ingreso.
    - Fecha de salida.
    - Períodos trabajados completos.
    - Período proporcional en curso.
    - Aguinaldo devengado (`x/12`) y porcentaje.

## Consideraciones

- Los cálculos se guardan por empleado para trazabilidad.
- El esquema está preparado para agregar más tipos de liquidación sin cambiar la lógica base.
- El valor de salida en UI depende de la fecha de salida seleccionada en el formulario.
- La redirección post-guardado al historial facilita validación operativa inmediata.

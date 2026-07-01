# Liquidaciones

## Objetivo

Documentar la estructura y el flujo de cálculo de liquidaciones por empleado.

## Flujo de cálculo

Empleado -> historial de nóminas -> cálculo por conceptos -> promedio laboral -> persistencia -> liquidación final.

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
- Vacaciones:
  - Vacaciones generadas: antigüedad + regla legal.
  - Vacaciones utilizadas: editable por el usuario.
  - Vacaciones pendientes: `generadas - utilizadas`.
  - Monto vacaciones: `dias_pendientes * promedio_diario`.
- Preaviso e indemnización:
  - Se aplican según tipo de liquidación y antigüedad.

## Estado en UI

- La pantalla de liquidaciones muestra:
  - Resumen por concepto con detalle de fórmula aplicada.
  - Estado de vacaciones (generadas, usadas, pendientes).
  - Períodos registrados (meses realmente cargados para ese empleado).

## Consideraciones

- Los cálculos se guardan por empleado para trazabilidad.
- El esquema está preparado para agregar más tipos de liquidación sin cambiar la lógica base.
- El valor de salida en UI depende de la fecha de salida seleccionada en el formulario.

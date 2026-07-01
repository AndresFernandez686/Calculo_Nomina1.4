# Base de Datos - Resumen

## Objetivo

La base de datos guarda historial de cálculo de nómina por empleado, detalle diario de asistencia, liquidaciones históricas, promedios laborales y metadatos de carga para trazabilidad.

## Motor y archivo

- Motor: SQLite
- Archivo principal: `instance/sueldos.db`

## Tablas principales

### employees

Guarda el maestro de empleados.

- `id`
- `nombre` (único)
- `created_at`
- `hire_date`
- `liquidation_type`
- `vacation_generated_days`
- `vacation_used_days`
- `vacation_pending_days`
- `vacation_used_from`
- `vacation_used_to`

Uso:

- Selección de empleado para procesar archivos.
- Relación con corridas de cálculo, detalle histórico y estado de vacaciones/liquidación.
- Conserva configuración de liquidación y estado de vacaciones por empleado.

### calculation_runs

Guarda una corrida de cálculo completa (cabecera de lote).

- `id`
- `employee_id`
- `created_at`
- `source_name` / `source_type`
- `valor_por_hora`
- `feriados`
- `seguro_ips`

Totales operativos:

- `total_registros`
- `total_horas`
- `total_horas_normales`
- `total_horas_especiales`
- `total_sueldos`

Totales IPS:

- `total_salario_bruto`
- `total_descuento_ips`
- `total_aporte_empleador_ips`
- `total_ips`
- `total_salario_neto_ips`

Totales de origen del cálculo (auditoría):

- `total_monto_horas_normales`
- `total_monto_horas_especiales`
- `total_monto_feriados`
- `total_bonificacion`

Uso:

- Mostrar resumen final de una corrida.
- Soporte de auditoría del origen del salario.
- Base para reemplazo de mes repetido.

### employee_records

Guarda detalle diario por corrida (detalle técnico del run).

- `id`
- `run_id`
- `employee_id`
- `empleado`
- `fecha`
- `entrada` / `salida`
- `feriado`
- `horas_trabajadas`
- `horas_normales`
- `horas_especiales`
- `monto_horas_normales`
- `monto_horas_especiales`
- `monto_feriado`
- `bonificacion`
- `sueldo_bruto`
- `descuento_inventario`
- `descuento_caja`
- `descuento_ips`
- `retiro`
- `sueldo_final`
- `observaciones`

Uso:

- Reconstruir y explicar el cálculo fila a fila.
- Recalculo/migración de corridas antiguas.

### employee_payroll

Guarda el histórico mensual consultable por empleado (vista de nómina).

- `id`
- `employee_id`
- `fecha`
- `entrada` / `salida`
- `feriado`
- `horas_trabajadas`
- `horas_normales`
- `horas_especiales`
- `monto_horas_normales`
- `monto_horas_especiales`
- `monto_feriado`
- `bonificacion`
- `sueldo_bruto`
- `descuento_inventario`
- `descuento_caja`
- `descuento_ips`
- `retiro`
- `sueldo_final`
- `observaciones`
- `run_id`
- `created_at`

Uso:

- Pantalla de registros de nómina por mes.
- Descarga mensual en Excel/PDF.

### employee_attendances

Guarda metadatos de archivos de asistencia cargados.

- `id`
- `employee_id`
- `run_id`
- `source_name`
- `source_type`
- `total_registros`
- `created_at`

Uso:

- Trazabilidad de origen de datos.

### promedios_laborales

Guarda el promedio salarial calculado desde la nómina histórica para usarlo en liquidaciones.

- `id`
- `empleado_id`
- `periodo`
- `total_salarios`
- `dias_trabajados`
- `promedio_diario`
- `promedio_mensual`
- `created_at`

Uso:

- Base para calcular vacaciones y montos de liquidación.
- Conserva el promedio aplicado en cada generación.

### liquidaciones

Guarda cada liquidación generada por empleado.

- `id`
- `empleado_id`
- `tipo`
- `fecha_salida`
- `salario_pendiente`
- `aguinaldo`
- `vacaciones`
- `preaviso`
- `indemnizacion`
- `total_liquidacion`
- `created_at`

Uso:

- Historial de liquidaciones por empleado.
- Auditoría de montos finales y reglas aplicadas.

## Flujo de registro

1. Usuario selecciona empleado y sube archivo.
2. Se procesa y calcula (horas, especiales, feriados, descuentos, IPS).
3. Se inserta cabecera en `calculation_runs`.
4. Se inserta detalle en `employee_records` y `employee_payroll`.
5. Se registra metadato de carga en `employee_attendances`.
6. Al generar liquidación se calcula promedio laboral, se guarda el resumen en `promedios_laborales` y se persiste la liquidación en `liquidaciones`.

## Migración automática al iniciar

La aplicación valida y agrega columnas faltantes en tiempo de arranque para mantener compatibilidad con bases SQLite antiguas.

Columnas relevantes cubiertas por esta migración:

- `employees.hire_date`
- `employees.liquidation_type`
- `employees.vacation_generated_days`
- `employees.vacation_used_days`
- `employees.vacation_pending_days`
- `employees.vacation_used_from`
- `employees.vacation_used_to`

## Regla de mes repetido

- No se mantiene duplicado del mismo mes-año por empleado.
- Si el mes ya existe, el sistema pide confirmación para actualizar.
- Al confirmar, elimina datos previos de ese mes (cabecera, detalle y asistencia) y guarda la nueva corrida.

## Notas de auditoría

- La base ya guarda el origen del salario en componentes separados (normal, especial, feriado, bonificación, bruto).
- Esto permite justificar liquidación, aguinaldo y revisiones posteriores con evidencia trazable.
- Los promedios y liquidaciones quedan historizados por empleado para auditoría y reutilización.

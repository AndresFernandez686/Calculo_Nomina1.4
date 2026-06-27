# Base de Datos - Resumen

## Objetivo
La base de datos guarda historial de calculos de nomina por empleado, detalle diario de asistencia/liquidacion y metadatos de carga para trazabilidad.

## Motor y archivo
- Motor: SQLite
- Archivo principal: `instance/sueldos.db`

## Tablas principales

### employees
Guarda el maestro de empleados.
- id
- nombre (unico)
- created_at

Uso:
- Seleccion de empleado para procesar archivos.
- Relacion con corridas de calculo y detalle historico.

### calculation_runs
Guarda una corrida de calculo completa (cabecera de lote).
- id
- employee_id
- created_at
- source_name / source_type
- valor_por_hora
- feriados
- seguro_ips

Totales operativos:
- total_registros
- total_horas
- total_horas_normales
- total_horas_especiales
- total_sueldos

Totales IPS:
- total_salario_bruto
- total_descuento_ips
- total_aporte_empleador_ips
- total_ips
- total_salario_neto_ips

Totales de origen del calculo (auditoria):
- total_monto_horas_normales
- total_monto_horas_especiales
- total_monto_feriados
- total_bonificacion

Uso:
- Mostrar resumen final de una corrida.
- Soporte de auditoria de origen del salario.
- Base para reemplazo de mes repetido.

### employee_records
Guarda detalle diario por corrida (detalle tecnico del run).
- id
- run_id
- employee_id
- empleado
- fecha
- entrada / salida
- feriado
- horas_trabajadas
- horas_normales
- horas_especiales

Montos de origen por fila:
- monto_horas_normales
- monto_horas_especiales
- monto_feriado
- bonificacion
- sueldo_bruto

Descuentos y resultado:
- descuento_inventario
- descuento_caja
- descuento_ips
- retiro
- sueldo_final
- observaciones

Uso:
- Reconstruir y explicar el calculo fila a fila.
- Recalculo/migracion de corridas antiguas.

### employee_payroll
Guarda el historico mensual consultable por empleado (vista de nomina).
- id
- employee_id
- fecha
- entrada / salida
- feriado
- horas_trabajadas
- horas_normales
- horas_especiales

Montos de origen por fila:
- monto_horas_normales
- monto_horas_especiales
- monto_feriado
- bonificacion
- sueldo_bruto

Descuentos y resultado:
- descuento_inventario
- descuento_caja
- descuento_ips
- retiro
- sueldo_final
- observaciones
- run_id
- created_at

Uso:
- Pantalla de Registros de nomina por mes.
- Descarga mensual en Excel/PDF.

### employee_attendances
Guarda metadatos de archivos de asistencia cargados.
- id
- employee_id
- run_id
- source_name
- source_type
- total_registros
- created_at

Uso:
- Trazabilidad de origen de datos.

## Flujo de registro
1. Usuario selecciona empleado y sube archivo.
2. Se procesa y calcula (horas, especiales, feriados, descuentos, IPS).
3. Se inserta cabecera en calculation_runs.
4. Se inserta detalle en employee_records y employee_payroll.
5. Se registra metadato de carga en employee_attendances.

## Regla de mes repetido
- No se mantiene duplicado del mismo mes-año por empleado.
- Si el mes ya existe, el sistema pide confirmacion para actualizar.
- Al confirmar, elimina datos previos de ese mes (cabecera, detalle y asistencia) y guarda la nueva corrida.

## Notas de auditoria
- La base ya guarda el origen del salario en componentes separados (normal, especial, feriado, bonificacion, bruto).
- Esto permite justificar liquidacion, aguinaldo y revisiones posteriores con evidencia trazable.

# Historial Salarial

## Objetivo

Garantizar trazabilidad completa del valor por hora de cada empleado, de modo que cualquier liquidación futura sea reproducible exactamente con los datos históricos y pueda auditarse ante una inspección laboral.

## Principio fundamental

**Los registros históricos nunca se sobreescriben ni se eliminan.**

Al registrar un aumento de salario:
1. El registro vigente anterior se cierra: `fecha_fin = nueva_fecha_inicio - 1 día`.
2. Se crea un nuevo registro con el nuevo valor y `fecha_fin = NULL` (vigente).

## Tabla `historial_salarios`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Clave primaria |
| `empleado_id` | INTEGER FK | Referencia a `employees.id` |
| `fecha_inicio` | VARCHAR(20) | Fecha desde la que aplica este valor (ISO: YYYY-MM-DD) |
| `fecha_fin` | VARCHAR(20) nullable | Fecha hasta la que aplica (NULL = vigente) |
| `valor_hora` | FLOAT | Valor por hora en guaraníes |
| `motivo_cambio` | VARCHAR(50) | Ingreso / Ascenso / Aumento por salario mínimo / Ajuste / Otro |
| `observaciones` | VARCHAR(500) nullable | Detalle libre |
| `usuario` | VARCHAR(100) nullable | Persona que registró el cambio |
| `created_at` | DATETIME | Timestamp de creación del registro |

## Campo `valor_hora_utilizado` en `employee_payroll`

Al generar una nómina, se guarda una copia del valor por hora en `employee_payroll.valor_hora_utilizado`.

- Es una **copia inmutable**: aunque haya aumentos futuros, este campo no cambia.
- La liquidación puede usar este valor directamente sin necesidad de reconstruir el historial.

## Flujo de uso

### Al contratar un empleado
```
POST /empleado/<id>/historial-salarial
  fecha_inicio = fecha de ingreso
  valor_hora   = salario inicial
  motivo_cambio = "Ingreso"
```

### Al registrar un aumento
```
POST /empleado/<id>/historial-salarial
  fecha_inicio = fecha de vigencia del nuevo salario
  valor_hora   = nuevo valor por hora
  motivo_cambio = "Ascenso" | "Aumento por salario mínimo" | "Ajuste" | "Otro"
```
El sistema cierra automáticamente el registro anterior.

### Al generar nómina
El campo `valor_hora_utilizado` de cada `EmployeePayroll` queda fijado al `config["valor_por_hora"]` del momento del cálculo.

### Al generar una liquidación
- `salario_pendiente`: usa `sueldo_final` de los registros de nómina (que ya tiene el valor correcto de la época).
- `promedio_diario` (para vacaciones, preaviso e indemnización): promedio de los últimos 6 meses de `sueldo_final` / 30, según art. 92 CT.
- No se recalculan nóminas antiguas; se usan los importes ya guardados.

## Pantalla de línea de tiempo

Acceso: `GET /empleado/<id>/historial-salarial`

Muestra:
- Valor hora vigente destacado.
- Línea de tiempo vertical con todos los cambios (más reciente arriba).
- Cada entrada: monto, motivo (badge), rango de fechas, observaciones, usuario y timestamp.
- Formulario para registrar nuevo cambio.

## Reglas de negocio

1. Solo puede haber **un registro vigente** (fecha_fin = NULL) por empleado a la vez.
2. La `fecha_inicio` del nuevo registro debe ser **mayor** a la `fecha_inicio` del registro vigente.
3. El valor por hora debe ser mayor a 0.
4. Los motivos permitidos son: `Ingreso`, `Ascenso`, `Aumento por salario mínimo`, `Ajuste`, `Otro`.

## Consideraciones de auditoría

- Al generar una liquidación, los importes de nómina ya están fijados en `employee_payroll.sueldo_final`.
- El `valor_hora_utilizado` permite verificar qué tarifa se usó en cada nómina.
- El historial salarial permite verificar que la tarifa era correcta para ese período.
- Combinando ambas tablas, cualquier concepto de liquidación es totalmente trazable.

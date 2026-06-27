# calculations.py

## Rol
Modulo utilitario con funciones puras para calculos de tiempo.

## Funciones
- `calcular_horas_especiales(entrada_dt, salida_dt)`:
  - Calcula horas totales.
  - Determina interseccion con ventana especial 20:00-22:00.
  - Retorna horas normales y horas especiales.
- `horas_a_horasminutos(horas)`:
  - Convierte horas decimales a cadena `HH:MM`.
  - Corrige desbordes cuando minutos redondean a 60.

## Dependencias
- `datetime` estandar de Python.

## Relacion con IPS
- Este modulo no calcula IPS de forma directa.
- Su aporte al flujo IPS es proveer la base de horas normales/especiales para el salario bruto.
- Los calculos de IPS (9% empleado, 16.5% empleador, neto) se aplican en la capa de negocio de [payroll/data_processor.py](payroll/data_processor.py).

## Flujo actual con IPS habilitado
- Primero se calculan horas y salario base usando este modulo.
- Luego la capa de negocio decide si IPS esta habilitado y aplica descuento/aporte sobre el salario bruto resultante.
- El detalle por fila guarda descuento_ips y los totales del run guardan:
  - total_salario_bruto
  - total_descuento_ips
  - total_aporte_empleador_ips
  - total_ips
  - total_salario_neto_ips

## Supuestos
- Entrada y salida ya vienen en orden temporal correcto (si cruza medianoche, se ajusta aguas arriba).
- La ventana especial es fija y no configurable por UI.

## Vacios y riesgos
- No contempla multiples ventanas especiales por jornada.
- No contempla segundos en conversion final (redondea a minutos).

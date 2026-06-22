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

## Supuestos
- Entrada y salida ya vienen en orden temporal correcto (si cruza medianoche, se ajusta aguas arriba).
- La ventana especial es fija y no configurable por UI.

## Vacios y riesgos
- No contempla multiples ventanas especiales por jornada.
- No contempla segundos en conversion final (redondea a minutos).

# smart_parser.py

## Rol
Contiene heuristicas de parsing para fechas/horas y agrupacion por empleado/fecha.

## Clases principales
- `SmartTimeParser`:
  - Detecta patrones de fecha, hora y fecha+hora en multiples formatos.
  - Normaliza fechas a `YYYY-MM-DD` y horas a `HH:MM`.
- `EntradaSalidaDetector`:
  - Determina tipo de marca por palabras clave y heuristica horaria.
  - Usa contexto de lineas vecinas para resolver ambiguedad parcial.
- `DataGrouper`:
  - Agrupa por empleado+fecha.
  - Regla actual: primera hora del dia = entrada, segunda = salida.
  - Si solo hay una hora, salida queda en `0:00` para correccion posterior.

## Dependencias
- `re`, `datetime`, `pandas`.

## Supuestos
- La secuencia temporal por dia representa asistencia valida.
- Dos marcas por dia son suficientes para reconstruir jornada.

## Vacios y riesgos
- No maneja explicitamente jornadas con mas de dos marcas utiles (almuerzo, pausas).
- Ambiguedad entre formatos `DD/MM` y `MM/DD` se resuelve por una sola convencion.
- Las heuristicas de contexto son basicas y pueden etiquetar mal casos frontera.

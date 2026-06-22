# ui_components.py

## Rol
Define componentes visuales Streamlit y flujos de interaccion para correcciones administrativas.

## Responsabilidades
- Configuracion de valor por hora y feriados.
- Descarga de plantilla de Excel.
- Selector de tipo de archivo (Excel/PDF) y uploader.
- Editor de registros incompletos (decision entrada/salida + hora faltante).
- Editor de horarios ambiguos (intercambio entrada/salida).
- Aplicacion de correcciones sobre DataFrames.

## Gestion de estado
- Usa `st.session_state` para persistir:
  - `file_type`
  - `feriados_list`
  - `correcciones_horarios`
  - `correcciones_ambiguos`

## Dependencias
- `streamlit`, `datetime`, `calendar`.

## Supuestos
- El administrador define la verdad operativa en registros incompletos.
- El indice del DataFrame se mantiene estable para aplicar correcciones por `idx`.

## Vacios y riesgos
- Uso intensivo de `st.rerun()` puede volver complejo seguir el flujo en mantenimiento.
- Si cambia el orden del DataFrame, las correcciones por indice pueden quedar desalineadas.
- UX de formularios es extensa y susceptible a regresiones visuales.

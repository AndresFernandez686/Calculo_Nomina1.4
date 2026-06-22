# loading_components.py

## Rol
Modulo de presentacion para feedback visual durante operaciones costosas.

## Capacidades
- Loaders simples, de procesamiento, validacion, PDF, Excel y calculo.
- `loading_context` como context manager para mostrar/limpiar loaders.
- Skeleton de tabla.
- Barra de progreso con porcentaje (`get_progress_html`).

## Dependencias
- `streamlit`, `contextlib`.

## Supuestos
- El HTML/CSS inyectado es compatible con el tema y clases actuales.

## Vacios y riesgos
- La capa es visual, sin control de tiempos reales ni cancelacion.
- Cambios de DOM interno de Streamlit podrian afectar estilos custom.

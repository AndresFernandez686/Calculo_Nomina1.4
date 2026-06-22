# DOCS_MAP

## Objetivo
Este indice organiza la documentacion tecnica del proyecto para mantenimiento, onboarding y cambios seguros.

## Como usar este mapa
1. Leer `README.md` para contexto funcional y flujo de usuario.
2. Leer `docs/ARQUITECTURA_GENERAL.md` para vista de alto nivel.
3. Segun la tarea, ir al documento por archivo indicado abajo.
4. Antes de cambiar reglas de negocio, revisar riesgos y supuestos en cada modulo.

## Documentos generados

| Documento | Proposito | Cuando leerlo |
|---|---|---|
| `docs/ARQUITECTURA_GENERAL.md` | Flujo end-to-end, componentes, dependencias y puntos de entrada | Siempre al iniciar trabajo en el repo |
| `docs/main.py.md` | Orquestacion UI y procesamiento en Streamlit | Cambios en flujo principal, carga de archivos o session state |
| `docs/data_processor.py.md` | Reglas de calculo por fila, agregados y exportacion | Cambios de negocio en sueldo, feriados, descuentos, validaciones |
| `docs/calculations.py.md` | Funciones atomicas de horas normales/especiales y formato | Ajustes de rango de horas especiales o conversiones de tiempo |
| `docs/pdf_processor.py.md` | Extraccion y normalizacion desde PDF a DataFrame estandar | Fallas en lectura de PDF o nuevos formatos de reporte |
| `docs/smart_parser.py.md` | Parsing de fecha/hora y agrupacion inteligente entrada/salida | Ajustes de heuristicas y formatos de fecha/hora |
| `docs/ui_components.py.md` | Controles Streamlit, editores de correccion y aplicacion de cambios | Cambios UX, formularios o logica de correccion manual |
| `docs/loading_components.py.md` | Componentes de loading y progreso reutilizables | Mejoras de feedback visual y placeholders |
| `docs/styles.css.md` | Sistema visual CSS y personalizacion de widgets Streamlit | Cambios visuales, responsive y consistencia de estilo |
| `docs/operacion_y_scripts.md` | Dependencias Python y scripts de ejecucion en Windows | Setup local, ejecucion, soporte operacional |

## Relacion entre documentos
- `docs/main.py.md` depende de `docs/ui_components.py.md`, `docs/data_processor.py.md`, `docs/pdf_processor.py.md` y `docs/loading_components.py.md`.
- `docs/data_processor.py.md` depende de `docs/calculations.py.md`.
- `docs/pdf_processor.py.md` depende de `docs/smart_parser.py.md`.
- `docs/operacion_y_scripts.md` cruza todo porque define entorno y forma de arranque.

## Cobertura y limites
- Cobertura actual: todos los archivos fuente principales del raiz del proyecto.
- Limite: no se documentan detalles de `.git/`, `.devcontainer/` ni `__pycache__/` por no aportar reglas funcionales.
- Limite: no se valida comportamiento en runtime en este documento; es analisis estatico del codigo.

## Riesgos globales detectados
- Rutas absolutas en scripts `.bat` pueden romper ejecucion fuera del entorno original.
- Existen dos definiciones de `validar_datos_pdf` en `pdf_processor.py`; la segunda sobrescribe la primera.
- Fuertes acoplamientos a `st.session_state` en UI pueden generar efectos colaterales en flujos largos.

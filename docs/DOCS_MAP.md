# DOCS_MAP

## Objetivo

Este índice organiza la documentación técnica del proyecto para mantenimiento, onboarding y cambios seguros.

## Cómo usar este mapa

1. Leer `README.md` para contexto funcional y flujo de usuario.
2. Leer `docs/ARQUITECTURA_GENERAL.md` para vista de alto nivel.
3. Según la tarea, ir al documento por archivo indicado abajo.
4. Antes de cambiar reglas de negocio, revisar riesgos y supuestos en cada módulo.

## Documentos generados

| Documento | Propósito | Cuándo leerlo |
| --- | --- | --- |
| `docs/ARQUITECTURA_GENERAL.md` | Flujo end-to-end, componentes, dependencias y puntos de entrada | Siempre al iniciar trabajo en el repo |
| `docs/main.py.md` | Referencia histórica del flujo previo en Streamlit | Solo para contexto de migración o trazabilidad |
| `docs/data_processor.py.md` | Reglas de cálculo por fila, agregados y exportación | Cambios de negocio en sueldo, feriados, descuentos, validaciones |
| `docs/calculations.py.md` | Funciones atómicas de horas normales/especiales y formato | Ajustes de rango de horas especiales o conversiones de tiempo |
| `docs/pdf_processor.py.md` | Extracción y normalización desde PDF a DataFrame estándar | Fallas en lectura de PDF o nuevos formatos de reporte |
| `docs/smart_parser.py.md` | Parsing de fecha/hora y agrupación inteligente entrada/salida | Ajustes de heurísticas y formatos de fecha/hora |
| `docs/ui_components.py.md` | Controles Streamlit, editores de corrección y aplicación de cambios | Cambios UX, formularios o lógica de corrección manual |
| `docs/loading_components.py.md` | Componentes de loading y progreso reutilizables | Mejoras de feedback visual y placeholders |
| `docs/styles.css.md` | Sistema visual CSS y personalización de widgets Streamlit | Cambios visuales, responsive y consistencia de estilo |
| `docs/operacion_y_scripts.md` | Dependencias Python y scripts de ejecución en Windows | Setup local, ejecución, soporte operacional |
| `docs/liquidaciones.md` | Esquema y flujo de liquidaciones y promedios laborales | Cambios en vacaciones, promedio salarial o cálculo legal |

## Nota de versión actual

- El punto de entrada operativo actual es `app.py` (Flask).
- Las reglas de liquidación vigentes (salario pendiente prorrateado, aguinaldo histórico, estado de vacaciones y periodos registrados) están documentadas en `docs/liquidaciones.md`.

## Relación entre documentos

- `docs/main.py.md` depende de `docs/ui_components.py.md`, `docs/data_processor.py.md`, `docs/pdf_processor.py.md` y `docs/loading_components.py.md`.
- `docs/data_processor.py.md` depende de `docs/calculations.py.md`.
- `docs/pdf_processor.py.md` depende de `docs/smart_parser.py.md`.
- `docs/operacion_y_scripts.md` cruza todo porque define entorno y forma de arranque.

## Cobertura y límites

- Cobertura actual: todos los archivos fuente principales del raíz del proyecto.
- Límite: no se documentan detalles de `.git/`, `.devcontainer/` ni `__pycache__/` por no aportar reglas funcionales.
- Límite: no se valida comportamiento en runtime en este documento; es análisis estático del código.

## Riesgos globales detectados

- Rutas absolutas en scripts `.bat` pueden romper ejecución fuera del entorno original.
- Existen dos definiciones de `validar_datos_pdf` en `pdf_processor.py`; la segunda sobrescribe la primera.
- Fuertes acoplamientos a `st.session_state` en UI pueden generar efectos colaterales en flujos largos.

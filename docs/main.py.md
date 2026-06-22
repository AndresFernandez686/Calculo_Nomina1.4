# main.py

## Rol
Punto de entrada Streamlit y orquestador principal del flujo de negocio.

## Responsabilidades
- Configurar pagina y cargar estilos CSS.
- Renderizar header y bloques de configuracion.
- Delegar widgets a `ui_components.py`.
- Ejecutar pipeline Excel/PDF y mostrar resultados.
- Gestionar `st.session_state` para salida de app y limpieza de correcciones.

## Flujo principal
1. Configura Streamlit (`set_page_config`).
2. Carga CSS desde `styles.css`.
3. Muestra configuracion (valor hora, plantilla, feriados, subida archivo).
4. Si archivo es Excel:
   - Lee DataFrame.
   - Valida columnas.
   - Filtra sin asistencia.
   - Solicita correcciones incompletos y ambiguos.
   - Calcula y muestra resultados.
5. Si archivo es PDF:
   - Procesa uno o varios PDFs.
   - Valida y concatena DataFrames.
   - Aplica mismo flujo de correcciones.
   - Calcula y muestra resultados.

## Dependencias directas
- UI: `ui_components.py`.
- Datos: `data_processor.py`.
- PDF/correcciones: `pdf_processor.py`.
- Loading: `loading_components.py`.
- Librerias: `streamlit`, `pandas`.

## Datos de entrada/salida
- Entrada: archivo Excel o lista de PDFs, valor por hora, fechas de feriado.
- Salida: visualizacion de tabla y metricas + descarga de Excel final.

## Supuestos
- El archivo Excel trae columnas esperadas.
- Los indices del DataFrame siguen siendo estables para aplicar correcciones.
- En PDF, un maximo de 2 archivos por UX (quincenas).

## Vacios y riesgos
- Codigo de orquestacion extenso en un solo archivo, dificil de testear.
- `st.stop()` interrumpe flujo y depende de interaccion del usuario para continuar.
- Errores en parseo PDF pueden dejar estados parciales no triviales.

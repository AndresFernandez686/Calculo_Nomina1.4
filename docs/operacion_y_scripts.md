# Operacion y scripts

## Dependencias Python
Definidas en `requirements.txt`:
- streamlit
- pandas
- matplotlib
- openpyxl
- PyPDF2
- pdfplumber
- python-dateutil
- regex

## Scripts de arranque

### run_app.bat
- Instala requerimientos.
- Ejecuta `python -m streamlit run main.py`.
- Tiene ruta absoluta fija con version antigua del proyecto.

### test_run.bat
- Valida `main.py`.
- Verifica streamlit e instala si falta.
- Ejecuta `streamlit run main.py`.
- Tambien usa ruta absoluta fija y antigua.

## Recomendaciones de mantenimiento
- Reemplazar rutas absolutas por rutas relativas al script (`%~dp0`).
- Evitar instalar dependencias en cada ejecucion normal.
- Documentar version minima de Python y flujo de entorno virtual.

## Riesgos operativos
- En otras maquinas, los `.bat` pueden fallar por rutas hardcodeadas.
- Instalar paquetes en cada arranque puede aumentar tiempo y riesgo de conflictos.

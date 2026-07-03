# Calculadora de Sueldos v1.4

Sistema web en Flask para gestionar asistencia, calcular sueldos, administrar nómina y generar liquidaciones laborales para Paraguay.

## Resumen del Sistema

- Carga de asistencia por Excel o por hasta 2 PDFs en una sola operación.
- Cálculo de horas normales, horas especiales (20:00-22:00, +30%) y feriados (x2).
- Gestión de descuentos (inventario, caja, retiro) y cálculo de sueldo final.
- Historial por empleado, por mes, con vista detallada, agrupación por año y exportación.

## Módulo de Historial Salarial (nuevo en v1.4)

- Tabla `historial_salarios` que registra **cada cambio de valor por hora** con fecha, motivo y usuario.
- **Los registros históricos nunca se sobreescriben**: al registrar un aumento, el registro anterior se cierra automáticamente (`fecha_fin = nueva_fecha - 1 día`).
- Cada nómina almacena una copia del `valor_hora_utilizado` al momento del cálculo (inmutable).
- Vista de línea de tiempo con todos los cambios salariales del empleado.
- Motivos de cambio: Ingreso, Ascenso, Aumento por salario mínimo, Ajuste, Otro.
- Accesible desde la página de nómina del empleado (“Historial salarial”).
- **Objetivo:** garantizar trazabilidad completa y que cualquier liquidación sea reproducible exactamente con los datos históricos.

## Módulo de Liquidaciones

- Vista de liquidaciones por empleado con interfaz renovada.
- Pestañas: Nueva liquidación, Historial, Exportar PDF.
- Historial persistente con desglose completo por concepto auditable.
- Salario pendiente con toggle “¿Ya se pagó el último sueldo mensual?” (mes completo vs. días proporcionales).
- Aguinaldo proporcional con desglose mes a mes (auditable, art. 243 CT).
- Vacaciones con detalle de antigüedad, valor día y monto total.
- Promedio salarial últimos meses (art. 92 CT) con tabla mensual.
- Preaviso e indemnización según escala legal art. 87 CT (4 tramos hasta 90 días).
- Base legal implementada según Código Laboral Paraguayo (Ley 213/93).

## Persistencia y Migración

- Migración automática al arrancar para columnas nuevas en tablas existentes.
- Tablas principales: `employees`, `employee_payroll`, `calculation_runs`, `historial_salarios`, `liquidaciones`, `promedios_laborales`.
- Ver `docs/BASE_DE_DATOS_RESUMEN.md` y `docs/HISTORIAL_SALARIAL.md` para detalle completo.

## Interfaz y UX

- Diseño unificado en tarjetas, tabs y bloques de métricas.
- Modo oscuro global con switch estilo iOS en el encabezado.
- Responsive para cualquier tamaño de dispositivo.
- Historial de liquidaciones con búsqueda, badges de tipo/estado y detalles expandibles.
- Loading overlay con mínimo de 10 s en acciones críticas.

## Ejecución Rápida

```bash
pip install -r requirements.txt
python app.py
```

## Stack Tecnológico

- Backend: Flask + SQLAlchemy
- Datos: Pandas + OpenPyXL
- PDF: pdfplumber
- Frontend: HTML + CSS + JavaScript

Estado: En evolución activa

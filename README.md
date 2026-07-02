# Calculadora de Sueldos v1.4

Sistema web en Flask para gestionar asistencia, calcular sueldos y administrar nómina por empleado con historial mensual.

## Resumen del Sistema

- Carga de asistencia por Excel o por hasta 2 PDFs en una sola operación.
- Cálculo de horas normales, horas especiales (20:00-22:00, +30%) y feriados (x2).
- Gestión de descuentos (inventario, caja, retiro) y cálculo de sueldo final.
- Historial por empleado, por mes, con vista detallada, agrupación por año y exportación.

## Funcionalidades Clave

- Seguro IPS configurable por cálculo (Sí/No).
- Desglose IPS completo: descuento del empleado, aporte empleador, total IPS y salario neto.
- Detección/corrección de registros incompletos (marcado único) y horarios ambiguos.
- Reemplazo inteligente de meses ya cargados para evitar duplicados.

## Módulo de Liquidaciones

- Vista de liquidaciones por empleado con interfaz renovada.
- Pestañas ordenadas por flujo operativo: Nueva liquidación, Historial, Exportar PDF.
- Después de generar una liquidación, la vista redirige automáticamente a Historial.
- Historial persistente de liquidaciones por empleado con desglose completo por concepto.
- Cálculo de liquidación basado en historial real del empleado (nómina cargada).
- Salario pendiente prorrateado por fecha de salida.
  - Si existe nómina del mismo mes de salida, usa los registros hasta esa fecha.
  - Si no existe nómina en ese mes, estima solo el tramo transcurrido del mes de salida usando promedio diario del último mes registrado.
- Aguinaldo proporcional calculado desde periodos históricos previos en orden cronológico.
- Vacaciones generadas/usadas/pendientes con persistencia en base de datos.
- Estado de vacaciones mostrando periodos registrados (meses realmente cargados).
- Tarjeta visual "Composición de la liquidación (%)" con donut por concepto sobre el total a pagar.
- Tarjeta visual "Línea de tiempo de antigüedad y derechos" con fecha de ingreso/salida, períodos completos, proporcional y aguinaldo devengado.
- Base legal implementada según Código Laboral Paraguayo:
  - 1 a 5 años: 12 días.
  - Más de 5 a 10 años: 18 días.
  - Más de 10 años: 30 días.

## Persistencia y Migración

- Se guardan liquidaciones históricas por empleado en `liquidaciones`.
- Se guardan promedios usados en liquidación en `promedios_laborales`.
- Migración automática al arrancar para columnas nuevas de `employees`:
  - `hire_date`
  - `liquidation_type`
  - `vacation_generated_days`
  - `vacation_used_days`
  - `vacation_pending_days`
  - `vacation_used_from`
  - `vacation_used_to`

## Interfaz y UX

- Diseño unificado en tarjetas, tabs y bloques de métricas.
- Modo oscuro global con switch estilo iOS en el encabezado (persistido por navegador).
- Detalle mensual desplegable con mejor visualización de resultados.
- Registros de nómina agrupados por año (cuando hay más de un año) y meses ordenados cronológicamente dentro de cada bloque anual.
- Preparado para extender componentes reutilizables en futuras tarjetas.

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

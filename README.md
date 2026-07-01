# Calculadora de Sueldos v1.4

Sistema web en Flask para gestionar asistencia, calcular sueldos y administrar nómina por empleado con historial mensual.

## Resumen del Sistema

- Carga de asistencia por Excel o por hasta 2 PDFs en una sola operación.
- Cálculo de horas normales, horas especiales (20:00-22:00, +30%) y feriados (x2).
- Gestión de descuentos (inventario, caja, retiro) y cálculo de sueldo final.
- Historial por empleado, por mes, con vista detallada y exportación.

## Funcionalidades Clave

- Seguro IPS configurable por cálculo (Sí/No).
- Desglose IPS completo: descuento del empleado, aporte empleador, total IPS y salario neto.
- Detección/corrección de registros incompletos (marcado único) y horarios ambiguos.
- Reemplazo inteligente de meses ya cargados para evitar duplicados.

## Módulo de Liquidaciones

- Vista de liquidaciones por empleado con interfaz renovada.
- Sección Nueva liquidación con resumen de cálculo y tipos de liquidación.
- Cálculo de vacaciones automático por antigüedad y proporcional por rango de fechas.
- Base legal implementada según Código Laboral Paraguayo:
  - 1 a 5 años: 12 días.
  - Más de 5 a 10 años: 18 días.
  - Más de 10 años: 30 días.

## Interfaz y UX

- Diseño unificado en tarjetas, tabs y bloques de métricas.
- Detalle mensual desplegable con mejor visualización de resultados.
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

# Organización de las liquidaciones

Las funciones que estaban en `app.py` se distribuyen así:

- `payroll/liquidaciones/servicios.py`: consultas salariales y cálculos de salario pendiente, aguinaldo, vacaciones, preaviso, indemnización y antigüedad.
- `payroll/liquidaciones/vistas.py`: atención de GET/POST, guardado e historial de liquidaciones y datos para la plantilla.
- `payroll/periodos.py`: agrupación de registros por mes y nombres de períodos, compartidos con las otras vistas de nómina.
- `payroll/configuracion.py`: valor por hora predeterminado compartido.

`app.py` inicializa Flask y registra la ruta mediante `registrar_rutas_liquidaciones(app)`. Se conserva la URL `/empleado/<int:empleado_id>/liquidaciones` y el endpoint `liquidaciones`, por lo que las plantillas y redirecciones siguen usando `url_for("liquidaciones", ...)`.

Para ampliar los cálculos actuales, modificar `servicios.py`; para agregar acciones o datos de pantalla, modificar `vistas.py`. Los módulos no deben importar `app.py`: usan los modelos y `db` de `payroll.models` dentro del contexto de Flask.

El motor existente de conceptos, tipos y montos en el resto de `payroll/liquidaciones/` se mantiene. Esta separación traslada las funciones actuales sin cambiar las fórmulas ni sustituirlas por ese motor.

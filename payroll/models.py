"""
Modelos de base de datos (SQLAlchemy) para la Calculadora de Sueldos.

Se persisten los cálculos realizados y el detalle por empleado/día,
de modo que puedan consultarse en el historial.
"""
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class CalculationRun(db.Model):
    """Una ejecución de cálculo de sueldos (un lote procesado)."""

    __tablename__ = "calculation_runs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    source_name = db.Column(db.String(255), nullable=True)
    source_type = db.Column(db.String(20), nullable=False, default="excel")
    valor_por_hora = db.Column(db.Float, nullable=False, default=0.0)
    feriados = db.Column(db.String(255), nullable=True)  # fechas separadas por coma

    total_horas = db.Column(db.Float, nullable=False, default=0.0)
    total_horas_normales = db.Column(db.Float, nullable=False, default=0.0)
    total_horas_especiales = db.Column(db.Float, nullable=False, default=0.0)
    total_sueldos = db.Column(db.Float, nullable=False, default=0.0)
    total_registros = db.Column(db.Integer, nullable=False, default=0)

    records = db.relationship(
        "EmployeeRecord",
        backref="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
            "source_name": self.source_name,
            "source_type": self.source_type,
            "valor_por_hora": self.valor_por_hora,
            "feriados": self.feriados,
            "total_horas": self.total_horas,
            "total_horas_normales": self.total_horas_normales,
            "total_horas_especiales": self.total_horas_especiales,
            "total_sueldos": self.total_sueldos,
            "total_registros": self.total_registros,
        }


class EmployeeRecord(db.Model):
    """Detalle de un registro calculado (un empleado en un día)."""

    __tablename__ = "employee_records"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(
        db.Integer, db.ForeignKey("calculation_runs.id"), nullable=False
    )

    empleado = db.Column(db.String(255), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    entrada = db.Column(db.String(10), nullable=True)
    salida = db.Column(db.String(10), nullable=True)
    feriado = db.Column(db.String(5), nullable=True)
    horas_trabajadas = db.Column(db.String(10), nullable=True)
    horas_normales = db.Column(db.String(10), nullable=True)
    horas_especiales = db.Column(db.String(10), nullable=True)
    descuento_inventario = db.Column(db.Float, nullable=False, default=0.0)
    descuento_caja = db.Column(db.Float, nullable=False, default=0.0)
    retiro = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_final = db.Column(db.Float, nullable=False, default=0.0)
    observaciones = db.Column(db.String(255), nullable=True)

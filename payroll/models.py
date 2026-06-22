"""
Modelos de base de datos (SQLAlchemy) para la Calculadora de Sueldos.

Se persisten los cálculos realizados y el detalle por empleado/día,
de modo que puedan consultarse en el historial.
"""
from datetime import datetime
from typing import Optional

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Employee(db.Model):
    """Representa un empleado del sistema."""

    __tablename__ = "employees"

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    payroll_records = db.relationship(
        "EmployeePayroll",
        backref="employee",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    attendance_uploads = db.relationship(
        "EmployeeAttendance",
        backref="employee",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    calculation_runs = db.relationship(
        "CalculationRun",
        backref="employee",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    records = db.relationship(
        "EmployeeRecord",
        backref="employee",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Employee {self.nombre}>"


class EmployeePayroll(db.Model):
    """Tabla de nómina individual de un empleado."""

    __tablename__ = "employee_payroll"

    id: int = db.Column(db.Integer, primary_key=True)
    employee_id: int = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    fecha: str = db.Column(db.String(20), nullable=False)
    entrada: Optional[str] = db.Column(db.String(10), nullable=True)
    salida: Optional[str] = db.Column(db.String(10), nullable=True)
    feriado: Optional[str] = db.Column(db.String(5), nullable=True)
    horas_trabajadas: Optional[str] = db.Column(db.String(10), nullable=True)
    horas_normales: float = db.Column(db.Float, nullable=False, default=0.0)
    horas_especiales: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_inventario: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_caja: float = db.Column(db.Float, nullable=False, default=0.0)
    retiro: float = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_final: float = db.Column(db.Float, nullable=False, default=0.0)
    observaciones: Optional[str] = db.Column(db.String(255), nullable=True)
    run_id: Optional[int] = db.Column(db.Integer, nullable=True)  # Referencia al cálculo que generó este registro


class EmployeeAttendance(db.Model):
    """Registros de archivos de asistencia vinculados a un empleado."""

    __tablename__ = "employee_attendances"

    id: int = db.Column(db.Integer, primary_key=True)
    employee_id: int = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=False
    )
    run_id: Optional[int] = db.Column(db.Integer, db.ForeignKey("calculation_runs.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    source_name: Optional[str] = db.Column(db.String(255), nullable=False)
    source_type: str = db.Column(db.String(20), nullable=False, default="excel")
    total_registros: int = db.Column(db.Integer, nullable=False, default=0)


class CalculationRun(db.Model):
    """Una ejecución de cálculo de sueldos (un lote procesado)."""

    __tablename__ = "calculation_runs"

    id: int = db.Column(db.Integer, primary_key=True)
    employee_id: Optional[int] = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    source_name: Optional[str] = db.Column(db.String(255), nullable=True)
    source_type: str = db.Column(db.String(20), nullable=False, default="excel")
    valor_por_hora: float = db.Column(db.Float, nullable=False, default=0.0)
    feriados: Optional[str] = db.Column(db.String(255), nullable=True)  # fechas separadas por coma

    total_horas: float = db.Column(db.Float, nullable=False, default=0.0)
    total_horas_normales: float = db.Column(db.Float, nullable=False, default=0.0)
    total_horas_especiales: float = db.Column(db.Float, nullable=False, default=0.0)
    total_sueldos: float = db.Column(db.Float, nullable=False, default=0.0)
    total_registros: int = db.Column(db.Integer, nullable=False, default=0)

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

    id: int = db.Column(db.Integer, primary_key=True)
    run_id: int = db.Column(
        db.Integer, db.ForeignKey("calculation_runs.id"), nullable=False
    )
    employee_id: Optional[int] = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=True
    )

    empleado: str = db.Column(db.String(255), nullable=False)
    fecha: str = db.Column(db.String(20), nullable=False)
    entrada: Optional[str] = db.Column(db.String(10), nullable=True)
    salida: Optional[str] = db.Column(db.String(10), nullable=True)
    feriado: Optional[str] = db.Column(db.String(5), nullable=True)
    horas_trabajadas: Optional[str] = db.Column(db.String(10), nullable=True)
    horas_normales: float = db.Column(db.Float, nullable=False, default=0.0)
    horas_especiales: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_inventario: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_caja: float = db.Column(db.Float, nullable=False, default=0.0)
    retiro: float = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_final: float = db.Column(db.Float, nullable=False, default=0.0)
    observaciones: Optional[str] = db.Column(db.String(255), nullable=True)

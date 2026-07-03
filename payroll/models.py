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
    hire_date: Optional[str] = db.Column(db.String(20), nullable=True)
    liquidation_type: Optional[str] = db.Column(db.String(50), nullable=True)
    vacation_generated_days: float = db.Column(db.Float, nullable=False, default=0.0)
    vacation_used_days: float = db.Column(db.Float, nullable=False, default=0.0)
    vacation_pending_days: float = db.Column(db.Float, nullable=False, default=0.0)
    vacation_used_from: Optional[str] = db.Column(db.String(20), nullable=True)
    vacation_used_to: Optional[str] = db.Column(db.String(20), nullable=True)

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

    liquidations = db.relationship(
        "Liquidacion",
        backref="employee",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    laboral_averages = db.relationship(
        "PromedioLaboral",
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
    monto_horas_normales: float = db.Column(db.Float, nullable=False, default=0.0)
    monto_horas_especiales: float = db.Column(db.Float, nullable=False, default=0.0)
    monto_feriado: float = db.Column(db.Float, nullable=False, default=0.0)
    bonificacion: float = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_bruto: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_inventario: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_caja: float = db.Column(db.Float, nullable=False, default=0.0)
    retiro: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_ips: float = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_final: float = db.Column(db.Float, nullable=False, default=0.0)
    observaciones: Optional[str] = db.Column(db.String(255), nullable=True)
    run_id: Optional[int] = db.Column(db.Integer, nullable=True)  # Referencia al cálculo que generó este registro
    valor_hora_utilizado: Optional[float] = db.Column(db.Float, nullable=True)  # Copia inmutable del valor hora al generar nómina


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
    total_monto_horas_normales: float = db.Column(db.Float, nullable=False, default=0.0)
    total_monto_horas_especiales: float = db.Column(db.Float, nullable=False, default=0.0)
    total_monto_feriados: float = db.Column(db.Float, nullable=False, default=0.0)
    total_bonificacion: float = db.Column(db.Float, nullable=False, default=0.0)
    total_sueldos: float = db.Column(db.Float, nullable=False, default=0.0)
    total_registros: int = db.Column(db.Integer, nullable=False, default=0)
    seguro_ips: str = db.Column(db.String(5), nullable=False, default="No")
    total_salario_bruto: float = db.Column(db.Float, nullable=False, default=0.0)
    total_descuento_ips: float = db.Column(db.Float, nullable=False, default=0.0)
    total_aporte_empleador_ips: float = db.Column(db.Float, nullable=False, default=0.0)
    total_ips: float = db.Column(db.Float, nullable=False, default=0.0)
    total_salario_neto_ips: float = db.Column(db.Float, nullable=False, default=0.0)

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
            "total_monto_horas_normales": self.total_monto_horas_normales,
            "total_monto_horas_especiales": self.total_monto_horas_especiales,
            "total_monto_feriados": self.total_monto_feriados,
            "total_bonificacion": self.total_bonificacion,
            "total_sueldos": self.total_sueldos,
            "total_registros": self.total_registros,
            "seguro_ips": self.seguro_ips,
            "total_salario_bruto": self.total_salario_bruto,
            "total_descuento_ips": self.total_descuento_ips,
            "total_aporte_empleador_ips": self.total_aporte_empleador_ips,
            "total_ips": self.total_ips,
            "total_salario_neto_ips": self.total_salario_neto_ips,
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
    monto_horas_normales: float = db.Column(db.Float, nullable=False, default=0.0)
    monto_horas_especiales: float = db.Column(db.Float, nullable=False, default=0.0)
    monto_feriado: float = db.Column(db.Float, nullable=False, default=0.0)
    bonificacion: float = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_bruto: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_inventario: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_caja: float = db.Column(db.Float, nullable=False, default=0.0)
    descuento_ips: float = db.Column(db.Float, nullable=False, default=0.0)
    retiro: float = db.Column(db.Float, nullable=False, default=0.0)
    sueldo_final: float = db.Column(db.Float, nullable=False, default=0.0)
    observaciones: Optional[str] = db.Column(db.String(255), nullable=True)


class Liquidacion(db.Model):
    """Cabecera histórica de liquidaciones por empleado."""

    __tablename__ = "liquidaciones"

    id: int = db.Column(db.Integer, primary_key=True)
    empleado_id: int = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    tipo: str = db.Column(db.String(50), nullable=False)
    fecha_salida: Optional[str] = db.Column(db.String(20), nullable=True)
    salario_pendiente: float = db.Column(db.Float, nullable=False, default=0.0)
    aguinaldo: float = db.Column(db.Float, nullable=False, default=0.0)
    vacaciones: float = db.Column(db.Float, nullable=False, default=0.0)
    preaviso: float = db.Column(db.Float, nullable=False, default=0.0)
    indemnizacion: float = db.Column(db.Float, nullable=False, default=0.0)
    total_liquidacion: float = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PromedioLaboral(db.Model):
    """Promedio salarial usado para liquidaciones y vacaciones."""

    __tablename__ = "promedios_laborales"

    id: int = db.Column(db.Integer, primary_key=True)
    empleado_id: int = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    periodo: str = db.Column(db.String(50), nullable=False)
    total_salarios: float = db.Column(db.Float, nullable=False, default=0.0)
    dias_trabajados: int = db.Column(db.Integer, nullable=False, default=0)
    promedio_diario: float = db.Column(db.Float, nullable=False, default=0.0)
    promedio_mensual: float = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class HistorialSalarios(db.Model):
    """Historial de cambios de valor por hora para un empleado (inmutable).

    Cada registro cubre un período: desde ``fecha_inicio`` hasta ``fecha_fin``
    (null = vigente). Al registrar un aumento se cierra el anterior asignando
    ``fecha_fin = nueva_fecha_inicio - 1 día``.
    """

    __tablename__ = "historial_salarios"

    MOTIVOS = ["Ingreso", "Ascenso", "Aumento por salario mínimo", "Ajuste", "Otro"]

    id: int = db.Column(db.Integer, primary_key=True)
    empleado_id: int = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=False
    )
    fecha_inicio: str = db.Column(db.String(20), nullable=False)
    fecha_fin: Optional[str] = db.Column(db.String(20), nullable=True)  # null = vigente
    valor_hora: float = db.Column(db.Float, nullable=False)
    motivo_cambio: str = db.Column(
        db.String(50), nullable=False, default="Ingreso"
    )
    observaciones: Optional[str] = db.Column(db.String(500), nullable=True)
    usuario: Optional[str] = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        estado = "vigente" if self.fecha_fin is None else f"hasta {self.fecha_fin}"
        return f"<HistorialSalarios emp={self.empleado_id} desde={self.fecha_inicio} {estado} Gs.{self.valor_hora:,.0f}>"

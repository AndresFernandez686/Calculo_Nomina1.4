"""Cálculo de vacaciones para liquidación de empleados."""

from datetime import date, datetime, timedelta
from typing import Any

MESES_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _fin_de_mes(anio: int, mes: int) -> date:
    if mes == 12:
        return date(anio, mes, 31)
    return date(anio, mes + 1, 1) - timedelta(days=1)


def _normalizar_fecha(valor: Any, usar_fin_mes: bool = False) -> date:
    """Convierte fechas en distintos formatos a date."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor

    texto = str(valor).strip().lower()
    if not texto:
        raise ValueError("Fecha vacía")

    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    for formato in ("%Y-%m", "%m/%Y"):
        try:
            parsed = datetime.strptime(texto, formato)
            if usar_fin_mes:
                return _fin_de_mes(parsed.year, parsed.month)
            return date(parsed.year, parsed.month, 1)
        except ValueError:
            continue

    partes = texto.split()
    if len(partes) == 2 and partes[0] in MESES_ES and partes[1].isdigit():
        anio = int(partes[1])
        mes = MESES_ES[partes[0]]
        if usar_fin_mes:
            return _fin_de_mes(anio, mes)
        return date(anio, mes, 1)

    raise ValueError(f"Formato de fecha no soportado: {valor}")


def _dias_anuales_por_antiguedad(anios_cumplidos: int) -> int:
    """Escala legal Paraguay: 1-5 => 12, >5-10 => 18, >10 => 30."""
    if anios_cumplidos <= 5:
        return 12
    if anios_cumplidos <= 10:
        return 18
    return 30


def calcular_vacaciones_por_rango(fecha_inicio: Any, fecha_fin: Any) -> dict[str, Any]:
    """
    Calcula vacaciones acumuladas según días trabajados.

    Fórmula aplicada:
    - Tramos anuales completos: suma de días legales por cada año cumplido.
    - Tramo incompleto: (días_tramo / 365) * días_legales_del_siguiente_año.
    """
    inicio = _normalizar_fecha(fecha_inicio, usar_fin_mes=False)
    fin = _normalizar_fecha(fecha_fin, usar_fin_mes=True)
    if fin < inicio:
        raise ValueError("La fecha fin no puede ser menor que la fecha inicio")

    dias_trabajados = (fin - inicio).days + 1
    anios_completos = dias_trabajados // 365
    dias_restantes = dias_trabajados % 365

    vacaciones = 0.0
    for anio in range(1, anios_completos + 1):
        vacaciones += _dias_anuales_por_antiguedad(anio)

    if dias_restantes > 0:
        vacaciones += (dias_restantes / 365) * _dias_anuales_por_antiguedad(anios_completos + 1)

    vacaciones = round(vacaciones, 2)
    return {
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": fin.isoformat(),
        "dias_trabajados": dias_trabajados,
        "dias_vacaciones": vacaciones,
        "mensaje": (
            f"Trabajado {dias_trabajados} dias\n"
            f"Corresponde {vacaciones} dias de vacaciones"
        ),
    }


def calcular_vacaciones_desde_historial(
    historial_mensual: list[dict[str, Any]],
    fecha_inicio: Any | None = None,
    fecha_fin: Any | None = None,
) -> dict[str, Any]:
    """
    Toma el historial del empleado y calcula vacaciones automáticamente.

    Si no recibe fechas directas, usa la menor y mayor fecha encontrada en
    las claves comunes del historial: fecha / Fecha / created_at.
    """
    if fecha_inicio is None or fecha_fin is None:
        fechas_historial = []
        for registro in historial_mensual:
            for key in ("fecha", "Fecha", "created_at"):
                if key in registro and registro[key]:
                    fechas_historial.append(str(registro[key]))
                    break

        if not fechas_historial:
            raise ValueError("No hay fechas en el historial para calcular vacaciones")

        fechas_ordenadas = sorted(
            _normalizar_fecha(f, usar_fin_mes=False) for f in fechas_historial
        )
        fecha_inicio = fecha_inicio or fechas_ordenadas[0]
        fecha_fin = fecha_fin or fechas_ordenadas[-1]

    return calcular_vacaciones_por_rango(fecha_inicio, fecha_fin)


def obtener_mensaje_liquidacion(
    historial_mensual: list[dict[str, Any]] | None = None,
    fecha_inicio: Any | None = None,
    fecha_fin: Any | None = None,
) -> str:
    """Compatibilidad con app.py: retorna el texto de liquidación."""
    if historial_mensual or (fecha_inicio is not None and fecha_fin is not None):
        resultado = calcular_vacaciones_desde_historial(
            historial_mensual=historial_mensual or [],
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        return str(resultado["mensaje"])

    return "Sin datos suficientes para calcular vacaciones"

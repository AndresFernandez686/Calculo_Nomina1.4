"""Valores predeterminados compartidos de la aplicación."""

VALOR_POR_HORA_DEFAULT = 13937.0


def normalizar_valor_por_hora(valor) -> float:
    """Acepta importes enteros con puntos o comas como separadores de miles."""
    import re

    texto = str(valor).strip()
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(\.[0-9]{3})+|[0-9]{1,3}(,[0-9]{3})+)", texto):
        raise ValueError("Valor por hora inválido")
    monto = int(texto.replace(".", "").replace(",", ""))
    if monto > 9007199254740991:
        raise ValueError("Valor por hora fuera de rango")
    return float(monto)

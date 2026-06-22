"""
Módulo de cálculos para la aplicación de sueldos
Contiene funciones para cálculo de horas y conversiones
"""
from datetime import datetime, timedelta

def calcular_horas_especiales(entrada_dt, salida_dt):
    """
    Calcula las horas normales y especiales trabajadas.
    Horas especiales son las trabajadas entre 20:00 y 22:00
    
    Args:
        entrada_dt (datetime): Hora de entrada
        salida_dt (datetime): Hora de salida
    
    Returns:
        tuple: (horas_normales, horas_especiales)
    """
    # Calcular total de horas trabajadas
    total_horas = (salida_dt - entrada_dt).total_seconds() / 3600
    
    # Calcular horas especiales (20:00 - 22:00)
    inicio_especial = entrada_dt.replace(hour=20, minute=0, second=0)
    fin_especial = entrada_dt.replace(hour=22, minute=0, second=0)
    
    inicio_interseccion = max(entrada_dt, inicio_especial)
    fin_interseccion = min(salida_dt, fin_especial)
    
    if inicio_interseccion >= fin_interseccion:
        horas_especiales = 0
    else:
        horas_especiales = (fin_interseccion - inicio_interseccion).total_seconds() / 3600
    
    # Horas normales = total - especiales
    horas_normales = total_horas - horas_especiales
    
    return horas_normales, horas_especiales

def horas_a_horasminutos(horas):
    """
    Convierte horas decimales a formato horas:minutos
    
    Args:
        horas (float): Horas en formato decimal
    
    Returns:
        str: Horas en formato "HH:MM"
    """
    horas_int = int(horas)
    minutos = int(round((horas - horas_int) * 60))
    if minutos >= 60:
        horas_int += minutos // 60
        minutos = minutos % 60
    return f"{horas_int}:{minutos:02d}"
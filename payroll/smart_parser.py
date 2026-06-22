"""
Parser inteligente para diferentes formatos de fecha/hora
Maneja automáticamente separación y agrupamiento de datos
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd

class SmartTimeParser:
    """Clase para parsing inteligente de fechas y horas"""
    
    def __init__(self):
        self.patrones_fecha = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{1,2}/\d{1,2}/\d{4})',  # DD/MM/YYYY o MM/DD/YYYY
            r'(\d{1,2}-\d{1,2}-\d{4})',  # DD-MM-YYYY
            r'(\d{1,2}\.\d{1,2}\.\d{4})',  # DD.MM.YYYY
        ]
        
        self.patrones_hora = [
            r'(\d{1,2}:\d{2}:\d{2})',  # HH:MM:SS
            r'(\d{1,2}:\d{2})',  # HH:MM
            r'(\d{1,2}\.\d{2})',  # HH.MM
        ]
        
        self.patrones_fecha_hora = [
            r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}:\d{2})',  # YYYY-MM-DD HH:MM:SS
            r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})',  # YYYY-MM-DD HH:MM
            r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})',  # DD/MM/YYYY HH:MM:SS
            r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2})',  # DD/MM/YYYY HH:MM
            r'(\d{1,2}-\d{1,2}-\d{4})\s+(\d{1,2}:\d{2}:\d{2})',  # DD-MM-YYYY HH:MM:SS
            r'(\d{1,2}-\d{1,2}-\d{4})\s+(\d{1,2}:\d{2})',  # DD-MM-YYYY HH:MM
        ]
    
    def extraer_fecha_hora(self, texto: str) -> List[Dict]:
        """
        Extrae todas las fechas y horas de un texto
        
        Args:
            texto: Texto a procesar
            
        Returns:
            List[Dict]: Lista de fechas y horas encontradas
        """
        resultados = []
        
        # Buscar patrones de fecha y hora juntas
        for patron in self.patrones_fecha_hora:
            matches = re.finditer(patron, texto)
            for match in matches:
                fecha_str = match.group(1)
                hora_str = match.group(2)
                
                fecha_normalizada = self.normalizar_fecha(fecha_str)
                hora_normalizada = self.normalizar_hora(hora_str)
                
                if fecha_normalizada and hora_normalizada:
                    resultados.append({
                        'fecha': fecha_normalizada,
                        'hora': hora_normalizada,
                        'texto_original': match.group(0),
                        'posicion': match.start()
                    })
        
        return resultados
    
    def normalizar_fecha(self, fecha_str: str) -> Optional[str]:
        """
        Normaliza diferentes formatos de fecha a YYYY-MM-DD
        
        Args:
            fecha_str: String de fecha en formato variable
            
        Returns:
            str: Fecha normalizada o None si no se puede procesar
        """
        try:
            # Formato YYYY-MM-DD (ya normalizado)
            if re.match(r'\d{4}-\d{2}-\d{2}', fecha_str):
                return fecha_str
            
            # Formato DD/MM/YYYY
            if re.match(r'\d{1,2}/\d{1,2}/\d{4}', fecha_str):
                partes = fecha_str.split('/')
                if len(partes) == 3:
                    dia, mes, año = partes
                    return f"{año}-{mes.zfill(2)}-{dia.zfill(2)}"
            
            # Formato DD-MM-YYYY
            if re.match(r'\d{1,2}-\d{1,2}-\d{4}', fecha_str):
                partes = fecha_str.split('-')
                if len(partes) == 3:
                    dia, mes, año = partes
                    return f"{año}-{mes.zfill(2)}-{dia.zfill(2)}"
            
            # Formato DD.MM.YYYY
            if re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', fecha_str):
                partes = fecha_str.split('.')
                if len(partes) == 3:
                    dia, mes, año = partes
                    return f"{año}-{mes.zfill(2)}-{dia.zfill(2)}"
                    
        except Exception:
            pass
            
        return None
    
    def normalizar_hora(self, hora_str: str) -> Optional[str]:
        """
        Normaliza diferentes formatos de hora a HH:MM
        
        Args:
            hora_str: String de hora en formato variable
            
        Returns:
            str: Hora normalizada o None si no se puede procesar
        """
        try:
            # Formato HH:MM:SS -> HH:MM
            if re.match(r'\d{1,2}:\d{2}:\d{2}', hora_str):
                return hora_str[:5]
            
            # Formato HH:MM (ya normalizado)
            if re.match(r'\d{1,2}:\d{2}', hora_str):
                partes = hora_str.split(':')
                return f"{partes[0].zfill(2)}:{partes[1]}"
            
            # Formato HH.MM -> HH:MM
            if re.match(r'\d{1,2}\.\d{2}', hora_str):
                return hora_str.replace('.', ':')
                
        except Exception:
            pass
            
        return None

class EntradaSalidaDetector:
    """Clase para detectar automáticamente entrada y salida"""
    
    def __init__(self):
        self.palabras_entrada = [
            'entrada', 'entry', 'in', 'inicio', 'start', 'llegada', 'ingreso'
        ]
        self.palabras_salida = [
            'salida', 'exit', 'out', 'fin', 'end', 'partida', 'egreso'
        ]
    
    def detectar_tipo(self, texto: str, hora: str, context: Optional[List[str]] = None) -> str:
        """
        Detecta si una hora es entrada o salida
        
        Args:
            texto: Texto que contiene la hora
            hora: Hora en formato HH:MM
            context: Contexto adicional (líneas anteriores/posteriores)
            
        Returns:
            str: 'Entrada' o 'Salida'
        """
        texto_lower = texto.lower()
        
        # Búsqueda por palabras clave
        for palabra in self.palabras_entrada:
            if palabra in texto_lower:
                return 'Entrada'
        
        for palabra in self.palabras_salida:
            if palabra in texto_lower:
                return 'Salida'
        
        # Detección por hora (heurística)
        try:
            hora_obj = datetime.strptime(hora, '%H:%M').time()
            
            # Antes de las 12:00 probablemente sea entrada
            if hora_obj.hour < 12:
                return 'Entrada'
            # Después de las 15:00 probablemente sea salida
            elif hora_obj.hour >= 15:
                return 'Salida'
            # Entre 12:00 y 15:00 es ambiguo, usar contexto
            else:
                if context:
                    return self._analizar_contexto(context, hora)
                return 'Entrada'  # Por defecto
                
        except Exception:
            return 'Entrada'  # Por defecto
    
    def _analizar_contexto(self, context: List[str], hora: str) -> str:
        """Analiza el contexto para determinar tipo"""
        # Si hay otras horas en el contexto, comparar
        for linea in context:
            parser = SmartTimeParser()
            fecha_horas = parser.extraer_fecha_hora(linea)
            
            for fh in fecha_horas:
                if fh['hora'] != hora:
                    try:
                        hora_ctx = datetime.strptime(fh['hora'], '%H:%M').time()
                        hora_actual = datetime.strptime(hora, '%H:%M').time()
                        
                        # Si hay una hora anterior, esta probablemente sea salida
                        if hora_ctx < hora_actual:
                            return 'Salida'
                        # Si hay una hora posterior, esta probablemente sea entrada
                        elif hora_ctx > hora_actual:
                            return 'Entrada'
                    except:
                        continue
        
        return 'Entrada'  # Por defecto

class DataGrouper:
    """Clase para agrupar datos por empleado y fecha"""
    
    def agrupar_por_empleado_fecha(self, datos: List[Dict]) -> List[Dict]:
        """
        Agrupa datos por empleado y fecha, combinando entradas y salidas
        
        LÓGICA CORREGIDA:
        - Primera hora del día = Entrada
        - Segunda hora del día = Salida
        
        Args:
            datos: Lista de datos con empleado, fecha, hora, tipo
            
        Returns:
            List[Dict]: Datos agrupados
        """
        # Agrupar por empleado y fecha
        grupos = {}
        
        for item in datos:
            clave = f"{item.get('empleado', 'Unknown')}_{item.get('fecha', 'Unknown')}"
            
            if clave not in grupos:
                grupos[clave] = {
                    'empleado': item.get('empleado', 'Unknown'),
                    'fecha': item.get('fecha', 'Unknown'),
                    'horas': [],  # Todas las horas del día
                    'registros': []
                }
            
            grupos[clave]['registros'].append(item)
            grupos[clave]['horas'].append(item.get('hora'))
        
        # Procesar grupos usando lógica: primera hora = entrada, segunda = salida
        resultado = []
        for grupo in grupos.values():
            # Ordenar horas para asegurar el orden correcto
            horas_ordenadas = sorted(set(grupo['horas']))  # Eliminar duplicados y ordenar
            
            # Primera hora = Entrada, Segunda hora = Salida
            entrada_final = horas_ordenadas[0] if len(horas_ordenadas) >= 1 else '08:00'
            
            # Si solo hay UNA hora, significa que falta la salida
            if len(horas_ordenadas) == 1:
                salida_final = '0:00'  # Marcar como faltante
            else:
                salida_final = horas_ordenadas[1]  # Segunda hora
            
            resultado.append({
                'Empleado': grupo['empleado'],
                'Fecha': grupo['fecha'],
                'Entrada': entrada_final,
                'Salida': salida_final,
                'Registros_Originales': len(grupo['registros'])
            })
        
        return resultado
    
    def _obtener_entrada_definitiva(self, entradas: List[str]) -> str:
        """Obtiene la entrada definitiva (primera del día)"""
        if not entradas:
            return '08:00'  # Por defecto
        
        # Ordenar y tomar la primera
        entradas_ordenadas = sorted(entradas)
        return entradas_ordenadas[0]
    
    def _obtener_salida_definitiva(self, salidas: List[str]) -> str:
        """Obtiene la salida definitiva (última del día)"""
        if not salidas:
            return '17:00'  # Por defecto
        
        # Ordenar y tomar la última
        salidas_ordenadas = sorted(salidas)
        return salidas_ordenadas[-1]
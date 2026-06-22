# 💰 Calculadora de Sueldos v1.3

Sistema avanzado para el cálculo automático de sueldos basado en registros de entrada y salida de empleados.

## 🆕 **NUEVA FUNCIONALIDAD v1.3: Gestión de Marcado Único**

### ⭐ **Problema Resuelto**
Cuando un empleado marca **solo 1 vez** en el día (en lugar de entrada + salida), el sistema ahora permite al administrador decidir explícitamente si fue **entrada** o **salida** y completar el horario faltante.

### 🎯 **Características Principales**
- ✅ **Detección Inteligente**: Identifica automáticamente registros incompletos
- ✅ **Panel Administrativo**: Interfaz clara para tomar decisiones
- ✅ **Control Total del Administrador**: El administrador decide completamente los horarios
- ✅ **Horarios Ambiguos**: Detecta y permite corregir horarios mal asignados
- ✅ **Cálculos Precisos**: Garantiza resultados correctos basados en decisiones administrativas

## 🚀 **Funcionalidades Generales**

### 📊 **Procesamiento de Datos**
- **Excel**: Carga y procesa archivos Excel tradicionales
- **PDF**: Procesamiento inteligente de múltiples PDFs simultáneos
- **Validación**: Verificación automática de estructura y datos

### ⏰ **Cálculo de Horas**
- **Horas Normales**: Cálculo estándar de tiempo trabajado
- **Horas Especiales**: 30% extra para horario 20:00-22:00
- **Feriados**: Factor x2 para días feriados configurables
- **Descuentos**: Inventario, caja y retiros

### 🛠️ **Gestión de Casos Especiales**
- **Marcado Único**: ⭐ Nueva funcionalidad para decidir entrada/salida
- **Horarios Ambiguos**: Detección y corrección de horarios sospechosos
- **Exclusión Automática**: Registros sin entrada ni salida (empleado no trabajó)
- **Turnos Nocturnos**: Manejo correcto de horarios que cruzan medianoche

## 📁 **Estructura del Proyecto**

```
Calculo_sueldo1.2/
├── main.py                           # Aplicación principal Streamlit
├── pdf_processor.py                  # Procesamiento inteligente de PDFs
├── ui_components.py                  # Componentes de interfaz de usuario
├── data_processor.py                 # Procesamiento de datos y cálculos
├── calculations.py                   # Lógica de cálculo de horas
├── smart_parser.py                   # Parser inteligente de horarios
├── loading_components.py             # Componentes de carga y progreso
├── styles.css                        # Estilos personalizados
├── requirements.txt                  # Dependencias Python
├── run_app.bat                       # Script de ejecución Windows
├── plantilla_sueldos_feriados_dias.xlsx  # Plantilla Excel
├── NUEVA_FUNCIONALIDAD_MARCADO_UNICO.md   # ⭐ Documentación nueva funcionalidad
└── EJEMPLO_USO_MARCADO_UNICO.md          # ⭐ Ejemplos de uso
```

## 🔧 **Instalación y Uso**

### **Opción 1: Ejecutar con Batch (Recomendado)**
```bash
# Hacer doble clic en:
run_app.bat
```

### **Opción 2: Ejecución Manual**
```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Ejecutar aplicación
streamlit run main.py
```

## 📋 **Flujo de Trabajo**

### **1. Configuración**
- Descargar plantilla Excel si es necesario
- Configurar valor por hora
- Seleccionar feriados del calendario

### **2. Subir Archivo**
- **Excel**: Archivo único con estructura predefinida
- **PDF**: Uno o múltiples archivos PDF simultáneos

### **3. ⭐ Corrección de Registros Incompletos (NUEVO)**
Si hay empleados que marcaron solo una vez:
- El sistema detecta automáticamente los casos
- Se muestra panel administrativo para cada empleado
- Administrador decide si el horario fue entrada o salida
- Sistema sugiere horario faltante basado en contexto
- Se valida y aplican las correcciones

### **4. Revisión de Horarios Ambiguos (NUEVO)**
Si hay horarios sospechosos (ej: entrada muy tarde):
- Sistema detecta patrones anómalos
- Permite intercambiar entrada ↔ salida si es necesario
- Muestra impacto en horas calculadas

### **5. Cálculo y Descarga**
- Procesamiento automático con todas las correcciones
- Generación de reporte final en Excel
- Descarga con nombre automático basado en archivo fuente

## 📊 **Ejemplo de Caso de Uso**

```
🔍 Detección: María González marcó solo a las 22:00
💡 Sugerencia: "Horario nocturno - podría ser SALIDA tardía"
👨‍💼 Decisión Admin: "Fue SALIDA"
⏰ Completa entrada: 14:00 (sugerido automáticamente)
✅ Resultado: 14:00 → 22:00 = 8 horas trabajadas
```

## 🛠️ **Tecnologías Utilizadas**

- **Frontend**: Streamlit + HTML/CSS personalizado
- **Backend**: Python 3.8+
- **Procesamiento**: Pandas, OpenPyXL
- **PDFs**: pdfplumber (opcional)
- **UI/UX**: Componentes interactivos avanzados
- IA para desarrollo de codigo y optimizacion

## 📈 **Mejoras en v1.3**

- ✅ **Detección automática de marcado único**
- ✅ **Panel administrativo intuitivo**
- ✅ **Sugerencias contextuales inteligentes**
- ✅ **Detección de horarios ambiguos**
- ✅ **Interfaz mejorada para correcciones**
- ✅ **Validaciones más robustas**
- ✅ **Documentación completa**

## 🔗 **Documentación Adicional**

- [📝 Nueva Funcionalidad Detallada](NUEVA_FUNCIONALIDAD_MARCADO_UNICO.md)
- [📋 Ejemplos de Uso](EJEMPLO_USO_MARCADO_UNICO.md)


**Versión**: 1.3 | **Fecha**: Noviembre 2024 | **Estado**: ✅ Producción

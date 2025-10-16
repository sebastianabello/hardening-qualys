# 📊 Sistema de Índices de Elasticsearch

## 🎯 Estrategia de Indexación

### **Problema Resuelto**
Los archivos grandes se particionan en múltiples archivos (`-part-02`, `-part-03`, etc.), pero **TODOS deben ir al mismo índice** de Elasticsearch.

### **Solución Implementada**
El sistema automáticamente **remueve los sufijos de partición** antes de crear el nombre del índice, garantizando que todos los archivos particionados se consoliden en un solo índice.

---

## 📁 Ejemplos de Indexación

### **Caso 1: Archivos Sin Particionar**

**Archivos generados:**
```
cliente-hardening-2024-octubre-16.csv
cliente-hardening-control-statics-2024-octubre-16.csv
cliente-hardening-2024-octubre-16-ajustado.csv
cliente-hardening-control-statics-2024-octubre-16-ajustado.csv
```

**Índices en Elasticsearch:**
```
✅ cliente-hardening-2024-octubre-16
✅ cliente-hardening-control-statics-2024-octubre-16
✅ cliente-hardening-2024-octubre-16-ajustado
✅ cliente-hardening-control-statics-2024-octubre-16-ajustado
```

**Total: 4 índices** ✅

---

### **Caso 2: Archivos Particionados (Tu Caso)**

**Archivos generados:**
```
cliente-hardening-2024-octubre-16.csv              ← parte 1
cliente-hardening-2024-octubre-16-part-02.csv      ← parte 2
cliente-hardening-2024-octubre-16-part-03.csv      ← parte 3

cliente-hardening-control-statics-2024-octubre-16.csv
cliente-hardening-control-statics-2024-octubre-16-part-02.csv

cliente-hardening-2024-octubre-16-ajustado.csv
cliente-hardening-2024-octubre-16-ajustado-part-02.csv

cliente-hardening-control-statics-2024-octubre-16-ajustado.csv
```

**Índices en Elasticsearch (DESPUÉS DE LA CORRECCIÓN):**
```
✅ cliente-hardening-2024-octubre-16
   ↳ Contiene datos de: parte 1 + parte 2 + parte 3

✅ cliente-hardening-control-statics-2024-octubre-16
   ↳ Contiene datos de: parte 1 + parte 2

✅ cliente-hardening-2024-octubre-16-ajustado
   ↳ Contiene datos de: parte 1 + parte 2

✅ cliente-hardening-control-statics-2024-octubre-16-ajustado
   ↳ Contiene datos de: parte 1
```

**Total: 4 índices** ✅ (consolidados desde 8 archivos)

---

## 🔧 Cómo Funciona el Código

### **Función de Limpieza de Nombres**

```python
def _get_index_name_from_file(file_name: str) -> tuple[str, bool]:
    """
    Remueve sufijos de partición para consolidar índices.
    """
    base_name = Path(file_name).stem
    
    # PASO CLAVE: Remover -part-XX
    base_name = re.sub(r'-part-\d+$', '', base_name, flags=re.IGNORECASE)
    
    # cliente-hardening-2024-octubre-16-part-02 → cliente-hardening-2024-octubre-16
    
    index_name = base_name.lower()
    # Normalizar caracteres especiales
    index_name = re.sub(r'[^a-z0-9\-]', '_', index_name)
    
    return index_name, ajustada
```

### **Ejemplos de Transformación**

| Archivo | Índice Generado |
|---------|-----------------|
| `cliente-hardening-2024-octubre-16.csv` | `cliente-hardening-2024-octubre-16` |
| `cliente-hardening-2024-octubre-16-part-02.csv` | `cliente-hardening-2024-octubre-16` ✅ |
| `cliente-hardening-2024-octubre-16-part-03.csv` | `cliente-hardening-2024-octubre-16` ✅ |
| `cliente-hardening-control-statics-2024-octubre-16-ajustado-part-05.csv` | `cliente-hardening-control-statics-2024-octubre-16-ajustado` ✅ |

---

## 📊 Verificación en Elasticsearch

### **1. Ver todos los índices**
```bash
# Desde Kibana Dev Tools o curl
GET _cat/indices?v&s=index

# Deberías ver solo 4 índices (o menos):
# cliente-hardening-2024-octubre-16
# cliente-hardening-control-statics-2024-octubre-16
# cliente-hardening-2024-octubre-16-ajustado
# cliente-hardening-control-statics-2024-octubre-16-ajustado
```

### **2. Ver número de documentos por índice**
```bash
GET _cat/indices/cliente-hardening-*?v&h=index,docs.count

# Ejemplo de salida:
# cliente-hardening-2024-octubre-16                         1,234,567
# cliente-hardening-control-statics-2024-octubre-16           345,678
# cliente-hardening-2024-octubre-16-ajustado                  567,890
# cliente-hardening-control-statics-2024-octubre-16-ajustado 123,456
```

### **3. Verificar que todos los archivos se consolidaron**
```bash
# Ver documentos de un índice
GET cliente-hardening-2024-octubre-16/_count

# Debería retornar el total de TODOS los archivos particionados
```

---

## 🎯 Estructura de Índices

### **Siempre tendrás máximo 4 índices por cliente/fecha:**

1. **`{cliente}-hardening-{fecha}`**
   - Datos de tabla T2 (RESULTS) normales
   - Puede venir de múltiples archivos particionados

2. **`{cliente}-hardening-control-statics-{fecha}`**
   - Datos de tabla T1 (Control Statistics) normales
   - Puede venir de múltiples archivos particionados

3. **`{cliente}-hardening-{fecha}-ajustado`**
   - Datos de tabla T2 (RESULTS) ajustadas
   - Puede venir de múltiples archivos particionados

4. **`{cliente}-hardening-control-statics-{fecha}-ajustado`**
   - Datos de tabla T1 (Control Statistics) ajustadas
   - Puede venir de múltiples archivos particionados

---

## ✅ Ventajas de Esta Estrategia

### **1. Consolidación Automática**
- ✅ Múltiples archivos → 1 solo índice
- ✅ Sin duplicación de datos
- ✅ Búsquedas más simples

### **2. Escalabilidad**
- ✅ Archivos de cualquier tamaño
- ✅ Particionamiento automático sin afectar índices
- ✅ Ingesta paralela (múltiples partes a la vez)

### **3. Simplicidad en Kibana**
- ✅ Solo 4 índices por ver (máximo)
- ✅ Dashboards más limpios
- ✅ Queries más simples

---

## 🔍 Logs de Ingesta

Durante la ingesta, verás logs como:

```
🔑 Conectando con API Key
✅ Conectado a Elasticsearch: my-cluster (v8.11.0)

📁 Archivo: cliente-hardening-2024-octubre-16.csv → Índice: cliente-hardening-2024-octubre-16 (ajustada: False)
✅ 500,000 documentos indexados en 'cliente-hardening-2024-octubre-16'

📁 Archivo: cliente-hardening-2024-octubre-16-part-02.csv → Índice: cliente-hardening-2024-octubre-16 (ajustada: False)
✅ 500,000 documentos indexados en 'cliente-hardening-2024-octubre-16'

📁 Archivo: cliente-hardening-2024-octubre-16-part-03.csv → Índice: cliente-hardening-2024-octubre-16 (ajustada: False)
✅ 234,567 documentos indexados en 'cliente-hardening-2024-octubre-16'

Total en índice 'cliente-hardening-2024-octubre-16': 1,234,567 documentos ✅
```

---

## 🚨 Notas Importantes

### ✅ **Lo Que SÍ Hace**
- ✅ Consolida archivos particionados en un solo índice
- ✅ Preserva la distinción entre normal/ajustado
- ✅ Preserva la distinción entre T1/T2 (control stats vs results)
- ✅ Ingesta todos los documentos sin pérdida

### ❌ **Lo Que NO Hace**
- ❌ No mezcla datos de diferentes fechas
- ❌ No mezcla datos de diferentes clientes
- ❌ No mezcla datos ajustados con normales
- ❌ No mezcla T1 con T2

---

## 🔧 Configuración de Particionamiento

Si quieres **menos archivos particionados** (y por ende menos ingesta), ajusta:

```bash
# backend/.env

# Aumentar filas por archivo (menos particiones)
CSV_PART_MAX_ROWS=2000000  # 2M filas por archivo (en lugar de 1M)

# Esto reduce la cantidad de archivos -part-XX generados
```

**Trade-off:**
- 📈 Más `CSV_PART_MAX_ROWS` = Menos archivos, ingesta más rápida
- 📉 Menos `CSV_PART_MAX_ROWS` = Más archivos, mejor manejo de memoria

---

## 📝 Resumen Ejecutivo

### **Pregunta Original:**
> "Al tener archivos con `-part-02`, `-part-03`, ¿se crearán índices diferentes en Elasticsearch?"

### **Respuesta:**
**NO** ✅ - Todos los archivos particionados se consolidan en un **solo índice** gracias a la función `_get_index_name_from_file()` que remueve automáticamente los sufijos `-part-XX`.

### **Resultado Final:**
- 📁 **8 archivos CSV** (con particiones)
- 📊 **4 índices Elasticsearch** (consolidados)
- ✅ **Sin duplicación**
- ✅ **Sin confusión**

---

**Última actualización**: Octubre 16, 2025  
**Estado**: ✅ Corregido y funcionando  
**Archivos modificados**: `backend/app/ingest.py`

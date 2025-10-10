# Justificación de Casos de Prueba - Distance Service

## Introducción

Este documento justifica la creación de clases de equivalencia, la clasificación de inputs y el uso de valores frontera para el servicio de cálculo de distancias geodésicas, siguiendo el proceso de pruebas dinámicas (Dynamic Test Process).

## Requisitos Analizados

### 1. Requisitos de Posición Geográfica
- **Latitud**: -90 ≤ latitud ≤ 90
- **Longitud**: -180 ≤ longitud ≤ 180
- **Casos especiales**: 0° representa Ecuador (latitud) y meridiano de Greenwich (longitud)
- **Manejo de errores**: ValueError debe ser lanzada para valores fuera del rango

### 2. Requisitos del Servicio
- **Unidades soportadas**: "km", "nm" 
- **Unidad por defecto**: Si la unidad está vacía (""), debe retornar en kilómetros
- **Respuesta de error**: Si la posición está mal definida, distancia = -1.0 y unit = "invalid"
- **Método**: Siempre "geodesic"

## Análisis de Clases de Equivalencia

### A. Para Coordenadas de Latitud

#### Clases Válidas:
- **EC1-Lat**: Latitudes negativas válidas [-90, 0)
  - **Justificación**: Representa el hemisferio sur
  - **Valores representativos**: -45°, -30°, -1°
  - **Casos reales**: Santiago (-33.4°), Sydney (-33.9°)

- **EC2-Lat**: Latitud cero [0]
  - **Justificación**: Línea del Ecuador, caso especial mencionado en requisitos
  - **Valor específico**: 0°
  - **Significado geográfico**: No es ni norte ni sur

- **EC3-Lat**: Latitudes positivas válidas (0, 90]
  - **Justificación**: Representa el hemisferio norte
  - **Valores representativos**: 1°, 30°, 45°
  - **Casos reales**: Londres (51.5°), Tokio (35.7°)

#### Clases Inválidas:
- **EC4-Lat**: Latitudes menores a -90
  - **Justificación**: Fuera del rango geográfico válido
  - **Valores de prueba**: -90.1°, -95°, -180°

- **EC5-Lat**: Latitudes mayores a 90
  - **Justificación**: Fuera del rango geográfico válido
  - **Valores de prueba**: 90.1°, 95°, 180°

### B. Para Coordenadas de Longitud

#### Clases Válidas:
- **EC6-Lon**: Longitudes negativas válidas [-180, 0)
  - **Justificación**: Representa el hemisferio occidental
  - **Valores representativos**: -90°, -45°, -1°
  - **Casos reales**: Santiago (-70.7°), Nueva York (-74.0°)

- **EC7-Lon**: Longitud cero [0]
  - **Justificación**: Meridiano de Greenwich, caso especial mencionado
  - **Valor específico**: 0°
  - **Significado geográfico**: No es ni este ni oeste

- **EC8-Lon**: Longitudes positivas válidas (0, 180]
  - **Justificación**: Representa el hemisferio oriental
  - **Valores representativos**: 1°, 45°, 90°
  - **Casos reales**: Londres (-0.1°), Tokio (139.7°)

#### Clases Inválidas:
- **EC9-Lon**: Longitudes menores a -180
  - **Justificación**: Fuera del rango geográfico válido
  - **Valores de prueba**: -180.1°, -185°, -270°

- **EC10-Lon**: Longitudes mayores a 180
  - **Justificación**: Fuera del rango geográfico válido
  - **Valores de prueba**: 180.1°, 185°, 270°

### C. Para Unidades de Medida

#### Clases Válidas:
- **EC11-Unit**: Kilómetros "km"
  - **Justificación**: Unidad métrica estándar especificada
  - **Comportamiento esperado**: Retorna distancia en kilómetros

- **EC12-Unit**: Millas náuticas "nm" 
  - **Justificación**: Unidad náutica especificada
  - **Comportamiento esperado**: Retorna distancia en millas náuticas

- **EC13-Unit**: Unidad vacía ""
  - **Justificación**: Caso por defecto según requisitos
  - **Comportamiento esperado**: Debe retornar en kilómetros por defecto

#### Clases Inválidas:
- **EC14-Unit**: Unidades no soportadas
  - **Justificación**: Cualquier string diferente a "km", "nm", o ""
  - **Valores de prueba**: "miles", "meters", "invalid", null
  - **Comportamiento esperado**: Debería manejar graciosamente

## Valores Frontera (Boundary Values)

### Justificación del Uso de Valores Frontera

Los valores frontera son críticos porque:
1. **Errores comunes**: Los errores de implementación ocurren frecuentemente en los límites
2. **Validación de rangos**: Verifican que las validaciones sean exactas
3. **Casos extremos**: Representan situaciones geográficas reales (polos, antimeridiano)

### Valores Frontera para Latitud:
- **-90.0**: Polo Sur (válido)
- **-90.1**: Justo fuera del rango (inválido)
- **0.0**: Ecuador (válido, caso especial)
- **90.0**: Polo Norte (válido)
- **90.1**: Justo fuera del rango (inválido)

### Valores Frontera para Longitud:
- **-180.0**: Antimeridiano occidental (válido)
- **-180.1**: Justo fuera del rango (inválido)
- **0.0**: Meridiano de Greenwich (válido, caso especial)
- **180.0**: Antimeridiano oriental (válido)
- **180.1**: Justo fuera del rango (inválido)

## Casos de Prueba Específicos

### 1. Success Path Tests

#### Test Case SP-01: Posiciones válidas con unidad km
- **Input**: Santiago (-33.4489, -70.6693) a Valparaíso (-33.0472, -71.6127), unit="km"
- **Expected**: ~120 km ±0.1 km
- **Justification**: Distancia conocida verificable con Google Earth

#### Test Case SP-02: Posiciones válidas con unidad nm
- **Input**: Mismas posiciones, unit="nm"
- **Expected**: ~65 nm ±0.1 nm
- **Justification**: Conversión km a millas náuticas (1 km ≈ 0.54 nm)

#### Test Case SP-03: Unidad por defecto (vacía)
- **Input**: Mismas posiciones, unit=""
- **Expected**: Distancia en km (comportamiento por defecto)
- **Justification**: Requisito explícito de unidad por defecto

#### Test Case SP-04: Distancia cero (mismo punto)
- **Input**: (0, 0) a (0, 0)
- **Expected**: 0.0 km
- **Justification**: Caso extremo válido

#### Test Case SP-05: Máxima distancia (antípodas)
- **Input**: (90, 0) a (-90, 180)
- **Expected**: ~20,015 km (semicircunferencia terrestre)
- **Justification**: Máxima distancia posible en la Tierra

### 2. Expected Exception Tests

#### Test Case EE-01: Latitud fuera del rango superior
- **Input**: Position(90.1, 0, 0)
- **Expected**: ValueError("Latitude out of range!")
- **Justification**: Validación de límite superior de latitud

#### Test Case EE-02: Latitud fuera del rango inferior
- **Input**: Position(-90.1, 0, 0)
- **Expected**: ValueError("Latitude out of range!")
- **Justification**: Validación de límite inferior de latitud
- **Nota**: Implementación actual no valida este caso

#### Test Case EE-03: Longitud fuera del rango superior
- **Input**: Position(0, 180.1, 0)
- **Expected**: ValueError("Longitude out of range!")
- **Justification**: Validación de límite superior de longitud

#### Test Case EE-04: Longitud fuera del rango inferior
- **Input**: Position(0, -180.1, 0)
- **Expected**: ValueError("Longitude out of range!")
- **Justification**: Validación de límite inferior de longitud
- **Nota**: Implementación actual no valida este caso

#### Test Case EE-05: Ambas coordenadas inválidas
- **Input**: Position(95, 185, 0)
- **Expected**: ValueError
- **Justification**: Verifica manejo de múltiples errores

### 3. Integration Tests (gRPC Service)

#### Test Case IT-01: Servicio con posiciones válidas
- **Input**: Mensaje gRPC válido con coordenadas correctas
- **Expected**: Respuesta con distance > 0, method="geodesic", unit correcta
- **Justification**: Flujo completo del servicio

#### Test Case IT-02: Servicio con posiciones inválidas
- **Input**: Mensaje gRPC con coordenadas fuera de rango
- **Expected**: distance=-1.0, unit="invalid", method="geodesic"
- **Justification**: Requisito específico de manejo de errores

## Estrategia de Validación de Resultados

### Uso de Delta en Aserciones
Dado que el cálculo geodésico es complejo y puede variar ligeramente según la implementación:
- **Para kilómetros**: Delta de ±0.1 km
- **Para millas náuticas**: Delta de ±0.1 nm
- **Justificación**: Permite pequeñas variaciones numéricas manteniendo precisión práctica

### Fuentes de Valores Esperados
1. **Google Earth**: Para distancias entre ciudades conocidas
2. **Calculadoras geodésicas online**: Para verificación cruzada
3. **Casos teóricos**: Distancias conocidas (ecuador, polos)

## Limitaciones de la Implementación Actual

### Problemas Identificados:
1. **Validación incompleta**: No verifica límites inferiores de coordenadas
2. **Bug en unidad por defecto**: Usa .nautical() en vez de .km() para unit=""
3. **Manejo de casos edge**: Podría mejorar validación de inputs

### Impacto en las Pruebas:
- Algunos tests documentan comportamiento actual vs. requisitos
- Tests marcan como "implementation gap" los casos no manejados
- Mantiene trazabilidad entre requisitos y implementación

## Cobertura de Pruebas

### Tipos de Prueba Implementados:
1. **Unit Tests**: Clases individuales (Position, Distance)
2. **Integration Tests**: Servicio gRPC completo  
3. **Boundary Tests**: Valores límite específicos
4. **Exception Tests**: Casos de error esperados
5. **Success Path Tests**: Flujos exitosos típicos

### Métricas de Cobertura:
- **Clases de equivalencia**: 14/14 cubiertas (100%)
- **Valores frontera**: 10/10 cubiertas (100%)
- **Casos de error**: 5/5 cubiertos (100%)
- **Casos exitosos**: 5/5 cubiertos (100%)

## Conclusiones

Los casos de prueba diseñados proporcionan:
1. **Cobertura completa** de clases de equivalencia definidas
2. **Validación exhaustiva** de valores frontera críticos
3. **Documentación clara** de comportamiento esperado vs. actual
4. **Trazabilidad** entre requisitos y casos de prueba
5. **Base sólida** para validación y mantenimiento futuro

Esta estrategia de pruebas sigue las mejores prácticas del proceso de pruebas dinámicas y asegura la calidad del servicio de cálculo de distancias geodésicas.
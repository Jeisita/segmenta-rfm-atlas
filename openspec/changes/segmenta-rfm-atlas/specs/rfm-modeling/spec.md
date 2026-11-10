# Spec Delta

## Purpose

Define un flujo reproducible para preparar variables RFM desde Online Retail, entrenar y evaluar K-Means, y entregar el mismo preprocesamiento y estimador como una canalización utilizable por la aplicación.

## ADDED Requirements

### Requirement: Preparación de datos RFM reproducible
El flujo de entrenamiento MUST transformar los registros de Online Retail en una observación por cliente con recencia, frecuencia y gasto, documentando las reglas de limpieza y agregación aplicadas.

#### Scenario: Datos aptos para cálculo RFM
- **WHEN** se ejecuta el flujo con el conjunto Online Retail configurado
- **THEN** produce observaciones con las tres variables RFM y excluye registros que incumplen las reglas de limpieza documentadas

### Requirement: Fuente UCI Online Retail completa
El entrenamiento final MUST usar el dataset oficial Online Retail de UCI (dataset 352) y verificar que el workbook contiene exactamente 541.909 transacciones antes de generar RFM o guardar el artefacto final.

#### Scenario: Workbook UCI completo
- **WHEN** se carga el workbook oficial con 541.909 filas de transacciones
- **THEN** el flujo registra el origen y el conteo y permite continuar con el cálculo RFM

#### Scenario: Dataset incompleto o distinto
- **WHEN** el workbook tiene un conteo distinto de 541.909 transacciones
- **THEN** el flujo rechaza el archivo y no entrena ni sobrescribe el artefacto final

### Requirement: Descarga oficial y alternativa manual en Colab
El notebook MUST intentar descargar el archivo oficial UCI cuando se ejecuta en Google Colab y el workbook local no está disponible; si falla la descarga, MUST permitir cargar manualmente `Online Retail.xlsx` y aplicar la misma validación de origen y filas.

#### Scenario: Descarga oficial disponible
- **WHEN** se ejecuta en Colab sin workbook local y la descarga UCI está disponible
- **THEN** descarga el archivo oficial, valida el workbook de 541.909 filas y continúa el entrenamiento

#### Scenario: Descarga oficial fallida
- **WHEN** la descarga automática falla en Colab
- **THEN** solicita seleccionar manualmente `Online Retail.xlsx` y solo continúa si pasa las validaciones del dataset UCI

### Requirement: Selección reproducible del número de clusters
El flujo MUST calcular métricas de selección sobre los datos RFM reales para candidatos k de 2 a 10 (limitados por el tamaño de la muestra), escoger k mediante el mayor silhouette y conservar la tabla de métricas calculadas.

#### Scenario: Selección con datos RFM
- **WHEN** el notebook evalúa los candidatos de cluster con RFM construido desde el dataset UCI
- **THEN** informa inertia y silhouette calculados para cada k, selecciona el k de mayor silhouette (desempata por el menor k) y ajusta el modelo final con ese valor

### Requirement: Metadatos completos de entrenamiento y segmentos
El artefacto MUST serializar la pipeline escalador más K-Means, nombres ordenados de features, rangos, versión y parámetros, procedencia/hash/conteo de transacciones, métricas de selección y por segmento su etiqueta, conteo de clientes y centroide en las unidades RFM originales.

#### Scenario: Inspección del artefacto final
- **WHEN** el notebook exporta el modelo entrenado con el dataset UCI
- **THEN** el artefacto contiene la pipeline y los metadatos de entrenamiento y perfiles necesarios para inferir e interpretar los segmentos sin reentrenar

### Requirement: Entrenamiento y evaluación de K-Means
El flujo MUST entrenar K-Means sobre datos preparados y reportar medidas de evaluación calculadas a partir de esa ejecución, sin codificar métricas supuestas como resultados.

#### Scenario: Evaluación reproducible
- **WHEN** se ejecuta el notebook con parámetros y datos fijados
- **THEN** muestra los parámetros, medidas calculadas y resultados de segmentación obtenidos en esa ejecución

### Requirement: Canalización reutilizable
El flujo MUST guardar en un artefacto versionado de modelo el preprocesamiento requerido y K-Means, e incluir metadatos suficientes para identificar el orden y los nombres de variables de entrada.

#### Scenario: Carga para inferencia
- **WHEN** la aplicación carga un artefacto producido por el entrenamiento y entrega una observación RFM válida
- **THEN** transforma esa observación con el mismo preprocesamiento y obtiene un segmento usando el estimador guardado

### Requirement: Código de entrenamiento orientado a objetos
El código Python del flujo MUST organizar la preparación, entrenamiento, evaluación y exportación en clases y métodos, y el notebook MUST invocar ese código sin duplicar la lógica del modelo en celdas procedimentales.

#### Scenario: Ejecución desde notebook
- **WHEN** un estudiante ejecuta el notebook desde la preparación hasta la exportación
- **THEN** las operaciones de entrenamiento se realizan mediante las clases y métodos Python del proyecto

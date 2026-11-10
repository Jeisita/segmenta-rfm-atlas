# Proposal

## Why

El proyecto académico previo de segmentación RFM con Online Retail y K-Means necesita convertirse en una solución reproducible y demostrable que conecte entrenamiento, inferencia y persistencia sin exponer datos personales ni credenciales. La propuesta define un contrato verificable para que la aplicación use el mismo preprocesamiento y modelo entrenados, registre de forma controlada cada clasificación válida y documente su arquitectura.

## What Changes

- Añadir un notebook Jupyter que obtenga exclusivamente Online Retail del repositorio oficial UCI (dataset 352, 541.909 transacciones), intente descargarlo automáticamente en Colab y permita cargar manualmente `Online Retail.xlsx` si la descarga falla; preparar RFM, evaluar/seleccionar clusters y guardar una canalización reutilizable con metadatos completos de segmento.
- Añadir una aplicación Flask con vistas basadas en clases y lógica de entrenamiento/inferencia/persistencia escrita en Python y organizada en clases y métodos.
- Desplegar la aplicación Flask en un entorno de alojamiento accesible por HTTP, con un servidor WSGI adecuado y configuración de ejecución externa.
- Aceptar recencia, frecuencia y gasto mediante formulario; validar entradas inválidas y advertir o rechazar observaciones fuera del rango de entrenamiento antes de inferir.
- Ejecutar inferencia en tiempo real y persistir cada entrada válida junto con su segmento en MongoDB Atlas mediante una única operación `insert_one` por envío.
- Prohibir funciones de consulta, edición o eliminación en la integración de MongoDB; excluir datos personales y credenciales del repositorio.
- Incluir pruebas funcionales, README, dependencias, documento técnico y diagramas C4 y UML coherentes con la implementación.
- Mantener la interfaz en plantillas HTML y CSS, sin JavaScript ni lógica del sistema fuera de Python.

## Capabilities

### New Capabilities

- `rfm-modeling`: Preparación de datos RFM, entrenamiento y evaluación académica de K-Means, y exportación de una canalización reutilizable.
- `rfm-segmentation-web`: Formulario web, validación de rangos, inferencia de segmentos y flujo de persistencia de solo inserción.
- `rfm-project-documentation`: Instrucciones de uso, dependencias, pruebas funcionales y documentación técnica con diagramas alineados con el sistema.

### Modified Capabilities

Ninguna. El inventario actual no contiene capacidades existentes.

## Impact

El cambio añadirá un notebook y módulos Python para el modelo y la aplicación Flask, plantillas HTML, estilos CSS, configuración de dependencias, pruebas funcionales y configuración de despliegue. La solución dependerá de bibliotecas de análisis y ML, Flask, un servidor WSGI y un cliente Python para MongoDB Atlas. `MONGO_URI` y toda credencial o secreto se proporcionarán como variables de entorno del entorno de ejecución, nunca como archivos o valores versionados. No hay código de implementación presente en la raíz actual; la planificación se basa en el alcance del proyecto anterior descrito por el usuario y define un sistema nuevo.

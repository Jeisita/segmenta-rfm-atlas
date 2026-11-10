# Spec Delta

## Purpose

Establece documentación reproducible para instalar, entrenar, ejecutar y verificar la solución académica, incluyendo diagramas que representen los componentes y sus colaboraciones reales.

## ADDED Requirements

### Requirement: Guía de proyecto reproducible
El proyecto MUST incluir README y dependencias declaradas que expliquen los prerrequisitos, preparación de datos, entrenamiento, configuración externa de Atlas, ejecución web local, despliegue WSGI accesible y ejecución de pruebas. El código de todas las pruebas MUST estar escrito en Python y organizado en clases y métodos.

#### Scenario: Preparación de entorno
- **WHEN** una persona sigue el README en un entorno limpio con Python
- **THEN** puede instalar las dependencias declaradas, conocer las variables externas requeridas sin buscar credenciales versionadas y seguir los pasos documentados para publicar la aplicación

### Requirement: Pruebas funcionales
El proyecto MUST incluir pruebas funcionales Python organizadas en clases y métodos que cubran el formulario, validación, inferencia, política de rango, respuesta a fallos y persistencia simulada, incluida la verificación de una sola inserción y la ausencia de operaciones de consulta, edición o eliminación.

#### Scenario: Verificación de flujo válido y de rechazo
- **WHEN** se ejecutan las pruebas funcionales
- **THEN** se comprueba mediante clases y métodos Python el resultado del envío válido, la falta de persistencia para entradas rechazadas y el número de inserciones invocadas

### Requirement: Documento técnico y diagramas coherentes
El proyecto MUST incluir un documento técnico y diagramas C4 y UML que describan el flujo de entrenamiento, los componentes Flask, las clases Python, el artefacto del modelo y el límite de persistencia Atlas según la implementación entregada.

#### Scenario: Correspondencia con la implementación
- **WHEN** se revisa el documento técnico y sus diagramas junto con el código
- **THEN** los actores, componentes, clases, dependencias y flujos representados corresponden a elementos presentes en la implementación

### Requirement: Sin resultados académicos inventados
La documentación MUST distinguir instrucciones y resultados esperados de resultados obtenidos, y MUST presentar métricas únicamente cuando hayan sido generadas por una ejecución del notebook.

#### Scenario: Documentación previa a la ejecución
- **WHEN** se prepara la documentación antes de ejecutar el entrenamiento
- **THEN** describe cómo obtener métricas sin atribuir valores numéricos no observados al modelo

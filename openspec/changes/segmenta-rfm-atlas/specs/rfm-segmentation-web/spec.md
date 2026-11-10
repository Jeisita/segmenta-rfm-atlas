# Spec Delta

## Purpose

Define el comportamiento de la aplicación web para recibir variables RFM, validarlas, predecir un segmento en tiempo real y guardar una única clasificación válida en MongoDB Atlas sin ofrecer acceso de lectura o modificación.

## ADDED Requirements

### Requirement: Formulario RFM accesible
La aplicación MUST ofrecer un formulario que solicite recencia, frecuencia y gasto, y que devuelva una respuesta HTML con el resultado o errores comprensibles.

#### Scenario: Presentación inicial
- **WHEN** una persona abre la vista de segmentación
- **THEN** recibe un formulario con campos identificados para recencia, frecuencia y gasto

### Requirement: Validación de entrada
La aplicación MUST rechazar campos ausentes, no numéricos, no finitos o fuera de las restricciones de dominio definidas para cada variable, y MUST informar los errores sin ejecutar inferencia ni persistencia.

#### Scenario: Entrada malformada
- **WHEN** se envía un valor ausente, texto, infinito o una magnitud incompatible con el dominio RFM
- **THEN** se muestra un error de validación y no se solicita una predicción ni se guarda un documento

### Requirement: Política de valores fuera del rango de entrenamiento
La aplicación MUST comparar valores válidos con los límites de entrenamiento registrados en los metadatos del modelo y advertir claramente o rechazar la observación antes de inferir, según una política explícita y documentada.

#### Scenario: Observación fuera de rango bajo política de rechazo
- **WHEN** una variable validada queda fuera del rango de entrenamiento y la política configurada es rechazo
- **THEN** se informa qué variable excede el rango y no se ejecuta inferencia ni persistencia

#### Scenario: Observación fuera de rango bajo política de aviso
- **WHEN** una variable validada queda fuera del rango de entrenamiento y la política configurada es aviso
- **THEN** se muestra la advertencia y la aplicación continúa con inferencia únicamente si el aviso no bloqueante está configurado

### Requirement: Inferencia en tiempo real
La aplicación MUST aplicar al envío aceptado la canalización de preprocesamiento y K-Means exportada por el entrenamiento, y devolver el identificador de segmento asignado.

#### Scenario: Clasificación satisfactoria
- **WHEN** se envía una observación válida y permitida por la política de rango
- **THEN** la respuesta muestra el segmento obtenido mediante el artefacto cargado

### Requirement: Persistencia de una sola inserción
Por cada envío aceptado que obtiene una predicción, la aplicación MUST guardar las tres variables RFM y el segmento en MongoDB Atlas mediante exactamente una llamada `insert_one`.

#### Scenario: Clasificación aceptada
- **WHEN** la observación válida se clasifica correctamente
- **THEN** se realiza exactamente una inserción que contiene las tres variables y el segmento

#### Scenario: Atlas no disponible
- **WHEN** la inserción falla o Atlas no está disponible
- **THEN** la aplicación comunica que no pudo completar el registro y no informa que la operación fue persistida

### Requirement: Interfaz Atlas de solo inserción
La integración con MongoDB Atlas MUST limitar sus operaciones de aplicación a insertar el registro de clasificación y MUST no exponer funciones de consulta, edición o eliminación.

#### Scenario: Inspección del adaptador de persistencia
- **WHEN** se examina el adaptador usado por la aplicación
- **THEN** su interfaz ofrece solo la operación de inserción de un documento de clasificación y no incorpora operaciones de lectura, actualización ni borrado

### Requirement: Privacidad y secretos
La aplicación MUST guardar únicamente variables RFM y segmento necesarios para la clasificación, y MUST obtener credenciales de configuración externa al repositorio.

#### Scenario: Registro sin datos personales ni secretos
- **WHEN** se procesa una solicitud y se crea su documento Atlas
- **THEN** el documento contiene solo variables RFM y segmento y la URL de conexión no se incluye en archivos versionados ni en la respuesta HTML

### Requirement: Lógica Python orientada a objetos y presentación sin JavaScript
La lógica de validación, inferencia y persistencia MUST estar implementada en Python mediante clases y métodos; la presentación web MUST limitarse a plantillas HTML y estilos CSS sin JavaScript.

#### Scenario: Envío y respuesta HTML
- **WHEN** una persona envía el formulario
- **THEN** la vista procesa el envío con la lógica Python y genera una respuesta HTML sin depender de JavaScript

### Requirement: Despliegue accesible de la aplicación
La solución MUST desplegar la aplicación Flask en un entorno de alojamiento accesible por HTTP mediante un servidor WSGI, y MUST configurar modelo, política de rangos y conexión Atlas mediante configuración de ejecución externa.

#### Scenario: Uso de la aplicación desplegada
- **WHEN** el despliegue está activo y una persona abre su URL pública o de demostración
- **THEN** recibe la aplicación Flask funcional servida por WSGI y puede usar el formulario sin iniciar el servidor localmente

#### Scenario: Configuración de despliegue sin credenciales versionadas
- **WHEN** se configura el entorno de despliegue
- **THEN** `MONGO_URI` y cualquier otra credencial o secreto se proporcionan mediante variables de entorno o el gestor de secretos del alojamiento y no aparecen en archivos del repositorio, registros públicos ni respuestas HTML

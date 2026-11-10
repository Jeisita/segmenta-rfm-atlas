# Documento técnico

## Alcance y componentes

El sistema tiene dos flujos. El entrenamiento offline lee el archivo Online Retail, calcula agregados de cliente y exporta un único objeto de modelo. El servicio web carga ese artefacto al iniciar, recibe RFM, valida y clasifica usando la misma pipeline, y después intenta una inserción MongoDB Atlas. La app no contiene código de entrenamiento ni endpoints de administración de datos.

Los detalles de responsabilidades por clase aparecen en [UML](architecture/uml-classes.puml); el contexto y contenedores se muestran en [C4 contexto](architecture/c4-context.puml) y [C4 contenedores](architecture/c4-container.puml).

## Datos RFM y entrenamiento

La fuente es [UCI Online Retail, dataset 352](https://archive.ics.uci.edu/dataset/352/online-retail), cuyo workbook oficial `Online Retail.xlsx` contiene 541.909 transacciones. `OnlineRetailDatasetLoader` descarga el ZIP oficial desde UCI si no existe un workbook local, valida esquema y conteo exacto, y registra SHA-256, procedencia y número de filas. En Google Colab, si falla la descarga, permite cargar manualmente el workbook oficial y aplica las mismas comprobaciones. El notebook no sigue al entrenamiento si el conteo no es 541.909.

Se esperan las columnas `CustomerID`, `InvoiceDate`, `InvoiceNo`, `Quantity` y `UnitPrice`. La preparación elimina filas incompletas o no numéricas, excluye facturas cuyo identificador empieza por `C` y cantidades no positivas. El archivo define `UnitPrice` en libras esterlinas; el gasto se calcula como suma de `Quantity * UnitPrice` y se descartan precios negativos. Frecuencia cuenta `InvoiceNo` distintos. Recencia es la diferencia en días entre la última fecha de factura del cliente (normalizada a día) y el día posterior a la fecha máxima válida del conjunto.

El entrenador calcula inertia y silhouette para candidatos k de 2 a 10 (acotados por las observaciones RFM disponibles), selecciona la silhouette máxima con desempate por el menor k y ajusta `sklearn.pipeline.Pipeline` con `StandardScaler` y `KMeans` usando `random_state=42` y `n_init=10`. La evaluación final informa inertia, silhouette y tamaño de clusters. Todas las métricas son valores calculados al ejecutar sobre el dataset real; no se ha ejecutado entrenamiento UCI en esta implementación.

El objeto `RFMModelArtifact` serializado con joblib conserva pipeline, orden de variables, rangos observados, métricas y criterio de selección, parámetros, versión de scikit-learn, origen/hash/conteo del workbook y por segmento su etiqueta, conteo de clientes y centroide RFM en unidades originales. Exportación final y carga de la app requieren metadatos UCI del dataset 352, 541.909 filas y hash SHA-256. La aplicación verifica esquema y versión compatible al cargar y no reentrena. Solo se deben cargar artefactos de confianza.

## Aplicación e inferencia

`FlaskApplicationFactory.create` configura Flask. Si no se inyecta un servicio de prueba, carga el artefacto ya existente y construye `ClassificationService`, `RFMInputValidator`, `ModelSegmentPredictor` y `AtlasInsertStore`. La vista `SegmentView` usa `MethodView` con GET/POST y renderiza HTML del servidor. Validación y política de rango ocurren en Python aun cuando el HTML incluya restricciones de usabilidad.

Recencia y gasto aceptan números finitos no negativos; frecuencia debe ser un entero positivo. Fuera del rango de entrenamiento, `reject` es el predeterminado y detiene inferencia/persistencia. `warn` informa las variables fuera de rango y permite la predicción.

## Persistencia y privacidad

`AtlasInsertStore.insert_classification` construye un documento con solo `recency`, `frequency`, `monetary` y `segment`; realiza una única llamada `insert_one` por clasificación aceptada. La clase no ofrece métodos de consulta, edición o eliminación. Si MongoDB falla, el servicio web responde con error de persistencia y no declara éxito.

`MONGO_URI`, `FLASK_SECRET_KEY` y todo secreto deben configurarse como variables de entorno o en el gestor secreto del alojamiento. No guardar URIs reales, contraseñas, datos personales, el workbook o artefactos entrenados en el repositorio. No incluir datos identificativos de clientes en el documento MongoDB.

## Operación y despliegue

`wsgi.py` expone `app`; `Procfile` inicia Gunicorn usando el puerto proporcionado por el alojamiento. `MODEL_PATH`, `OUT_OF_RANGE_POLICY`, `MONGO_URI`, `MONGO_DATABASE`, `MONGO_COLLECTION` y `FLASK_SECRET_KEY` controlan runtime. La plataforma debe proporcionar un sistema compatible con Gunicorn, publicar de forma privada el artefacto, definir secretos fuera de Git y permitir conectividad saliente a Atlas.

No se incluye configuración de un proveedor concreto ni se declara una URL desplegada porque no hay cuenta o credenciales de hosting asociadas al proyecto. La publicación, configuración de Atlas y entrenamiento con el dataset real son pasos manuales.

## Pruebas

`python -m unittest discover -s tests -v` ejecuta pruebas funcionales basadas en `unittest.TestCase`, con doubles para predictor, almacenamiento y colección. Comprueban agregación, orden y persistencia del artefacto, validación, rangos, respuestas HTTP, una inserción y ausencia de métodos de lectura/actualización/borrado. No requieren Atlas. La ejecución de entrenamiento y la verificación de la URL desplegada requieren el dataset y el entorno externos.

## Revisión de entrega

En la verificación de esta revisión, las 30 pruebas Python cubren selección y serialización con fixtures unitarios y validan formato/sintaxis del notebook sin ejecutar su entrenamiento final. El guardado y la carga de producción rechazan artefactos que no registren UCI dataset 352, 541.909 transacciones y SHA-256. No se descargó UCI ni se generó el artefacto final; no se reportan métricas del modelo. La descarga y entrenamiento UCI deben ejecutarse en Colab (o localmente con el workbook oficial). La revisión del código encontró una sola llamada `insert_one` en el adaptador Atlas y ningún método de consulta, actualización o eliminación; tampoco encontró archivos JavaScript ni secretos reales en los archivos de la solución. Esta copia de trabajo no incluye metadatos `.git`, así que se revisaron los archivos del proyecto presentes. La publicación WSGI y una inserción en una instancia Atlas real siguen pendientes de configuración externa.

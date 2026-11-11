# Segmenta RFM Atlas

Aplicación académica para preparar variables RFM desde Online Retail, entrenar una canalización `StandardScaler` + `KMeans`, clasificar entradas mediante Flask y guardar cada clasificación válida en MongoDB Atlas.

## Requisitos

- Python 3.10 o posterior.
- El archivo Online Retail `Online_Retail.xlsx` (no se distribuye en este repositorio).
- Para usar la app en producción: un artefacto de modelo entrenado y una instancia MongoDB Atlas con acceso de red configurado.

## Entorno local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[notebook]"
```

Configura las variables de entorno en la sesión o el gestor local de secretos. En Windows, por ejemplo, se puede establecer la ruta de datos para la sesión de PowerShell con `$env:ONLINE_RETAIL_PATH="data/Online_Retail.xlsx"`. `.env.example` es una referencia de nombres sin valores secretos; no se carga automáticamente.

## Entrenamiento

El notebook carga el [Online Retail de UCI, dataset 352](https://archive.ics.uci.edu/dataset/352/online-retail) (541.909 transacciones). En Colab intenta descargar el archivo oficial automáticamente; si no puede, abre una carga manual para `Online Retail.xlsx`. En local, coloca ese workbook en `data/Online Retail.xlsx` o define `ONLINE_RETAIL_PATH`. En ambos casos se rechaza cualquier workbook que no tenga exactamente 541.909 filas y las columnas esperadas. El artefacto registra el origen UCI y el SHA-256 del archivo.

Abre `notebooks/train_rfm_kmeans.ipynb` en un frontend Jupyter ya instalado o un IDE compatible y ejecuta las celdas en orden. Para instalar JupyterLab desde este proyecto, usa `python -m pip install -e ".[notebook,notebook-ui]"`. El código orientado a objetos evalúa k de 2 a 10 (acotado por la cantidad de clientes) mediante inertia y silhouette; elige la silhouette máxima, con desempate por el menor k. Los resultados se calculan solo al ejecutar sobre el UCI real. El artefacto `artifacts/rfm_kmeans.joblib` contiene `StandardScaler`, K-Means, rangos, parámetros, métricas de selección y metadatos por segmento (etiqueta, número de clientes y centroide RFM). El guardado final y la app rechazan artefactos sin metadatos UCI válidos. El dataset está excluido de Git. El artefacto entrenado `artifacts/rfm_kmeans.joblib` está incluido en el repositorio.
## Ejecutar la aplicación local

Configura estas variables en el entorno antes de iniciar:

| Variable | Uso | Requerida |
|---|---|---|
| `MODEL_PATH` | Artefacto generado por el notebook | Sí |
| `OUT_OF_RANGE_POLICY` | `reject` (predeterminado) o `warn` | No |
| `MONGO_URI` | URI privada de MongoDB Atlas | Sí |
| `MONGO_DATABASE` | Base destino | No, predeterminado `segmenta_rfm` |
| `MONGO_COLLECTION` | Colección destino | No, predeterminado `predicciones` |
| `FLASK_SECRET_KEY` | Secreto de Flask | Sí al iniciar el despliegue |

Ejemplo de sesión PowerShell (usa valores propios; no los guardes en archivos versionados):

```powershell
$env:MODEL_PATH="artifacts/rfm_kmeans.joblib"
$env:OUT_OF_RANGE_POLICY="reject"
$env:MONGO_URI="<configurar-en-el-entorno-privado>"
$env:FLASK_SECRET_KEY="<configurar-en-el-entorno-privado>"
flask --app wsgi:app run
```

La app carga el artefacto al iniciar. No reentrena. Cada envío aceptado predice un segmento y hace exactamente una llamada `insert_one` con recencia, frecuencia, gasto y segmento. El adaptador Atlas no expone lectura, edición ni eliminación. Para valores fuera del rango de entrenamiento, `reject` impide predicción y persistencia; `warn` muestra un aviso y permite continuar.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan modelos y colecciones de prueba; no requieren credenciales ni conexión Atlas.

## Despliegue WSGI

El repositorio incluye `wsgi.py` y un `Procfile` que ejecuta Gunicorn enlazado al puerto `PORT` del proveedor. 

El proyecto está desplegado en Render: [Abrir la aplicación](https://segmenta-rfm-atlas.onrender.com). Render inicia el servicio cuando recibe una solicitud, aunque, en el plan gratuito, puede tardar un poco si estaba inactivo.

`artifacts/rfm_kmeans.joblib` es el modelo entrenado que carga la aplicación; no necesita reentrenarlo para usarla. Las credenciales de MongoDB Atlas y `FLASK_SECRET_KEY` se configuran como variables privadas en Render y no se guardan en el repositorio.

## Documentación técnica

Consulta [docs/technical-design.md](docs/technical-design.md) y los diagramas fuente en `docs/architecture/`.

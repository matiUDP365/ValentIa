# Captura de muestras de dos manos y envío a Flask

Este cliente captura muestras etiquetadas con la cámara de un equipo Linux y las guarda en un CSV local. Si se configuran la URL y el token, también manda cada muestra a Flask para guardarla en Supabase. **No transmite video en vivo ni conecta el lector web a la cámara de la Raspberry.**

## Preparar el servidor Flask

1. Configura Supabase y ejecuta `schema.sql` según [GUIA_SUPABASE.md](GUIA_SUPABASE.md).
2. En `.env`, define `DEVICE_API_TOKEN` y las claves de Flask/Supabase.
3. Para aceptar conexiones desde otro equipo de la red, inicia Flask con `FLASK_HOST=0.0.0.0` y permite el puerto 5000 en el firewall si es necesario.
4. Obtén la IP privada del equipo que ejecuta Flask. La URL del cliente debe usar esa IP, no `127.0.0.1`.

## Ejecutar el cliente Linux

Copia la carpeta `raspberry_client/` y el archivo `hand_landmarker.task` al equipo Linux. El equipo necesita una cámara, una sesión gráfica/teclado y versiones compatibles de OpenCV, NumPy y MediaPipe. El cliente no se ha probado en hardware Raspberry real.

En una terminal Linux, configura:

```bash
export DATASET_URL='http://IP-DEL-SERVIDOR:5000/api/raspberry/sign-samples'
read -rs -p 'Token del dispositivo: ' DEVICE_API_TOKEN
echo
export DEVICE_API_TOKEN
export SIGN_LABEL='GRACIAS'
export REQUIERE_DOS_MANOS='1'
python Generador_DataSet.py
```

La variable `SIGN_LABEL` es la etiqueta manual que se asignará a las muestras. Cambia su valor antes de capturar otra seña. Con `REQUIERE_DOS_MANOS=1`, la barra espaciadora guarda solo cuando aparecen ambas manos; con `0`, permite guardar una mano y completa el bloque ausente con ceros.

Al pulsar espacio, el cliente escribe una fila sin cabecera en `dataset_senias_2manos.csv` y envía las 126 características a Flask. Si no se definen `DATASET_URL` o `DEVICE_API_TOKEN`, conserva el CSV local y no hace el envío. `q` cierra la ventana. La llamada de red es síncrona y puede pausar la captura hasta 15 segundos si hay problemas de conexión.

## Contrato de la API

El cliente hace un `POST` a `/api/raspberry/sign-samples` con `Content-Type: application/json` y `Authorization: Bearer <DEVICE_API_TOKEN>`:

```json
{
  "label": "GRACIAS",
  "handedness": "Both",
  "features": [0.0, 0.0, 0.0]
}
```

El ejemplo muestra solo el inicio del arreglo: `features` debe contener exactamente 126 números, en el orden izquierda y luego derecha, 63 por mano. Cada bloque se normaliza restando las coordenadas de la muñeca. Para una muestra de una mano, el bloque ausente contiene 63 ceros. El servidor responde `201` con `saved: true` solo cuando confirma que Supabase guardó la muestra. `401` indica token inválido, `400` datos inválidos y `503` falta configuración o falla el almacenamiento.

Este endpoint guarda **muestras de entrenamiento**, no predicciones en vivo. El reconocimiento en el panel web ejecuta el modelo en el equipo que aloja Flask.

## Entrenamiento

El administrador puede consultar los registros en **Datasets en Supabase → Señas**. El enlace CSV descarga la página actual (hasta 50 filas) en formato sin cabecera: etiqueta y 126 características. Reúne las páginas necesarias en `dataset_senias_2manos.csv` antes de ejecutar `Entrenamiento_2manos.py`. El entrenamiento y la actualización del modelo son pasos manuales; guardar muestras no cambia automáticamente el clasificador.

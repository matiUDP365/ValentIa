# Proyecto valenTIa · Proyectos en TICS 1

Panel web local para iniciar sesión con perfil de **operador** o **administrador**, consultar el diagnóstico de hardware y ejecutar el lector de señas del proyecto.

## Ejecutar en VS Code

1. Instala Python 3.10 o superior.
2. En la terminal, desde esta carpeta, instala las dependencias: `python -m pip install -r requirements.txt`.
3. Inicia la aplicación con: `python app.py`.
4. Abre `http://127.0.0.1:5000`.

Credenciales de demostración:

| Perfil | Usuario | Contraseña |
| --- | --- | --- |
| Operador | `operador` | `operador123` |
| Administrador | `admin` | `admin123` |

## Perfiles

- **Operador:** inicia y detiene el lector, ve la cámara del equipo que ejecuta Flask, observa la seña y frase reconocidas, y puede borrar, separar palabras y reproducir audio.
- **Administrador:** ve el resumen general, detalle de dispositivos, actividad reciente y ajustes de integración. No tiene controles del lector.

El lector carga el modelo Random Forest y MediaPipe al pulsar **Iniciar lector**; no abre la cámara al iniciar Flask ni al abrir el sitio. La inferencia procesa una cámara conectada al equipo que ejecuta el servidor. Si Flask corre en un computador, esa es su cámara; para usar la cámara de la Raspberry, la aplicación deberá ejecutarse en la propia Raspberry o se debe integrar el flujo de cámara de su API.

El umbral de aceptación de señas es 85 % y la seña se confirma al mantenerla por 2 segundos, siguiendo el código recibido. El audio local contiene los clips recibidos en `audios`; para reproducir MP3, el equipo servidor necesita FFmpeg y una salida de audio.

## Integración pendiente

`sign_reader.py` adapta el lector de escritorio a un trabajador en segundo plano y entrega fotogramas, confianza y texto traducido a la interfaz. El modelo y el asset de MediaPipe están en `assets/sign_reader/`; los clips recibidos están en `assets/audios/`. El dataset CSV y `Entrenamiento.py` no se cargan en tiempo de ejecución: sirven para volver a entrenar el modelo.

`raspberry.py` expone `get_monitoring_data()`, el adaptador que alimenta ambos paneles. El endpoint `POST /api/raspberry/telemetry` define un contrato para recibir estados de HC-SR04, ESP32-CAM y LCD. Los datos recibidos se mantienen en memoria y se marcan como sin señal después de 30 segundos; reiniciar Flask los borra. Supabase todavía no está conectado.

### Probar el contrato sin Raspberry Pi

El emisor de ejemplo manda datos ficticios. Sirve para revisar el recorrido hasta el panel, pero no simula sensores físicos ni debe presentarse como una conexión real.

1. En una terminal de PowerShell, define un token local e inicia Flask:

   ```powershell
   $env:DEVICE_API_TOKEN = "token-demo-local"
   python app.py
   ```

2. En otra terminal de PowerShell, usa el mismo token e inicia el emisor de muestra:

   ```powershell
   $env:DEVICE_API_TOKEN = "token-demo-local"
   $env:MONITORING_URL = "http://127.0.0.1:5000/api/raspberry/telemetry"
   python examples/send_demo_telemetry.py
   ```

3. Inicia sesión en la web. Las tarjetas se actualizan automáticamente cada 3 segundos. La interfaz identifica estos datos como simulados.

Formato esperado por el endpoint:

```json
{
  "device_id": "VT-001",
  "source": "raspberry",
  "components": [
    {"id": "proximity", "status": "online", "value": 42, "unit": "cm"},
    {"id": "esp32_cam", "status": "online"},
    {"id": "screen", "status": "online"}
  ]
}
```

Estados permitidos: `online`, `offline`, `error` y `maintenance`. La Raspberry debe enviar el token en `Authorization: Bearer <DEVICE_API_TOKEN>`. Este endpoint acepta los IDs `proximity`, `esp32_cam` y `screen`; hay que ajustarlos a los módulos reales. Para conectar una Raspberry en la misma red local, Flask debe escuchar en la red del computador (`FLASK_HOST=0.0.0.0`) y el emisor debe apuntar a la IP privada de ese computador, no a `127.0.0.1`. No publiques el token en el HTML ni en el repositorio.

## Antes de publicar en AWS

Esta versión es una demo local: las cuentas están definidas en `app.py`, la actividad es de muestra y el control de pantalla sigue siendo simulado. Para producción se deben conectar las cuentas a una base de datos, definir `FLASK_SECRET_KEY` como secreto de entorno y desplegar detrás de HTTPS. El modo `debug` está apagado por defecto; no lo actives en un servidor compartido. No reutilices las contraseñas de demostración.

Los archivos anteriores de la maqueta CRM (`index.html`, `cinthya/` y `felipe/`) se mantienen disponibles; la aplicación valenTIa se inicia con `python app.py`.

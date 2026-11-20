# Proyecto valenTIa · Proyectos en TICS 1

> **Versión con persistencia de sensores y dataset de señas:** sigue primero [GUIA_SUPABASE.md](GUIA_SUPABASE.md). Configura `.env` y ejecuta `schema.sql` en Supabase. Las cuentas siguen siendo de demo.

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

El lector carga dos modelos y MediaPipe al pulsar **Iniciar lector**; no abre la cámara al iniciar Flask ni al abrir el sitio. Si detecta una mano, usa el modelo de 63 características entrenado con las filas válidas de una mano en `dataset_senias.csv`; si detecta dos, usa el modelo de 126 características entrenado con las muestras válidas de ambos CSV. El modelo de dos manos tiene por ahora las etiquetas `TARJETA` y `GRACIAS`. La inferencia procesa una cámara conectada al equipo que ejecuta Flask. Para usar la cámara de la Raspberry como fuente del lector web, se necesita ejecutar Flask allí o diseñar otro flujo de video.

El umbral de aceptación de señas es 85 % y la seña se confirma al mantenerla por 2 segundos, siguiendo el código recibido. El audio local contiene los clips recibidos en `audios`; para reproducir MP3, el equipo servidor necesita FFmpeg y una salida de audio.

### Completar letras y acciones

En el panel del operador, **Dataset de señas** permite agregar muestras reales al CSV local. Los botones sugieren las letras pendientes y `SOLICITAR DEPOSITO`; también se puede escribir otra etiqueta. Cada fila se guarda con 63 características para una mano o 126 para dos manos, sin fotos. Se recomienda reunir al menos 30 ejemplos por etiqueta y conservar el mismo número de manos para cada seña. Las muestras no cambian el modelo hasta volver a entrenarlo.

Desde la carpeta del proyecto, ejecuta `python Entrenamiento_1mano.py` para actualizar el modelo de una mano. Ejecuta `python Entrenamiento_2manos.py` para actualizar el de dos manos. Cada entrenamiento guarda el modelo en `assets/sign_reader/`; reinicia Flask después de entrenar para que el lector cargue la versión nueva. Si el equipo no reconoce correctamente una seña, recopila más ejemplos reales y vuelve a entrenar.

## Integración pendiente

`sign_reader.py` adapta el lector de escritorio a un trabajador en segundo plano y entrega fotogramas, confianza y texto traducido a la interfaz. Los dos modelos y el asset de MediaPipe están en `assets/sign_reader/`; los clips recibidos están en `assets/audios/`. Los CSV no se cargan en tiempo de ejecución: sirven para entrenar los modelos con `Entrenamiento_1mano.py` y `Entrenamiento_2manos.py`, respectivamente. Las etiquetas dependen de los datos disponibles: el CSV de una mano incluye palabras y letras, pero no todas las letras del alfabeto ni la acción de depósito.

`raspberry.py` expone `get_monitoring_data()`, el adaptador que alimenta ambos paneles. El endpoint `POST /api/raspberry/telemetry` recibe estados de HC-SR04, ESP32-CAM y LCD. El endpoint `POST /api/raspberry/sign-samples` admite muestras con 63 o 126 características, para una o dos manos, y puede persistirlas en Supabase. Ambos endpoints requieren `DEVICE_API_TOKEN`; las claves privadas de Supabase solo se configuran en el servidor. La captura manual y la consulta histórica de señas están disponibles en los paneles.

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

Formato esperado por el endpoint de telemetría:

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

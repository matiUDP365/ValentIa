# Conectar valenTIa con Supabase

Esta carpeta es una copia completa del proyecto con el backend de datasets agregado. Los originales del Escritorio no se modificaron. Abre esta carpeta en VS Code para trabajar con esta versión.

## 1. Crear la base

1. Crea un proyecto en https://supabase.com/dashboard.
2. Abre SQL Editor, pega el contenido de `schema.sql` y ejecútalo.
3. En la configuración del proyecto copia la URL del proyecto y una clave **secreta** `sb_secret_...`. También se admite la clave antigua `service_role`.
4. Copia `.env.example` como `.env` en esta misma carpeta y sustituye todos los valores. La clave de Supabase se coloca solo allí, nunca en HTML o JavaScript, ni en el chat.
5. Genera dos secretos distintos para `DEVICE_API_TOKEN` y `FLASK_SECRET_KEY`. Puedes ejecutar dos veces `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python app.py
```

Abre http://127.0.0.1:5000. El servidor carga `.env` al iniciar; las variables ya definidas en la terminal tienen prioridad. Reinicia Flask después de cambiar la configuración.

## 2. Guardar sensores

La Raspberry sigue enviando el contrato descrito en README.md a `POST /api/raspberry/telemetry`, con `Authorization: Bearer <DEVICE_API_TOKEN>`. Ahora cada paquete válido se guarda en `telemetry_packets` antes de actualizar las tarjetas del panel.

Ejemplo desde otra terminal PowerShell (usa el mismo token configurado en `.env`):

```powershell
$tokenDispositivo = Read-Host 'Token del dispositivo'
$paquete = @{
    device_id = 'VT-001'
    source = 'simulation'
    components = @(
        @{ id = 'proximity'; status = 'online'; value = 42; unit = 'cm' },
        @{ id = 'esp32_cam'; status = 'online' },
        @{ id = 'screen'; status = 'online' }
    )
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/raspberry/telemetry' -Method Post -Headers @{ Authorization = "Bearer $tokenDispositivo" } -ContentType 'application/json' -Body $paquete
```

Una respuesta `201` con `saved: true` confirma que Supabase aceptó el registro. Un `503` significa que no se confirmó el guardado; no se actualiza la memoria como si hubiese tenido éxito. No hay cola local ni reintentos automáticos. Si el cliente pierde la respuesta después de que Supabase confirme, reenviar puede duplicar un paquete: este endpoint no implementa deduplicación. `received_at` es la hora UTC de recepción en Flask. `source=simulation` distingue las pruebas de los envíos reales (`raspberry`).

## 3. Guardar muestras de señas

1. Ingresa como operador (`operador` / `operador123`, cuentas de demo existentes).
2. Inicia el lector y muestra la seña con una o dos manos.
3. En **Dataset de señas**, escribe la etiqueta real, por ejemplo `HOLA`, y pulsa **Guardar muestra en Supabase**.
4. La confirmación aparece solamente si Supabase guardó la muestra.

Cada clic guarda la muestra más reciente (máximo un segundo de antigüedad). La inferencia usa el modelo de 63 características si detecta una mano y el modelo de 126 características si detecta dos. La fila puede incluir hasta 42 puntos `[x,y,z]`, lateralidad, fecha, etiqueta real, predicción y confianza (0 a 1). No se guardan fotos.

La etiqueta real la escribe la persona; la predicción se conserva por separado para evitar convertir errores del modelo en etiquetas de entrenamiento. Estas muestras no actualizan el modelo automáticamente: hay que revisar el dataset y entrenar por separado. `Entrenamiento_2manos.py` usa las filas de 127 columnas (etiqueta + 126 características) y omite filas antiguas de 64 columnas.

## 4. Consultar los datos

Ingresa como administrador (`admin` / `admin123`) y abre **Datasets en Supabase**. Puedes alternar sensores y señas, avanzar por páginas de 50 registros y descargar el JSON de cada página, con coordenadas y características incluidas en las muestras de señas.

También se puede consultar desde una sesión de administrador:

- `GET /api/datasets/sensors?limit=50&offset=0`
- `GET /api/datasets/signs?limit=50&offset=0`

`limit` admite de 1 a 100. La respuesta incluye `data`, `offset`, `limit` y `next_offset`. El orden es por fecha descendente y UUID para desempatar. Son consultas por desplazamiento: nuevos registros mientras navegas pueden desplazar las páginas. No es una exportación completa en un clic.

El historial permanece en Supabase tras reiniciar Flask. Las tarjetas en vivo siguen usando la última telemetría recibida en memoria y vuelven a esperar un envío después de reiniciar; no reconstruyen el estado actual desde el historial.

## Seguridad y alcance

Las tablas tienen RLS activado y no conceden acceso a `anon` ni `authenticated`. Flask usa la clave secreta del servidor para insertar y consultar. La ruta de sensores requiere el token del dispositivo; el historial requiere administrador; la captura requiere operador y token CSRF. La vista de datasets muestra texto mediante `textContent`.

Las cuentas de inicio de sesión siguen siendo las cuentas de demostración originales, y la actividad de muestra no se migró a Supabase. Antes de publicar, sustituye esas cuentas por autenticación real, configura HTTPS y revisa las protecciones de las otras acciones de la demo. Esta entrega implementa persistencia de los dos datasets, no una migración completa de autenticación ni de controles de hardware.

## Comprobación

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan un cliente HTTP de Supabase simulado; no requieren claves ni crean registros reales. Para verificar la conexión real, ejecuta `schema.sql`, configura `.env`, envía el paquete de prueba y comprueba el registro en la vista de administrador y en Table Editor de Supabase.

Documentación oficial: https://supabase.com/docs/guides/api/creating-routes y https://supabase.com/docs/guides/getting-started/api-keys.

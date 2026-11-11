"""Adaptador de telemetría del terminal y estados locales del lector."""

from datetime import datetime, timezone
import math
import threading


TELEMETRY_MAX_AGE_SECONDS = 30
DEVICE_COMPONENTS = {"proximity", "esp32_cam", "screen"}
DEVICE_STATUSES = {"online", "offline", "error", "maintenance"}
_telemetry_lock = threading.Lock()
_latest_telemetry = {}
_latest_device_id = None
_latest_source = None


def receive_telemetry(payload):
    """Valida y guarda en memoria un paquete enviado por el terminal.

    Contrato JSON esperado: device_id, components[] con id/status opcionalmente
    value/unit/message, y source ("raspberry" o "simulation").
    """
    global _latest_device_id, _latest_source

    if not isinstance(payload, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON.")
    device_id = payload.get("device_id")
    components = payload.get("components")
    source = payload.get("source", "raspberry")
    if not isinstance(device_id, str) or not device_id.strip() or len(device_id) > 64:
        raise ValueError("device_id debe ser un texto de 1 a 64 caracteres.")
    if source not in ("raspberry", "simulation"):
        raise ValueError("source debe ser 'raspberry' o 'simulation'.")
    if not isinstance(components, list) or not components or len(components) > 3:
        raise ValueError("components debe incluir de 1 a 3 módulos.")

    received_at = datetime.now(timezone.utc)
    parsed = {}
    for item in components:
        if not isinstance(item, dict):
            raise ValueError("Cada componente debe ser un objeto.")
        component_id = item.get("id")
        status = item.get("status")
        if component_id not in DEVICE_COMPONENTS:
            raise ValueError("id de componente no reconocido.")
        if component_id in parsed:
            raise ValueError("No repitas componentes en el mismo paquete.")
        if status not in DEVICE_STATUSES:
            raise ValueError("status debe ser online, offline, error o maintenance.")

        value = item.get("value")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError("value debe ser un texto, número o booleano.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("value debe ser un número finito.")
        unit = item.get("unit", "")
        message = item.get("message", "")
        if not isinstance(unit, str) or len(unit) > 16:
            raise ValueError("unit debe tener hasta 16 caracteres.")
        if not isinstance(message, str) or len(message) > 120:
            raise ValueError("message debe tener hasta 120 caracteres.")

        parsed[component_id] = {
            "status": status,
            "value": value,
            "unit": unit,
            "message": message,
            "received_at": received_at,
        }

    with _telemetry_lock:
        _latest_telemetry.update(parsed)
        _latest_device_id = device_id.strip()
        _latest_source = source

    return {"device_id": device_id.strip(), "received": len(parsed)}


def _telemetry_snapshot():
    with _telemetry_lock:
        return dict(_latest_telemetry), _latest_device_id, _latest_source


def get_monitoring_data(reader_status=None):
    """Entrega el formato compartido por los paneles de operador y admin."""
    now = datetime.now().astimezone()
    reader_status = reader_status or {}
    running = reader_status.get("running", False)
    model_ready = reader_status.get("model_ready", False)
    camera_ready = reader_status.get("camera_ready", False)
    error = reader_status.get("state") == "error"
    audio_ready = reader_status.get("audio_ready", False)
    telemetry, device_id, source = _telemetry_snapshot()

    components = [
        {
            "id": "proximity", "name": "Detección de usuario",
            "detail": "Sensor ultrasónico HC-SR04", "icon": "sensor",
            "state": "Pendiente de conexión", "health": "pending", "latency": "—",
        },
        {
            "id": "camera", "name": "Cámara del lector",
            "detail": "Cámara del equipo que ejecuta Flask", "icon": "camera",
            "state": "Capturando" if camera_ready else ("Error" if error else "Detenida"),
            "health": "healthy" if camera_ready else ("error" if error else "pending"),
            "latency": "—",
        },
        {
            "id": "esp32_cam", "name": "Cámara operativa",
            "detail": "Módulo ESP32-CAM (OV2640)", "icon": "camera",
            "state": "Pendiente de conexión", "health": "pending", "latency": "—",
        },
        {
            "id": "edge", "name": "Procesamiento local",
            "detail": "Lector Python · modelo Random Forest", "icon": "processor",
            "state": "Activo" if running else ("Listo" if model_ready else "Detenido"),
            "health": "healthy" if model_ready else ("error" if error else "pending"),
            "latency": "—",
        },
        {
            "id": "gestures", "name": "Reconocimiento de señas",
            "detail": "MediaPipe · Random Forest · umbral 85 %", "icon": "hand",
            "state": "Detectando" if running else ("Modelo cargado" if model_ready else "Detenido"),
            "health": "healthy" if model_ready else ("error" if error else "pending"),
            "latency": "< 2 s objetivo",
        },
        {
            "id": "screen", "name": "Pantalla LCD",
            "detail": "Display 16×2", "icon": "screen",
            "state": "Pendiente de conexión", "health": "pending", "latency": "—",
        },
        {
            "id": "audio", "name": "Audio de señas",
            "detail": "Clips locales · carpeta audios", "icon": "audio",
            "state": "Disponible" if audio_ready else "No disponible",
            "health": "healthy" if audio_ready else "pending", "latency": "—",
        },
    ]

    display_names = {
        "proximity": "Detección de usuario",
        "esp32_cam": "Cámara operativa",
        "screen": "Pantalla LCD",
    }
    labels = {
        "online": ("En línea", "healthy"),
        "offline": ("Fuera de línea", "pending"),
        "error": ("Error", "error"),
        "maintenance": ("En mantenimiento", "pending"),
    }
    newest_received = None
    for component in components:
        entry = telemetry.get(component["id"])
        if not entry:
            continue
        age = (datetime.now(timezone.utc) - entry["received_at"]).total_seconds()
        received_local = entry["received_at"].astimezone()
        newest_received = max(newest_received or received_local, received_local)
        if age > TELEMETRY_MAX_AGE_SECONDS:
            component["state"] = "Sin señal reciente"
            component["health"] = "pending"
            component["latency"] = received_local.strftime("%H:%M:%S")
        else:
            component["state"], component["health"] = labels[entry["status"]]
            component["latency"] = received_local.strftime("%H:%M:%S")
        details = []
        if entry["value"] is not None:
            value = str(entry["value"])
            details.append(f"{value} {entry['unit']}".strip())
        if entry["message"]:
            details.append(entry["message"])
        if details:
            component["detail"] = f"{component['detail']} · {' · '.join(details)}"

    live_source = bool(newest_received and
                       (datetime.now(timezone.utc) - newest_received.astimezone(timezone.utc)).total_seconds()
                       <= TELEMETRY_MAX_AGE_SECONDS)
    actual_raspberry = live_source and source == "raspberry"
    if actual_raspberry:
        integration_note = f"Telemetría reciente recibida desde Raspberry Pi {device_id}."
        page_source = "raspberry"
    elif live_source:
        integration_note = "Datos recibidos por el simulador local; no provienen de una Raspberry real."
        page_source = "demo"
    else:
        integration_note = (
            "El lector de señas funciona localmente. El endpoint de telemetría está preparado; "
            "los módulos de Raspberry aún no han enviado datos."
        )
        page_source = "demo"

    updated_at = (newest_received.strftime("%H:%M:%S") if newest_received else now.strftime("%H:%M:%S"))
    return {
        "source": page_source,
        "device_id": device_id,
        "updated_at": updated_at,
        "updated_label": now.strftime("%d %b %Y, %H:%M"),
        "system_online": True,
        "integration_note": integration_note,
        "components": components,
    }

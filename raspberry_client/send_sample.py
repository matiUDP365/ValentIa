"""Cliente de la Raspberry: solo necesita la URL de Flask y el token del dispositivo."""
import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


def send_sample(features, label, handedness="unknown"):
    url = os.environ.get("DATASET_URL", "")
    token = os.environ.get("DEVICE_API_TOKEN", "")
    if not url or not token:
        print("[SERVIDOR] Falta DATASET_URL o DEVICE_API_TOKEN; solo se guardó el CSV local.")
        return False
    payload = json.dumps({
        "label": label,
        "features": features,
        "handedness": handedness,
    }, allow_nan=False).encode()
    request = Request(url, data=payload, method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
            if response.status != 201 or result.get("saved") is not True:
                raise ValueError()
        print("[SERVIDOR] Muestra guardada en Supabase.")
        return True
    except (URLError, OSError, ValueError):
        print("[SERVIDOR] No se confirmó el guardado remoto. El CSV local conserva la muestra; no se reenvía automáticamente.")
        return False

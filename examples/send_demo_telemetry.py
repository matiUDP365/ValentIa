"""Envía lecturas ficticias al endpoint local para ensayar el panel.

No lee sensores físicos. Sirve para comprobar el contrato antes de conectar
el código real de la Raspberry Pi.
"""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = os.environ.get(
    "MONITORING_URL", "http://127.0.0.1:5000/api/raspberry/telemetry"
)
TOKEN = os.environ.get("DEVICE_API_TOKEN", "")


def main():
    if not TOKEN:
        raise SystemExit("Define DEVICE_API_TOKEN en esta terminal antes de iniciar el simulador.")

    while True:
        payload = {
            "device_id": "VT-DEMO-001",
            "source": "simulation",
            "components": [
                {"id": "proximity", "status": "online", "value": 42, "unit": "cm"},
                {"id": "esp32_cam", "status": "online", "message": "Señal de demostración"},
                {"id": "screen", "status": "online", "message": "Pantalla de demostración"},
            ],
        }
        request = Request(
            URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                print(f"Telemetría de muestra enviada: {result}")
        except HTTPError as error:
            print(f"El servidor respondió {error.code}: {error.read().decode('utf-8', errors='replace')}")
        except URLError as error:
            print(f"No se pudo conectar con {URL}: {error.reason}")
        time.sleep(5)


if __name__ == "__main__":
    main()

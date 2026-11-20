"""Acceso a la Data API de Supabase, exclusivamente desde el servidor."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class StorageError(Exception):
    pass


def configured():
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SECRET_KEY"))


def _request(table, method="GET", rows=None, params=None):
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "")
    if not configured():
        raise StorageError("Configura SUPABASE_URL y SUPABASE_SECRET_KEY en .env.")
    parts = urlsplit(base)
    if parts.scheme != "https" or not parts.hostname or parts.path or parts.query or parts.fragment or parts.username:
        raise StorageError("SUPABASE_URL debe ser la URL HTTPS del proyecto, sin rutas.")
    headers = {"apikey": key, "Content-Type": "application/json", "Prefer": "return=representation"}
    # Las claves sb_secret_ se envían solo en apikey. Compatibilidad con service_role JWT.
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    url = base + "/rest/v1/" + table
    if params:
        url += "?" + urlencode(params)
    body = json.dumps(rows, allow_nan=False).encode() if rows is not None else None
    try:
        with urlopen(Request(url, data=body, headers=headers, method=method), timeout=10) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        # No devolver respuestas del proveedor ni claves al navegador o los logs.
        raise StorageError("No se pudo acceder a Supabase. Revisa la conexión, las claves y schema.sql.") from exc


def save_telemetry(device_id, source, components, received_at):
    return _request("telemetry_packets", "POST", {
        "device_id": device_id, "source": source,
        "components": components, "received_at": received_at,
    })[0]


def save_sample(sample):
    return _request("sign_samples", "POST", sample)[0]


def list_rows(kind, limit=50, offset=0):
    tables = {"sensors": "telemetry_packets", "signs": "sign_samples"}
    if kind not in tables:
        raise ValueError("Dataset desconocido.")
    return _request(tables[kind], params={
        "select": "*", "order": "received_at.desc,id.desc" if kind == "sensors" else "captured_at.desc,id.desc",
        "limit": limit, "offset": offset,
    })

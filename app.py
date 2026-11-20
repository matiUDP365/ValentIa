"""Aplicación web local para el panel de diagnóstico valenTIa."""

from datetime import datetime
from functools import wraps
import hmac
import os
import time
import csv
import io
import secrets
import threading
from pathlib import Path
from dotenv import load_dotenv

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, stream_with_context, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from raspberry import get_monitoring_data, receive_telemetry
from sign_reader import reader
import storage
from dataset import validate_sample

load_dotenv(Path(__file__).with_name(".env"))

LOCAL_SIGN_DATASET = Path(os.environ.get(
    "LOCAL_SIGN_DATASET",
    str(Path(__file__).with_name("dataset_senias.csv")),
))
LOCAL_SIGN_DATASET_LOCK = threading.Lock()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "valentia-local-demo-change-before-deploy"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=16 * 1024,
)

# Cuentas de demostración locales. Cambiar por almacenamiento persistente y
# altas de usuarios antes de publicar el sistema.
USERS = {
    "operador": {
        "name": "Camila Rojas",
        "role": "operator",
        "role_label": "Operadora",
        "password_hash": generate_password_hash("operador123"),
        "initials": "CR",
    },
    "admin": {
        "name": "Valentina Soto",
        "role": "admin",
        "role_label": "Administradora",
        "password_hash": generate_password_hash("admin123"),
        "initials": "VS",
    },
}

AUDIT_EVENTS = [
    ("09:42", "Camila Rojas", "Revisión de módulos", "Revisión completada"),
    ("09:18", "Sistema", "Conexión de cámara", "Dispositivo en línea"),
    ("08:56", "Valentina Soto", "Inicio de sesión", "Acceso administrador"),
    ("Ayer", "Camila Rojas", "Modo de pantalla", "Pantalla activada"),
]

def log_event(user_name, event, detail):
    now_str = datetime.now().strftime("%H:%M")
    AUDIT_EVENTS.insert(0, (now_str, user_name, event, detail))
    if len(AUDIT_EVENTS) > 30:
        AUDIT_EVENTS.pop()

def login_required(role=None):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect(url_for("login"))
            if role and user.get("role") != role:
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorate


@app.context_processor
def shared_template_data():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return {"current_year": datetime.now().year, "csrf_token": session["csrf_token"]}


@app.get("/")
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    role = request.args.get("role", "operator")
    if role not in ("operator", "admin"):
        role = "operator"
    return render_template("login.html", selected_role=role)


@app.post("/login")
def sign_in():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    requested_role = request.form.get("role", "operator")
    user = USERS.get(username)
    if (requested_role not in ("operator", "admin") or not user
            or user["role"] != requested_role
            or not check_password_hash(user["password_hash"], password)):
        flash("Revisa el usuario, la contraseña y el tipo de acceso.", "error")
        return redirect(url_for("login", role=requested_role))

    session.clear()
    session["user"] = {key: user[key] for key in ("name", "role", "role_label", "initials")}
    session["screen_awake"] = True

    log_event(user["name"], "Inicio de sesión", f"Acceso {user['role_label']}")

    return redirect(url_for("dashboard"))


@app.post("/logout")
def sign_out():
    user = session.get("user")
    if user:
        log_event(user["name"], "Cierre de sesión", "Salida del sistema")

    session.clear()
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required()
def dashboard():
    reader_status = reader.status()
    monitoring = get_monitoring_data(reader_status)
    user = session["user"]
    if user["role"] == "admin":
        tab = request.args.get("tab", "overview")
        if tab not in ("overview", "devices", "activity", "settings"):
            tab = "overview"
        return render_template(
            "admin.html", user=user, tab=tab, monitoring=monitoring,
            events=AUDIT_EVENTS, users=USERS, reader_status=reader_status,
        )
    return render_template(
        "operator.html", user=user, monitoring=monitoring,
        screen_awake=session.get("screen_awake", True),
        reader_status=reader_status,
    )


@app.get("/api/reader/status")
@login_required()
def reader_status_api():
    return jsonify(reader.status())


@app.get("/api/monitoring")
@login_required()
def monitoring_status_api():
    """Estado actual para refrescar las tarjetas sin recargar la página."""
    return jsonify(get_monitoring_data(reader.status()))


@app.post("/api/raspberry/telemetry")
def raspberry_telemetry_api():
    """Recibe el estado de la Raspberry; requiere DEVICE_API_TOKEN en el servidor."""
    expected_token = os.environ.get("DEVICE_API_TOKEN", "")
    if not expected_token:
        return jsonify({"error": "La recepción de telemetría no está configurada."}), 503

    authorization = request.headers.get("Authorization", "")
    supplied_token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    if not hmac.compare_digest(supplied_token, expected_token):
        return jsonify({"error": "Token de dispositivo inválido."}), 401
    if not request.is_json:
        return jsonify({"error": "Envía el paquete con Content-Type: application/json."}), 415

    try:
        result = receive_telemetry(request.get_json(silent=False), persist=storage.save_telemetry)
    except storage.StorageError as exc:
        return jsonify({"error": str(exc), "saved": False}), 503
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "saved": True, **result}), 201


@app.post("/api/raspberry/sign-samples")
def raspberry_sign_sample():
    expected = os.environ.get("DEVICE_API_TOKEN", "")
    if not expected:
        return jsonify({"error": "Configura DEVICE_API_TOKEN.", "saved": False}), 503
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not hmac.compare_digest(token, expected):
        return jsonify({"error": "Token inválido.", "saved": False}), 401
    if not request.is_json:
        return jsonify({"error": "Se requiere application/json.", "saved": False}), 415
    try:
        sample = validate_sample(request.get_json())
        saved = storage.save_sample(sample)
    except ValueError as exc:
        return jsonify({"error": str(exc), "saved": False}), 400
    except storage.StorageError as exc:
        return jsonify({"error": str(exc), "saved": False}), 503
    return jsonify({"saved": True, "id": saved["id"]}), 201


@app.post("/operator/dataset/capture", endpoint="capture_dataset_sample")
@login_required("operator")
def capture_dataset_sample():
    token = request.form.get("csrf_token", "")
    if not token or not hmac.compare_digest(token, session.get("csrf_token", "")):
        abort(403)
    try:
        sample = validate_sample({**reader.capture_sample(), "label": request.form.get("label", "")})
        row = [sample["label"], *sample["features"]]
        if len(sample["features"]) == 126 and sample["handedness"] != "Both":
            start = 0 if sample["handedness"] == "Left" else 63
            row = [sample["label"], *sample["features"][start:start + 63]]
        LOCAL_SIGN_DATASET.parent.mkdir(parents=True, exist_ok=True)
        with LOCAL_SIGN_DATASET_LOCK, LOCAL_SIGN_DATASET.open("a", newline="", encoding="utf-8") as output:
            csv.writer(output).writerow(row)
    except (ValueError, OSError) as exc:
        flash(str(exc), "error")
    else:
        if storage.configured():
            try:
                storage.save_sample(sample)
            except storage.StorageError:
                flash(f"Muestra de {sample['label']} guardada localmente; Supabase no respondió.", "success")
            else:
                flash(f"Muestra de {sample['label']} guardada localmente y en Supabase.", "success")
        else:
            flash(f"Muestra de {sample['label']} guardada en {LOCAL_SIGN_DATASET.name}.", "success")
    return redirect(url_for("dashboard"))


@app.get("/api/datasets/<kind>")
def dataset_history(kind):
    if not session.get("user"):
        return jsonify({"error": "Inicia sesión."}), 401
    if session["user"].get("role") != "admin":
        return jsonify({"error": "Se requiere acceso administrador."}), 403
    if kind not in ("sensors", "signs"):
        abort(404)
    try:
        limit = int(request.args.get("limit", "50"))
        offset = int(request.args.get("offset", "0"))
        if not 1 <= limit <= 100 or not 0 <= offset <= 1000000:
            raise ValueError()
    except ValueError:
        return jsonify({"error": "limit debe ser 1–100 y offset 0–1000000."}), 400
    try:
        rows = storage.list_rows(kind, limit, offset)
    except storage.StorageError as exc:
        return jsonify({"error": str(exc)}), 503
    if request.args.get("format") == "csv":
        if kind != "signs":
            return jsonify({"error": "CSV disponible solo para señas."}), 400
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerows([row["label"], *row["features"]] for row in rows)
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f'attachment; filename="dataset_senias_{offset}.csv"'
        response.headers["Cache-Control"] = "no-store"
        return response
    response = jsonify({"data": rows, "limit": limit, "offset": offset,
                        "next_offset": offset + limit if len(rows) == limit else None})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/admin/datasets")
@login_required("admin")
def datasets_page():
    return render_template("datasets.html", user=session["user"])


@app.get("/reader/video")
@login_required()
def reader_video():
    if not reader.status()["running"]:
        abort(409)

    @stream_with_context
    def stream_frames():
        while reader.status()["running"]:
            frame = reader.current_frame()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            else:
                time.sleep(0.1)

    return Response(stream_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.post("/operator/screen")
@login_required("operator")
def toggle_screen():
    session["screen_awake"] = not session.get("screen_awake", True)
    estado = "Pantalla activada" if session["screen_awake"] else "Modo descanso activado"
    log_event(session["user"]["name"], "Modo de pantalla", estado)
    flash("Pantalla activada." if session["screen_awake"] else "Modo descanso activado. (Simulación)", "success")
    return redirect(url_for("dashboard"))


@app.post("/operator/reader/<action>")
@login_required("operator")
def reader_action(action):
    actions = {
        "start": reader.start,
        "stop": reader.stop,
        "clear": reader.clear,
        "undo": reader.undo,
        "word": reader.new_word,
    }
    if action == "speak":
        flash(
            "Audio enviado al equipo." if reader.speak()
            else "El audio no está listo o aún no hay texto para reproducir.",
            "success" if reader.status()["audio_ready"] else "error",
        )
    elif action in actions:
        result = actions[action]()
        messages = {
            "start": "Iniciando el lector en la cámara del equipo…",
            "stop": "Deteniendo el lector…",
            "clear": "Texto borrado.",
            "undo": "Última seña eliminada.",
            "word": "Espacio agregado.",
        }
        flash(messages[action] if result is not False else "El lector ya está iniciado.", "success")
    else:
        abort(404)
    return redirect(url_for("dashboard"))


@app.post("/admin/maintenance")
@login_required("admin")
def maintenance():
    flash("Solicitud registrada en la demo. El equipo no recibió ningún comando.", "success")
    return redirect(url_for("dashboard", tab="devices"))


@app.errorhandler(403)
def forbidden(_error):
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=5000,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )

"""Validación de muestras etiquetadas para modelos de una o dos manos."""
from datetime import datetime, timezone
import math


def validate_sample(payload):
    if not isinstance(payload, dict):
        raise ValueError("La muestra debe ser un objeto JSON.")
    label = payload.get("label")
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 64:
        raise ValueError("La etiqueta debe tener de 1 a 64 caracteres.")
    points = payload.get("landmarks", [])
    if not isinstance(points, list) or len(points) not in (0, 21, 42):
        raise ValueError("landmarks debe contener 21 o 42 puntos [x, y, z], o estar vacío si se envían features.")
    clean = []
    for point in points:
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("Cada punto debe incluir x, y, z.")
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100 for v in point):
            raise ValueError("Las coordenadas deben ser números finitos entre -100 y 100.")
        clean.append([float(v) for v in point])
    confidence = payload.get("confidence")
    if confidence is not None and (type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise ValueError("La confianza debe estar entre 0 y 1.")
    handedness = payload.get("handedness", "unknown")
    if handedness not in ("Left", "Right", "Both", "unknown"):
        raise ValueError("handedness debe ser Left, Right, Both o unknown.")
    prediction = payload.get("prediction")
    if prediction is not None and (not isinstance(prediction, str) or len(prediction) > 64):
        raise ValueError("La predicción debe tener hasta 64 caracteres.")
    captured_at = payload.get("captured_at", datetime.now(timezone.utc).isoformat())
    try:
        stamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("captured_at debe ser una fecha ISO 8601 con zona horaria.") from None
    supplied_features = payload.get("features")
    if supplied_features is not None:
        if not isinstance(supplied_features, list) or len(supplied_features) not in (63, 126):
            raise ValueError("features debe contener 63 o 126 coordenadas.")
        if any(type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 100
               for value in supplied_features):
            raise ValueError("features debe contener números finitos entre -100 y 100.")
        features = [float(value) for value in supplied_features]
        if clean and len(features) != len(clean) * 3:
            raise ValueError("La cantidad de features no coincide con los landmarks enviados.")
    elif len(clean) == 21:
        features = [point[i] - clean[0][i] for point in clean for i in range(3)]
    elif len(clean) == 42:
        features = []
        for start in (0, 21):
            hand = clean[start:start + 21]
            if all(value == 0 for point in hand for value in point):
                features.extend([0.0] * 63)
            else:
                features.extend(point[i] - hand[0][i] for point in hand for i in range(3))
    else:
        raise ValueError("Envía landmarks o un vector de 63/126 features.")

    return {
        "label": label.strip().upper(), "landmarks": clean,
        "features": features,
        "confidence": confidence, "prediction": prediction, "handedness": handedness,
        "captured_at": stamp.astimezone(timezone.utc).isoformat(),
    }

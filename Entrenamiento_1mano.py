"""Entrena el lector de una mano usando las filas de 64 columnas del CSV mixto."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "dataset_senias.csv"
MODEL_PATH = ROOT / "assets" / "sign_reader" / "modelo_random_forest_1mano.pkl"
EXPECTED_COLUMNS = 64  # etiqueta + 63 coordenadas de una mano


def main() -> None:
    if not CSV_PATH.is_file():
        raise SystemExit(f"No se encontró el dataset: {CSV_PATH}")

    features: list[list[float]] = []
    labels: list[str] = []
    skipped = 0

    with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as source:
        for row in csv.reader(source):
            if len(row) != EXPECTED_COLUMNS:
                # Las filas de 127 columnas pertenecen al modelo de dos manos.
                skipped += 1
                continue
            label = row[0].strip().upper()
            try:
                vector = [float(value) for value in row[1:]]
            except ValueError:
                skipped += 1
                continue
            if not label or not all(math.isfinite(value) for value in vector):
                skipped += 1
                continue
            labels.append(label)
            features.append(vector)

    classes = sorted(set(labels))
    if len(classes) < 2:
        raise SystemExit("El CSV necesita al menos dos señas válidas para entrenar.")

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    model.fit(np.asarray(features, dtype=np.float32), np.asarray(labels))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    counts = {label: labels.count(label) for label in classes}
    print(f"Muestras de una mano usadas: {len(labels)}")
    print(f"Filas mixtas/incorrectas omitidas: {skipped}")
    print(f"Etiquetas entrenadas: {', '.join(classes)}")
    print(f"Muestras por etiqueta: {counts}")
    print(f"Modelo guardado en: {MODEL_PATH}")


if __name__ == "__main__":
    main()

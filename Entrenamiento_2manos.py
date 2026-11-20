import os
import csv
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

CSV_MIXTO = 'dataset_senias.csv'
CSV_LIMPIO_2MANOS = 'dataset_senias_2manos.csv'
NOMBRE_MODELO = os.path.join('assets', 'sign_reader', 'modelo_random_forest_2manos.pkl')
COLUMNAS_ESPERADAS = 127  # 1 Etiqueta + 63 Mano Izquierda + 63 Mano Derecha

print("1. Filtrando y separando muestras válidas de 127 columnas...")

X, y = [], []
filas_viejas_64 = 0

# Leer desde el CSV limpio si ya existe, o rescatar las filas de 127 cols desde dataset_senias.csv
archivos_a_revisar = [f for f in [CSV_LIMPIO_2MANOS, CSV_MIXTO] if os.path.exists(f)]

if not archivos_a_revisar:
    print(f" Error: No se encontró '{CSV_LIMPIO_2MANOS}' ni '{CSV_MIXTO}'.")
    exit(1)

filas_rescatadas_desde_mixto = []

for archivo in archivos_a_revisar:
    with open(archivo, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for fila in reader:
            if not fila:
                continue
            if len(fila) == COLUMNAS_ESPERADAS:
                y.append(fila[0])
                X.append([float(val) for val in fila[1:]])
                if archivo == CSV_MIXTO:
                    filas_rescatadas_desde_mixto.append(fila)
            elif len(fila) == 64:
                filas_viejas_64 += 1

# Guardar las filas nuevas rescatadas en su archivo limpio para no volver a mezclarlas
if filas_rescatadas_desde_mixto and not os.path.exists(CSV_LIMPIO_2MANOS):
    with open(CSV_LIMPIO_2MANOS, mode='w', newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out)
        writer.writerows(filas_rescatadas_desde_mixto)
    print(f" Se migraron {len(filas_rescatadas_desde_mixto)} muestras nuevas a '{CSV_LIMPIO_2MANOS}'.")

if filas_viejas_64 > 0:
    print(f" Se ignoraron {filas_viejas_64} filas antiguas de 64 columnas en '{CSV_MIXTO}'.")

if len(X) == 0:
    print(" Error: Aún no hay filas de 127 columnas. Graba tus señas primero con 'Generador_DataSet.py'.")
    exit(1)

clases_unicas = sorted(set(y))
print(f" Muestras válidas de 127 columnas cargadas: {len(X)}")
print(f" Señas detectadas ({len(clases_unicas)}): {clases_unicas}")

if len(clases_unicas) < 2:
    print("\n Advertencia: Solo tienes 1 seña grabada en 127 columnas.")
    print(" Graba al menos 1 seña más en 'Generador_DataSet.py' (por ejemplo, una de 1 mano y otra de 2 manos) antes de entrenar.")
    exit(1)

X = np.array(X, dtype=np.float32)
y = np.array(y)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print("\n2. Entrenando el clasificador Random Forest (1 y 2 manos)...")
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)

y_pred = clf.predict(X_test)
precision = accuracy_score(y_test, y_pred) * 100

print("\n==================================================")
print("   ¡ENTRENAMIENTO COMPLETADO EXITOSAMENTE!")
print(f"   Precisión global obtenida: {precision:.2f}%")
print("==================================================\n")

print("Reporte de desempeño por seña:")
print(classification_report(y_test, y_pred))

os.makedirs(os.path.dirname(NOMBRE_MODELO), exist_ok=True)
joblib.dump(clf, NOMBRE_MODELO)
print(f" Modelo exportado y listo para usar: '{NOMBRE_MODELO}'")

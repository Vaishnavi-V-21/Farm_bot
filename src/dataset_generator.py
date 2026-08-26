"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/dataset_generator.py
Description   : Agronomic dataset generator, feature engineering, ML algorithm
                benchmark comparison (Random Forest, Decision Tree, SVM, XGBoost, KNN),
                and model training pipeline.
=====================================================================================
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, classification_report

# Crop Ideal Benchmarks (12 Major Indian Crops)
CROP_DATASETS = {
    'Paddy':     {'N': 100, 'P': 50,  'K': 50,  'temp': (22, 35), 'hum': (60, 90), 'ph': (5.5, 6.5), 'moist': (60, 90), 'yield': 2.5},
    'Wheat':    {'N': 120, 'P': 60,  'K': 40,  'temp': (15, 25), 'hum': (40, 70), 'ph': (6.0, 7.5), 'moist': (40, 65), 'yield': 2.2},
    'Maize':    {'N': 130, 'P': 60,  'K': 50,  'temp': (18, 32), 'hum': (50, 80), 'ph': (5.8, 7.2), 'moist': (45, 70), 'yield': 3.0},
    'Cotton':   {'N': 150, 'P': 60,  'K': 60,  'temp': (21, 35), 'hum': (50, 75), 'ph': (6.0, 8.0), 'moist': (40, 65), 'yield': 1.8},
    'Sugarcane':{'N': 250, 'P': 110, 'K': 110, 'temp': (20, 38), 'hum': (60, 85), 'ph': (6.0, 7.5), 'moist': (65, 90), 'yield': 35.0},
    'Groundnut':{'N': 40,  'P': 60,  'K': 40,  'temp': (22, 33), 'hum': (50, 75), 'ph': (6.0, 7.0), 'moist': (35, 60), 'yield': 1.2},
    'Tomato':   {'N': 140, 'P': 80,  'K': 100, 'temp': (18, 30), 'hum': (50, 75), 'ph': (6.0, 7.0), 'moist': (50, 75), 'yield': 12.0},
    'Onion':    {'N': 80,  'P': 50,  'K': 80,  'temp': (15, 30), 'hum': (45, 70), 'ph': (6.0, 7.5), 'moist': (40, 65), 'yield': 8.5},
    'Potato':   {'N': 120, 'P': 100, 'K': 120, 'temp': (15, 24), 'hum': (60, 85), 'ph': (5.2, 6.4), 'moist': (55, 75), 'yield': 10.0},
    'Chili':    {'N': 100, 'P': 50,  'K': 50,  'temp': (20, 32), 'hum': (50, 75), 'ph': (6.0, 7.0), 'moist': (45, 70), 'yield': 4.0},
    'Banana':   {'N': 200, 'P': 90,  'K': 200, 'temp': (26, 35), 'hum': (65, 90), 'ph': (5.5, 7.5), 'moist': (65, 85), 'yield': 18.0},
    'Millets':  {'N': 40,  'P': 20,  'K': 20,  'temp': (25, 38), 'hum': (30, 60), 'ph': (5.5, 8.0), 'moist': (20, 45), 'yield': 1.1}
}

def generate_agronomic_dataset(num_samples_per_crop=300):
    """Generates a realistic synthetic agronomic dataset based on standard ICAR benchmarks."""
    data = []
    np.random.seed(42)

    for crop, profile in CROP_DATASETS.items():
        for _ in range(num_samples_per_crop):
            n = max(5, int(np.random.normal(profile['N'], profile['N'] * 0.15)))
            p = max(5, int(np.random.normal(profile['P'], profile['P'] * 0.15)))
            k = max(5, int(np.random.normal(profile['K'], profile['K'] * 0.15)))
            temp  = round(np.random.uniform(profile['temp'][0] - 2, profile['temp'][1] + 2), 1)
            hum   = round(np.random.uniform(profile['hum'][0] - 5, profile['hum'][1] + 5), 1)
            ph    = round(np.random.uniform(profile['ph'][0] - 0.3, profile['ph'][1] + 0.3), 2)
            moist = round(np.random.uniform(profile['moist'][0] - 5, profile['moist'][1] + 5), 1)
            
            data.append([n, p, k, temp, hum, ph, moist, crop])

    columns = ['N', 'P', 'K', 'temp', 'hum', 'ph', 'moisture', 'crop']
    df = pd.DataFrame(data, columns=columns)
    return df

def compare_ml_algorithms(df):
    """Evaluates multiple ML classifiers to select the best architecture."""
    X = df[['N', 'P', 'K', 'temp', 'hum', 'ph', 'moisture']]
    y = df['crop']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        'Random Forest Classifier': RandomForestClassifier(n_estimators=100, random_state=42),
        'Decision Tree Classifier': DecisionTreeClassifier(random_state=42),
        'Support Vector Machine (SVM)': SVC(kernel='rbf', C=1.0, probability=True),
        'K-Nearest Neighbors (KNN)': KNeighborsClassifier(n_neighbors=5)
    }

    print("\n========================================================")
    print("      MACHINE LEARNING ALGORITHM BENCHMARK RESULTS      ")
    print("========================================================")

    best_model = None
    best_acc = 0.0
    best_name = ""

    for name, clf in models.items():
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        acc = accuracy_score(y_test, preds)
        cv_scores = cross_val_score(clf, X, y, cv=5)
        print(f"Algorithm: {name:<30} | Test Accuracy: {acc*100:.2f}% | 5-Fold CV: {cv_scores.mean()*100:.2f}%")

        if acc > best_acc:
            best_acc = acc
            best_model = clf
            best_name = name

    print(f"\n[WINNER]: {best_name} with {best_acc*100:.2f}% Accuracy!")
    return best_model, X_test, y_test

def train_and_save_model():
    """Executes dataset generation, model training, and serializes artifacts."""
    df = generate_agronomic_dataset()
    best_model, X_test, y_test = compare_ml_algorithms(df)

    output_dir = os.path.join(os.path.dirname(__file__), '../models')
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, 'crop_recommendation_rf.pkl')

    with open(model_path, 'wb') as f:
        pickle.dump(best_model, f)

    print(f"[MODEL SAVED]: Exported model to {model_path}")
    return best_model

if __name__ == '__main__':
    train_and_save_model()

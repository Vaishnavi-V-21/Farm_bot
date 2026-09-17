"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/ml_engine.py
Description   : Machine Learning inference engine for crop recommendation,
                suitability score calculation (0-100%), top 3 crops, expected yield,
                and agronomic reason explanations.
=====================================================================================
"""

import os
import sys
import pickle
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from src.dataset_generator import CROP_DATASETS, train_and_save_model
except ModuleNotFoundError:
    from dataset_generator import CROP_DATASETS, train_and_save_model

MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/crop_recommendation_rf.pkl')

def load_or_train_model():
    """Loads pre-trained model or trains a new model if missing."""
    if not os.path.exists(MODEL_PATH):
        return train_and_save_model()
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)

class CropRecommendationEngine:
    def __init__(self):
        self.model = load_or_train_model()
        self.crop_profiles = CROP_DATASETS

    def calculate_suitability_score(self, current_telemetry, crop_name):
        """Calculates a normalized suitability score (0-100%) for a given crop."""
        if crop_name not in self.crop_profiles:
            return 0.0

        p = self.crop_profiles[crop_name]

        # Calculate deviation penalties
        n_penalty = abs(current_telemetry['N'] - p['N']) / float(p['N'])
        p_penalty = abs(current_telemetry['P'] - p['P']) / float(p['P'])
        k_penalty = abs(current_telemetry['K'] - p['K']) / float(p['K'])

        temp_mid = (p['temp'][0] + p['temp'][1]) / 2.0
        t_penalty = abs(current_telemetry['temp'] - temp_mid) / temp_mid

        hum_mid = (p['hum'][0] + p['hum'][1]) / 2.0
        h_penalty = abs(current_telemetry['hum'] - hum_mid) / hum_mid

        ph_mid = (p['ph'][0] + p['ph'][1]) / 2.0
        ph_penalty = abs(current_telemetry['ph'] - ph_mid) / ph_mid

        # Weighted aggregate penalty
        total_penalty = (0.25 * n_penalty + 0.20 * p_penalty + 0.20 * k_penalty +
                         0.15 * t_penalty + 0.10 * h_penalty + 0.10 * ph_penalty)

        score = max(0.0, 100.0 * (1.0 - total_penalty))
        return round(score, 1)

    def generate_crop_rationale(self, telemetry, crop_name):
        """Generates human-readable agronomic reasons for crop suitability."""
        p = self.crop_profiles.get(crop_name)
        if not p:
            return "General agronomic match based on historical yield data."

        reasons = []
        if p['temp'][0] <= telemetry['temp'] <= p['temp'][1]:
            reasons.append(f"Ideal ambient temperature range ({p['temp'][0]}-{p['temp'][1]}°C).")
        if p['ph'][0] <= telemetry['ph'] <= p['ph'][1]:
            reasons.append(f"Optimal soil pH balance ({p['ph'][0]}-{p['ph'][1]}).")
        if abs(telemetry['N'] - p['N']) < 30:
            reasons.append(f"Soil Nitrogen content matches nutrient intake profile.")
        if abs(telemetry['K'] - p['K']) < 40:
            reasons.append(f"Adequate Potassium reserve for root development.")

        if not reasons:
            reasons.append("Moderate match across environmental parameters.")

        return " ".join(reasons)

    def predict_top_crops(self, telemetry, top_n=3):
        """Predicts top N crops with probability scores, suitability %, and yields."""
        features = np.array([[
            telemetry['N'], telemetry['P'], telemetry['K'],
            telemetry['temp'], telemetry['hum'], telemetry['ph'], telemetry['moisture']
        ]])

        probs = self.model.predict_proba(features)[0]
        classes = self.model.classes_

        top_indices = np.argsort(probs)[::-1][:top_n]
        results = []

        for idx in top_indices:
            crop_name = classes[idx]
            model_prob = float(probs[idx])
            suitability_score = self.calculate_suitability_score(telemetry, crop_name)
            est_yield = self.crop_profiles[crop_name]['yield']
            rationale = self.generate_crop_rationale(telemetry, crop_name)

            results.append({
                'crop': crop_name,
                'model_confidence_pct': round(model_prob * 100, 1),
                'suitability_score_pct': suitability_score,
                'estimated_yield_tons_per_acre': est_yield,
                'rationale': rationale
            })

        return results

if __name__ == '__main__':
    engine = CropRecommendationEngine()
    sample_telemetry = {'N': 110, 'P': 55, 'K': 48, 'temp': 24.5, 'hum': 65.0, 'ph': 6.2, 'moisture': 55.0}
    recs = engine.predict_top_crops(sample_telemetry)
    print("\n--- SAMPLE CROP RECOMMENDATION OUTPUT ---")
    for r in recs:
        print(f"Crop: {r['crop']:<10} | Suitability: {r['suitability_score_pct']}% | Yield: {r['estimated_yield_tons_per_acre']} Tons/Acre")
        print(f"Rationale: {r['rationale']}\n")

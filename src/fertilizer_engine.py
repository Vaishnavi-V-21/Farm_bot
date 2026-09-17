"""
=====================================================================================
Project Title : Farm Bot: Intelligent Farming with Fertility & Crop Recommendation
File          : src/fertilizer_engine.py
Description   : Fertility improvement engine, Target Crop Goal Mode analyzer,
                chemical fertilizer dosage calculator (Urea, SSP, MOP), organic
                manure recommendations, pH amendments, and soil preparation schedule.
=====================================================================================
"""

import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from src.dataset_generator import CROP_DATASETS
except ModuleNotFoundError:
    from dataset_generator import CROP_DATASETS

# Commercial Fertilizer Factors
UREA_N_CONVERSION = 100.0 / 46.0   # 46% Nitrogen
SSP_P_CONVERSION  = 100.0 / 16.0   # 16% P2O5
MOP_K_CONVERSION  = 100.0 / 60.0   # 60% K2O

class FertilizerAndTargetCropEngine:
    def __init__(self):
        self.crop_db = CROP_DATASETS

    def calculate_fertilizer_dosages(self, current_n, current_p, current_k, target_n, target_p, target_k):
        """Calculates commercial chemical fertilizer dosages in kg/acre."""
        def_n = max(0.0, float(target_n - current_n))
        def_p = max(0.0, float(target_p - current_p))
        def_k = max(0.0, float(target_k - current_k))

        urea_kg = round(def_n * UREA_N_CONVERSION, 2)
        ssp_kg  = round(def_p * SSP_P_CONVERSION, 2)
        mop_kg  = round(def_k * MOP_K_CONVERSION, 2)

        return {
            'deficit_n_ppm': round(def_n, 1),
            'deficit_p_ppm': round(def_p, 1),
            'deficit_k_ppm': round(def_k, 1),
            'urea_kg_per_acre': urea_kg,
            'ssp_kg_per_acre': ssp_kg,
            'mop_kg_per_acre': mop_kg
        }

    def recommend_organic_alternatives(self, fert_result):
        """Recommends eco-friendly organic manures and bio-fertilizers."""
        organic = []
        if fert_result['urea_kg_per_acre'] > 0:
            vermi = round(fert_result['urea_kg_per_acre'] * 12.5, 1)
            organic.append(f"Vermicompost: Apply ~{vermi} kg/acre (Provides slow-release Organic Nitrogen & Humus).")
            organic.append("Azotobacter / Rhizobium Bio-fertilizer: 2 kg/acre seed packet treatment.")

        if fert_result['ssp_kg_per_acre'] > 0:
            fym = round(fert_result['ssp_kg_per_acre'] * 8.0, 1)
            organic.append(f"Farmyard Manure (FYM): Apply ~{fym} kg/acre well-decomposed cow dung.")
            organic.append("Phosphate Solubilizing Bacteria (PSB): 2 kg/acre soil application.")

        if fert_result['mop_kg_per_acre'] > 0:
            organic.append("Wood Ash / Neem Cake: 150 kg/acre to enrich Potassium and protect roots against pests.")

        return organic

    def evaluate_ph_amendments(self, current_ph, target_ph_range):
        """Recommends lime or gypsum/sulfur to adjust soil pH."""
        min_ph, max_ph = target_ph_range
        if current_ph < min_ph:
            diff = round(min_ph - current_ph, 2)
            lime_kg = round(diff * 200, 0)
            return {
                'ph_status': 'ACIDIC',
                'recommendation': f"Soil is Acidic (pH {current_ph}). Apply Agricultural Lime (Calcium Carbonate) ~{int(lime_kg)} kg/acre to raise pH.",
                'amendment_material': 'Agricultural Lime (CaCO3)'
            }
        elif current_ph > max_ph:
            diff = round(current_ph - max_ph, 2)
            gypsum_kg = round(diff * 250, 0)
            return {
                'ph_status': 'ALKALINE',
                'recommendation': f"Soil is Alkaline (pH {current_ph}). Apply Agricultural Gypsum / Elemental Sulfur ~{int(gypsum_kg)} kg/acre to lower pH.",
                'amendment_material': 'Gypsum (CaSO4.2H2O)'
            }
        else:
            return {
                'ph_status': 'OPTIMAL',
                'recommendation': f"Soil pH ({current_ph}) is within the optimal range ({min_ph} - {max_ph}). No amendment required.",
                'amendment_material': 'None'
            }

    def analyze_target_crop_goal(self, telemetry, target_crop):
        """Part 4: Comprehensive analysis for a farmer-selected target crop."""
        if target_crop not in self.crop_db:
            return {'status': 'ERROR', 'msg': f"Crop '{target_crop}' not in agronomic database."}

        target = self.crop_db[target_crop]

        # Calculate fertilizer deficit
        fert = self.calculate_fertilizer_dosages(
            telemetry['N'], telemetry['P'], telemetry['K'],
            target['N'], target['P'], target['K']
        )

        # Organic recommendations
        organic = self.recommend_organic_alternatives(fert)

        # pH Analysis
        ph_analysis = self.evaluate_ph_amendments(telemetry['ph'], target['ph'])

        # Suitability Assessment
        unsuitable_reasons = []
        if fert['urea_kg_per_acre'] > 50:
            unsuitable_reasons.append(f"High Nitrogen deficit (Requires {fert['urea_kg_per_acre']} kg Urea/acre).")
        if ph_analysis['ph_status'] != 'OPTIMAL':
            unsuitable_reasons.append(ph_analysis['recommendation'])
        if not (target['temp'][0] <= telemetry['temp'] <= target['temp'][1]):
            unsuitable_reasons.append(f"Current temp ({telemetry['temp']}°C) outside target window ({target['temp'][0]}-{target['temp'][1]}°C).")
        moist_val = telemetry.get('moisture', telemetry.get('moist', 0.0))
        if not (target['moist'][0] <= moist_val <= target['moist'][1]):
            unsuitable_reasons.append(f"Soil moisture ({moist_val}%) requires adjustment to target ({target['moist'][0]}-{target['moist'][1]}%).")

        is_currently_suitable = len(unsuitable_reasons) == 0

        # Estimated Preparation Time (Days)
        prep_days = 7
        if ph_analysis['ph_status'] != 'OPTIMAL':
            prep_days += 10
        if fert['urea_kg_per_acre'] > 40 or fert['ssp_kg_per_acre'] > 40:
            prep_days += 5

        return {
            'status': 'SUCCESS',
            'target_crop': target_crop,
            'is_currently_suitable': is_currently_suitable,
            'unsuitable_reasons': unsuitable_reasons if unsuitable_reasons else ["Soil conditions match target crop requirements."],
            'chemical_fertilizers': fert,
            'organic_alternatives': organic,
            'ph_analysis': ph_analysis,
            'ideal_ranges': {
                'moisture_pct': target['moist'],
                'temperature_c': target['temp'],
                'humidity_pct': target['hum'],
                'ph': target['ph']
            },
            'irrigation_schedule': f"Maintain moisture between {target['moist'][0]}% and {target['moist'][1]}%. Irrigate every 2-3 days.",
            'est_prep_time_days': prep_days
        }

if __name__ == '__main__':
    engine = FertilizerAndTargetCropEngine()
    telemetry = {'N': 40, 'P': 20, 'K': 30, 'temp': 28.0, 'hum': 60.0, 'ph': 5.2, 'moist': 30.0}
    res = engine.analyze_target_crop_goal(telemetry, 'Paddy')
    print("\n--- TARGET CROP ANALYSIS OUTPUT ---")
    print(res)

"""
Random Forest classifier for oil spill severity estimation.

Features:
    - Spill volume (barrels)
    - Wind speed (m/s)
    - Current speed (m/s)
    - Wave height (m)
    - Hours since spill
    - Water temperature (°C)
    - Spread area (km²)

Labels: low / moderate / high
"""

import logging
import os
from typing import Dict, Optional

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier

from backend.config import MODEL_PATH, SEVERITY_LABELS

logger = logging.getLogger(__name__)


class SpillClassifier:
    """Wrapper around a trained RandomForestClassifier for severity prediction."""

    FEATURE_NAMES = [
        "volume_barrels",
        "wind_speed",
        "current_speed",
        "wave_height",
        "hours_since_spill",
        "water_temperature",
        "spread_area_km2",
    ]

    def __init__(self, model_path: str = MODEL_PATH):
        self.model: Optional[RandomForestClassifier] = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        """Load the trained model from disk, or create a default one."""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info("Loaded severity classifier from %s", self.model_path)
                return
            except Exception as exc:
                logger.warning("Failed to load model: %s", exc)

        # Create and train a default model with synthetic data
        logger.info("No pre-trained model found — training default classifier")
        self._train_default()

    def _train_default(self):
        """Train a quick default classifier with synthetic data."""
        from backend.ml.train_model import generate_training_data, train_classifier
        X, y = generate_training_data(n_samples=2000)
        self.model = train_classifier(X, y)
        # Save for future use
        os.makedirs(os.path.dirname(self.model_path) or ".", exist_ok=True)
        joblib.dump(self.model, self.model_path)
        logger.info("Saved default model to %s", self.model_path)

    def predict(self, metadata: Dict) -> Dict:
        """
        Predict spill severity from metadata.

        Parameters
        ----------
        metadata : dict with keys matching FEATURE_NAMES.
                   Missing keys default to reasonable values.

        Returns
        -------
        dict with:
            severity   : str ('low', 'moderate', 'high')
            confidence : float (0-1)
            probabilities : dict mapping each label to its probability
            spread_rate_km2_hr : float (estimated from model + physics)
        """
        # Build feature vector with defaults
        defaults = {
            "volume_barrels": 1000,
            "wind_speed": 5.0,
            "current_speed": 0.3,
            "wave_height": 1.5,
            "hours_since_spill": 6,
            "water_temperature": 22.0,
            "spread_area_km2": 10.0,
        }

        features = []
        for name in self.FEATURE_NAMES:
            features.append(float(metadata.get(name, defaults[name])))

        X = np.array([features])

        # Predict
        prediction = self.model.predict(X)[0]
        probas = self.model.predict_proba(X)[0]

        severity = SEVERITY_LABELS[prediction]
        confidence = float(probas[prediction])

        prob_dict = {}
        for i, label in enumerate(SEVERITY_LABELS):
            prob_dict[label] = round(float(probas[i]), 4)

        # Estimate spread rate from features (empirical relation)
        vol = features[0]
        wind = features[1]
        current = features[2]
        spread_rate = 0.5 * (vol / 5000) ** 0.5 * (1 + wind / 10) * (1 + current / 0.5)
        spread_rate = round(spread_rate, 2)

        return {
            "severity": severity,
            "confidence": round(confidence, 4),
            "probabilities": prob_dict,
            "spread_rate_km2_hr": spread_rate,
        }


# Singleton classifier instance
_classifier: Optional[SpillClassifier] = None


def get_classifier() -> SpillClassifier:
    """Get or create the singleton classifier."""
    global _classifier
    if _classifier is None:
        _classifier = SpillClassifier()
    return _classifier

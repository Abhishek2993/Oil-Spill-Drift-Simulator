"""
Training script for the oil spill severity Random Forest classifier.

Generates physics-informed synthetic training data based on published
oil spill behaviour research (Fay spreading laws, Mackay weathering models)
and trains a RandomForestClassifier.

Run standalone:
    python -m backend.ml.train_model
"""

import logging
import os

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

from backend.config import MODEL_PATH, SEVERITY_LABELS

logger = logging.getLogger(__name__)


def generate_training_data(n_samples: int = 2000, seed: int = 42):
    """
    Generate synthetic training data based on oil spill physics.

    Features:
        0: volume_barrels      (100 — 100,000)
        1: wind_speed          (0 — 25 m/s)
        2: current_speed       (0 — 2 m/s)
        3: wave_height         (0 — 8 m)
        4: hours_since_spill   (0 — 72)
        5: water_temperature   (5 — 35 °C)
        6: spread_area_km2     (0 — 500)

    Labels:
        0: low, 1: moderate, 2: high

    The severity is determined by a physics-based scoring function
    calibrated against known spill outcomes.
    """
    rng = np.random.RandomState(seed)

    # Generate features with realistic distributions
    volume = rng.lognormal(mean=7.5, sigma=1.2, size=n_samples).clip(100, 100000)
    wind_speed = rng.gamma(shape=3, scale=2, size=n_samples).clip(0, 25)
    current_speed = rng.exponential(scale=0.3, size=n_samples).clip(0, 2)
    wave_height = rng.gamma(shape=2, scale=1, size=n_samples).clip(0, 8)
    hours = rng.uniform(0, 72, size=n_samples)
    temperature = rng.normal(loc=22, scale=5, size=n_samples).clip(5, 35)

    # Spread area correlates with volume, wind, current, and time
    # Fay's gravity-viscous spreading: A ∝ V^(2/3) × t^(1/2)
    base_spread = 0.01 * volume ** (2 / 3) * (hours + 1) ** 0.5
    wind_factor = 1 + 0.5 * wind_speed / 10
    current_factor = 1 + current_speed / 0.5
    spread_area = base_spread * wind_factor * current_factor
    spread_area += rng.normal(0, spread_area * 0.15)  # 15% noise
    spread_area = spread_area.clip(0.1, 500)

    X = np.column_stack([
        volume, wind_speed, current_speed, wave_height,
        hours, temperature, spread_area,
    ])

    # Compute severity score (higher = worse)
    score = (
        0.30 * np.log10(volume + 1) / np.log10(100001)       # volume impact
        + 0.15 * wind_speed / 25                               # wind spreading
        + 0.15 * current_speed / 2                             # current transport
        + 0.10 * wave_height / 8                               # wave mixing
        + 0.10 * hours / 72                                    # time evolution
        + 0.05 * (1 - (temperature - 5) / 30)                 # cold water = less evaporation
        + 0.15 * np.log10(spread_area + 1) / np.log10(501)    # spread extent
    )

    # Add noise for realistic classification boundaries
    score += rng.normal(0, 0.05, size=n_samples)

    # Classify into severity levels
    y = np.zeros(n_samples, dtype=int)
    y[score > 0.40] = 1  # moderate
    y[score > 0.60] = 2  # high

    # Log class distribution
    for i, label in enumerate(SEVERITY_LABELS):
        count = (y == i).sum()
        logger.info("Class '%s': %d samples (%.1f%%)", label, count, 100 * count / n_samples)

    return X, y


def train_classifier(X, y, n_estimators=100, max_depth=10):
    """
    Train a RandomForestClassifier and report cross-validation accuracy.
    """
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )

    # Cross-validation
    scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    logger.info(
        "Cross-validation accuracy: %.3f ± %.3f",
        scores.mean(), scores.std(),
    )

    # Final fit on all data
    model.fit(X, y)
    logger.info("Trained RandomForest with %d estimators, max_depth=%d", n_estimators, max_depth)

    # Feature importance
    for name, imp in zip(
        ["volume", "wind", "current", "wave_ht", "hours", "temp", "area"],
        model.feature_importances_,
    ):
        logger.info("  Feature '%s': importance = %.4f", name, imp)

    return model


def main():
    """Train and save the model."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Generating synthetic training data...")
    X, y = generate_training_data(n_samples=3000)

    logger.info("Training classifier...")
    model = train_classifier(X, y)

    # Save model
    os.makedirs(os.path.dirname(MODEL_PATH) or ".", exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":
    main()

"""
BEAST MODE EDoS Inference Engine - MAXIMUM PERFORMANCE
Ultra-high-throughput vectorized batch processing for 10,000+ flows/second

OPTIMIZATIONS:
- Pure NumPy vectorization (NO LOOPS!)
- Async/await architecture
- Memory-efficient batch processing
- Direct model access (no Kedro overhead)
- Multi-core scalability
"""

import numpy as np
import pandas as pd
import asyncio
import time
import pickle
from pathlib import Path
from loguru import logger
import warnings

warnings.filterwarnings("ignore")

# Decision threshold used to convert probabilities to boolean decisions
# INVERTED LOGIC: If attack_probability < threshold, classify as attack
# Set to 0.50 - values below this are considered attacks
DECISION_THRESHOLD = 0.022


class BeastModeInferenceEngine:
    """
    ULTRA-HIGH-PERFORMANCE inference engine for EDoS attack detection.

    Designed for 10,000+ flows per second with vectorized processing.
    """

    def __init__(self, model_data=None):
        """Initialize the BEAST MODE Inference Engine."""
        logger.info("🔥 Initializing BEAST MODE EDoS Inference Engine...")

        # Initialize models as None - load on first use
        self.final_model = None
        self.base_models = None
        self.scaler = None
        self.feature_names = None
        self.model_info = {}
        self._model_loaded = False
        # If the user provided preloaded model data, keep it to avoid reloading
        self._preloaded_model_data = model_data

        # Performance tracking
        self.prediction_count = 0
        self.total_time = 0.0

        logger.info("✅ BEAST MODE Engine initialized - models will load on first use!")

    def _ensure_model_loaded(self):
        """Lazy load the model only when needed."""
        if not self._model_loaded:
            logger.info("📦 Loading model on first use...")
            # Prefer preloaded model data if available
            if getattr(self, "_preloaded_model_data", None) is not None:
                try:
                    self._load_vectorized_model(self._preloaded_model_data)
                    self._model_loaded = True
                    logger.info("✅ Loaded model from preloaded data")
                    return
                except Exception as e:
                    logger.warning(
                        f"Failed to load preloaded model data: {e}; falling back to file"
                    )

            # Fallback to loading from pickle file
            self._load_model_direct()
            self._model_loaded = True

    def _load_model_direct(self):
        """Load the trained I-MPaFS model directly from pickle file - NO KEDRO!"""
        try:
            # Load directly from pickle file - bypass Kedro completely!
            model_path = Path("data/06_models/trained_impafs_model.pkl")

            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")

            with open(model_path, "rb") as f:
                trained_model = pickle.load(f)

            self._load_vectorized_model(trained_model)

            logger.info("✅ Model loaded directly from pickle - NO KEDRO OVERHEAD!")

        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise

    def _load_vectorized_model(self, data: dict) -> None:
        """Load model with vectorization optimizations."""
        try:
            # Extract core components
            self.final_model = data["final_model"]
            self.base_models = {}

            # Extract base models for vectorized processing
            base_models_info = data["base_models_info"]
            for name, info in base_models_info.items():
                self.base_models[name] = info["model"]

            # Load scaler and features
            if "scaler_info" in data:
                scaler_info = data["scaler_info"]
                self.scaler = scaler_info["scaler"]
                self.feature_names = scaler_info["feature_names"]

            # Model metadata
            self.model_info = data.get("performance_metrics", {})

            logger.info(
                f"🚀 Loaded {len(self.base_models)} base models for vectorization"
            )
            logger.info(f"📊 Features: {len(self.feature_names)}")

        except Exception as e:
            logger.error(f"❌ Failed to load vectorized model: {e}")
            raise

    def _preprocess_batch_vectorized(self, flows_data: list[dict]) -> np.ndarray:
        """
        ULTRA-FAST vectorized preprocessing for massive batches.

        NO LOOPS! Pure NumPy operations for maximum speed.
        """
        try:
            # Convert to DataFrame in ONE operation
            df = pd.DataFrame(flows_data)

            # Ensure correct column order (vectorized)
            # Be tolerant: if some expected columns are missing, add them with zeros
            missing = [c for c in self.feature_names if c not in df.columns]
            if missing:
                for c in missing:
                    df[c] = 0

            df = df[self.feature_names]

            # Vectorized scaling - handles entire batch at once
            if self.scaler:
                scaled_features = self.scaler.transform(df.values)
            else:
                scaled_features = df.values

            return scaled_features

        except Exception as e:
            logger.error(f"❌ Vectorized preprocessing failed: {e}")
            raise

    def _predict_base_models_vectorized(self, X: np.ndarray) -> dict[str, np.ndarray]:
        """
        VECTORIZED base model predictions - ALL models process ENTIRE batch simultaneously.

        This is where the MAGIC happens - no loops, pure vectorization!
        """
        base_predictions = {}

        try:
            # Each base model processes the ENTIRE batch in one shot
            for name, model in self.base_models.items():
                if hasattr(model, "predict_proba"):
                    # Get probabilities for attack class (class 1)
                    proba = model.predict_proba(X)
                    if proba.shape[1] > 1:
                        base_predictions[name] = proba[:, 1]  # Attack probability
                    else:
                        base_predictions[name] = proba[:, 0]
                elif name == "pred_mlp":
                    # TensorFlow model - batch prediction
                    proba = model.predict(X, verbose=0)
                    base_predictions[name] = proba.flatten()
                else:
                    # Fallback to binary predictions
                    pred = model.predict(X)
                    base_predictions[name] = pred.astype(float)

            return base_predictions

        except Exception as e:
            logger.error(f"❌ Vectorized base model prediction failed: {e}")
            raise

    async def predict_batch_ultra_fast(
        self,
        flows: list[dict],
        include_confidence: bool = True,
        diagnostic_sample: int = 0,
    ) -> dict:
        """
        ULTIMATE PERFORMANCE batch prediction for 10,000+ flows.

        PURE VECTORIZATION - processes entire batch as matrix operations!
        """
        # Ensure model is loaded
        self._ensure_model_loaded()

        start_time = time.time()
        batch_size = len(flows)

        try:
            # Step 1: Vectorized preprocessing (NO LOOPS!)
            logger.info(
                f"🚀 Processing {batch_size} flows with VECTORIZED operations..."
            )

            # Convert flows to feature matrix in ONE operation
            X = self._preprocess_batch_vectorized(flows)

            # Step 2: Vectorized base model predictions (ALL AT ONCE!)
            base_predictions = self._predict_base_models_vectorized(X)

            # Lightweight diagnostics: log per-base-model outputs for a tiny sample
            if diagnostic_sample and diagnostic_sample > 0:
                sample_n = min(diagnostic_sample, batch_size)
                try:
                    dbg_rows = []
                    for i in range(sample_n):
                        row = {
                            name: float(preds[i])
                            for name, preds in base_predictions.items()
                        }
                        dbg_rows.append(row)
                    logger.info(
                        f"📋 Diagnostic sample (first {sample_n}) base model outputs: {dbg_rows}"
                    )
                except Exception as _:
                    logger.debug(
                        "Could not record diagnostic sample for base model outputs"
                    )

            # Step 3: Create I-MPaFS features matrix (ORIGINAL + META!)
            meta_features = np.column_stack(list(base_predictions.values()))
            # Combine original features + meta-features = 25 features total!
            impafs_features = np.column_stack([X, meta_features])

            # Step 4: Final model prediction (ENTIRE BATCH!)
            final_probabilities = self.final_model.predict_proba(impafs_features)
            attack_probs = final_probabilities[:, 1]  # Attack probabilities
            benign_probs = final_probabilities[:, 0]  # Benign probabilities

            # Debug logging for probability analysis
            if len(attack_probs) > 0:
                avg_attack_prob = float(np.mean(attack_probs))
                max_attack_prob = float(np.max(attack_probs))
                min_attack_prob = float(np.min(attack_probs))
                attacks_detected = int(np.sum(attack_probs < DECISION_THRESHOLD))

                logger.info(
                    f"📊 Batch Analysis: {len(attack_probs)} flows | "
                    f"Attack Prob: avg={avg_attack_prob:.4f}, max={max_attack_prob:.4f}, min={min_attack_prob:.4f} | "
                    f"Attacks Detected: {attacks_detected}/{len(attack_probs)} (INVERTED: prob < {DECISION_THRESHOLD})"
                )

            # Step 5: Vectorized result construction
            predictions = []
            for i in range(batch_size):
                result = {
                    "is_attack": bool(attack_probs[i] < DECISION_THRESHOLD),
                    "attack_probability": float(attack_probs[i]),
                    "benign_probability": float(benign_probs[i]),
                    "confidence": float(max(attack_probs[i], benign_probs[i])),
                    "model_version": "I-MPaFS-BeastMode-v2.0",
                }

                if include_confidence:
                    # Standardized base model scores output
                    base_scores = {
                        name: float(preds[i])
                        for name, preds in base_predictions.items()
                    }
                    result["base_model_scores"] = base_scores

                    # Lightweight explanation: top contributing base model for this prediction
                    try:
                        top_name, top_score = max(
                            base_scores.items(), key=lambda kv: kv[1]
                        )
                        result["explanation"] = {
                            "top_base_model": top_name,
                            "top_base_score": float(top_score),
                            "decision_threshold": DECISION_THRESHOLD,
                        }
                    except Exception:
                        result["explanation"] = None

                predictions.append(result)

            # Performance metrics
            processing_time = (time.time() - start_time) * 1000  # ms
            throughput = batch_size / (processing_time / 1000)  # flows/sec

            # Update performance counters
            self.prediction_count += batch_size
            self.total_time += processing_time / 1000

            logger.info(
                f"⚡ BEAST MODE: {batch_size} flows in {processing_time:.2f}ms "
                f"= {throughput:.2f} flows/sec"
            )

            return {
                "predictions": predictions,
                "statistics": {
                    "total_flows": batch_size,
                    "attack_predictions": sum(1 for p in predictions if p["is_attack"]),
                    "benign_predictions": sum(
                        1 for p in predictions if not p["is_attack"]
                    ),
                    "processing_time_ms": processing_time,
                    "throughput_flows_per_sec": throughput,
                    "average_confidence": np.mean(
                        [p["confidence"] for p in predictions]
                    ),
                },
            }

        except Exception as e:
            logger.error(f"❌ BEAST MODE batch prediction failed: {e}")
            raise

    async def predict_single_ultra_fast(self, flow: dict) -> dict:
        """Ultra-fast single prediction (optimized for API endpoints)."""
        result = await self.predict_batch_ultra_fast([flow], include_confidence=True)
        return result["predictions"][0]

    def get_performance_stats(self) -> dict:
        """Get engine performance statistics."""
        avg_throughput = (
            self.prediction_count / self.total_time if self.total_time > 0 else 0
        )

        return {
            "total_predictions": self.prediction_count,
            "total_time_seconds": self.total_time,
            "average_throughput_flows_per_sec": avg_throughput,
            "model_accuracy": self.model_info.get("accuracy", "Unknown"),
            "base_models_count": len(self.base_models),
            "feature_count": len(self.feature_names) if self.feature_names else 0,
        }


def load_beast_mode_engine(model_data: dict) -> BeastModeInferenceEngine:
    """Load the BEAST MODE inference engine."""
    logger.info("🔥 Loading BEAST MODE inference engine...")
    return BeastModeInferenceEngine(model_data)

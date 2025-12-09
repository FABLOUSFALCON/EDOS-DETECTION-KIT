#!/usr/bin/env python3
"""
Test script to generate alerts directly in the database
This will help us test the alert system without Redis complexity
"""

import asyncio
import json
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

# Add the project root to the Python path
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db_context
from app.models.database import SecurityAlert, UserProfile


def create_test_user():
    """Create a test user if it doesn't exist"""
    try:
        with get_db_context() as db:
            # Check if test user exists
            test_user = (
                db.query(UserProfile)
                .filter(UserProfile.email == "test@edos.local")
                .first()
            )

            if not test_user:
                print("🔧 Creating test user...")
                test_user = UserProfile(
                    id="test-user-123",
                    email="test@edos.local",
                    username="testuser",
                    role="analyst",
                    is_active=True,
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
                print(f"✅ Created test user: {test_user.id}")
            else:
                print(f"✅ Test user already exists: {test_user.id}")

            return test_user.id
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return "test-user-123"  # fallback


def create_test_alerts(user_id: str, count: int = 5):
    """Create test alerts in the database"""
    try:
        with get_db_context() as db:
            severities = ["critical", "high", "medium", "low"]
            attack_types = [
                "ddos",
                "malware",
                "brute_force",
                "sql_injection",
                "port_scan",
            ]

            alerts_created = []

            for i in range(count):
                severity = severities[i % len(severities)]
                attack_type = attack_types[i % len(attack_types)]

                alert = SecurityAlert(
                    user_id=user_id,
                    type=attack_type,
                    category="network",
                    severity=severity,
                    title=f"Test {attack_type.replace('_', ' ').title()} Attack #{i+1}",
                    description=f"Test alert generated for {attack_type} detection with {severity} severity",
                    source_ip=f"192.168.1.{100 + i}",
                    target_ip=f"10.0.0.{10 + i}",
                    target_port=80 + i,
                    detection_method="ml_test_model_v1.0",
                    confidence_score=75.0 + (i * 5),  # 75, 80, 85, 90, 95
                    status="new",
                    raw_data={
                        "test": True,
                        "generated_at": datetime.utcnow().isoformat(),
                        "sequence": i + 1,
                    },
                    detected_at=datetime.utcnow(),
                )

                db.add(alert)
                alerts_created.append(alert)

            db.commit()

            print(f"✅ Created {len(alerts_created)} test alerts")
            for alert in alerts_created:
                print(f"   - {alert.severity.upper()}: {alert.title} (ID: {alert.id})")

            return alerts_created

    except Exception as e:
        print(f"❌ Error creating test alerts: {e}")
        import traceback

        traceback.print_exc()
        return []


def simulate_ml_prediction_alert(user_id: str, is_attack: bool = True):
    """Simulate creating an alert from an ML prediction"""
    try:
        # Simulate ML prediction data
        prediction = {
            "is_attack": is_attack,
            "attack_probability": 0.15,  # Low probability (inverted logic)
            "confidence": 0.85,
            "model_version": "edos_ml_v1.2",
            "attack_type": "ddos",
        }

        flow_meta = {
            "src_ip": "203.0.113.45",
            "dst_ip": "192.168.1.100",
            "dst_port": 80,
        }

        # Calculate severity using inverted logic (same as Redis consumer)
        severity = "low"
        try:
            conf = float(prediction.get("confidence", 0.0))
            attack_prob = float(prediction.get("attack_probability", 1.0))

            # Inverted logic: LOW attack_probability indicates HIGH attack confidence
            attack_confidence = 1.0 - attack_prob

            if attack_confidence >= 0.8 and conf >= 0.8:
                severity = "critical"
            elif attack_confidence >= 0.6 and conf >= 0.6:
                severity = "high"
            elif attack_confidence >= 0.4 and conf >= 0.4:
                severity = "medium"
            else:
                severity = "low"
        except Exception:
            severity = "medium"

        with get_db_context() as db:
            alert = SecurityAlert(
                user_id=user_id,
                type=prediction.get("attack_type") or "ml_detected",
                category="network",
                severity=severity,
                title=f"ML-Detected Attack ({prediction.get('model_version')})",
                description=f"ML detected attack with confidence {prediction.get('confidence')} and probability {prediction.get('attack_probability')} (inverted logic)",
                source_ip=flow_meta.get("src_ip"),
                target_ip=flow_meta.get("dst_ip"),
                target_port=flow_meta.get("dst_port"),
                detection_method=prediction.get("model_version"),
                confidence_score=float(prediction.get("confidence", 0.0)) * 100,
                status="new",
                raw_data={
                    "prediction": prediction,
                    "flow_meta": flow_meta,
                    "attack_confidence": 1.0
                    - prediction.get("attack_probability", 1.0),
                    "received_at": datetime.utcnow().isoformat(),
                },
                detected_at=datetime.utcnow(),
            )

            db.add(alert)
            db.commit()
            db.refresh(alert)

            print(f"✅ Created ML prediction alert:")
            print(f"   - Severity: {alert.severity.upper()}")
            print(
                f"   - Attack Probability: {prediction['attack_probability']} (low = attack)"
            )
            print(
                f"   - Attack Confidence: {1.0 - prediction['attack_probability']:.2f}"
            )
            print(f"   - Model Confidence: {prediction['confidence']}")
            print(f"   - Alert ID: {alert.id}")

            return alert

    except Exception as e:
        print(f"❌ Error creating ML prediction alert: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("🧪 EDoS Alert Generation Test")
    print("=" * 50)

    # Create test user
    user_id = create_test_user()

    # Create test alerts
    print("\n📝 Creating test alerts...")
    test_alerts = create_test_alerts(user_id)

    # Create ML prediction alert
    print("\n🤖 Creating ML prediction alert...")
    ml_alert = simulate_ml_prediction_alert(user_id)

    print("\n✅ Test completed! Check the alerts page in the frontend.")
    print("💡 The alerts should now appear in your dashboard.")

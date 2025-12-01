#!/usr/bin/env python3
"""
ML Integration Test Script
Demonstrates how to send ML predictions to the EDoS dashboard
"""

import requests
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_USER_TOKEN = "your_supabase_jwt_token"  # Replace with actual token

# Sample ML prediction data (matches your ML API schema)
sample_ml_prediction = {
    "resource_id": "resource_123",  # This would come from your resource mapping
    "source_ip": "192.168.1.100",
    "target_ip": "10.0.1.50",
    "flow_data": {
        "dst_port": 443,
        "flow_duration": 15.5,
        "tot_fwd_pkts": 25,
        "tot_bwd_pkts": 12,
        "fwd_pkt_len_max": 1500,
        "fwd_pkt_len_min": 60,
        "bwd_pkt_len_max": 1200,
        "bwd_pkt_len_mean": 850.5,
        "flow_byts_s": 1024.7,
        "flow_pkts_s": 2.4,
        "flow_iat_mean": 0.6,
        "flow_iat_std": 0.2,
        "flow_iat_max": 1.2,
        "fwd_iat_std": 0.1,
        "bwd_pkts_s": 0.8,
        "psh_flag_cnt": 5,
        "ack_flag_cnt": 15,
        "init_fwd_win_byts": 65535,
        "init_bwd_win_byts": 8192,
        "fwd_seg_size_min": 20,
    },
    "prediction": {
        "is_attack": True,
        "attack_probability": 0.87,
        "benign_probability": 0.13,
        "confidence": 0.92,
        "model_version": "I-MPaFS-BeastMode-v2.0",
        "base_model_scores": {"random_forest": 0.85, "svm": 0.89, "neural_net": 0.91},
        "explanation": {"top_features": ["flow_duration", "packet_rate", "port_443"]},
    },
}


def test_ml_integration():
    """Test the ML integration endpoint"""

    print("🤖 Testing ML Integration with EDoS Dashboard")
    print("=" * 50)

    # Headers for authentication
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_USER_TOKEN}",
    }

    try:
        # Test 1: Send single ML prediction
        print("📡 Sending ML prediction to dashboard...")
        response = requests.post(
            f"{API_BASE_URL}/api/alerts/ml-prediction",
            json=sample_ml_prediction,
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Alert created successfully!")
            print(f"   Alert ID: {result.get('alert_id')}")
            print(f"   Severity: {result.get('severity')}")
            print(f"   Confidence: {result.get('confidence'):.1%}")
            print(f"   Attack Type: {result.get('attack_type')}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print(
            "❌ Could not connect to API. Make sure the backend is running on port 8000"
        )
    except Exception as e:
        print(f"❌ Error: {e}")


def test_batch_predictions():
    """Test batch ML predictions"""

    print("\n🚀 Testing Batch ML Predictions")
    print("=" * 50)

    # Create multiple predictions
    batch_predictions = []
    for i in range(3):
        prediction = sample_ml_prediction.copy()
        prediction["source_ip"] = f"192.168.1.{100 + i}"
        prediction["flow_data"]["dst_port"] = 443 + i
        prediction["prediction"]["attack_probability"] = 0.8 + (i * 0.05)
        prediction["prediction"]["confidence"] = 0.85 + (i * 0.05)
        batch_predictions.append(prediction)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_USER_TOKEN}",
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/alerts/batch-ml-predictions",
            json=batch_predictions,
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Batch alerts created successfully!")
            print(f"   Total Predictions: {result.get('total_predictions')}")
            print(f"   Attack Predictions: {result.get('attack_predictions')}")
            print(f"   Alerts Created: {result.get('alerts_created')}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print(
            "❌ Could not connect to API. Make sure the backend is running on port 8000"
        )
    except Exception as e:
        print(f"❌ Error: {e}")


def simulate_ml_service():
    """Simulate a continuous ML service sending predictions"""

    print("\n🔄 Simulating Continuous ML Service")
    print("=" * 50)

    import time
    import random

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_USER_TOKEN}",
    }

    attack_types = [
        {"port": 80, "attack_prob": 0.85, "confidence": 0.92},
        {"port": 443, "attack_prob": 0.78, "confidence": 0.88},
        {"port": 22, "attack_prob": 0.95, "confidence": 0.97},
        {"port": 25, "attack_prob": 0.72, "confidence": 0.84},
    ]

    print("Sending ML predictions every 5 seconds (press Ctrl+C to stop)...")

    try:
        for i in range(5):  # Send 5 predictions
            attack = random.choice(attack_types)

            prediction = sample_ml_prediction.copy()
            prediction["source_ip"] = f"192.168.1.{random.randint(1, 254)}"
            prediction["flow_data"]["dst_port"] = attack["port"]
            prediction["prediction"]["attack_probability"] = attack["attack_prob"]
            prediction["prediction"]["confidence"] = attack["confidence"]
            prediction["prediction"]["is_attack"] = random.choice(
                [True, True, False]
            )  # 66% attacks

            response = requests.post(
                f"{API_BASE_URL}/api/alerts/ml-prediction",
                json=prediction,
                headers=headers,
            )

            if response.status_code == 200:
                result = response.json()
                if "alert_id" in result:
                    print(
                        f"⚠️  Alert #{i+1}: {result.get('attack_type')} (confidence: {result.get('confidence'):.1%})"
                    )
                else:
                    print(f"ℹ️  Prediction #{i+1}: No attack detected")
            else:
                print(f"❌ Error #{i+1}: {response.status_code}")

            time.sleep(2)  # Wait 2 seconds between predictions

    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped")
    except requests.exceptions.ConnectionError:
        print("❌ Lost connection to API")
    except Exception as e:
        print(f"❌ Simulation error: {e}")


def show_integration_info():
    """Show information about the ML integration"""

    print("🔗 EDoS ML Integration Information")
    print("=" * 50)
    print()
    print("📋 INTEGRATION ENDPOINTS:")
    print("   POST /api/alerts/ml-prediction        - Single ML prediction")
    print("   POST /api/alerts/batch-ml-predictions - Batch ML predictions")
    print()
    print("🗃️  DATABASE COMPATIBILITY:")
    print("   ✅ user_id - Multi-tenant isolation")
    print("   ✅ resource_id - Link to infrastructure")
    print("   ✅ confidence_score - ML confidence (0-100%)")
    print("   ✅ detection_method - ML model version")
    print("   ✅ raw_data - Complete ML prediction data")
    print("   ✅ source_ip, target_port - Network details")
    print()
    print("📡 REAL-TIME FEATURES:")
    print("   ✅ WebSocket broadcasting to user channels")
    print("   ✅ General alerts channel broadcast")
    print("   ✅ Background task processing")
    print()
    print("🎯 ATTACK CLASSIFICATION:")
    print("   • Port-based: web_attack, ssh_attack, dns_attack")
    print("   • Flow-based: ddos, persistent_threat, data_exfiltration")
    print()
    print("⚡ SEVERITY CALCULATION:")
    print("   • Critical: confidence ≥ 90% AND attack_prob ≥ 80%")
    print("   • High: confidence ≥ 80% AND attack_prob ≥ 60%")
    print("   • Medium: confidence ≥ 60% AND attack_prob ≥ 40%")
    print("   • Low: below medium thresholds")


if __name__ == "__main__":
    print("🛡️  EDoS Security Dashboard - ML Integration Test")
    print("=" * 60)

    # Show integration information
    show_integration_info()

    print("\n" + "=" * 60)
    print("⚠️  NOTE: Update TEST_USER_TOKEN with a valid Supabase JWT token")
    print("   before running the tests!")
    print("=" * 60)

    # Uncomment to run tests (need valid auth token)
    # test_ml_integration()
    # test_batch_predictions()
    # simulate_ml_service()

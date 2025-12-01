"""
ML Integration Strategy for EDoS Security Dashboard

This file demonstrates how ML predictions can be integrated with your existing SecurityAlert database schema.
Your current schema is perfect for ML integration!

INTEGRATION APPROACH:
==================

1. RESOURCE IDENTIFICATION:
   Since ML API doesn't provide user_id/resource_id, we need to:
   - Add a resource_mapping service
   - Use IP address or other identifiers to map predictions to user resources
   - Create API endpoints that accept resource context with predictions

2. PERFECT DATABASE COMPATIBILITY:
   ✅ user_id - for multi-tenancy isolation
   ✅ resource_id - link alerts to specific infrastructure
   ✅ confidence_score - store ML confidence (0-100)
   ✅ detection_method - mark as ML-generated
   ✅ raw_data - JSONB field for complete ML prediction data
   ✅ source_ip, target_ip, target_port - network flow details

3. ALERT CREATION PIPELINE:
   ML Prediction → Resource Mapping → SecurityAlert → WebSocket Broadcast
"""

from pydantic import BaseModel, Field
from app.utils.pydantic_compat import model_to_dict
from typing import Dict, Any, List, Optional
from datetime import datetime

# ================================
# ML API INTEGRATION SCHEMAS
# ================================


class NetworkFlowInput(BaseModel):
    """Input schema matching your ML API"""

    dst_port: int
    flow_duration: float
    tot_fwd_pkts: int
    tot_bwd_pkts: int
    fwd_pkt_len_max: int
    fwd_pkt_len_min: int
    bwd_pkt_len_max: int
    bwd_pkt_len_mean: float
    flow_byts_s: float
    flow_pkts_s: float
    flow_iat_mean: float
    flow_iat_std: float
    flow_iat_max: float
    fwd_iat_std: float
    bwd_pkts_s: float
    psh_flag_cnt: int
    ack_flag_cnt: int
    init_fwd_win_byts: int
    init_bwd_win_byts: int
    fwd_seg_size_min: int


class MLPredictionOutput(BaseModel):
    """Output schema matching your ML API"""

    is_attack: bool
    attack_probability: float
    benign_probability: float
    confidence: float
    model_version: str
    base_model_scores: Optional[Dict[str, float]] = None
    explanation: Optional[Dict[str, Any]] = None


class AlertCreationRequest(BaseModel):
    """Request to create alerts from ML predictions with resource context"""

    resource_id: str = Field(description="User's resource ID from database")
    source_ip: str = Field(description="Source IP from network monitoring")
    target_ip: Optional[str] = Field(
        default=None, description="Target IP (resource IP)"
    )
    flow_data: NetworkFlowInput
    ml_prediction: MLPredictionOutput


# ================================
# INTEGRATION STRATEGY FUNCTIONS
# ================================


def create_alert_from_ml_prediction(
    user_id: str,
    resource_id: str,
    source_ip: str,
    flow_data: NetworkFlowInput,
    prediction: MLPredictionOutput,
) -> dict:
    """
    Strategy for converting ML predictions to SecurityAlert data
    This shows how to map ML outputs to your database schema
    """

    # Only create alerts for detected attacks
    if not prediction.is_attack:
        return None

    # Calculate severity based on ML confidence and attack probability
    severity = calculate_severity(prediction.confidence, prediction.attack_probability)

    # Determine attack type from network characteristics
    attack_type = determine_attack_type(flow_data.dst_port, flow_data, prediction)

    # Create SecurityAlert data structure
    alert_data = {
        "user_id": user_id,
        "resource_id": resource_id,
        "type": attack_type,
        "category": "network",
        "severity": severity,
        "title": f"ML-Detected {attack_type.replace('_', ' ').title()} Attack",
        "description": generate_alert_description(source_ip, prediction, flow_data),
        "source_ip": source_ip,
        "target_port": flow_data.dst_port,
        "detection_method": prediction.model_version,
        "confidence_score": prediction.confidence * 100,  # Convert to percentage
        "status": "new",
        "raw_data": {
            "ml_prediction": model_to_dict(prediction),
            "flow_data": model_to_dict(flow_data),
            "processed_at": datetime.utcnow().isoformat(),
            "model_scores": prediction.base_model_scores,
            "explanation": prediction.explanation,
        },
        "detected_at": datetime.utcnow(),
    }

    return alert_data


def calculate_severity(confidence: float, attack_probability: float) -> str:
    """
    Calculate alert severity based on ML metrics
    """
    if confidence >= 0.9 and attack_probability >= 0.8:
        return "critical"
    elif confidence >= 0.8 and attack_probability >= 0.6:
        return "high"
    elif confidence >= 0.6 and attack_probability >= 0.4:
        return "medium"
    else:
        return "low"


def determine_attack_type(
    dst_port: int, flow_data: NetworkFlowInput, prediction: MLPredictionOutput
) -> str:
    """
    Determine attack type from network flow characteristics
    """
    # Port-based classification
    if dst_port in [80, 443, 8080, 8443]:
        return "web_attack"
    elif dst_port in [22, 2222]:
        return "ssh_attack"
    elif dst_port in [21]:
        return "ftp_attack"
    elif dst_port in [53]:
        return "dns_attack"
    elif dst_port in [25, 587, 465]:
        return "email_attack"

    # Flow-based classification
    packet_rate = flow_data.flow_pkts_s
    flow_duration = flow_data.flow_duration

    if packet_rate > 100:
        return "ddos"
    elif flow_duration > 300:
        return "persistent_threat"
    elif flow_data.psh_flag_cnt > 10:
        return "data_exfiltration"
    else:
        return "network_intrusion"


def generate_alert_description(
    source_ip: str, prediction: MLPredictionOutput, flow_data: NetworkFlowInput
) -> str:
    """
    Generate human-readable alert description
    """
    return (
        f"Machine learning model detected suspicious network activity from {source_ip} "
        f"targeting port {flow_data.dst_port}. "
        f"Confidence: {prediction.confidence:.1%}, "
        f"Attack Probability: {prediction.attack_probability:.1%}. "
        f"Flow characteristics: {flow_data.tot_fwd_pkts} forward packets, "
        f"{flow_data.flow_duration:.1f}s duration."
    )


# ================================
# RESOURCE MAPPING STRATEGY
# ================================


def map_ip_to_user_resource(target_ip: str, source_ip: str = None) -> dict:
    """
    Strategy for mapping network flows to user resources
    You would implement this based on your infrastructure data
    """
    # Example mapping logic:
    # 1. Query user_resources table for matching public_ip or private_ip
    # 2. Use network topology to identify which resource is being targeted
    # 3. Return user_id and resource_id for alert creation

    # This is where you'd query your database:
    # resource = db.query(UserResource).filter(
    #     or_(UserResource.public_ip == target_ip, UserResource.private_ip == target_ip)
    # ).first()

    return {
        "user_id": "user_123",  # Replace with actual lookup
        "resource_id": "resource_456",  # Replace with actual lookup
        "resource_name": "Web Server",
        "resource_type": "ec2_instance",
    }


# ================================
# WEBSOCKET BROADCAST STRATEGY
# ================================


def create_websocket_alert_message(alert_data: dict) -> dict:
    """
    Create WebSocket message for real-time alerts
    """
    return {
        "type": "new_alert",
        "data": {
            "alert_id": alert_data["id"] if "id" in alert_data else "pending",
            "severity": alert_data["severity"],
            "title": alert_data["title"],
            "description": (
                alert_data["description"][:200] + "..."
                if len(alert_data["description"]) > 200
                else alert_data["description"]
            ),
            "source_ip": alert_data["source_ip"],
            "target_port": alert_data["target_port"],
            "confidence": alert_data["confidence_score"],
            "detected_at": (
                alert_data["detected_at"].isoformat()
                if isinstance(alert_data["detected_at"], datetime)
                else alert_data["detected_at"]
            ),
            "attack_type": alert_data["type"],
            "status": alert_data["status"],
        },
    }


# ================================
# IMPLEMENTATION EXAMPLE
# ================================


def process_ml_prediction_example():
    """
    Complete example of processing an ML prediction into a database alert
    """

    # 1. Receive ML prediction from your model
    flow_input = NetworkFlowInput(
        dst_port=443,
        flow_duration=15.5,
        tot_fwd_pkts=25,
        tot_bwd_pkts=12,
        fwd_pkt_len_max=1500,
        fwd_pkt_len_min=60,
        bwd_pkt_len_max=1200,
        bwd_pkt_len_mean=850.5,
        flow_byts_s=1024.7,
        flow_pkts_s=2.4,
        flow_iat_mean=0.6,
        flow_iat_std=0.2,
        flow_iat_max=1.2,
        fwd_iat_std=0.1,
        bwd_pkts_s=0.8,
        psh_flag_cnt=5,
        ack_flag_cnt=15,
        init_fwd_win_byts=65535,
        init_bwd_win_byts=8192,
        fwd_seg_size_min=20,
    )

    ml_prediction = MLPredictionOutput(
        is_attack=True,
        attack_probability=0.87,
        benign_probability=0.13,
        confidence=0.92,
        model_version="I-MPaFS-BeastMode-v2.0",
        base_model_scores={"random_forest": 0.85, "svm": 0.89, "neural_net": 0.91},
        explanation={"top_features": ["flow_duration", "packet_rate", "port_443"]},
    )

    # 2. Map to user resource
    source_ip = "192.168.1.100"
    target_ip = "10.0.1.50"
    resource_mapping = map_ip_to_user_resource(target_ip, source_ip)

    # 3. Create alert data
    alert_data = create_alert_from_ml_prediction(
        user_id=resource_mapping["user_id"],
        resource_id=resource_mapping["resource_id"],
        source_ip=source_ip,
        flow_data=flow_input,
        prediction=ml_prediction,
    )

    # 4. Create WebSocket message
    ws_message = create_websocket_alert_message(alert_data)

    return alert_data, ws_message


if __name__ == "__main__":
    # Example execution
    alert_data, ws_message = process_ml_prediction_example()
    print("Alert Data:", alert_data)
    print("WebSocket Message:", ws_message)

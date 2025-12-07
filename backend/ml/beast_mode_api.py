"""
BEAST MODE FastAPI Server - MAXIMUM THROUGHPUT
Ultra-high-performance async API for 10,000+ flows/second

OPTIMIZATIONS:
"""

# Imports and runtime dependencies
from fastapi import (
    FastAPI,
    HTTPException,
    status,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn
import asyncio
import time
import pickle
from datetime import datetime
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys

# Ensure the repository `backend/` directory is on sys.path so sibling
# package `app` can be imported when this module is executed directly
# (e.g. via `uvicorn beast_mode_api:app`). Insert before importing `app`.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from beast_mode_inference import BeastModeInferenceEngine
from app.utils.pydantic_compat import model_to_dict
from collections import deque
import asyncio

# Redis publisher for predictions (minimal metadata only)
from publisher import publish_prediction, publish_batch_results


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global BEAST MODE engine
beast_engine = None

# ===================================================================
# BUFFERED FLOW PROCESSING - CICFLOWMETER INTEGRATION
# ===================================================================


# Buffering configuration
BUFFER_SIZE = 500  # Optimal batch size for vectorized processing
MAX_WAIT_TIME = (
    5.0  # Max seconds to wait before processing partial batch (increased per request)
)
MAX_BUFFER_CAPACITY = 2000  # Prevent memory overflow
# Threat level thresholds (named constants for clarity)
THREAT_CRITICAL_PCT = 75.0
THREAT_HIGH_PCT = 50.0
THREAT_MEDIUM_PCT = 25.0
THREAT_LOW_PCT = 10.0

# Thread-safe flow buffer and statistics
flow_buffer = deque()
buffer_lock = None  # created at startup as asyncio.Lock()
buffer_stats = {
    "total_flows_received": 0,
    "total_batches_processed": 0,
    "total_attacks_detected": 0,
    "last_batch_attack_rate": 0.0,
    "current_threat_level": "LOW",
    "start_time": time.time(),
    "last_flush_time": time.time(),
}

# ===================================================================
# PYDANTIC MODELS FOR ULTRA-FAST SERIALIZATION
# ===================================================================


class NetworkFlow(BaseModel):
    """Ultra-fast network flow model with minimal overhead."""

    # All model input fields are REQUIRED — missing values should raise validation errors.
    dst_port: float = Field(..., alias="dst_port")
    flow_duration: float = Field(..., alias="flow_duration")
    tot_fwd_pkts: float = Field(..., alias="tot_fwd_pkts")
    tot_bwd_pkts: float = Field(..., alias="tot_bwd_pkts")
    fwd_pkt_len_max: float = Field(..., alias="fwd_pkt_len_max")
    fwd_pkt_len_min: float = Field(..., alias="fwd_pkt_len_min")
    bwd_pkt_len_max: float = Field(..., alias="bwd_pkt_len_max")
    bwd_pkt_len_mean: float = Field(..., alias="bwd_pkt_len_mean")
    flow_byts_s: float = Field(..., alias="flow_byts_s")
    flow_pkts_s: float = Field(..., alias="flow_pkts_s")
    flow_iat_mean: float = Field(..., alias="flow_iat_mean")
    flow_iat_std: float = Field(..., alias="flow_iat_std")
    flow_iat_max: float = Field(..., alias="flow_iat_max")
    fwd_iat_std: float = Field(..., alias="fwd_iat_std")
    bwd_pkts_s: float = Field(..., alias="bwd_pkts_s")
    psh_flag_cnt: float = Field(..., alias="psh_flag_cnt")
    ack_flag_cnt: float = Field(..., alias="ack_flag_cnt")
    init_fwd_win_byts: float = Field(..., alias="init_fwd_win_byts")
    init_bwd_win_byts: float = Field(..., alias="init_bwd_win_byts")
    fwd_seg_size_min: float = Field(..., alias="fwd_seg_size_min")

    class Config:
        populate_by_name = True
        extra = "allow"


class SinglePredictionRequest(BaseModel):
    """Payload for a single prediction request that includes required routing metadata."""

    flow: NetworkFlow
    client_id: str = Field(..., description="Client identifier (required)")
    resource_id: str = Field(..., description="Resource identifier (required)")
    timestamp: str | None = Field(
        None, description="Optional ISO8601 timestamp for the flow"
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "flow": {
                    "dst_port": 443,
                    "flow_duration": 120.5,
                    "tot_fwd_pkts": 10,
                    "tot_bwd_pkts": 2,
                    "fwd_pkt_len_max": 1500,
                    "fwd_pkt_len_min": 60,
                    "bwd_pkt_len_max": 1448,
                    "bwd_pkt_len_mean": 512,
                    "flow_byts_s": 1000.0,
                    "flow_pkts_s": 50.0,
                    "flow_iat_mean": 0.02,
                    "flow_iat_std": 0.01,
                    "flow_iat_max": 0.1,
                    "fwd_iat_std": 0.005,
                    "bwd_pkts_s": 5.0,
                    "psh_flag_cnt": 0,
                    "ack_flag_cnt": 1,
                    "init_fwd_win_byts": 65535,
                    "init_bwd_win_byts": 8192,
                    "fwd_seg_size_min": 0,
                    "timestamp": "2025-11-21T00:00:00Z",
                    "src_ip": "192.0.2.10",
                    "dst_ip": "198.51.100.5",
                    "src_port": 52341,
                    "protocol": "TCP",
                },
                "client_id": "demo-client-0001",
                "resource_id": "demo-resource-0001",
                "timestamp": "2025-11-21T00:00:00Z",
            }
        }


class BatchPredictionRequest(BaseModel):
    """Batch prediction payload containing multiple network flows."""

    flows: list[NetworkFlow] = Field(
        ..., description="Network flows for batch processing"
    )
    include_confidence: bool = Field(True, description="Include confidence metrics")
    client_id: str = Field(..., description="Client identifier (required)")
    resource_id: str = Field(..., description="Resource identifier (required)")

    class Config:
        json_schema_extra = {
            "example": {
                "flows": [
                    {
                        "dst_port": 443,
                        "flow_duration": 120.5,
                        "tot_fwd_pkts": 10,
                        "tot_bwd_pkts": 2,
                        "fwd_pkt_len_max": 1500,
                        "fwd_pkt_len_min": 60,
                        "bwd_pkt_len_max": 1448,
                        "bwd_pkt_len_mean": 512,
                        "flow_byts_s": 1000.0,
                        "flow_pkts_s": 50.0,
                        "flow_iat_mean": 0.02,
                        "flow_iat_std": 0.01,
                        "flow_iat_max": 0.1,
                        "fwd_iat_std": 0.005,
                        "bwd_pkts_s": 5.0,
                        "psh_flag_cnt": 0,
                        "ack_flag_cnt": 1,
                        "init_fwd_win_byts": 65535,
                        "init_bwd_win_byts": 8192,
                        "fwd_seg_size_min": 0,
                        "timestamp": "2025-11-21T00:00:00Z",
                        "src_ip": "192.0.2.10",
                        "dst_ip": "198.51.100.5",
                        "src_port": 52341,
                        "protocol": "TCP",
                    }
                ],
                "include_confidence": True,
                "client_id": "demo-client-0001",
                "resource_id": "demo-resource-0001",
            }
        }


class PredictionDetail(BaseModel):
    """Detailed prediction returned for each flow."""

    is_attack: bool
    attack_probability: float
    benign_probability: float
    confidence: float
    model_version: str
    base_model_scores: Optional[dict[str, float]] = None
    explanation: Optional[dict[str, object]] = None


class BatchPredictionResponse(BaseModel):
    """Batch prediction response."""

    predictions: list[PredictionDetail]
    statistics: dict[str, object]


# ===================================================================
# BEAST MODE FASTAPI APPLICATION
# ===================================================================


async def background_buffer_monitor():
    """Background task to monitor and flush buffer automatically"""
    while True:
        try:
            await asyncio.sleep(MAX_WAIT_TIME)  # Check every MAX_WAIT_TIME seconds

            async with buffer_lock:
                buffer_size = len(flow_buffer)
                time_since_flush = time.time() - buffer_stats["last_flush_time"]

            # Auto-flush if buffer has flows and timeout reached
            if buffer_size > 0 and time_since_flush >= MAX_WAIT_TIME:
                logger.info(f"🔄 Auto-flushing {buffer_size} flows (timeout reached)")
                await process_buffer_batch()

        except Exception as e:
            logger.error(f"❌ Background monitor error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ULTRA-FAST application lifecycle with background buffer monitoring."""
    # Startup
    logger.info(
        "🔥 Starting BEAST MODE EDoS Attack Detection API with Buffered Processing..."
    )

    global beast_engine

    try:
        # DIRECT model loading - bypass Kedro overhead completely!
        logger.info("⚡ Loading model DIRECTLY for maximum performance...")

        model_path = Path("data/06_models/trained_impafs_model.pkl")

        with open(model_path, "rb") as f:
            model_data = pickle.load(f)

        # Initialize BEAST MODE engine
        beast_engine = BeastModeInferenceEngine(model_data)

        # Create asyncio lock for buffer protection
        global buffer_lock
        buffer_lock = asyncio.Lock()
        # Create asyncio lock for live websocket clients
        global live_clients_lock
        live_clients_lock = asyncio.Lock()

        # Runtime sanity check: validate conversion mapping matches model feature names
        try:
            expected = None
            if isinstance(model_data, dict):
                si = model_data.get("scaler_info") or {}
                expected = si.get("feature_names")
            if expected is None:
                expected = getattr(beast_engine, "feature_names", None)
            if expected:
                expected_set = set(expected)
                # Build a sample cicflow dict with all cic keys present
                sample_cic = {k: 0 for k in CICFLOW_FIELD_MAPPING.keys()}
                converted = convert_cicflow_to_beast_format(sample_cic)
                converted_set = set(converted.keys())
                if expected_set != converted_set:
                    logger.error(
                        "❌ Feature mapping mismatch between CICFlow conversion and model features"
                    )
                    logger.error(f"Expected: {sorted(expected_set)}")
                    logger.error(f"Converted: {sorted(converted_set)}")
                    raise RuntimeError(
                        "Feature mapping mismatch; check CICFLOW_FIELD_MAPPING"
                    )
                # store for runtime validation
                app.state.expected_feature_set = expected_set
        except Exception as e:
            logger.error(f"❌ Runtime sanity check failed: {e}")
            raise

        logger.info("🚀 BEAST MODE engine loaded - READY FOR MAXIMUM THROUGHPUT!")

        # Start background buffer monitoring task (keep handle to cancel on shutdown)
        logger.info("🔄 Starting background buffer monitoring...")
        bg_task = asyncio.create_task(background_buffer_monitor())
        app.state._background_buffer_task = bg_task

    except Exception as e:
        logger.error(f"❌ Failed to load BEAST MODE engine: {e}")
        raise

    # Record startup time
    app.state.startup_time = datetime.now()
    logger.info("✅ BEAST MODE API with Buffered Processing is READY!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down BEAST MODE API...")
    # Cancel background task if running
    try:
        task = getattr(app.state, "_background_buffer_task", None)
        if task is not None:
            task.cancel()
    except Exception:
        pass

    beast_engine = None


# Create BEAST MODE FastAPI app
app = FastAPI(
    title="BEAST MODE EDoS Attack Detection System",
    description="Ultra-high-performance network flow attack detection - 10,000+ flows/second",
    version="2.0.0-BeastMode",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================================================================
# BEAST MODE API ENDPOINTS
# ===================================================================

# Connected WebSocket clients for live predictions
connected_live_clients: set[WebSocket] = set()
live_clients_lock = None


async def broadcast_to_live_clients(message: dict):
    """Broadcast a JSON-serializable message to all connected live clients."""
    to_remove: list[WebSocket] = []
    async with live_clients_lock:
        for ws in list(connected_live_clients):
            try:
                await ws.send_json(message)
            except Exception:
                to_remove.append(ws)

        for ws in to_remove:
            try:
                connected_live_clients.remove(ws)
            except KeyError:
                pass


@app.websocket("/ws/live")
async def websocket_live_endpoint(ws: WebSocket):
    """WebSocket endpoint that streams raw ML predictions to connected clients.

    Frontend Live Monitor pages should connect here (e.g. ws://<ml-host>:23333/ws/live)
    """
    await ws.accept()
    async with live_clients_lock:
        connected_live_clients.add(ws)

    try:
        while True:
            # Keep connection open and optionally accept pings from client
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # ignore other receive errors; continue
                await asyncio.sleep(0.1)
    finally:
        async with live_clients_lock:
            if ws in connected_live_clients:
                connected_live_clients.remove(ws)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page for the BEAST MODE API - polished, interactive, and informative."""
    html = """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width,initial-scale=1" />
            <title>BEAST MODE — EDoS Attack Detection</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, 'Roboto Mono', 'Segoe UI Mono', monospace; }
            </style>
        </head>
        <body class="bg-slate-50 text-slate-900">
            <!-- NAVBAR -->
            <nav class="bg-white shadow-md">
                <div class="max-w-7xl mx-auto px-6">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center gap-4">
                            <div class="text-teal-600 bg-teal-50 rounded-full p-2">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12h18M3 6h18M3 18h18"/></svg>
                            </div>
                            <div>
                                <a href="/" class="text-lg font-bold text-slate-800">BEAST MODE</a>
                                <div class="text-xs text-slate-500">EDoS Detection — I-MPaFS</div>
                            </div>
                        </div>
                        <div class="hidden md:flex items-center gap-6">
                            <a href="/docs" class="text-sm text-slate-700 hover:text-teal-600 transition">Docs</a>
                            <a href="/health" class="text-sm text-slate-700 hover:text-teal-600 transition">Health</a>
                            <a href="/performance" class="text-sm text-slate-700 hover:text-teal-600 transition">Performance</a>
                            <a href="/buffer-stats" class="text-sm text-slate-700 hover:text-teal-600 transition">Buffer Stats</a>
                        </div>
                    </div>
                </div>
            </nav>

            <!-- HERO -->
            <header class="max-w-7xl mx-auto px-6 py-10">
                <div class="bg-gradient-to-r from-slate-50 to-white p-8 rounded-2xl shadow-sm">
                    <h1 class="text-4xl font-extrabold text-slate-900">BEAST MODE — EDoS Attack Detection</h1>
                    <p class="mt-3 text-slate-600">High-throughput flow-based detection with vectorized inference and buffered CICFlowMeter ingestion. Production-ready, explainable outputs.</p>
                </div>
            </header>

            <main class="max-w-7xl mx-auto px-6 pb-12">
                <section class="grid md:grid-cols-3 gap-6">
                    <div class="bg-white p-6 rounded-xl shadow">
                        <h3 class="text-lg font-semibold">Overview</h3>
                        <p class="mt-2 text-sm text-slate-600">BEAST MODE uses an I-MPaFS ensemble: base-model scores are combined with original features to produce robust attack detection. Use the API endpoints for single, batch, and buffered predictions.</p>
                        <ul class="mt-3 text-sm text-slate-600 space-y-1">
                            <li>• Vectorized batch inference</li>
                            <li>• Buffered ingestion with threat scoring</li>
                            <li>• Per-flow explanation (top base model)</li>
                        </ul>
                    </div>

                    <div class="bg-white p-6 rounded-xl shadow">
                        <h3 class="text-lg font-semibold">Quick Links</h3>
                        <div class="mt-3 flex flex-col gap-2 text-sm">
                            <a href="/docs" class="text-teal-600 hover:underline">API Docs (OpenAPI)</a>
                            <a href="/health" class="text-teal-600 hover:underline">Health</a>
                            <a href="/performance" class="text-teal-600 hover:underline">Performance</a>
                            <a href="/buffer-stats" class="text-teal-600 hover:underline">Buffer Stats</a>
                        </div>
                    </div>

                    <div class="bg-white p-6 rounded-xl shadow">
                        <h3 class="text-lg font-semibold">How to Use</h3>
                        <p class="mt-2 text-sm text-slate-600">Recommended flow: send CICFlowMeter flows to <code class="mono">/predict/buffered</code> for high-throughput environments, or POST batches to <code class="mono">/predict/batch</code> for ad-hoc analysis.</p>
                    </div>
                </section>

                <!-- CURL EXAMPLES -->
                <section class="mt-8">
                    <div class="grid md:grid-cols-2 gap-6">
                        <div class="bg-white p-6 rounded-xl shadow">
                            <div class="flex items-center justify-between">
                                <h4 class="font-semibold">Batch Prediction (curl)</h4>
                                <button data-copy-target="#curlBatch" class="copy-btn inline-flex items-center gap-2 bg-teal-600 text-white px-3 py-1.5 rounded transition hover:scale-105">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16h8M8 12h8M8 8h8"/></svg>
                                    Copy
                                </button>
                            </div>
                            <pre id="curlBatch" class="mt-4 p-3 bg-slate-900 text-slate-100 rounded mono text-sm">curl -X POST 'http://localhost:23333/predict/batch' -H 'Content-Type: application/json' -d '{"flows":[{"dst_port":443,"flow_duration":120.5,"tot_fwd_pkts":10,"tot_bwd_pkts":2,"fwd_pkt_len_max":1500,"fwd_pkt_len_min":60,"bwd_pkt_len_max":1448,"bwd_pkt_len_mean":512,"flow_byts_s":1000.0,"flow_pkts_s":50.0,"flow_iat_mean":0.02,"flow_iat_std":0.01,"flow_iat_max":0.1,"fwd_iat_std":0.005,"bwd_pkts_s":5.0,"psh_flag_cnt":0,"ack_flag_cnt":1,"init_fwd_win_byts":65535,"init_bwd_win_byts":8192,"fwd_seg_size_min":0,"timestamp":"2025-11-21T00:00:00Z","src_ip":"192.0.2.10","dst_ip":"198.51.100.5","src_port":52341,"protocol":"TCP"},{"dst_port":443,"flow_duration":60.0,"tot_fwd_pkts":6,"tot_bwd_pkts":1,"fwd_pkt_len_max":1400,"fwd_pkt_len_min":64,"bwd_pkt_len_max":1024,"bwd_pkt_len_mean":400,"flow_byts_s":750.0,"flow_pkts_s":30.0,"flow_iat_mean":0.03,"flow_iat_std":0.008,"flow_iat_max":0.12,"fwd_iat_std":0.004,"bwd_pkts_s":3.0,"psh_flag_cnt":0,"ack_flag_cnt":1,"init_fwd_win_byts":65535,"init_bwd_win_byts":8192,"fwd_seg_size_min":0,"timestamp":"2025-11-21T00:00:05Z","src_ip":"1.2.3.5","dst_ip":"5.6.7.9","src_port":12346,"protocol":"TCP"},{"dst_port":80,"flow_duration":8.2,"tot_fwd_pkts":4,"tot_bwd_pkts":0,"fwd_pkt_len_max":1500,"fwd_pkt_len_min":120,"bwd_pkt_len_max":0,"bwd_pkt_len_mean":0,"flow_byts_s":200.0,"flow_pkts_s":12.0,"flow_iat_mean":0.01,"flow_iat_std":0.002,"flow_iat_max":0.02,"fwd_iat_std":0.002,"bwd_pkts_s":0.0,"psh_flag_cnt":0,"ack_flag_cnt":1,"init_fwd_win_byts":65535,"init_bwd_win_byts":8192,"fwd_seg_size_min":0,"timestamp":"2025-11-21T00:00:10Z","src_ip":"1.2.3.6","dst_ip":"5.6.7.10","src_port":12347,"protocol":"TCP"},{"dst_port":53,"flow_duration":0.5,"tot_fwd_pkts":1,"tot_bwd_pkts":1,"fwd_pkt_len_max":128,"fwd_pkt_len_min":128,"bwd_pkt_len_max":128,"bwd_pkt_len_mean":128,"flow_byts_s":64.0,"flow_pkts_s":2.0,"flow_iat_mean":0.0005,"flow_iat_std":0.0001,"flow_iat_max":0.001,"fwd_iat_std":0.0002,"bwd_pkts_s":2.0,"psh_flag_cnt":0,"ack_flag_cnt":0,"init_fwd_win_byts":65535,"init_bwd_win_byts":8192,"fwd_seg_size_min":0,"timestamp":"2025-11-21T00:00:15Z","src_ip":"1.2.3.7","dst_ip":"5.6.7.11","src_port":12348,"protocol":"UDP"},{"dst_port":443,"flow_duration":30.0,"tot_fwd_pkts":8,"tot_bwd_pkts":2,"fwd_pkt_len_max":1500,"fwd_pkt_len_min":64,"bwd_pkt_len_max":1200,"bwd_pkt_len_mean":600,"flow_byts_s":600.0,"flow_pkts_s":25.0,"flow_iat_mean":0.015,"flow_iat_std":0.006,"flow_iat_max":0.08,"fwd_iat_std":0.003,"bwd_pkts_s":4.0,"psh_flag_cnt":0,"ack_flag_cnt":1,"init_fwd_win_byts":65535,"init_bwd_win_byts":8192,"fwd_seg_size_min":0,"timestamp":"2025-11-21T00:00:20Z","src_ip":"1.2.3.8","dst_ip":"5.6.7.12","src_port":12349,"protocol":"TCP"}],"include_confidence":true,"client_id":"demo-client-0001","resource_id":"demo-resource-0001"}'</pre>
                            <p class="mt-3 text-xs text-slate-500">Add <code class="mono">?diagnostic_sample=3</code> to log small per-base-model outputs (for debugging).</p>
                        </div>

                        <div class="bg-white p-6 rounded-xl shadow">
                            <div class="flex items-center justify-between">
                                <h4 class="font-semibold">Buffered Ingestion (curl)</h4>
                                <button data-copy-target="#curlBuffered" class="copy-btn inline-flex items-center gap-2 bg-teal-600 text-white px-3 py-1.5 rounded transition hover:scale-105">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16h8M8 12h8M8 8h8"/></svg>
                                    Copy
                                </button>
                            </div>
                            <pre id="curlBuffered" class="mt-4 p-3 bg-slate-900 text-slate-100 rounded mono text-sm">curl -X POST 'http://localhost:23333/predict/buffered' -H 'Content-Type: application/json' -d '{"dst_port":443,"flow_duration":120.5,"tot_fwd_pkts":10,"tot_bwd_pkts":2,"fwd_pkt_len_max":1500,"fwd_pkt_len_min":60,"bwd_pkt_len_max":1448,"bwd_pkt_len_mean":512,"flow_byts_s":1000.0,"flow_pkts_s":50.0,"flow_iat_mean":0.02,"flow_iat_std":0.01,"flow_iat_max":0.1,"fwd_iat_std":0.005,"bwd_pkts_s":5.0,"psh_flag_cnt":0,"ack_flag_cnt":1,"init_fwd_win_byts":65535,"init_bwd_win_byts":8192,"fwd_seg_size_min":0,"timestamp":"2025-11-21T00:00:00Z","src_ip":"192.0.2.10","dst_ip":"198.51.100.5","src_port":52341,"protocol":"TCP","client_id":"demo-client-0001","resource_id":"demo-resource-0001"}'</pre>
                            <p class="mt-3 text-xs text-slate-500">POST individual CICFlowMeter flows here to buffer them for batch processing.</p>
                        </div>
                    </div>
                </section>

                <section class="mt-8 bg-white p-6 rounded-xl shadow">
                    <h4 class="font-semibold">Flush / Monitor</h4>
                    <div class="mt-3 grid md:grid-cols-2 gap-4">
                        <div>
                            <label class="text-sm text-slate-600">Manual flush (curl)</label>
                            <div class="mt-2 flex gap-2 items-start">
                                <pre id="curlFlush" class="p-3 bg-slate-900 text-slate-100 rounded mono text-sm">curl -X POST 'http://localhost:23333/flush-buffer'</pre>
                                <button data-copy-target="#curlFlush" class="copy-btn inline-flex items-center gap-2 border px-3 py-1.5 rounded">Copy</button>
                            </div>
                        </div>
                        <div>
                            <label class="text-sm text-slate-600">Buffer stats (curl)</label>
                            <div class="mt-2 flex gap-2 items-start">
                                <pre id="curlStats" class="p-3 bg-slate-900 text-slate-100 rounded mono text-sm">curl -X GET 'http://localhost:23333/buffer-stats'</pre>
                                <button data-copy-target="#curlStats" class="copy-btn inline-flex items-center gap-2 border px-3 py-1.5 rounded">Copy</button>
                            </div>
                        </div>
                    </div>
                </section>
            </main>

            <footer class="border-t bg-white mt-8">
                <div class="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between text-sm text-slate-500">
                    <div id="footer-year">© <span id="year"></span> BEAST MODE</div>
                    <div>Model: I-MPaFS-BeastMode-v2.0</div>
                </div>
            </footer>

            <script>
                // Set footer year
                document.getElementById('year').textContent = new Date().getFullYear();

                // Copy-to-clipboard for curl examples
                document.querySelectorAll('.copy-btn').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const target = btn.getAttribute('data-copy-target');
                        const el = document.querySelector(target);
                        if (!el) return;
                        try {
                            await navigator.clipboard.writeText(el.textContent.trim());
                            btn.classList.add('bg-teal-700');
                            setTimeout(()=>btn.classList.remove('bg-teal-700'), 900);
                        } catch(e) {
                            alert('Copy failed: '+e);
                        }
                    });
                });
            </script>
        </body>
        </html>
        """

    return HTMLResponse(content=html, status_code=200)


@app.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    """HTML health dashboard (fetches `/health/json`)."""
    html = """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width,initial-scale=1" />
            <title>BEAST MODE — Health</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>.mono{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, 'Roboto Mono', 'Segoe UI Mono', monospace;}</style>
        </head>
        <body class="bg-slate-50 text-slate-900">
            <nav class="bg-white shadow-md">
                <div class="max-w-7xl mx-auto px-6">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center gap-4">
                            <a href="/" class="text-lg font-bold text-slate-800">BEAST MODE</a>
                        </div>
                        <div class="hidden md:flex items-center gap-6">
                            <a href="/docs" class="text-sm text-slate-700 hover:text-teal-600">Docs</a>
                            <a href="/health" class="text-sm text-slate-700 hover:text-teal-600">Health</a>
                            <a href="/performance" class="text-sm text-slate-700 hover:text-teal-600">Performance</a>
                        </div>
                    </div>
                </div>
            </nav>
            <main class="max-w-7xl mx-auto px-6 py-8">
                <h1 class="text-2xl font-semibold">Health & Monitoring</h1>
                <p class="mt-2 text-sm text-slate-600">Live health dashboard and diagnostics for the BEAST MODE API. This page periodically refreshes metrics.</p>

                <div class="mt-6 grid md:grid-cols-3 gap-4">
                    <div class="bg-white p-4 rounded-lg shadow">
                        <h3 class="font-medium">Service Status</h3>
                        <div id="serviceStatus" class="mt-2 text-sm text-slate-700">Loading...</div>
                    </div>

                    <div class="bg-white p-4 rounded-lg shadow">
                        <h3 class="font-medium">Throughput</h3>
                        <div id="throughput" class="mt-2 text-sm text-slate-700">Loading...</div>
                    </div>

                    <div class="bg-white p-4 rounded-lg shadow">
                        <h3 class="font-medium">Threat Summary</h3>
                        <div id="threatSummary" class="mt-2 text-sm text-slate-700">Loading...</div>
                    </div>
                </div>

                <div class="mt-6 bg-white p-4 rounded-lg shadow">
                    <h3 class="font-medium">Buffer Details</h3>
                    <pre id="bufferDetails" class="mt-2 p-3 bg-slate-900 text-slate-100 rounded mono text-sm">Loading...</pre>
                </div>

                <div class="mt-6 bg-white p-4 rounded-lg shadow">
                    <h3 class="font-medium">Engine Performance</h3>
                    <pre id="enginePerf" class="mt-2 p-3 bg-slate-900 text-slate-100 rounded mono text-sm">Loading...</pre>
                </div>
            </main>

            <script>
                async function fetchHealth(){
                    try{
                        const r = await fetch('/health/json');
                        const j = await r.json();
                        document.getElementById('serviceStatus').textContent = j.status;
                        document.getElementById('throughput').textContent = `Throughput: ${j.metrics.throughput_flows_per_sec} flows/s — Total requests: ${j.metrics.total_requests}`;
                        document.getElementById('threatSummary').textContent = `Level: ${j.metrics.current_threat_level} — Attack rate: ${j.metrics.last_batch_attack_rate_percent}% — Total attacks: ${j.metrics.total_attacks_detected}`;
                        document.getElementById('bufferDetails').textContent = JSON.stringify(j.buffer_status, null, 2);
                        document.getElementById('enginePerf').textContent = JSON.stringify(j.engine_performance || {}, null, 2);
                    }catch(e){
                        console.error('Failed to fetch health', e);
                    }
                }
                fetchHealth();
                setInterval(fetchHealth, 5000);
            </script>
        </body>
        </html>
        """
    return HTMLResponse(content=html, status_code=200)


@app.get("/health/json")
async def health_check():
    """JSON health payload for programmatic monitoring."""

    current_time = datetime.utcnow().isoformat() + "Z"
    uptime = None

    if hasattr(app.state, "startup_time"):
        uptime = (datetime.utcnow() - app.state.startup_time).total_seconds()

    engine_stats = None
    engine_loaded = beast_engine is not None

    if engine_loaded:
        try:
            engine_stats = beast_engine.get_performance_stats()
        except Exception as e:
            logger.warning(f"Could not get engine stats: {e}")

    # Get buffer status
    async with buffer_lock:
        buffer_size = len(flow_buffer)

    runtime = time.time() - buffer_stats["start_time"]
    throughput = (
        round(buffer_stats["total_flows_received"] / runtime, 2) if runtime > 0 else 0
    )

    payload = {
        "status": "OK" if engine_loaded else "ENGINE_DOWN",
        "timestamp": current_time,
        "engine_loaded": engine_loaded,
        "uptime_seconds": uptime,
        "metrics": {
            "throughput_flows_per_sec": throughput,
            "total_requests": buffer_stats["total_flows_received"],
            "total_batches_processed": buffer_stats["total_batches_processed"],
            "total_attacks_detected": buffer_stats["total_attacks_detected"],
            "last_batch_attack_rate_percent": round(
                buffer_stats["last_batch_attack_rate"], 2
            ),
            "current_threat_level": buffer_stats["current_threat_level"],
        },
        "buffer_status": {
            "current_size": buffer_size,
            "capacity": BUFFER_SIZE,
            "utilization_percent": round((buffer_size / BUFFER_SIZE) * 100, 1),
            "max_capacity": MAX_BUFFER_CAPACITY,
            "time_since_last_flush_sec": round(
                time.time() - buffer_stats["last_flush_time"], 2
            ),
        },
        "engine_performance": engine_stats,
    }

    return JSONResponse(content=payload)


@app.post("/predict", response_model=PredictionDetail)
async def predict_single_flow_ultra_fast(
    request: SinglePredictionRequest,
) -> PredictionDetail:
    """
    ULTRA-FAST single flow prediction.

    Optimized for minimum latency with vectorized processing.
    """

    if beast_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BEAST MODE engine not available",
        )

    try:
        # Convert Pydantic model to dict with correct field names
        flow = request.flow
        flow_data = {
            "Dst Port": flow.dst_port,
            "Flow Duration": flow.flow_duration,
            "Tot Fwd Pkts": flow.tot_fwd_pkts,
            "Tot Bwd Pkts": flow.tot_bwd_pkts,
            "Fwd Pkt Len Max": flow.fwd_pkt_len_max,
            "Fwd Pkt Len Min": flow.fwd_pkt_len_min,
            "Bwd Pkt Len Max": flow.bwd_pkt_len_max,
            "Bwd Pkt Len Mean": flow.bwd_pkt_len_mean,
            "Flow Byts/s": flow.flow_byts_s,
            "Flow Pkts/s": flow.flow_pkts_s,
            "Flow IAT Mean": flow.flow_iat_mean,
            "Flow IAT Std": flow.flow_iat_std,
            "Flow IAT Max": flow.flow_iat_max,
            "Fwd IAT Std": flow.fwd_iat_std,
            "Bwd Pkts/s": flow.bwd_pkts_s,
            "PSH Flag Cnt": flow.psh_flag_cnt,
            "ACK Flag Cnt": flow.ack_flag_cnt,
            "Init Fwd Win Byts": flow.init_fwd_win_byts,
            "Init Bwd Win Byts": flow.init_bwd_win_byts,
            "Fwd Seg Size Min": flow.fwd_seg_size_min,
        }

        # ULTRA-FAST prediction
        result = await beast_engine.predict_single_ultra_fast(flow_data)

        # Broadcast raw prediction + minimal flow metadata to live clients (non-persistent)
        try:
            # build full flow dict then reduce to minimal metadata
            flow_meta_all = model_to_dict(flow, by_alias=True, exclude_none=True)
            flow_meta = {
                "src_ip": flow_meta_all.get("src_ip"),
                "dst_ip": flow_meta_all.get("dst_ip"),
                "dst_port": flow_meta_all.get("dst_port")
                or flow_meta_all.get("Dst Port"),
                "timestamp": request.timestamp or datetime.utcnow().isoformat(),
            }

            # Add required routing metadata for live monitor
            message = {
                "message_id": None,
                "timestamp": flow_meta["timestamp"],
                "model_version": result.get("model_version", "I-MPaFS-BeastMode-v2.0"),
                "prediction": result,
                "flow": flow_meta,
                "client_id": request.client_id,
                "resource_id": request.resource_id,
            }
            # Only attempt broadcast if lock exists
            if live_clients_lock is not None:
                await broadcast_to_live_clients(message)

            # Publish minimal prediction message to Redis (fire-and-forget)
            try:
                asyncio.create_task(
                    publish_prediction(
                        result, request.client_id, request.resource_id, flow_meta
                    )
                )
            except Exception:
                logger.debug("Failed to schedule publish to Redis")
        except Exception:
            # Don't fail prediction on broadcast/publish errors
            logger.debug("Failed to broadcast or publish live prediction to clients")

        return PredictionDetail(**result)

    except Exception as e:
        logger.error(f"❌ BEAST MODE single prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        )


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch_ultra_high_throughput(
    request: BatchPredictionRequest, diagnostic_sample: int = 0
) -> BatchPredictionResponse:
    """
    🔥 BEAST MODE BATCH PROCESSING 🔥

    ULTRA-HIGH-THROUGHPUT batch prediction for 10,000+ flows.
    Pure vectorized processing - NO LOOPS!
    """

    if beast_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BEAST MODE engine not available",
        )

    batch_size = len(request.flows)
    logger.info(f"🚀 BEAST MODE: Processing {batch_size} flows...")

    try:
        # Convert flows to the format expected by BEAST MODE engine
        flows_data = []
        for flow in request.flows:
            flow_data = {
                "Dst Port": flow.dst_port,
                "Flow Duration": flow.flow_duration,
                "Tot Fwd Pkts": flow.tot_fwd_pkts,
                "Tot Bwd Pkts": flow.tot_bwd_pkts,
                "Fwd Pkt Len Max": flow.fwd_pkt_len_max,
                "Fwd Pkt Len Min": flow.fwd_pkt_len_min,
                "Bwd Pkt Len Max": flow.bwd_pkt_len_max,
                "Bwd Pkt Len Mean": flow.bwd_pkt_len_mean,
                "Flow Byts/s": flow.flow_byts_s,
                "Flow Pkts/s": flow.flow_pkts_s,
                "Flow IAT Mean": flow.flow_iat_mean,
                "Flow IAT Std": flow.flow_iat_std,
                "Flow IAT Max": flow.flow_iat_max,
                "Fwd IAT Std": flow.fwd_iat_std,
                "Bwd Pkts/s": flow.bwd_pkts_s,
                "PSH Flag Cnt": flow.psh_flag_cnt,
                "ACK Flag Cnt": flow.ack_flag_cnt,
                "Init Fwd Win Byts": flow.init_fwd_win_byts,
                "Init Bwd Win Byts": flow.init_bwd_win_byts,
                "Fwd Seg Size Min": flow.fwd_seg_size_min,
            }
            flows_data.append(flow_data)

        # 🔥 BEAST MODE VECTORIZED BATCH PROCESSING 🔥
        results = await beast_engine.predict_batch_ultra_fast(
            flows_data,
            include_confidence=request.include_confidence,
            diagnostic_sample=diagnostic_sample,
        )
        # Convert to Pydantic models
        predictions = [PredictionDetail(**result) for result in results["predictions"]]

        # Broadcast each prediction with its original flow metadata to live clients
        try:
            if live_clients_lock is not None:
                for i, pred in enumerate(results.get("predictions", [])):
                    # Attempt to preserve minimal flow metadata from original request flows
                    orig_flow = None
                    try:
                        orig_flow = model_to_dict(request.flows[i])
                    except Exception:
                        orig_flow = None

                    flow_meta = {
                        "src_ip": orig_flow.get("src_ip") if orig_flow else None,
                        "dst_ip": orig_flow.get("dst_ip") if orig_flow else None,
                        "dst_port": (
                            orig_flow.get("dst_port")
                            if orig_flow
                            else (
                                flows_data[i].get("Dst Port")
                                if i < len(flows_data)
                                else None
                            )
                        ),
                        "timestamp": (
                            orig_flow.get("timestamp")
                            if orig_flow
                            else datetime.utcnow().isoformat()
                        ),
                    }

                    message = {
                        "message_id": None,
                        "timestamp": flow_meta.get("timestamp")
                        or datetime.utcnow().isoformat(),
                        "model_version": pred.get(
                            "model_version", "I-MPaFS-BeastMode-v2.0"
                        ),
                        "prediction": pred,
                        "flow": flow_meta,
                        "client_id": request.client_id,
                        "resource_id": request.resource_id,
                    }
                    await broadcast_to_live_clients(message)
                    # Publish prediction to Redis (fire-and-forget)
                    try:
                        asyncio.create_task(
                            publish_prediction(
                                pred, request.client_id, request.resource_id, flow_meta
                            )
                        )
                    except Exception:
                        logger.debug(
                            "Failed to schedule publish to Redis for batch prediction"
                        )
        except Exception:
            logger.debug("Failed to broadcast batch predictions to live clients")
        logger.info(
            f"⚡ BEAST MODE COMPLETE: {batch_size} flows processed "
            f"at {results['statistics']['throughput_flows_per_sec']:.2f} flows/sec"
        )

        return BatchPredictionResponse(
            predictions=predictions, statistics=results["statistics"]
        )

    except Exception as e:
        logger.error(f"❌ BEAST MODE batch prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"BEAST MODE batch prediction failed: {str(e)}",
        )


# ===================================================================
# BUFFERED CICFLOWMETER INTEGRATION WITH INTELLIGENT THREAT ASSESSMENT
# ===================================================================

# Field mapping for CICFlowMeter compatibility
CICFLOW_FIELD_MAPPING = {
    "dst_port": "Dst Port",
    "flow_duration": "Flow Duration",
    "tot_fwd_pkts": "Tot Fwd Pkts",
    "tot_bwd_pkts": "Tot Bwd Pkts",
    "fwd_pkt_len_max": "Fwd Pkt Len Max",
    "fwd_pkt_len_min": "Fwd Pkt Len Min",
    "bwd_pkt_len_max": "Bwd Pkt Len Max",
    "bwd_pkt_len_mean": "Bwd Pkt Len Mean",
    "flow_byts_s": "Flow Byts/s",
    "flow_pkts_s": "Flow Pkts/s",
    "flow_iat_mean": "Flow IAT Mean",
    "flow_iat_std": "Flow IAT Std",
    "flow_iat_max": "Flow IAT Max",
    "fwd_iat_std": "Fwd IAT Std",
    "bwd_pkts_s": "Bwd Pkts/s",
    "psh_flag_cnt": "PSH Flag Cnt",
    "ack_flag_cnt": "ACK Flag Cnt",
    "init_fwd_win_byts": "Init Fwd Win Byts",
    "init_bwd_win_byts": "Init Bwd Win Byts",
    "fwd_seg_size_min": "Fwd Seg Size Min",
}


def convert_cicflow_to_beast_format(
    cicflow_data: dict[str, object],
) -> dict[str, object]:
    """Convert CICFlowMeter field names to Beast Mode format"""
    converted = {}

    # Convert mapped ML feature fields
    for cicflow_field, beast_field in CICFLOW_FIELD_MAPPING.items():
        if cicflow_field in cicflow_data:
            converted[beast_field] = cicflow_data[cicflow_field]

    # Preserve metadata fields that we need for tracking and Redis publishing
    # (but exclude fields that are already converted above to avoid duplicates)
    metadata_fields = [
        "client_id",
        "resource_id",
        "src_ip",
        "dst_ip",
        "src_port",
        "protocol",
        "timestamp",
    ]

    # Only preserve metadata fields that are NOT already in the mapping
    mapped_fields = set(CICFLOW_FIELD_MAPPING.keys())
    for field in metadata_fields:
        if field in cicflow_data and field not in mapped_fields:
            converted[field] = cicflow_data[field]

    return converted


def assess_threat_level(attack_rate: float) -> str:
    """Determine threat level based on attack percentage in batch"""
    if attack_rate >= THREAT_CRITICAL_PCT:
        return "CRITICAL"
    elif attack_rate >= THREAT_HIGH_PCT:
        return "HIGH"
    elif attack_rate >= THREAT_MEDIUM_PCT:
        return "MEDIUM"
    elif attack_rate >= THREAT_LOW_PCT:
        return "LOW"
    else:
        return "NORMAL"


async def process_buffer_batch() -> dict[str, object]:
    """
    🔥 INTELLIGENT BATCH PROCESSING WITH THREAT ASSESSMENT 🔥

    Processes buffered flows and provides collective threat intelligence:
    - Individual flow predictions
    - Batch-wide attack rate analysis
    - Dynamic threat level assessment
    - Network-wide security status
    """
    async with buffer_lock:
        if not flow_buffer:
            return {"message": "Buffer empty", "flows_processed": 0}

        # Extract flows for processing (up to BUFFER_SIZE)
        flows_to_process = []
        while flow_buffer and len(flows_to_process) < BUFFER_SIZE:
            flows_to_process.append(flow_buffer.popleft())

        batch_size = len(flows_to_process)
        # mark flush time immediately so other requests see progress
        buffer_stats["last_flush_time"] = time.time()

    if batch_size == 0:
        return {"message": "No flows to process", "flows_processed": 0}

    try:
        # Convert CICFlowMeter format to Beast Mode format
        converted_flows = []
        for flow in flows_to_process:
            # If flow already appears converted (contains feature keys), use as-is
            expected_set = getattr(app.state, "expected_feature_set", set())
            if expected_set and expected_set.issubset(set(flow.keys())):
                converted_flows.append(flow)
            else:
                converted_flow = convert_cicflow_to_beast_format(flow)
                if converted_flow:  # Only add if conversion successful
                    converted_flows.append(converted_flow)

        if not converted_flows:
            logger.warning("No valid flows after conversion; re-queuing flows")
            # Re-queue the extracted flows back to the left of the buffer
            async with buffer_lock:
                for flow in reversed(flows_to_process):
                    flow_buffer.appendleft(flow)
            return {"message": "No valid flows after conversion", "flows_processed": 0}

        # 🔥 BEAST MODE BATCH PROCESSING 🔥
        start_time = time.time()
        # Use optional runtime diagnostic sample size if set in app.state
        diag_sample = getattr(app.state, "diagnostic_sample", 0)
        results = await beast_engine.predict_batch_ultra_fast(
            converted_flows, include_confidence=True, diagnostic_sample=diag_sample
        )
        processing_time = time.time() - start_time

        # Intelligent threat assessment
        predictions = results.get("predictions", [])

        # Count attack predictions robustly (pred may be dict with 'is_attack')
        attack_predictions = 0
        for pred in predictions:
            if isinstance(pred, dict):
                if pred.get("is_attack") in (True, 1):
                    attack_predictions += 1
            elif isinstance(pred, (int, bool)):
                if bool(pred):
                    attack_predictions += 1

        benign_predictions = len(predictions) - attack_predictions
        attack_rate = (
            (attack_predictions / len(predictions)) * 100 if predictions else 0
        )

        # Update global threat assessment under lock to avoid races
        async with buffer_lock:
            buffer_stats["total_batches_processed"] += 1
            buffer_stats["total_attacks_detected"] += attack_predictions
            buffer_stats["last_batch_attack_rate"] = attack_rate
            buffer_stats["current_threat_level"] = assess_threat_level(attack_rate)

        # Calculate throughput
        throughput = (
            len(converted_flows) / processing_time if processing_time > 0 else 0
        )

        logger.info(
            f"BATCH PROCESSED: {len(converted_flows)} flows, "
            f"{attack_predictions} attacks ({attack_rate:.1f}%), "
            f"Threat Level: {buffer_stats['current_threat_level']}, "
            f"Throughput: {throughput:.0f} flows/sec"
        )

        # Broadcast raw predictions for live monitoring (non-persistent)
        try:
            if live_clients_lock is not None:
                for i, pred in enumerate(predictions):
                    # Attempt to preserve minimal metadata from original queued flows
                    orig_flow = flows_to_process[i] if i < len(flows_to_process) else {}
                    flow_meta = {
                        "src_ip": orig_flow.get("src_ip"),
                        "dst_ip": orig_flow.get("dst_ip"),
                        "dst_port": orig_flow.get("dst_port")
                        or (
                            converted_flows[i].get("Dst Port")
                            if i < len(converted_flows)
                            else None
                        ),
                        "timestamp": orig_flow.get("timestamp")
                        or datetime.utcnow().isoformat(),
                    }

                    message = {
                        "message_id": None,
                        "timestamp": flow_meta.get("timestamp"),
                        "model_version": pred.get(
                            "model_version", "I-MPaFS-BeastMode-v2.0"
                        ),
                        "prediction": pred,
                        "flow": flow_meta,
                    }
                    await broadcast_to_live_clients(message)
        except Exception:
            logger.debug(
                "Failed to broadcast buffered batch predictions to live clients"
            )

        # Publish complete batch results to Redis (instead of individual predictions)
        try:
            # Get client_id and resource_id from first flow (they should be same for the batch)
            first_flow = flows_to_process[0] if flows_to_process else {}
            client_id = first_flow.get("client_id", "unknown_client")
            resource_id = first_flow.get("resource_id", "unknown_resource")

            # Debug: Log what we found in first_flow
            logger.info(f"🔍 First flow keys: {list(first_flow.keys())[:10]}...")
            logger.info(
                f"🔍 Extracted client_id: {client_id}, resource_id: {resource_id}"
            )

            batch_data = {
                "predictions": predictions,
                "statistics": {
                    "total_flows": len(converted_flows),
                    "attack_predictions": attack_predictions,
                    "benign_predictions": benign_predictions,
                    "processing_time_ms": processing_time * 1000,
                    "throughput_flows_per_sec": throughput,
                    "average_confidence": (
                        sum(p.get("confidence", 0) for p in predictions)
                        / len(predictions)
                        if predictions
                        else 0
                    ),
                },
            }

            asyncio.create_task(
                publish_batch_results(batch_data, client_id, resource_id)
            )
            logger.info(
                f"📤 Published batch results to Redis: {len(predictions)} predictions, {attack_predictions} attacks"
            )
        except Exception as e:
            logger.debug(f"Failed to publish batch results to Redis: {e}")

        return {
            "batch_processing": {
                "flows_processed": len(converted_flows),
                "processing_time_ms": processing_time * 1000,
                "throughput_flows_per_sec": throughput,
            },
            "threat_assessment": {
                "attack_predictions": attack_predictions,
                "benign_predictions": benign_predictions,
                "attack_rate_percent": round(attack_rate, 2),
                "threat_level": buffer_stats["current_threat_level"],
                "network_status": (
                    "UNDER_ATTACK" if attack_rate >= THREAT_HIGH_PCT else "NORMAL"
                ),
            },
            "predictions": predictions,
            "confidence_scores": results.get("confidence", {}),
            "beast_mode_stats": results["statistics"],
        }

    except Exception as e:
        logger.error(f"❌ Batch processing failed: {e}")
        # Return flows to buffer on failure
        async with buffer_lock:
            flows_to_process.reverse()
            for flow in flows_to_process:
                flow_buffer.appendleft(flow)
        raise


@app.post("/predict/buffered")
async def predict_buffered_cicflow(flow_data: dict[str, object]):
    """
    🔥 BUFFERED CICFLOWMETER PROCESSING 🔥

    Receives individual flows from CICFlowMeter, buffers them for batch processing.
    Provides intelligent threat assessment when batch is full.

    Flow: CICFlowMeter → Buffer → Batch Processing → Threat Intelligence
    """
    if beast_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BEAST MODE engine not available",
        )

    try:
        # Validate and add flow to buffer (thread-safe)
        # Convert CICFlowMeter -> beast fields first and validate
        expected_set = getattr(app.state, "expected_feature_set", None)
        converted = convert_cicflow_to_beast_format(flow_data)
        if expected_set is not None:
            missing = set(expected_set) - set(converted.keys())
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "missing_features", "missing": list(missing)},
                )
        async with buffer_lock:
            if len(flow_buffer) >= MAX_BUFFER_CAPACITY:
                # Buffer overflow protection - remove oldest flow
                logger.warning(
                    f"Buffer overflow: removing oldest flow. Buffer size: {len(flow_buffer)}"
                )
                flow_buffer.popleft()

            # Store converted (beast-format) flow to avoid double conversion
            flow_buffer.append(converted)
            current_buffer_size = len(flow_buffer)
            buffer_stats["total_flows_received"] += 1

        # Check if we should process the buffer
        should_process = False
        time_since_flush = time.time() - buffer_stats["last_flush_time"]

        if current_buffer_size >= BUFFER_SIZE:
            should_process = True
            logger.info(
                f"🔥 Buffer full ({BUFFER_SIZE} flows) - triggering batch processing"
            )
        elif current_buffer_size > 0 and time_since_flush >= MAX_WAIT_TIME:
            should_process = True
            logger.info(
                f"⏰ Timeout reached ({MAX_WAIT_TIME}s) - processing {current_buffer_size} flows"
            )

        # Process batch if conditions met
        batch_result = None
        if should_process:
            batch_result = await process_buffer_batch()

        # Calculate runtime statistics
        runtime = time.time() - buffer_stats["start_time"]
        avg_throughput = (
            buffer_stats["total_flows_received"] / runtime if runtime > 0 else 0
        )

        response = {
            "status": "processed" if batch_result else "buffered",
            "batch_processed": bool(batch_result),
            "flow_info": {
                "source_ip": flow_data.get("src_ip", "unknown"),
                "destination_port": flow_data.get("dst_port", 0),
                "timestamp": flow_data.get(
                    "timestamp", datetime.utcnow().isoformat() + "Z"
                ),
            },
            "buffer_status": {
                "current_size": current_buffer_size,
                "capacity": BUFFER_SIZE,
                "utilization_percent": round(
                    (current_buffer_size / BUFFER_SIZE) * 100, 1
                ),
                "next_process_at": (
                    BUFFER_SIZE - current_buffer_size
                    if current_buffer_size < BUFFER_SIZE
                    else 0
                ),
            },
            "statistics": {
                "total_flows_received": buffer_stats["total_flows_received"],
                "total_batches_processed": buffer_stats["total_batches_processed"],
                "avg_throughput_flows_per_sec": round(avg_throughput, 2),
                "current_threat_level": buffer_stats["current_threat_level"],
                "total_attacks_detected": buffer_stats["total_attacks_detected"],
            },
        }

        # Include batch processing results if available
        if batch_result:
            response["batch_processing_result"] = batch_result

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Buffered processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Buffered processing failed: {str(e)}",
        )


@app.post("/flush-buffer")
async def manual_buffer_flush():
    """Manual buffer flush for testing/monitoring"""
    try:
        result = await process_buffer_batch()
        return result
    except Exception as e:
        logger.error(f"❌ Manual flush failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual flush failed: {str(e)}",
        )


@app.get("/buffer-stats")
async def get_buffer_statistics():
    """Real-time buffer and threat assessment statistics"""
    async with buffer_lock:
        buffer_size = len(flow_buffer)

    runtime = time.time() - buffer_stats["start_time"]
    avg_throughput = (
        buffer_stats["total_flows_received"] / runtime if runtime > 0 else 0
    )
    time_since_flush = time.time() - buffer_stats["last_flush_time"]

    return {
        "buffer_status": {
            "current_size": buffer_size,
            "capacity": BUFFER_SIZE,
            "utilization_percent": round((buffer_size / BUFFER_SIZE) * 100, 1),
            "max_capacity": MAX_BUFFER_CAPACITY,
            "time_since_last_flush_sec": round(time_since_flush, 2),
            "max_wait_time_sec": MAX_WAIT_TIME,
        },
        "processing_statistics": {
            "total_flows_received": buffer_stats["total_flows_received"],
            "total_batches_processed": buffer_stats["total_batches_processed"],
            "total_attacks_detected": buffer_stats["total_attacks_detected"],
            "avg_throughput_flows_per_sec": round(avg_throughput, 2),
            "runtime_seconds": round(runtime, 2),
        },
        "threat_intelligence": {
            "current_threat_level": buffer_stats["current_threat_level"],
            "last_batch_attack_rate_percent": round(
                buffer_stats["last_batch_attack_rate"], 2
            ),
            "network_status": (
                "UNDER_ATTACK"
                if buffer_stats["last_batch_attack_rate"] >= THREAT_HIGH_PCT
                else "NORMAL"
            ),
            "threat_assessment": {
                "NORMAL": "< 10% attack rate",
                "LOW": "10-24% attack rate",
                "MEDIUM": "25-49% attack rate",
                "HIGH": "50-74% attack rate",
                "CRITICAL": "≥ 75% attack rate",
            },
        },
    }


@app.get("/performance", response_class=HTMLResponse)
async def performance_page(request: Request):
    """HTML performance dashboard (fetches `/performance/json`)."""
    html = """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width,initial-scale=1" />
            <title>BEAST MODE — Performance</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>.mono{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, 'Roboto Mono', 'Segoe UI Mono', monospace;}</style>
        </head>
        <body class="bg-slate-50 text-slate-900">
            <nav class="bg-white shadow-md">
                <div class="max-w-7xl mx-auto px-6">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center gap-4">
                            <a href="/" class="text-lg font-bold text-slate-800">BEAST MODE</a>
                        </div>
                        <div class="hidden md:flex items-center gap-6">
                            <a href="/docs" class="text-sm text-slate-700 hover:text-teal-600">Docs</a>
                            <a href="/health" class="text-sm text-slate-700 hover:text-teal-600">Health</a>
                            <a href="/performance" class="text-sm text-slate-700 hover:text-teal-600">Performance</a>
                        </div>
                    </div>
                </div>
            </nav>

            <main class="max-w-7xl mx-auto px-6 py-8">
                <h1 class="text-2xl font-semibold">Performance</h1>
                <p class="mt-2 text-sm text-slate-600">Engine and model performance metrics for monitoring and diagnostics.</p>

                <div class="mt-6 grid md:grid-cols-2 gap-4">
                    <div class="bg-white p-4 rounded-lg shadow">
                        <h3 class="font-medium">Engine Runtime Stats</h3>
                        <pre id="engineStats" class="mt-2 p-3 bg-slate-900 text-slate-100 rounded mono text-sm">Loading...</pre>
                    </div>

                    <div class="bg-white p-4 rounded-lg shadow">
                        <h3 class="font-medium">Model Summary</h3>
                        <pre id="modelSummary" class="mt-2 p-3 bg-slate-900 text-slate-100 rounded mono text-sm">Loading...</pre>
                    </div>
                </div>
            </main>

            <script>
                async function fetchPerf(){
                    try{
                        const r = await fetch('/performance/json');
                        const j = await r.json();
                        document.getElementById('engineStats').textContent = JSON.stringify(j.engine_performance || {}, null, 2);
                        document.getElementById('modelSummary').textContent = JSON.stringify(j.model_summary || {}, null, 2);
                    }catch(e){ console.error('Failed to fetch performance', e); }
                }
                fetchPerf();
                setInterval(fetchPerf, 5000);
            </script>
        </body>
        </html>
        """
    return HTMLResponse(content=html, status_code=200)


@app.get("/performance/json")
async def get_performance_stats():
    """JSON performance payload for monitoring systems."""

    if beast_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BEAST MODE engine not available",
        )

    try:
        stats = beast_engine.get_performance_stats()
        model_summary = {}
        # Try to surface useful model metadata if available
        try:
            model_summary = {
                "model_version": getattr(beast_engine, "model_version", None),
                "feature_count": getattr(beast_engine, "feature_count", None),
            }
        except Exception:
            model_summary = {}

        return JSONResponse(
            content={
                "beast_mode": True,
                "engine_performance": stats,
                "model_summary": model_summary,
                "optimization_level": "MAXIMUM",
                "processing_type": "Vectorized",
            }
        )
    except Exception as e:
        logger.error(f"Failed to get performance stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance stats: {str(e)}",
        )


# ===================================================================
# BEAST MODE DEPLOYMENT
# ===================================================================

if __name__ == "__main__":
    # For development - use Gunicorn for production!
    uvicorn.run(
        "beast_mode_api:app",
        host="0.0.0.0",
        port=23333,  # Updated port to avoid conflicts
        reload=False,  # Disable for performance
        log_level="info",
    )

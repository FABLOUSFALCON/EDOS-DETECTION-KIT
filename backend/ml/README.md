BEAST MODE (ML) — quick start

This folder contains the BEAST MODE EDoS inference API (moved into backend for shared environment).

Files of interest:

- `beast_mode_api.py` — FastAPI server (port 23333 by default)
- `beast_mode_inference.py` — Vectorized inference engine
- `data/06_models/trained_impafs_model.pkl` — Trained model artifact
- `requirements_minimal.txt` — Minimal Python dependencies
- `conf/config.yaml` — Minimal runtime configuration
- `Dockerfile` — Build container image for the ML service

Run locally (shared backend virtualenv):

```bash
cd backend
# activate your existing backend venv or create one
source .venv/bin/activate
pip install -r ml/requirements_minimal.txt
python ml/beast_mode_api.py
```

Build & run with Docker (from `backend`):

```bash
cd backend
docker build -t edos-beast-mode:local -f ml/Dockerfile .
# then run
docker run --rm -p 23333:23333 edos-beast-mode:local
```

Notes:

- The Dockerfile expects `requirements_minimal.txt` and a `conf/` directory; both are now under `backend/ml`.
- If your `trained_impafs_model.pkl` contains TensorFlow/Keras models, ensure `tensorflow-cpu` is available in `requirements_minimal.txt` (it is included by default here).
- To integrate with the backend, point the backend ML integration endpoints to `http://ml:23333` in a `docker-compose` network or to `http://localhost:23333` when running locally.

API usage notes (required routing metadata)

- The ML API endpoints now require `client_id` and `resource_id` as routing metadata for all single and batch prediction requests. These identify which registered client/resource the flow belongs to and are used by the backend to route alerts and persist them correctly.
- For local demos you can use stable demo IDs such as `demo-client-0001` and `demo-resource-0001`.

Single prediction example:

```bash
curl -X POST http://localhost:23333/predict \
	-H "Content-Type: application/json" \
	-d '{
		"flow": {
			"dst_port": 443,
			"flow_duration": 120.5,
			"tot_fwd_pkts": 10,
			"tot_bwd_pkts": 2,
			"fwd_pkt_len_max": 1500,
			"fwd_pkt_len_min": 60,
			"flow_byts_s": 1000.0,
			"flow_pkts_s": 50.0,
			"timestamp": "2025-11-21T00:00:00Z",
			"src_ip": "1.2.3.4",
			"dst_ip": "5.6.7.8",
			"src_port": 12345,
			"protocol": "TCP"
		},
		"client_id": "demo-client-0001",
		"resource_id": "demo-resource-0001",
		"timestamp": "2025-11-21T00:00:00Z"
	}'
```

Batch prediction example (notice `client_id` and `resource_id` supplied once per batch):

```bash
curl -X POST "http://localhost:23333/predict/batch" \
	-H "Content-Type: application/json" \
	-d '{
		"flows": [
			{
				"dst_port": 443,
				"flow_duration": 120.5,
				"tot_fwd_pkts": 10,
				"tot_bwd_pkts": 2,
				"fwd_pkt_len_max": 1500,
				"fwd_pkt_len_min": 60,
				"flow_byts_s": 1000.0,
				"flow_pkts_s": 50.0,
				"timestamp": "2025-11-21T00:00:00Z",
				"src_ip": "1.2.3.4",
				"dst_ip": "5.6.7.8",
				"src_port": 12345,
				"protocol": "TCP"
			}
		],
		"include_confidence": true,
		"client_id": "demo-client-0001",
		"resource_id": "demo-resource-0001"
	}'
```

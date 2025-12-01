# EDoS Detection Dashboard — API Specification for Spring Boot Rewrite

Version: 1.0
Date: 2025-11-22

Purpose: This document describes the current FastAPI backend APIs and ML service contracts, database mappings, realtime/websocket contracts, and a recommended Redis Pub/Sub integration. It's written as a handoff package for a backend engineer implementing a Spring Boot rewrite.

---

**Notes & Assumptions**

- Authentication: Supabase JWT (HS256). All protected endpoints require `Authorization: Bearer <token>`.
- WebSocket authentication: `token` query param validated on handshake; JWT `sub` is user id.
- Use `backend/app/models/schemas.py` and `backend/app/models/database.py` as the source of truth for field names and types when mapping to Java DTOs and JPA entities.
- ML service (BEAST MODE) runs separately at `http://ml-host:23333` (example) and exposes `/predict`, `/predict/batch`, `/predict/buffered`, `/ws/live`, `/health`, `/performance`.

---

**Table of Contents**

- Authentication
- Common response & error handling
- Alerts API (`/api/alerts`)
- ML Integration (backend proxy) (`/api/ml/*`) and ML Service contract
- WebSockets (`/ws/*`) — realtime contract
- Network API (`/api/network`)
- Resources API (`/api/resources`)
- Metrics API (`/api/metrics`)
- Logs API (`/api/logs`)
- Settings API (`/api/settings`)
- Database model mappings (key tables)
- Redis Pub/Sub design (recommended) — message schema & consumer semantics
- Examples & Test scenarios
- Migration / Spring Boot implementation notes
- Acceptance tests & deliverables for hire

---

**Authentication**

- Header: `Authorization: Bearer <jwt>`.
- Verify token with Supabase JWT secret (`SUPABASE_JWT_SECRET`). Validate `sub` claim as user id.
- WebSocket: supply `token` query param and verify it during handshake. If token `sub` != `user_id` path param, close connection.

**Common Error Codes**

- 200 OK — success
- 201 Created — resource created
- 400 Bad Request — invalid input
- 401 Unauthorized — invalid/missing token
- 403 Forbidden — insufficient role
- 404 Not Found — missing resource
- 422 Unprocessable Entity — validation/missing features
- 429 Too Many Requests — rate limited
- 500 Internal Server Error — server error

---

**Alerts API** (Base: `/api/alerts`)

1. GET `/api/alerts`

- Query: `level` (optional), `read` (bool optional), `limit` (default 50)
- Auth: required
- Response: JSON array of alert summaries
  - id: string (UUID)
  - level: string (CRITICAL/HIGH/MEDIUM/LOW)
  - message: string
  - source: string
  - timestamp: ISO-8601
  - time: short formatted timestamp
  - read: boolean
  - title, category, confidence, target_ip, target_port, detection_method
  - title, category, confidence, target_ip, target_port, detection_method

Example request (GET alerts):

```http
GET /api/alerts?level=HIGH&limit=20 HTTP/1.1
Host: api.example.com
Authorization: Bearer <jwt>
```

Example response (200):

```json
[
  {
    "id": "a1b2c3d4-...",
    "level": "HIGH",
    "message": "ML-Detected ddos attack",
    "source": "198.51.100.5",
    "timestamp": "2025-11-21T12:34:56Z",
    "time": "11/21 12:34",
    "read": false,
    "title": "ML-Detected DDoS Attack",
    "category": "network",
    "confidence": 0.91,
    "target_ip": "10.0.0.5",
    "target_port": 443,
    "detection_method": "I-MPaFS-BeastMode-v2.0"
  }
]
```

2. POST `/api/alerts` (legacy/test)

- Body: arbitrary dict representing an alert (dev helper)
- Response: { status: "alert_created", id }

Example request (create alert - dev):

```http
POST /api/alerts HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "title": "Manual test alert",
  "message": "This is a test",
  "source": "192.0.2.10",
  "severity": "low"
}
```

Example response (201):

```json
{ "status": "alert_created", "id": "uuid-1234" }
```

3. POST `/api/alerts/ml-prediction`

- Auth: required
- Body (MLAlertRequest):
  - resource_id: string (required) — maps to `user_resources`
  - source_ip: string (required)
  - target_ip: string | null
  - flow_data: NetworkFlowInput (fields below)
  - prediction: MLPrediction (fields below)
- Behavior: if `prediction.is_attack` is TRUE => create `SecurityAlert` record and broadcast.
- Response: { message, alert_id, severity, confidence }

Example request (single ML prediction -> create alert):

```http
POST /api/alerts/ml-prediction HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "resource_id": "demo-resource-0001",
  "source_ip": "192.0.2.10",
  "target_ip": "10.0.0.5",
  "flow_data": {
    "dst_port": 443,
    "flow_duration": 120.5,
    "tot_fwd_pkts": 10,
    "tot_bwd_pkts": 2,
    "fwd_pkt_len_max": 1500,
    "flow_pkts_s": 50.0
  },
  "prediction": {
    "is_attack": true,
    "attack_probability": 0.87,
    "benign_probability": 0.13,
    "confidence": 0.91,
    "model_version": "I-MPaFS-BeastMode-v2.0"
  }
}
```

Example response (200):

```json
{
  "message": "Alert created from ML prediction",
  "alert_id": "a1b2c3d4-...",
  "severity": "high",
  "confidence": 0.91
}
```

4. POST `/api/alerts/batch-ml-predictions`

- Body: array of `MLAlertRequest`
- Behavior: filter `is_attack` predictions then create alerts in bulk; schedule broadcasts.
- Response: { message, total_predictions, attack_predictions, alerts_created }

Example request (batch predictions):

```http
POST /api/alerts/batch-ml-predictions HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

[
  {
    "resource_id": "demo-resource-0001",
    "source_ip": "192.0.2.10",
    "flow_data": { "dst_port": 443, "flow_duration": 120.5, "tot_fwd_pkts": 10 },
    "prediction": { "is_attack": true, "attack_probability": 0.9, "confidence": 0.95, "model_version": "v2" }
  },
  {
    "resource_id": "demo-resource-0001",
    "source_ip": "192.0.2.11",
    "flow_data": { "dst_port": 80, "flow_duration": 8.2, "tot_fwd_pkts": 4 },
    "prediction": { "is_attack": false, "attack_probability": 0.1, "confidence": 0.2, "model_version": "v2" }
  }
]
```

Example response (200):

```json
{
  "message": "Processed 2 predictions, created 1 alerts",
  "total_predictions": 2,
  "attack_predictions": 1,
  "alerts_created": 1
}
```

5. PATCH `/api/alerts/{alert_id}/read` — mark single alert read
6. DELETE `/api/alerts/{alert_id}` — dismiss
7. PUT `/api/alerts/mark-all-read` — mark all read
8. GET `/api/alerts/stats` — aggregated counts & recent alerts count
9. POST `/api/alerts/generate-test-data` — dev/test helper

**NetworkFlowInput (fields)**

- dst_port: int
- flow_duration: float
- tot_fwd_pkts: int
- tot_bwd_pkts: int
- fwd_pkt_len_max: int
- fwd_pkt_len_min: int
- bwd_pkt_len_max: int
- bwd_pkt_len_mean: float
- flow_byts_s: float
- flow_pkts_s: float
- flow_iat_mean: float
- flow_iat_std: float
- flow_iat_max: float
- fwd_iat_std: float
- bwd_pkts_s: float
- psh_flag_cnt: int
- ack_flag_cnt: int
- init_fwd_win_byts: int
- init_bwd_win_byts: int
- fwd_seg_size_min: int

**MLPrediction (fields)**

- is_attack: bool
- attack_probability: float (0..1)
- benign_probability: float
- confidence: float
- model_version: string
- base_model_scores: object<string,float> | null
- explanation: object | null

---

**ML Integration (backend proxy) — Backend endpoints that call ML service**

Backend proxies for developer/test use live in `backend/app/api/ml_integration.py`.

1. POST `/api/ml/predict` (proxy)

- Auth: required
- Body: NetworkFlowData (same fields as NetworkFlowInput)
- Backend assembles request for ML service and posts to `http://ml-host:23333/predict` with a payload that includes `client_id` and `resource_id` (the backend should pass current user's id/metadata or accept them as fields). It returns ML response with extra user/timestamp.

Example request (proxy single flow):

```http
POST /api/ml/predict HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "dst_port": 443,
  "flow_duration": 120.5,
  "tot_fwd_pkts": 10,
  "flow_pkts_s": 50.0,
  "client_id": "demo-client-0001",
  "resource_id": "demo-resource-0001"
}
```

Example response (200):

```json
{
  "prediction": {
    "is_attack": true,
    "attack_probability": 0.87,
    "confidence": 0.91,
    "model_version": "I-MPaFS-BeastMode-v2.0"
  },
  "user_id": "user-uuid-0001",
  "timestamp": "2025-11-21T12:35:00Z"
}
```

2. POST `/api/ml/predict-batch`

- Auth: required
- Body: list of flows
- Backend forwards to ML `/predict/batch` and returns the batch result.

Example request (proxy batch):

```http
POST /api/ml/predict-batch HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "flows": [
    { "dst_port": 443, "flow_duration": 120.5, "tot_fwd_pkts": 10 },
    { "dst_port": 80, "flow_duration": 8.2, "tot_fwd_pkts": 4 }
  ],
  "include_confidence": true,
  "client_id": "demo-client-0001",
  "resource_id": "demo-resource-0001"
}
```

Example response (200):

```json
{
  "predictions": [
    { "is_attack": true, "attack_probability": 0.87, "confidence": 0.91, "model_version": "v2" },
    { "is_attack": false, "attack_probability": 0.05, "confidence": 0.2, "model_version": "v2" }
  ],
  "statistics": { "throughput_flows_per_sec": 1500.0 }
}
```

**ML Service (BEAST MODE) Contract** — for completeness (service runs separately)

- POST `/predict` — SinglePredictionRequest (flow, client_id, resource_id, timestamp)
  - Responds with `PredictionDetail` (see schema below).
- POST `/predict/batch` — BatchPredictionRequest (flows[], include_confidence, client_id, resource_id)
  - Responds with `BatchPredictionResponse` { predictions: [], statistics: {} }
- POST `/predict/buffered` — accepts single CICFlowMeter flow, buffers for batch.
- POST `/flush-buffer` — manually flush buffer.
- GET `/buffer-stats`, GET `/health/json`, GET `/performance/json`.
- WebSocket `/ws/live` — broadcasts raw prediction messages (non-persistent) with per-message: { message_id, timestamp, model_version, prediction, flow, client_id, resource_id }

**PredictionDetail (ML)**

- is_attack: boolean
- attack_probability: number
- benign_probability: number
- confidence: number
- model_version: string
- base_model_scores: map<string,number>
- explanation: object

---

**WebSockets (Realtime)**

Base path: `/ws` (backend); `/ws/live` for ML service.

1. Backend WebSocket: `/ws/alerts/{user_id}`

- Query: `token` (required)
- Flow:
  - On connect: server sends { type: "initial_alerts", data: [Alert], timestamp }
  - New alert broadcast: { type: "new_alert", data: { id, severity, title, description, source_ip, target_port, confidence, detected_at, status, attack_type } }
  - Resource selection messages from client: { type: "resource_selected", resource_id }

WebSocket examples:

Handshake (client connects):

```
ws://api.example.com/ws/alerts/{user_id}?token=<jwt>
```

Server -> client (initial alerts):

```json
{
  "type": "initial_alerts",
  "data": [
    {
      "id": "a1b2",
      "severity": "high",
      "title": "ML-Detected DDoS",
      "description": "...",
      "source_ip": "198.51.100.5",
      "detected_at": "2025-11-21T12:34:56Z"
    }
  ],
  "timestamp": "2025-11-21T12:35:00Z"
}
```

Server -> client (new alert):

```json
{
  "type": "new_alert",
  "data": {
    "id": "a1b2c3d4",
    "severity": "critical",
    "title": "ML-Detected DDoS Attack",
    "description": "High packet rate detected",
    "source_ip": "198.51.100.5",
    "target_port": 443,
    "confidence": 0.95,
    "detected_at": "2025-11-21T12:36:00Z",
    "status": "new",
    "attack_type": "ddos"
  }
}
```

Client -> server (resource selection):

```json
{ "type": "resource_selected", "resource_id": "demo-resource-0001" }
```

2. Backend other sockets: `/ws/metrics/{user_id}`, `/ws/network/{user_id}` with `token`.

3. ML `/ws/live` broadcasts raw predictions for live monitoring. These messages are non-persistent; backend should persist only via the ML -> Redis -> backend consumer pipeline (recommended).

**Recommended WebSocket topic naming for Spring**

- `/topic/alerts` — global
- `/user/{userId}/queue/alerts` — per-user

---

**Network API** (Base: `/api/network`)

- GET `/api/network/traffic/real-time` — returns `arcs` and `points` arrays
- GET `/api/network/threats/locations`
- GET `/api/network/connections/active`
- GET `/api/network/stats`
- POST `/api/network/traffic` — add traffic for testing
- GET `/api/network/locations`

Example request (real-time traffic):

```http
GET /api/network/traffic/real-time HTTP/1.1
Host: api.example.com
Authorization: Bearer <jwt>
```

Example response (200):

```json
{
  "arcs": [
    {
      "id": "arc1",
      "startLat": 40.7,
      "startLng": -74.0,
      "endLat": 51.5,
      "endLng": -0.12,
      "isAttack": true,
      "timestamp": "2025-11-21T12:30:00Z"
    }
  ],
  "points": [{ "lat": 40.7, "lng": -74.0, "label": "New York - Threat", "isAttack": true }],
  "timestamp": "2025-11-21T12:35:00Z",
  "total_connections": 12,
  "active_threats": 3
}
```

Example request (add traffic - test):

```http
POST /api/network/traffic HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{ "startLat": 40.7, "startLng": -74.0, "endLat": 51.5, "endLng": -0.12, "isAttack": false }
```

Example response (201):

```json
{ "status": "traffic_added", "id": "arc-uuid-1234" }
```

**Resource API** (Base: `/api/resources`)

- GET `/api/resources` (search/status/health)
- GET `/api/resources/providers`
- GET `/api/resources/types`
- POST `/api/resources` — create resource (ResourceCreate)
- GET `/api/resources/{resource_id}`
- PUT `/api/resources/{resource_id}`
- DELETE `/api/resources/{resource_id}`
- GET `/api/resources/stats/summary`

Example request (create resource):

```http
POST /api/resources HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "name": "web-server-1",
  "resource_type_id": "type-uuid-1",
  "cloud_provider_id": "provider-uuid-1",
  "region": "us-east-1",
  "instance_type": "t3.medium",
  "os_type": "ubuntu"
}
```

Example response (201):

```json
{ "id": "resource-uuid-1", "name": "web-server-1", "status": "active", "message": "Resource created successfully" }
```

Example request (list resources):

```http
GET /api/resources?search=web-server HTTP/1.1
Host: api.example.com
Authorization: Bearer <jwt>
```

Example response (200):

```json
[
  {
    "id": "resource-uuid-1",
    "name": "web-server-1",
    "type": "ec2",
    "os": "ubuntu",
    "status": "active",
    "region": "us-east-1"
  }
]
```

**Metrics API** (Base: `/api/metrics`)

- GET `/api/metrics/system`
- GET `/api/metrics/network`
- GET `/api/metrics/threats`
- GET `/api/metrics/dashboard`
- GET `/api/metrics/time-series?timerange=`
- GET `/api/metrics/alerts/timeline`

Example request (system metrics):

```http
GET /api/metrics/system HTTP/1.1
Host: api.example.com
Authorization: Bearer <jwt>
```

Example response (200):

```json
{
  "timestamp": "2025-11-21T12:35:00Z",
  "system": { "cpu_usage": 62, "memory_usage": 70, "disk_usage": 45, "network_io": 210.5 }
}
```

Example request (dashboard metrics):

```http
GET /api/metrics/dashboard HTTP/1.1
Host: api.example.com
Authorization: Bearer <jwt>
```

Example response (200):

```json
{
  "timestamp": "2025-11-21T12:35:00Z",
  "active_threats": 3,
  "blocked_attacks": 120,
  "total_requests": 1500,
  "network_traffic": "1.5TB"
}
```

**Logs API** (Base: `/api/logs`)

- GET `/api/logs/recent?limit=`
- GET `/api/logs?level=&source=&limit=`
- POST `/api/logs`
- DELETE `/api/logs`
- GET `/api/logs/sources`
- GET `/api/logs/levels`
- GET `/api/logs/stats`

Example request (recent logs):

```http
GET /api/logs/recent?limit=5 HTTP/1.1
Host: api.example.com
Authorization: Bearer <jwt>
```

Example response (200):

```json
[{ "id": "1", "timestamp": "12:34:00", "level": "INFO", "message": "User login", "source": "auth_system" }]
```

Example request (create log):

```http
POST /api/logs HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <jwt>

{ "level": "info", "message": "Background job completed", "source": "scheduler" }
```

Example response (201):

```json
{ "message": "Log created successfully", "id": "log-uuid-123" }
```

**Settings API** (Base: `/api/settings`)

- GET `/api/settings`, GET specific sections
- PUT to update sections
- POST `/api/settings/reset` and `/api/settings/reset/{section}`
- GET `/api/settings/schema`

---

**Database Model Mappings (key tables)**
Source: `backend/app/models/database.py` — map these to JPA entities.

1. `security_alerts` -> entity `SecurityAlert`

- id (UUID PK)
- user_id (UUID FK)
- resource_id (UUID FK)
- type, category, severity, title, description
- source_ip, target_ip, target_port
- detection_method
- confidence_score (DECIMAL(5,2)) — stored as percent 0.00–100.00
- raw_data (JSONB) — store the complete ML message and flow
- detected_at (timestamp)
- status (enum: new/investigating/acknowledged/resolved/false_positive)

2. `user_resources` -> entity `UserResource`

- id (UUID), user_id (UUID), resource_id (string unique per user), name
- region, instance_type, os_type, status, tags (json)

Mapping guidance for Spring JPA:

- Use `@Entity` with `UUID` type for PKs. Use `@Column(columnDefinition = "jsonb")` for Postgres JSON fields or map to `Map<String,Object>` with `@Type` (Hibernate Types) or `JsonNode`.
- Add indexes on `detected_at`, `severity`, `user_id`, `resource_id`.

---

**Recommended Redis Pub/Sub design (ML → Backend)**

Producer: ML service publishes each prediction to channel `ml:predictions`.

Message schema (JSON):

```json
{
  "message_id": "<uuid>",
  "timestamp": "2025-11-21T00:00:00Z",
  "client_id": "demo-client-0001",
  "resource_id": "demo-resource-0001",
  "flow": {
    /* original flow fields or Beast-format features */
  },
  "prediction": {
    /* MLPrediction object */
  },
  "source": "beast_mode_api"
}
```

Consumer semantics (backend):

- Run a long-running Redis subscriber (or use Redis Streams for reliability).
- For each message: validate required fields (`client_id`, `resource_id`, `prediction`).
- If `prediction.is_attack == true` -> create `SecurityAlert`:
  - Map `resource_id` -> `UserResource` to obtain `user_id`.
  - Fill `raw_data` with the entire message JSON.
  - Set `confidence_score` = `prediction.confidence * 100`.
  - Compute `severity` using backend algorithm (`_calculate_severity`).
  - Save and broadcast to WebSocket topics.
- If `is_attack == false`: do not persist (unless a flag enables persistence).

Advantages: decouples ML service from DB persistence and lets backend scale processing reliably.

---

**Examples**

Single ML predict (to ML service):

```json
{
  "flow": {
    /* NetworkFlow fields (see above) */
  },
  "client_id": "demo-client-0001",
  "resource_id": "demo-resource-0001",
  "timestamp": "2025-11-21T00:00:00Z"
}
```

Redis publish (ML -> backend): example shown earlier in "Recommended Redis Pub/Sub".

---

**Migration Notes & Implementation Suggestions for Spring Boot**

Controllers & DTOs:

- Create DTOs matching Pydantic models (NetworkFlow, SinglePredictionRequest, BatchPredictionRequest, PredictionDetail, MLAlertRequest, MLPrediction).
- Controllers:
  - `AlertsController` -> `/api/alerts`
  - `MlProxyController` -> `/api/ml` (proxies to ML service)
  - `ResourcesController`, `MetricsController`, `NetworkController`, `LogsController`, `SettingsController`

Services:

- `MlProxyService` — forward requests to ML (use `WebClient` for non-blocking)
- `RedisConsumerService` — subscribe to `ml:predictions` (prefer Redis Streams)
- `AlertService` — DB persistence & broadcast
- `RealtimeService` — WebSocket + STOMP

Datastore:

- Use Postgres; map JSON columns as `jsonb`.
- Use Flyway or Liquibase for schema migration.

WebSockets:

- Use Spring WebSocket + STOMP for topic management.
- Validate JWT at handshake using a `HandshakeInterceptor`.
- Topics: `/topic/alerts`, `/user/{userId}/queue/alerts`.

Background/Concurrency:

- Use `@Async` thread pool for heavy tasks. Use `TaskExecutor` for bursts.
- For high-throughput ML ingestion: prefer Redis Streams + consumer groups for scaling and reliable processing.

Observability & Health:

- Expose `/actuator/health`, `/actuator/metrics`.
- Export metrics to Prometheus; collect throughput, attack rates, and processing latency.

Security:

- Enforce rate limiting and input validation on ML endpoints. Return `429` if overloaded.
- Sanitize and limit `raw_data` length stored in DB.

---

**Acceptance Tests (recommended)**

1. Integration test — end-to-end:

- Start Redis, start ML service, start backend consumer.
- POST BatchPredictionRequest (5 flows) to ML `/predict/batch` with `client_id` & `resource_id`.
- Validate that backend receives Redis messages, persists expected `SecurityAlert` rows for `is_attack` flows, and broadcasts them on WebSocket.

2. Unit tests:

- `MlMessageHandler` parses prediction message -> constructs `SecurityAlert` DTO.
- `AlertService` persists alert -> result contains correct mapping and `raw_data` JSON.

3. Contract tests:

- OpenAPI generated schema imported into Spring and verify controllers satisfy request/response DTOs.

---

**Frontend (Next.js) Spec & Endpoint Mapping**

Purpose: define every Next.js page, the UI components and data to show, and the backend APIs (and WebSocket interactions) required to support the UI. The repository already uses Next.js App Router (see `app/`), so the recommendations below use Server Components for initial data fetches and Client Components for interactive/real-time parts.

Design principles

- Use Server Components for pages that render primarily on the server (dashboard initial loads, resource lists) and Client Components for interactive controls (filters, modals, charts).
- Use React Query or SWR for client caching, deduping, and background refresh of API data.
- Use WebSockets for high-frequency updates (alerts live feed, network arcs), and fall back to polling for low-priority data.
- Keep auth centralized: a client-side `AuthProvider` wrapping the app obtains a Supabase JWT (via existing auth flow) and injects `Authorization` headers for all API calls and `token` query on WebSocket connections.
- Keep accessibility & performance in mind: lazy-load heavy visualizations (globe, charts), add skeleton placeholders, and monitor real-user metrics.

Pages & UI routes (Next.js) — data & endpoints

- `/login` (Client page)

  - Purpose: standard login / social sign-in via Supabase. Redirect to `/dashboard` on success.
  - Data: form + third-party provider callback handling.
  - Backend calls: `POST /api/auth/login` (if backend handles exchange) or direct Supabase client flow.

- `/dashboard` (Server Component for initial render + Client components)

  - Purpose: high-level overview: active threats, recent alerts, key metrics, network map snapshot.
  - Data to show:
    - `GET /api/metrics/dashboard` → dashboard cards (active_threats, blocked_attacks, total_requests)
    - `GET /api/alerts?limit=10&read=false` → recent alerts list
    - `GET /api/network/traffic/real-time` (initial snapshot)
  - Realtime: subscribe to `/ws/alerts/{user_id}` for alert broadcasts and `/ws/network/{user_id}` for live network arcs.
  - Components: `MetricsCards`, `RecentAlertsList`, `NetworkGlobePreview`, `MLLiveMini` (mini live feed widget).

- `/dashboard/analytics` (Server + heavy Client components)

  - Purpose: drill-down analytics charts and historical metrics.
  - Data to show:
    - `GET /api/metrics/time-series?timerange=` → timeseries for charts
    - `GET /api/metrics/alerts/timeline` → alerts timeline
  - Components: `TimeSeriesChart`, `AlertsHistogram`, `FilterControls` (time ranges, resources).

- `/alerts` (Server initial list, Client interactive)

  - Purpose: full alerts list with filtering, search, pagination, and bulk actions.
  - Data & API calls:
    - `GET /api/alerts?level=&read=&limit=&offset=` — server-side initial load + client-side pagination
    - `PATCH /api/alerts/{alert_id}/read` — mark read
    - `PUT /api/alerts/mark-all-read` — bulk mark
    - `DELETE /api/alerts/{alert_id}` — dismiss
    - `GET /api/alerts/stats` — top summary stats
  - Realtime: open WebSocket `/ws/alerts/{user_id}?token=` to receive `new_alert` messages and optimistically insert to UI.
  - Components: `AlertsTable`, `AlertDetailDrawer` (or page `/alerts/[id]`), `AlertsFilterBar`.

- `/alerts/[id]` (Server Component for initial render)

  - Purpose: detailed alert view and investigation tools.
  - Data & API calls:
    - `GET /api/alerts/{alert_id}` — full alert record (including `raw_data`) for display
    - `GET /api/resources/{resource_id}` — link to resource details
    - `POST /api/alerts/generate-test-data` — dev-only if reproducing
  - Components: `AlertHeader`, `RawDataViewer` (JSON viewer with copy), `RelatedFlowsList`.

- `/ml/live-monitor` (Client-heavy)

  - Purpose: live stream of raw ML predictions (non-persistent) for operators.
  - Data & Realtime:
    - Connect to ML service WebSocket `ws://ml-host:23333/ws/live` (or backend proxy `/ws/ml/live`) — messages shaped as `{ message_id, timestamp, model_version, prediction, flow, client_id, resource_id }`.
    - Optionally enable `subscribe` filters (resource_id, model_version) and client-side highlight for `prediction.is_attack`.
  - Backend calls: none required for raw stream, but include `POST /api/ml/predict` examples to test single flows.
  - Components: `LiveStreamList`, `PredictionInspector`, `ModelPerformancePanel`.

- `/network` and subroutes (Server initial render)

  - Purpose: interactive world map / arcs and connections.
  - Data & APIs:
    - `GET /api/network/traffic/real-time` — initial arcs/points
    - `GET /api/network/connections/active` — active connections list
    - WebSocket `/ws/network/{user_id}` for live arc updates
  - Components: `NetworkMap`, `ConnectionsPanel`, `GeoThreatList`.

- `/resources` (Server list + client interactions)

  - Purpose: list, create, edit resources that are monitored
  - APIs:
    - `GET /api/resources?search=&limit=&offset=`
    - `POST /api/resources` — create
    - `GET /api/resources/{resource_id}` — details
    - `PUT /api/resources/{resource_id}` — update
    - `DELETE /api/resources/{resource_id}` — delete
  - Components: `ResourcesTable`, `ResourceFormModal`, `ResourceHealthCard`.

- `/settings` and `/profile`

  - Purpose: user and system settings management
  - APIs:
    - `GET /api/settings`, `PUT /api/settings`
    - `GET /api/settings/schema`
    - `GET/PUT /api/users/{user_id}/profile` (if present)

- `/logs` (Server list with search)
  - Purpose: view application logs, filter by source/level, link to alerts
  - APIs:
    - `GET /api/logs/recent?limit=`
    - `GET /api/logs?level=&source=&limit=&offset=`
    - `GET /api/logs/sources` and `/api/logs/levels`
  - Components: `LogsTable`, `LogFilters`, `LogDetailPane`.

Client Components & shared utilities

- `AuthProvider` — provides JWT, silent refresh, and `useAuth()` hook.
- `ApiClient` — wrapper around `fetch` or `WebClient` that attaches `Authorization` header and handles 401/refresh logic.
- `useWebSocket` hook — standardized connection lifecycle and reconnection logic, supports subscriptions and message parsing.
- `useRealtimeAlerts` — subscribes to `/ws/alerts/{user_id}` and exposes `initial` + `new_alert` messages.
- `Table`, `Paginator`, `SearchBar`, `FilterChip`, `Modal`, `Drawer`, `JsonViewer` — standard UI primitives to reuse across pages.

Data paging, filtering & caching rules

- Always support server-side pagination (`limit`/`offset`) for lists (alerts, logs, resources). Use cursor pagination for very large lists as an enhancement.
- Use `stale-while-revalidate` semantics for metrics and non-critical lists; use optimistic updates for quick actions (mark read/dismiss) with retry on failure.

WebSocket & real-time details (client-side)

- Alerts socket: `ws://api.example.com/ws/alerts/{user_id}?token=<jwt>`
  - Messages:
    - `initial_alerts`: array for initial hydration
    - `new_alert`: single alert object to insert
  - Client behavior:
    - On `initial_alerts`, replace list if local list empty; otherwise dedupe by `id`.
    - On `new_alert`, show top-of-list toast/notification and insert at top.
- ML live socket: `ws://ml-host:23333/ws/live` or backend proxied at `/ws/ml/live`
  - Client: streaming monitor only (no persistence). Allow toggling `highlight=true` for `is_attack` messages.

Backend endpoints required (summary mapping)

- Alerts: `GET /api/alerts`, `GET /api/alerts/{id}`, `PATCH /api/alerts/{id}/read`, `PUT /api/alerts/mark-all-read`, `DELETE /api/alerts/{id}`, `POST /api/alerts/ml-prediction`, `POST /api/alerts/batch-ml-predictions`.
- ML proxy & test: `POST /api/ml/predict`, `POST /api/ml/predict-batch` (include required `client_id` and `resource_id` fields in forwarded payloads).
- Metrics: `GET /api/metrics/*` endpoints used by dashboard and analytics.
- Network: `GET /api/network/*` and `POST /api/network/traffic` (test)
- Resources: CRUD endpoints (`/api/resources`)
- Logs: `GET /api/logs*`, `POST /api/logs`

Recommended infra & data stores for the frontend & backend

- Postgres: primary relational store (already used) for `security_alerts`, `user_resources`, users, and metadata.
- Redis: caching layer + Pub/Sub for ML → backend ingestion (channel `ml:predictions`), and use Redis for short-term caching of high-frequency queries (recent alerts count, leaderboard).
- Time-series DB (optional): TimescaleDB or InfluxDB for high-write metrics (if metrics ingestion grows). Alternatively store metrics in Postgres with downsampled tables.
- Search & logs (optional): Elasticsearch or OpenSearch for full-text search & log analytics if logs volume is high.

Observability & monitoring (frontend & backend)

- Frontend: instrument with RUM (e.g., Sentry, Datadog RUM) for performance and errors; track WebSocket uptime and reconnects.
- Backend: Prometheus metrics, Grafana dashboards, set alerts for consumer lag (Redis Streams or Pub/Sub), DB slow queries, and average processing latency for ML messages.

Developer UX & testing

- Provide a `test-data` admin page (dev-only) that posts to `POST /api/alerts/generate-test-data` and `POST /api/ml/predict` to exercise the pipeline.
- Provide a mocked WebSocket endpoint for local dev to simulate `new_alert` and ML live messages.
- Write contract tests using the OpenAPI YAML to ensure frontend DTOs and backend controllers remain compatible.

Security & rate-limiting for ML endpoints

- Enforce `client_id` and `resource_id` on ML endpoints (both proxy and ML service) and rate-limit `POST /api/ml/predict` and `/predict/batch` to prevent abuse.

Acceptance criteria for UI readiness

- Dashboard initial paint under 1s for cached UX; progressive hydration for large components.
- Alerts list supports filter + pagination and shows new incoming alerts within 2 seconds of backend broadcast.
- ML live-monitor shows continuous stream without blocking UI and supports pausing/resuming the stream.

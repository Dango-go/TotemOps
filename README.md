# TotemOps — Cloud-Native Microservices Platform

TotemOps is an enterprise-grade cloud-native food delivery platform (similar to Uber Eats / Glovo) built with **FastAPI (Python 3.12+)**, **PostgreSQL (SQLAlchemy 2.0)**, and Kubernetes-native health probes.

---

## 🏛️ Applications

| Service | Port | Database | Description |
| :--- | :--- | :--- | :--- |
| `identity` | 8001 | PostgreSQL (`users`) | User registration, authentication, bcrypt password hashing, and JWT token issuance/verification. |
| `catalog` | 8002 | PostgreSQL (`restaurants`, `menu_items`) | Restaurant store directory, menu management, category listings, and item search. |
| `pricing` | 8003 | Stateless | Dynamic delivery fee calculation, surge demand multipliers, and discount promo codes (`TOTEM10`). |
| `cart` | 8004 | In-Memory (Redis-ready) | Shopping cart management, item quantity updates, and cart subtotal calculation. |
| `inventory` | 8005 | PostgreSQL (`stock_items`, `reservations`) | Menu item stock tracking, reservation locking during checkout, and stock release/commit. |
| `payment` | 8006 | PostgreSQL (`payments`) | Payment processing with idempotency keys, authorization, capture, and refund handling. |
| `eta` | 8007 | Stateless | Distance-based preparation and delivery time estimations between restaurant and delivery address. |
| `geo-tracking` | 8008 | In-Memory (Redis-ready) | Real-time GPS coordinate telemetry ingestion and live courier location tracking. |
| `dispatch` | 8009 | In-Memory | Courier matching algorithms, order assignment, acceptance, and fleet status dispatching. |
| `fraud` | 8010 | Stateless | Transaction risk assessment engine evaluating order amounts and payment flags (`ALLOW`, `CHALLENGE`, `REJECT`). |
| `notification` | 8011 | Stateless | Dispatching push notifications and SMS alert simulations for order milestones. |
| `review` | 8012 | PostgreSQL (`reviews`) | Post-delivery ratings (1-5 stars) and review submissions for restaurants and couriers. |
| `analytics-sink` | 8013 | PostgreSQL (`analytics_events`) | Centralized audit log sink and analytical event ingestion pipeline. |
| `order` | 8014 | PostgreSQL (`orders`, `order_items`) | Core distributed Saga orchestrator managing order lifecycle from placement to fulfillment. |
| `bff-merchant` | 8020 | Gateway / BFF | Merchant portal gateway for restaurant order queue inspection and cooking status updates. |
| `bff-courier` | 8021 | Gateway / BFF | Courier portal gateway for assignment acceptance, order delivery completion, and live GPS streaming. |
| `bff-customer` | 8022 | Gateway / BFF | Customer-facing API aggregating catalog search, cart operations, checkout Saga, and live order tracking. |

---

## 🩺 Health & Readiness Probes

All 17 microservices implement standardized Kubernetes-native probes:

- **Liveness Probe (`GET /healthz`)**:
  - Verifies that the Python process is alive, running, and accepting HTTP requests.
  - Returns `200 OK` with service name and `uptime_seconds`.
- **Readiness Probe (`GET /readyz`)**:
  - For persistence services: executes an active `SELECT 1` ping via the SQLAlchemy engine.
  - If the database connection drops or is not yet initialized, returns `503 Service Unavailable` with `not_ready` status.
  - Prevents Kubernetes Ingress and Service mesh from routing traffic to pods before DB connectivity is established.

---

## 🐘 PostgreSQL Integration

Services utilize the `DATABASE_URL` environment variable:
- **Local development fallback**: Defaults to `sqlite:///./<service>.db` if no database URL is supplied.
- **PostgreSQL connection**:
  ```bash
  export DATABASE_URL="postgresql+psycopg://totem:totem_secret_password@localhost:5432/totemops"
  ```

### Start PostgreSQL locally via Docker:
```bash
docker compose up -d postgres
```

---

## 🚀 Running & Testing

### 1. Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run End-to-End Smoke Test:
Runs all 17 microservices concurrently, verifies `/healthz` and `/readyz`, executes a full customer checkout and courier delivery cycle, and shuts down cleanly:
```bash
python scripts/smoke_test.py
```

### 3. Build Docker container for any service:
The root `Dockerfile` accepts the `SERVICE` build argument:
```bash
docker build --build-arg SERVICE=order -t totemops-order:latest .
docker build --build-arg SERVICE=bff-customer -t totemops-bff-customer:latest .
```
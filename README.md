# TotemOps — Cloud-Native Microservices Platform
# Classical DevOps sandbox project

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


## 🔐 Technical & Security Highlights

- **AWS IAM Roles for Service Accounts (IRSA / Pod Identity)**: Використання OpenID Connect (OIDC) для авторизації робочих навантажень (Jenkins, External Secrets, Ingress Controller) в AWS без збереження довгоживучих ключів (`AWS_ACCESS_KEY_ID`).
- **Zero-Trust Networking**: Підтримка Service Mesh (Istio mTLS STRICT) та eBPF мережевих політик (Cilium).
- **Shift-Left DevSecOps**: Повна автоматизація перевірок коду, залежностей, образів та Kubernetes-маніфестів до моменту деплою у кластер.

---

## 🛠️ CI/CD & GitOps Architecture

Платформа використовує розділений конвеєр доставки: **Atlantis** для інфраструктури, **Jenkins** для збірки й тестування, та **Argo CD** для безпосередньої доставки в Kubernetes.

```mermaid
graph LR
    Dev[Developer] -->|git push| Git[GitHub Monorepo]
    
    subgraph "IaC Pipeline"
        Git -->|PR hook| Atl[Atlantis]
        Atl -->|terragrunt plan/apply| EKS[AWS EKS Clusters]
    end
    
    subgraph "Application CI (Jenkins)"
        Git -->|webhook| Jnk[Jenkins Controller]
        Jnk -->|ephemeral pod| Agent[K8s Agent]
        Agent -->|1. Detect & SAST| Sast[Gitleaks & Semgrep]
        Agent -->|2. Build & Scan| Img[BuildKit & Trivy]
        Agent -->|3. Sign Image| Cosign[Cosign + AWS KMS]
        Agent -->|4. Push Image| ECR[AWS ECR / Harbor]
        Agent -->|5. Update Tag| GitOpsRepo[Git: cluster/apps/overlays/*]
    end
    
    subgraph "Application CD (Argo CD)"
        GitOpsRepo -->|GitOps Pull| Argo[Argo CD]
        Argo -->|Sync & Self-Heal| Stage[EKS Stage Cluster]
        Argo -->|Sync & Rollouts| Prod[EKS Prod Cluster]
    end
```

### 1. IaC Automation (Atlantis)
- **Terraform & Terragrunt** управління трьома ізольованими середовищами (`mgmt`, `stage`, `prod`).
- Pull Request Workflow через **Atlantis**: виконання `atlantis plan` та `atlantis apply` безпосередньо з коментарів до PR.
- Автоматична валідація коду інфраструктури: `tflint`, безпековий аудит `checkov` та прогнозування витрат через `infracost`.

### 2. CI Engine (Jenkins DevSecOps Pipeline)
Jenkins розгорнутий у менеджмент-кластері з конфігурацією як код (**JCasC**) та **Kubernetes Plugin**, що динамічно запускає ізольовані (ephemeral) воркер-поди під кожен білд.

8-етапний DevSecOps конвеєр:
1. **Detect Changes**: смарт-визначення змінених мікросервісів у monorepo (`git diff`).
2. **Secret Detection & SAST**: детекція захардкодretux секретів через `Gitleaks` та статичний аналіз вразливостей коду через `Semgrep`.
3. **Dependency Scanning & SBOM**: перевірка CVE у бібліотеках (`pip-audit`) та генерація Software Bill of Materials (`Syft`).
4. **Lint & Unit Tests**: статична типізація, лінтинг коду та проходження тестів FastAPI (`pytest`).
5. **Containerization**: безпечна rootless multi-stage збірка образів (`BuildKit`).
6. **Image Vulnerability Scan & Signing**: сканування контейнера на CVE (`Trivy`) та накладання криптографічного цифрового підпису через `Cosign` із використанням ключів AWS KMS.
7. **Manifest Validation**: валідація Kubernetes-маніфестів проти OpenAPI схем (`kubeconform`) та перевірка security best practices (`kube-linter`).
8. **GitOps Manifest Update**: автоматичний комміт оновленого ECR-тегу (`newTag`) у відповідний Kustomize-оверлей (`cluster/apps/overlays/stage/kustomization.yaml`).

### 3. CD Engine (Argo CD & GitOps)
Доставка та синхронізація стану кластера реалізовані за принципами декларативного **GitOps**:
- **Argo CD** розгорнутий у `totemops-mgmt-eks` та здійснює pull-модель доставки у цільові середовища (`stage`, `prod`).
- **Kustomize Structure**:
  - `cluster/apps/base/`: уніфіковані шаблони microservices (Deployment, Service, ConfigMap).
  - `cluster/apps/overlays/stage/`: оверлей стейджингу (неймспейс `totem-stage`, ECR-теги, змінні середовища).
  - `cluster/apps/overlays/prod/`: оверлей продакшну (неймспейс `totem-prod`, high availability конфігурації, ліміти ресурсів).
- **Automated Sync & Self-Healing**: Argo CD автоматично виявляє зміни в Git після завершення CI, застосовує дельти, усуває дрифт конфігурації (`selfHeal: true`) та видаляє неактуальні ресурси (`prune: true`).
- **Zero-Downtime Releases**: інтеграція з **Argo Rollouts** для прогресивного розгортання трафіку (Canary / Blue-Green) у зв'язці з Istio Service Mesh.


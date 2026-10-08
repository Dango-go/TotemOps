# План реалізації мікросервісного застосунку (17 сервісів)

Цей документ визначає покроковий план створення чистого, робочого ядра застосунку для проєкту **totemops** без шару інфраструктури (без Envoy/Gateway, без Kafka та без метрик/трейсингу на цьому етапі). 

Мета: отримати повністю функціональну бізнес-систему на **Go** та **Python (FastAPI)**, де сервіси спілкуються між собою через **gRPC** та **REST**, мають робочі сховища (PostgreSQL / Redis / In-memory fallback), готові до майбутнього підключення event streaming (Kafka), OpenTelemetry та Istio Service Mesh.

---

## 0. Базовий рівень: Схеми контрактів та спільні бібліотеки

Перед написанням сервісів необхідно закласти фундамент типізації та контрактів:

1. **`proto/` (Protobuf + Buf)**:
   * Опис gRPC інтерфейсів для всіх сервісів:
     * `identity/v1/identity.proto`
     * `catalog/v1/catalog.proto`
     * `pricing/v1/pricing.proto`
     * `cart/v1/cart.proto`
     * `order/v1/order.proto`
     * `payment/v1/payment.proto`
     * `inventory/v1/inventory.proto`
     * `dispatch/v1/dispatch.proto`
     * `geo/v1/geo.proto`
     * `eta/v1/eta.proto`
     * `notification/v1/notification.proto`
     * `fraud/v1/fraud.proto`
   * Налаштування `buf.yaml` та `buf.gen.yaml` для генерації коду під Go та Python.
   * Згенеровані структури в `gen/go` та `gen/python`.

2. **`libs/` (Мінімальні спільні модулі)**:
   * `libs/go/common`: конфігурація з ENV, утиліти gRPC сервера/клієнта, healthcheck handler (`grpc.health.v1`), базове структуроване логування (zerolog/slog).
   * `libs/python/common`: Pydantic базові конфіги, gRPC клієнтські хелпери, логування.

---

## 1. Черговість реалізації сервісів

Черговість побудована за принципом **знизу вгору (від базових доменів до оркестраторів і BFF)**, щоб кожен наступний сервіс міг взаємодіяти з уже створеними.

```
[Рівень 1: Базові сервіси даних]
  ├── 1. identity (Python, gRPC)
  ├── 2. catalog (Python, gRPC)
  ├── 3. pricing (Python, gRPC)
  └── 4. cart (Python, gRPC)
        │
[Рівень 2: Операції, логістика та супутні домени]
  ├── 5. inventory (Python, gRPC)
  ├── 6. payment (Python, gRPC)
  ├── 7. eta (Python, gRPC)
  ├── 8. geo-tracking (Python, gRPC stream)
  ├── 9. dispatch (Python, gRPC)
  ├── 10. fraud (Python, gRPC)
  ├── 11. notification (Python, gRPC)
  ├── 12. review (FastAPI, REST)
  └── 13. analytics-sink (Python, gRPC)
        │
[Рівень 3: Доменний оркестратор]
  └── 14. order (FastAPI, gRPC + REST)
        │
[Рівень 4: BFF (Backend-For-Frontend)]
  ├── 15. bff-merchant (FastAPI, REST)
  ├── 16. bff-customer (FastAPI, REST -> gRPC)
  └── 17. bff-courier (FastAPI, WebSocket + REST)
```

> **Примітка**: `edge-gateway` (Envoy / Istio Ingress Gateway), як і Apache Kafka та OpenTelemetry метрики/трейсинг, реалізуються на інфраструктурному етапі. Зараз фокусуємося на 17 прикладних мікросервісах.

---

### Рівень 1: Базові сервіси даних та довідників

#### 1. `identity` (Go, gRPC)
* **Призначення**: Реєстрація, автентифікація, видача та валідація JWT (Access/Refresh), управління ролями (`customer`, `courier`, `merchant`, `admin`).
* **Сховище**: PostgreSQL (користувачі, хеші паролів bcrypt).
* **API**: `Register`, `Login`, `VerifyToken`, `GetUserProfile`.

#### 2. `catalog` (Go, gRPC)
* **Призначення**: Довідник ресторанів, категорій, страв, цін та модифікаторів.
* **Сховище**: PostgreSQL (структура меню) + інтерфейс для пошуку.
* **API**: `GetRestaurant`, `ListRestaurants`, `GetMenu`, `SearchItems`.

#### 3. `pricing` (Python, gRPC)
* **Призначення**: Розрахунок кінцевої вартості замовлення з урахуванням доставки, промокодів, сервісного збору та динамічного попиту (surge).
* **Сховище**: Redis (кешування зон і коефіцієнтів surge).
* **API**: `CalculateOrderPrice`, `GetDeliveryFee`.

#### 4. `cart` (Go, gRPC)
* **Призначення**: Зберігання та модифікація кошика клієнта з авто-очищенням за TTL.
* **Сховище**: Redis (Key-Value/Hash за `user_id`).
* **API**: `GetCart`, `AddItem`, `RemoveItem`, `ClearCart`.

---

### Рівень 2: Операційні та допоміжні сервіси

#### 5. `inventory` (Python, gRPC)
* **Призначення**: Облік доступності страв/інгредієнтів у ресторані, блокування та резервування залишків.
* **Сховище**: PostgreSQL (залишки на складі).
* **API**: `CheckStock`, `ReserveStock`, `ReleaseStock`, `CommitStock`.

#### 6. `payment` (Go, gRPC)
* **Призначення**: Фінансовий процесинг, double-entry ledger, сувора перевірка ідемпотентності транзакцій.
* **Сховище**: PostgreSQL (рахунки, проведення платежів, журнал транзакцій).
* **API**: `AuthorizePayment`, `CapturePayment`, `RefundPayment`, `GetBalance`.

#### 7. `eta` (Python, gRPC)
* **Призначення**: Розрахунок орієнтовного часу приготування та доставки на основі завантаженості ресторану і дистанції.
* **Сховище**: Redis (кеш матриці відстаней та завантаженості).
* **API**: `EstimateDeliveryTime`.

#### 8. `geo-tracking` (Go, gRPC Streaming)
* **Призначення**: Прийом потоку геокоординат від кур'єрів, збереження треків, віддача поточних координат.
* **Сховище**: In-memory / Redis GEO (швидкий lookup останньої точки кур'єра).
* **API**: `StreamCourierLocation` (Client Stream), `GetCourierLocation`.

#### 9. `dispatch` (Go, gRPC)
* **Призначення**: Пошук та призначення найближчого вільного кур'єра на замовлення з урахуванням гео-індексів.
* **Сховище**: Redis GEO (просторові радіальні запити `GEOSEARCH`).
* **API**: `FindCourierForOrder`, `AssignCourier`, `AcceptAssignment`.

#### 10. `fraud` (Python, gRPC)
* **Призначення**: Перевірка підозрілої активності клієнтів і транзакцій (антифрод-скоринг).
* **Сховище**: PostgreSQL / In-memory правила (чорні списки, ліміти спроб).
* **API**: `EvaluateTransactionRisk`.

#### 11. `notification` (Go, gRPC)
* **Призначення**: Шаблонізація та відправка сповіщень (Push/SMS/Email) клієнтам, кур'єрам і ресторанам.
* **Сховище**: Redis / In-memory журнал черги сповіщень.
* **API**: `SendNotification`, `GetDeliveryStatus`.

#### 12. `review` (FastAPI, REST)
* **Призначення**: Відгуки та оцінки страв, ресторанів та кур'єрів, розрахунок агрегованого рейтингу.
* **Сховище**: PostgreSQL (відгуки, бали 1-5).
* **API**: `POST /reviews`, `GET /restaurants/{id}/reviews`, `GET /couriers/{id}/reviews`.

#### 13. `analytics-sink` (Go, gRPC)
* **Призначення**: Прийом аудиторських та аналітичних подій від мікросервісів для подальшого збору статистики.
* **Сховище**: In-memory buffer / Batch sink інтерфейс.
* **API**: `IngestEvent`, `BatchIngestEvents`.

---

### Рівень 3: Доменний оркестратор

#### 14. `order` (FastAPI, gRPC + REST)
* **Призначення**: Центральний оркестратор життєвого циклу замовлення. Управляє станами: `CREATED` → `PAID` → `PREPARING` → `DISPATCHED` → `DELIVERING` → `DELIVERED` / `CANCELLED`.
* **Сховище**: PostgreSQL (таблиця замовлень, позицій, статусів).
* **Синхронна оркестрація**: Координує виклики до `cart`, `pricing`, `inventory`, `payment`, `fraud`, `dispatch`, `notification`.
* **API**: `CreateOrder`, `GetOrder`, `CancelOrder`, `UpdateOrderStatus`.

---

### Рівень 4: BFF (Backend-For-Frontend) та Edge Gateway

#### 15. `bff-merchant` (FastAPI, REST)
* **Призначення**: Панель ресторану. Управління меню, прийом та зміна статусу замовлення («Готується», «Готово до видачі»).
* **API**: `GET /api/v1/merchant/orders`, `POST /api/v1/merchant/orders/{id}/status`, `PUT /api/v1/merchant/menu`.

#### 16. `bff-customer` (FastAPI, REST → gRPC)
* **Призначення**: Клієнтський мобільний/веб API. Агрегує дані з `catalog`, `cart`, `pricing`, `order`, `eta`, `review`.
* **API**: `GET /api/v1/customer/restaurants`, `GET /api/v1/customer/cart`, `POST /api/v1/customer/orders/checkout`.

#### 17. `bff-courier` (Go, WebSocket + REST)
* **Призначення**: Мобільний додаток кур'єра. Прийом замовлень, передача стріму GPS-координат по WebSocket/gRPC.
* **API**: `GET /api/v1/courier/available-orders`, `POST /api/v1/courier/orders/{id}/accept`, `WS /api/v1/courier/ws/location`.

---

## 2. Локальна перевірка та запуск

Після реалізації всіх 18 сервісів створюється:
1. **`docker-compose.yml`**: опис запуску баз (PostgreSQL, Redis) та всіх сервісів для локальної перевірки.
2. **`scripts/smoke-test.sh`**: автоматизований end-to-end сценарій:
   * Реєстрація клієнта, ресторану, кур'єра.
   * Додавання товару в кошик.
   * Розрахунок цін та створення замовлення.
   * Оплата замовлення.
   * Призначення кур'єра та оновлення статусу.
   * Перевірка оновлення статусу в реальному часі.

---

## 3. Наступні фази (за межами поточного завдання)
* **Фаза інфраструктури**: Перенесення подій на Apache Kafka (Strimzi) + Transactional Outbox.
* **Фаза телеметрії**: Підключення OpenTelemetry (traces, metrics, logs) до Jaeger, Tempo та Prometheus.
* **Фаза Kubernetes**: Helm чарти, Istio VirtualServices, DestinationRules, Argo Rollouts та Kyverno політики.

# TotemOps — Архітектурний план та специфікація мікросервісів

Детальна технічна документація платформи: порти сервісів, схеми баз даних (PostgreSQL), поля таблиць та повні воркфлоу міжсервісної взаємодії.

---

## 1. Специфікація кожного мікросервісу

---

### 1.1. `identity` (Identity & Auth Service)

* **Внутрішній порт (HTTP)**: `8001`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назва таблиці**: `users`
* **Поля таблиці**:
  | Поле | Тип | Опис / Обмеження |
  | :--- | :--- | :--- |
  | `id` | `VARCHAR` | Первинний ключ (`usr-xxxxxxxx`), індекс |
  | `email` | `VARCHAR` | Унікальний email, індекс, `NOT NULL` |
  | `password_hash` | `VARCHAR` | Хеш пароля (bcrypt salt + hash), `NOT NULL` |
  | `full_name` | `VARCHAR` | Повне ім'я користувача, `NOT NULL` |
  | `role` | `VARCHAR` | Роль: `customer`, `courier`, `merchant`, `admin` |
  | `created_at` | `BIGINT` | Unix timestamp створення акаунта |
* **Основні ендпоінти**:
  * `GET /healthz` — Liveness перевірка процесу.
  * `GET /readyz` — Readiness перевірка (виконує `SELECT 1` в БД).
  
  * `POST /api/v1/auth/register` — Реєстрація нового користувача з хешуванням пароля.
     Приймає email, пароль, ім'я та роль. Записує нового користувача в таблицю users у PostgreSQL.

  * `POST /api/v1/auth/login` — Перевірка пароля та видача JWT токена.
     Клієнт передає email і пароль.
     Сервіс знаходить запис у БД, перевіряє хеш пароля.
     Якщо все вірно — випускає цифровий пропуск: JWT-токен (JSON Web Token), підписаний секретним ключем.
     У цьому токені зашито: хто цей користувач (user_id), яка в нього роль (role), коли спливає термін дії токена.

  * `POST /api/v1/auth/verify` — Валідація JWT токена іншими сервісами/шлюзами.
     Коли клієнт звертається, наприклад, до bff-customer або робить оплату, сервіси перевіряють цей токен через identity, щоб переконатися, що запит не підроблений і токен справжній.
---

### 1.2. `catalog` (Catalog & Restaurant Service)
* **Внутрішній порт (HTTP)**: `8002`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назви таблиць**:
  1. `restaurants`
  2. `menu_items`
* **Поля таблиць**:
  * **Таблиця `restaurants`**:
    | Поле | Тип | Опис / Обмеження |
    | :--- | :--- | :--- |
    | `id` | `VARCHAR` | Первинний ключ ресторану (`rest-xxx`) |
    | `name` | `VARCHAR` | Назва ресторану, `NOT NULL` |
    | `cuisine` | `VARCHAR` | Тип кухні (Pizza, Burgers, Sushi тощо), `NOT NULL` |
    | `lat` | `FLOAT` | Географічна широта розташування кухні |
    | `lon` | `FLOAT` | Географічна довгота розташування кухні |
    | `is_active` | `BOOLEAN` | Статус готовності приймати замовлення (default `True`) |
  * **Таблиця `menu_items`**:
    | Поле | Тип | Опис / Обмеження |
    | :--- | :--- | :--- |
    | `id` | `VARCHAR` | Первинний ключ страви (`item-xxx`) |
    | `restaurant_id` | `VARCHAR` | Зовнішній ключ ресторану, індекс |
    | `name` | `VARCHAR` | Назва страви, `NOT NULL` |
    | `category` | `VARCHAR` | Категорія (Main, Sides, Drinks, Dessert) |
    | `price_cents` | `INTEGER` | Вартість страви у центах (наприклад `1800` = $18.00) |
    | `description` | `VARCHAR` | Опис складу та інгредієнтів |
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `GET /api/v1/catalog/restaurants` — Список ресторанів (з фільтром по кухні).
  * `GET /api/v1/catalog/restaurants/{restaurant_id}/menu` — Меню обраного ресторану.
  * `GET /api/v1/catalog/items/{item_id}` — Інформація про конкретну страву.

---

### 1.3. `pricing` (Dynamic Pricing Engine)
* **Внутрішній порт (HTTP)**: `8003`
* **База даних**: **Stateless** (без власної БД, чистий обчислювальний сервіс).
* **Формула вартості**:
  $$\text{delivery\_fee} = \text{base\_fee (2500)} + (\text{distance\_km} \times 400 \times \text{surge\_multiplier})$$
  Промокод `TOTEM10` застосовує знижку 10% на `subtotal`.
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`


  * `POST /api/v1/pricing/calculate` — Приймає: `subtotal_cents`, `distance_km`, `surge_multiplier`, `promo_code`. Повертає: детальний розрахунок суми доставки, знижки та загального чека.
  Сервіс ордер надсилає запит (коли клієнт відкрив кошик і хоче побачити "Скільки коштуватиме доставка і яка знижка?").

ПРИКЛАД ЗАПИТУ
{
  "restaurant_id": "rest-01",
  "items": [
    {
      "item_id": "item-burger",
      "quantity": 2,
      "unit_price_cents": 1800
    },
    {
      "item_id": "item-cola",
      "quantity": 1,
      "unit_price_cents": 500
    }
  ],
  "distance_km": 3.5,
  "promo_code": "TOTEM10"
}

Прайсінг сервіс рахує суму всіх товарів (unit_price_cents) + рахує доставку (на скільки далеко distance_km) + Додає коефіцієнт підвищеного попиту + Перевіряє промокод якщо надходить.

ВІДПОВІДЬ
{
  "subtotal_cents": 4100,
  "delivery_fee_cents": 7800,
  "surge_fee_cents": 1300,
  "surge_multiplier": 1.2,
  "discount_cents": 410,
  "total_cents": 11490
}


---

### 1.4. `cart` (Shopping Cart Service)
* **Внутрішній порт (HTTP)**: `8004`
* **База даних**: **In-Memory** (словник за `user_id`, підготовлений до підключення Redis TTL).
* **Структура сесії в пам'яті**:
  ```json
  {
    "user_id": "usr-xxx",
    "restaurant_id": "rest-01",
    "items": [
      {
        "item_id": "item-01",
        "name": "Totem Classic Burger",
        "quantity": 2,
        "price_cents": 1800
      }
    ],
    "subtotal_cents": 3600
  }
  ```
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `GET /api/v1/cart/{user_id}` — Отримання вмісту поточного кошика.
    bff-customer:8022 надсилає отриманий йому запит http://cart:8004/api/v1/cart/usr-12345. Мікросервіс дістає з пам'яті сесію для "usr-12345". Рахує: subtotal = ∑(quantity * price). Повертає JSON з усім кошиком назад клієнту


  * `POST /api/v1/cart/{user_id}/items` — Додавання або зміна кількості страви.
  * `DELETE /api/v1/cart/{user_id}/items/{item_id}` — Видалення окремої страви.
  * `DELETE /api/v1/cart/{user_id}` — Повне очищення кошика після оформлення замовлення.

---

### 1.5. `inventory` (Stock & Reservation Service)
* **Внутрішній порт (HTTP)**: `8005`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назви таблиць**:
  1. `stock_items`
  2. `reservations`
* **Поля таблиць**:
  * **Таблиця `stock_items`**:
    | Поле | Тип | Опис / Обмеження |
    | :--- | :--- | :--- |
    | `item_id` | `VARCHAR` | Первинний ключ страви |
    | `available_qty` | `INTEGER` | Доступна кількість для продажу |
    | `reserved_qty` | `INTEGER` | Заблокована кількість у процесі чекауту |
  * **Таблиця `reservations`**:
    | Поле | Тип | Опис / Обмеження |
    | :--- | :--- | :--- |
    | `reservation_id` | `VARCHAR` | Первинний ключ резерву (`res-xxx`) |
    | `order_id` | `VARCHAR` | Номер замовлення, індекс |
    | `item_id` | `VARCHAR` | ID страви |
    | `quantity` | `INTEGER` | Зарезервована кількість |
    | `status` | `VARCHAR` | `PENDING`, `COMMITTED`, `RELEASED` |
    | `created_at` | `BIGINT` | Час створення резервації |
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/inventory/reserve` — Тимчасове блокування залишків під час створення замовлення.
  * `POST /api/v1/inventory/commit` — Фінальне списання залишків після успішної оплати.
  * `POST /api/v1/inventory/release` — Компенсуюча дія: повернення залишків при помилці оплати.

---

### 1.6. `payment` (Payment Processing & Idempotency)
* **Внутрішній порт (HTTP)**: `8006`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назва таблиці**: `payments`
* **Поля таблиці**:
  | Поле | Тип | Опис / Обмеження |
  | :--- | :--- | :--- |
  | `payment_id` | `VARCHAR` | Первинний ключ платежу (`pay-xxx`) |
  | `order_id` | `VARCHAR` | Номер замовлення, індекс |
  | `idempotency_key` | `VARCHAR` | Ключ ідемпотентності для захисту від подвійних списань, `UNIQUE` |
  | `amount_cents` | `INTEGER` | Сума транзакції у центах |
  | `currency` | `VARCHAR` | Валюта (`USD`) |
  | `status` | `VARCHAR` | `AUTHORIZED`, `CAPTURED`, `REFUNDED` |
  | `payment_method` | `VARCHAR` | Метод: `CARD`, `APPLE_PAY`, `GOOGLE_PAY` |
  | `created_at` | `BIGINT` | Timestamp проведення операції |
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/payments/authorize` — Авторизація холду коштів з обов'язковим `idempotency_key`.
  * `POST /api/v1/payments/capture` — Списання коштів після підтвердження замовлення.
  * `POST /api/v1/payments/refund` — Повернення коштів у разі скасування замовлення.

---

### 1.7. `eta` (Estimated Time of Arrival Service)
* **Внутрішній порт (HTTP)**: `8007`
* **База даних**: **Stateless** (без БД).
* **Логіка**: Розрахунок геодезичної відстані між координатами ресторану та адресою клієнта, розрахунок часу готування на кухні та часу руху кур'єра (середня швидкість 25 км/год).
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/eta/estimate` — Приймає координати (`origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`), повертає `distance_km`, `prep_time_minutes`, `delivery_time_minutes`, `total_eta_minutes`.

---

### 1.8. `geo-tracking` (Live Courier Telemetry Service)
* **Внутрішній порт (HTTP)**: `8008`
* **База даних**: **In-Memory** (словник координат кур'єрів, підготовлений до Redis Geospatial).
* **Структура телеметрії**:
  `locations[courier_id] = { courier_id, latitude, longitude, speed_kmh, heading, updated_at }`
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/geo/location` — Прийом чергової точки GPS від кур'єра.
  * `GET /api/v1/geo/location/{courier_id}` — Отримання останніх відомих координат кур'єра.

---

### 1.9. `dispatch` (Courier Matching & Fleet Dispatching)
* **Внутрішній порт (HTTP)**: `8009`
* **База даних**: **In-Memory** (пул вільних/зайнятих кур'єрів).
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/dispatch/find` — Пошук найближчого вільного кур'єра до ресторану.
  * `POST /api/v1/dispatch/assign` — Призначення кур'єра на конкретне замовлення.
  * `GET /api/v1/dispatch/orders/{order_id}` — Перевірка призначеного кур'єра.

---

### 1.10. `fraud` (Anti-Fraud & Risk Engine)
* **Внутрішній порт (HTTP)**: `8010`
* **База даних**: **Stateless** (правила оцінки ризику).
* **Правила ризику**:
  * Сума замовлення > $1,000 (100,000 cents) $\to$ `REJECT` (high risk).
  * Сума замовлення > $500 (50,000 cents) $\to$ `CHALLENGE` (вимагає додаткової перевірки 3D Secure).
  * Невідомий платіжний метод $\to$ `REJECT`.
  * Стандартне замовлення $\to$ `ALLOW` (ризик `0.05`).
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/fraud/evaluate` — Перевірка замовлення перед списанням коштів.

---

### 1.11. `notification` (Notification & Alerts Service)
* **Внутрішній порт (HTTP)**: `8011`
* **База даних**: **Stateless** (імітація шлюзів Apple APNs, Firebase FCM, Twilio SMS).
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/notifications/send` — Відправка PUSH/SMS клієнту або кур'єру про зміну статусу.

---

### 1.12. `review` (Ratings & Reviews Service)
* **Внутрішній порт (HTTP)**: `8012`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назва таблиці**: `reviews`
* **Поля таблиці**:
  | Поле | Тип | Опис / Обмеження |
  | :--- | :--- | :--- |
  | `id` | `VARCHAR` | Первинний ключ відгуку (`rev-xxx`) |
  | `order_id` | `VARCHAR` | ID виконаного замовлення, індекс |
  | `customer_id` | `VARCHAR` | ID клієнта, що залишив відгук |
  | `restaurant_id` | `VARCHAR` | ID оціненого ресторану, індекс |
  | `courier_id` | `VARCHAR` | ID оціненого кур'єра (опціонально) |
  | `rating` | `INTEGER` | Оцінка від 1 до 5 |
  | `comment` | `VARCHAR` | Текстовий коментар |
  | `created_at` | `BIGINT` | Час публікації відгуку |
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/reviews` — Створення нового відгуку після доставки.
  * `GET /api/v1/reviews/restaurant/{restaurant_id}` — Отримання середнього рейтингу та відгуків закладу.

---

### 1.13. `analytics-sink` (Centralized Audit & Event Sink)
* **Внутрішній порт (HTTP)**: `8013`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назва таблиці**: `analytics_events`
* **Поля таблиці**:
  | Поле | Тип | Опис / Обмеження |
  | :--- | :--- | :--- |
  | `id` | `VARCHAR` | Первинний ключ події (`evt-xxx`) |
  | `event_name` | `VARCHAR` | Назва події (`order.created`, `payment.authorized`, тощо), індекс |
  | `source_service` | `VARCHAR` | Назва мікросервісу-джерела (`order`, `payment`, тощо) |
  | `payload_json` | `TEXT` | Повний JSON-пейлоад події |
  | `timestamp` | `BIGINT` | Час виникнення події |
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/analytics/events` — Поодинокий прийом події.
  * `POST /api/v1/analytics/events/batch` — Пакетний прийом подій.
  * `GET /api/v1/analytics/events` — Читання аудит-лога.

---

### 1.14. `order` (Distributed Saga Orchestrator)
* **Внутрішній порт (HTTP)**: `8014`
* **База даних**: PostgreSQL (fallback: SQLite)
* **Назви таблиць**:
  1. `orders`
  2. `order_items`
* **Поля таблиць**:
  * **Таблиця `orders`**:
    | Поле | Тип | Опис / Обмеження |
    | :--- | :--- | :--- |
    | `order_id` | `VARCHAR` | Первинний ключ замовлення (`ord-xxx`), індекс |
    | `customer_id` | `VARCHAR` | ID замовника, індекс |
    | `restaurant_id` | `VARCHAR` | ID ресторану |
    | `subtotal_cents` | `INTEGER` | Вартість страв |
    | `delivery_fee_cents` | `INTEGER` | Вартість доставки |
    | `discount_cents` | `INTEGER` | Знижка за промокодом |
    | `total_cents` | `INTEGER` | Загальна сума до сплати |
    | `status` | `VARCHAR` | Статус: `CREATED`, `PAID`, `PREPARING`, `READY_FOR_PICKUP`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED` |
    | `delivery_address` | `VARCHAR` | Текстова адреса доставки |
    | `delivery_lat` | `FLOAT` | Координати точки доставки (широта) |
    | `delivery_lon` | `FLOAT` | Координати точки доставки (довгота) |
    | `courier_id` | `VARCHAR` | ID призначеного кур'єра |
    | `created_at` | `BIGINT` | Timestamp створення |
    | `updated_at` | `BIGINT` | Timestamp останньої зміни статусу |
  * **Таблиця `order_items`**:
    | Поле | Тип | Опис / Обмеження |
    | :--- | :--- | :--- |
    | `id` | `VARCHAR` | Первинний ключ рядка замовлення |
    | `order_id` | `VARCHAR` | Зовнішній ключ замовлення, індекс |
    | `item_id` | `VARCHAR` | ID замовленої страви |
    | `name` | `VARCHAR` | Назва страви |
    | `quantity` | `INTEGER` | Замовлена кількість |
    | `price_cents` | `INTEGER` | Ціна за одиницю |
* **Основні ендпоінти**:
  * `GET /healthz`, `GET /readyz`
  * `POST /api/v1/orders` — **Saga-оркестратор**: покроково координує інші сервіси та створює замовлення.
  * `GET /api/v1/orders/{order_id}` — Отримання замовлення та його позицій.
  * `PUT /api/v1/orders/{order_id}/status` — Зміна життєвого циклу замовлення (викликається рестораном або кур'єром).

---

### 1.15. `bff-merchant` (Merchant Web Portal Gateway)
* **Внутрішній порт (HTTP)**: `8020`
* **База даних**: **Stateless** (API Gateway / BFF).
* **Основні ендпоінти**:
  * `GET /api/v1/merchant/{restaurant_id}/menu` — Проксіювання запиту до `catalog` (8002).
  * `POST /api/v1/merchant/orders/{order_id}/status` — Оновлення стану замовлення через `order` (8014): перевід замовлення у `PREPARING` або `READY_FOR_PICKUP`.

---

### 1.16. `bff-courier` (Courier Mobile API Gateway)
* **Внутрішній порт (HTTP)**: `8021`
* **База даних**: **Stateless** (API Gateway / BFF).
* **Основні ендпоінти**:
  * `POST /api/v1/courier/orders/accept` — Прийняття доставки кур'єром $\to$ оновлення статусу в `order` на `IN_TRANSIT`.
  * `POST /api/v1/courier/orders/delivered` — Підтвердження вручення $\to$ оновлення в `order` на `DELIVERED`.
  * `POST /api/v1/courier/location` — Відправка точки GPS $\to$ передача в `geo-tracking` (8008).
  * `WebSocket /ws/location` — Живий стрімінг GPS-координат.

---

### 1.17. `bff-customer` (Customer Mobile/Web API Gateway)
* **Внутрішній порт (HTTP)**: `8022`
* **База даних**: **Stateless** (API Gateway / BFF).
* **Основні ендпоінти**:
  * `POST /api/v1/auth/register`, `POST /api/v1/auth/login` $\to$ делегування в `identity` (8001).
  * `GET /api/v1/restaurants`, `GET /api/v1/restaurants/{id}/menu` $\to$ агрегація з `catalog` (8002).
  * `GET /api/v1/cart`, `POST /api/v1/cart/items`, `DELETE /api/v1/cart` $\to$ керування через `cart` (8004).
  * `POST /api/v1/checkout` $\to$ запуск оформлення замовлення через `order` (8014).
  * `GET /api/v1/orders/{order_id}` $\to$ агрегує деталі замовлення з `order` (8014) та поточне положення кур'єра з `geo-tracking` (8008).

---

## 2. Повні воркфлоу взаємодії між сервісами

```
+---------------------------------------------------------------------------------------------------+
|                                   КЛІЄНТСЬКІ ТА ЗОВНІШНІ ІНТЕРФЕЙСИ                               |
|        [Customer App]                    [Courier App]                   [Merchant Portal]        |
+--------------+---------------------------------+----------------------------------+---------------+
               |                                 |                                  |
               v                                 v                                  v
       [bff-customer:8022]              [bff-courier:8021]                 [bff-merchant:8020]
```

---

### Воркфлоу 1: Реєстрація та Авторизація користувача
1. Клієнт відправляє email та пароль у `bff-customer:8022` (`/api/v1/auth/register`).
2. `bff-customer` робить HTTP POST до `identity:8001` (`/api/v1/auth/register`).
3. `identity`:
   - Хешує пароль за допомогою алгоритму `bcrypt`.
   - Записує нового користувача в таблицю `users` бази даних PostgreSQL.
   - Повертає згенерований `user_id`.
4. Клієнт викликає `/api/v1/auth/login`:
   - `identity` перевіряє хеш пароля.
   - Генерує підписаний симетричним ключем JWT-токен із полями `sub`, `email`, `role`, `exp`.

---

### Воркфлоу 2: Перегляд меню та наповнення кошика
1. Клієнт відкриває додаток:
   - `bff-customer` звертається до `catalog:8002` (`GET /api/v1/catalog/restaurants`).
   - `catalog` робить `SELECT` з таблиці `restaurants` і повертає список закладів.
2. Клієнт обирає ресторан:
   - `bff-customer` звертається до `catalog:8002` (`GET /api/v1/catalog/restaurants/{id}/menu`).
   - `catalog` повертає список страв із таблиці `menu_items`.
3. Додавання страви в кошик:
   - `bff-customer` надсилає запит до `cart:8004` (`POST /api/v1/cart/{user_id}/items`).
   - `cart` оновлює стан кошика в пам'яті (кількість, перераховує `subtotal_cents`).

---

### Воркфлоу 3: Чекаут замовлення (Розподілена Saga-оркестрація)

Це ключовий транзакційний ланцюжок системи:

```
[Customer]
    | (POST /api/v1/checkout)
    v
[bff-customer:8022]
    | (POST /api/v1/orders)
    v
[order:8014] (Saga Orchestrator)
    |
    |-- 1. POST /api/v1/pricing/calculate  --------> [pricing:8003]
    |      (розрахунок доставки + промокод)
    |
    |-- 2. POST /api/v1/fraud/evaluate -----------> [fraud:8010]
    |      (перевірка ризику суми та картки)
    |
    |-- 3. POST /api/v1/inventory/reserve --------> [inventory:8005]
    |      (блокування страв у таблиці reservations)
    |
    |-- 4. POST /api/v1/payments/authorize -------> [payment:8006]
    |      (холд суми замовлення з Idempotency-Key)
    |
    |-- 5. POST /api/v1/dispatch/find & assign ---> [dispatch:8009]
    |      (пошук та закріплення кур'єра)
    |
    |-- 6. POST /api/v1/notifications/send -------> [notification:8011]
    |      (PUSH клієнту: "Замовлення оформлено")
    |
    |-- 7. POST /api/v1/analytics/events ---------> [analytics-sink:8013]
    |      (аудит-подія "order.created" у БД)
    |
    |-- 8. Збереження замовлення у PostgreSQL (таблиці orders та order_items зі статусом PAID)
    v
[bff-customer:8022]
    | (DELETE /api/v1/cart/{user_id})
    v
[cart:8004] (Очищення кошика)
```

**Компенсуючі транзакції у разі збою:**
* Якщо `payment` відхилив транзакцію $\to$ `order` надсилає запит на відкат у `inventory` (`POST /api/v1/inventory/release`), залишки розблоковуються, статус замовлення переходить у `CANCELLED`.

---

### Воркфлоу 4: Приготування рестораном та прийом кур'єром
1. Менеджер кухні бачить замовлення на планшеті через `bff-merchant:8020`.
2. Ресторан закінчив готувати:
   - `bff-merchant` надсилає запит у `order:8014` (`PUT /api/v1/orders/{order_id}/status` зі статусом `READY_FOR_PICKUP`).
   - `order` оновлює статус у таблиці `orders` та сповіщає `notification` для кур'єра.
3. Кур'єр забирає замовлення:
   - Додаток кур'єра через `bff-courier:8021` викликає `order:8014`, перевівши статус у `IN_TRANSIT`.

---

### Воркфлоу 5: Live GPS трекінг руху кур'єра
1. Додаток кур'єра кожні кілька секунд надсилає координати через WebSocket або HTTP POST у `bff-courier:8021` (`/api/v1/courier/location`).
2. `bff-courier` передає телеметрію в `geo-tracking:8008` (`POST /api/v1/geo/location`).
3. Клієнт дивиться на карту в додатку:
   - `bff-customer:8022` робить запит на статус замовлення до `order:8014` (`GET /api/v1/orders/{order_id}`) і дізнається призначеного `courier_id`.
   - `bff-customer:8022` одночасно запитує актуальні координати в `geo-tracking:8008` (`GET /api/v1/geo/location/{courier_id}`).
   - Клієнт бачить на мапі рух кур'єра в реальному часі.

---

### Воркфлоу 6: Вручення замовлення та відгук
1. Кур'єр передав пакунок клієнту:
   - `bff-courier:8021` викликає `order:8014`, змінюючи статус на `DELIVERED`.
   - `order:8014` надсилає команду в `payment:8006` (`POST /api/v1/payments/capture`) для остаточного списання холду, а в `inventory:8005` (`POST /api/v1/inventory/commit`) для остаточного закриття резервації.
2. Клієнт оцінює доставку:
   - Клієнт надсилає оцінку (1-5 зірок) та відгук у `review:8012` (`POST /api/v1/reviews`).
   - `review` записує дані в таблицю `reviews` у PostgreSQL.
   - Заклад та кур'єр отримують оновлений середній рейтинг.


Для Management (totem-mgmt):

VPC CIDR: "10.0.0.0/16"
Публічні: ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
Приватні: ["10.0.10.0/24", "10.0.20.0/24", "10.0.30.0/24"]
Для Staging (totem-stage):

VPC CIDR: "10.1.0.0/16"
Публічні: ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
Приватні: ["10.1.10.0/24", "10.1.20.0/24", "10.1.30.0/24"]
Для Production (totem-prod):

VPC CIDR: "10.2.0.0/16"
Публічні: ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
Приватні: ["10.2.10.0/24", "10.2.20.0/24", "10.2.30.0/24"]
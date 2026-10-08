#!/usr/bin/env python3
import subprocess
import time
import sys
import os
import httpx

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_PYTHON = os.path.join(WORKSPACE_ROOT, ".venv/bin/python3")

services_procs = []

def start_service(name: str, path: str, port: int, extra_env=None):
    env = os.environ.copy()
    env["PORT"] = str(port)
    if extra_env:
        env.update(extra_env)
    svc_dir = os.path.join(WORKSPACE_ROOT, "services", name)
    p = subprocess.Popen([VENV_PYTHON, "main.py"], cwd=svc_dir, env=env)
    services_procs.append((name, p))

def cleanup():
    print("\n🛑 Stopping all services...")
    for name, p in services_procs:
        p.terminate()
    for name, p in services_procs:
        p.wait()
    print("✅ All services stopped.")

def main():
    try:
        print("🚀 Starting ALL 17 Pure FastAPI Microservices...")

        # Core Services
        start_service("identity", "services/identity/main.py", 8001)
        start_service("catalog", "services/catalog/main.py", 8002)
        start_service("pricing", "services/pricing/main.py", 8003)
        start_service("cart", "services/cart/main.py", 8004)
        start_service("inventory", "services/inventory/main.py", 8005)
        start_service("payment", "services/payment/main.py", 8006)
        start_service("eta", "services/eta/main.py", 8007)
        start_service("geo-tracking", "services/geo-tracking/main.py", 8008)
        start_service("dispatch", "services/dispatch/main.py", 8009)
        start_service("fraud", "services/fraud/main.py", 8010)
        start_service("notification", "services/notification/main.py", 8011)
        start_service("review", "services/review/main.py", 8012)
        start_service("analytics-sink", "services/analytics-sink/main.py", 8013)
        start_service("order", "services/order/main.py", 8014)

        # BFFs
        start_service("bff-merchant", "services/bff-merchant/main.py", 8020)
        start_service("bff-courier", "services/bff-courier/main.py", 8021)
        start_service("bff-customer", "services/bff-customer/main.py", 8022)

        print("⏳ Waiting 4 seconds for all services to spin up...")
        time.sleep(4)

        client = httpx.Client(timeout=10.0)

        # 1. Test Healthz & Readyz across all 17 services
        print("\n--- 1. Testing Healthz & Readyz on all 17 services ---")
        ports = [
            (8001, "identity"), (8002, "catalog"), (8003, "pricing"), (8004, "cart"),
            (8005, "inventory"), (8006, "payment"), (8007, "eta"), (8008, "geo-tracking"),
            (8009, "dispatch"), (8010, "fraud"), (8011, "notification"), (8012, "review"),
            (8013, "analytics-sink"), (8014, "order"), (8020, "bff-merchant"),
            (8021, "bff-courier"), (8022, "bff-customer")
        ]
        for port, name in ports:
            # Test liveness
            r_live = client.get(f"http://localhost:{port}/healthz")
            assert r_live.status_code == 200, f"{name} liveness failed on port {port}"
            # Test readiness (including DB check)
            r_ready = client.get(f"http://localhost:{port}/readyz")
            assert r_ready.status_code == 200, f"{name} readiness failed on port {port}: {r_ready.text}"
            print(f"  ✓ {name:15} (: {port}) Liveness: OK | Readiness: {r_ready.json()}")

        # 2. Test Auth via bff-customer
        print("\n--- 2. Customer Auth & Catalog via bff-customer ---")
        login_res = client.post("http://localhost:8022/api/v1/auth/login", json={
            "email": "customer@totem.ops",
            "password": "password123"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        user_info = login_res.json()
        print(f"  ✓ Logged in as: {user_info['user_id']} ({user_info['role']})")

        # 3. Test Catalog
        rests_res = client.get("http://localhost:8022/api/v1/restaurants")
        assert rests_res.status_code == 200
        restaurants = rests_res.json()
        assert len(restaurants) >= 3
        restaurant_id = restaurants[0]["id"]
        print(f"  ✓ Catalog returned {len(restaurants)} restaurants")

        menu_res = client.get(f"http://localhost:8022/api/v1/restaurants/{restaurant_id}/menu")
        assert menu_res.status_code == 200
        items = menu_res.json()
        first_item = items[0]
        print(f"  ✓ First menu item: '{first_item['name']}' ({first_item['price_cents'] / 100:.2f} UAH)")

        # 4. Test Cart
        print("\n--- 3. Cart Operations ---")
        cart_add_res = client.post(
            "http://localhost:8022/api/v1/cart/items",
            headers={"x-user-id": user_info["user_id"]},
            json={
                "restaurant_id": restaurant_id,
                "item_id": first_item["id"],
                "name": first_item["name"],
                "price_cents": first_item["price_cents"],
                "quantity": 2
            }
        )
        assert cart_add_res.status_code == 200
        print(f"  ✓ Added 2x '{first_item['name']}' to cart, subtotal: {cart_add_res.json()['subtotal_cents']} cents")

        # 5. Test End-to-End Checkout
        print("\n--- 4. End-to-End Checkout Orchestration ---")
        checkout_res = client.post(
            "http://localhost:8022/api/v1/checkout",
            headers={"x-user-id": user_info["user_id"]},
            json={
                "delivery_address": "Khreshchatyk St 1, Kyiv",
                "delivery_lat": 50.4501,
                "delivery_lon": 30.5234,
                "promo_code": "TOTEM10",
                "payment_method": "apple_pay"
            }
        )
        assert checkout_res.status_code in (200, 201), f"Checkout failed: {checkout_res.text}"
        order_data = checkout_res.json()
        order_id = order_data["order_id"]
        print(f"  ✓ Order created successfully: {order_id}")
        print(f"    - Status: {order_data['status']}")
        print(f"    - Subtotal: {order_data['subtotal_cents']} cents")
        print(f"    - Delivery Fee: {order_data['delivery_fee_cents']} cents")
        print(f"    - Discount: {order_data['discount_cents']} cents")
        print(f"    - Total: {order_data['total_cents']} cents")
        print(f"    - Assigned Courier: {order_data['courier_id']}")

        # 6. Merchant Update Status
        print("\n--- 5. Merchant Status Update via bff-merchant ---")
        merchant_res = client.post(
            f"http://localhost:8020/api/v1/merchant/orders/{order_id}/status",
            json={"status": "READY_FOR_PICKUP", "notes": "Order packed"}
        )
        assert merchant_res.status_code == 200
        print(f"  ✓ Merchant updated order to: {merchant_res.json()['status']}")

        # 7. Courier Complete Order
        print("\n--- 6. Courier Delivery via bff-courier ---")
        courier_res = client.post(
            "http://localhost:8021/api/v1/courier/orders/delivered",
            json={"order_id": order_id}
        )
        assert courier_res.status_code == 200
        print(f"  ✓ Courier completed order: status={courier_res.json()['status']}")

        # 8. Customer Track Order Details
        print("\n--- 7. Customer Track Order Details ---")
        track_res = client.get(f"http://localhost:8022/api/v1/orders/{order_id}")
        assert track_res.status_code == 200
        details = track_res.json()
        print(f"  ✓ Verified tracked order: status={details['status']}, courier_loc={details.get('courier_location')}")

        # 9. Review Service
        print("\n--- 8. Review Service ---")
        rev_res = client.post("http://localhost:8012/api/v1/reviews", json={
            "order_id": order_id,
            "user_id": user_info["user_id"],
            "restaurant_id": restaurant_id,
            "rating": 5,
            "comment": "Delicious food and super fast delivery!"
        })
        assert rev_res.status_code == 200
        print(f"  ✓ Review recorded: rating={rev_res.json()['rating']}, comment='{rev_res.json()['comment']}'")

        print("\n🎉 ALL 17 PURE FASTAPI SERVICES PASSED END-TO-END TEST 100%!")
        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}", file=sys.stderr)
        return 1
    finally:
        cleanup()

if __name__ == "__main__":
    sys.exit(main())

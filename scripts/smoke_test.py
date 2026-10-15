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
            # Poll until live and ready (up to 15 attempts, 1s interval)
            ready = False
            r_ready_json = {}
            for attempt in range(15):
                try:
                    r_live = client.get(f"http://localhost:{port}/healthz")
                    r_ready = client.get(f"http://localhost:{port}/readyz")
                    if r_live.status_code == 200 and r_ready.status_code == 200:
                        ready = True
                        r_ready_json = r_ready.json()
                        break
                except Exception:
                    time.sleep(1)
            assert ready, f"{name} failed to become ready on port {port} after 15 seconds"
            print(f"  ✓ {name:15} (: {port}) Liveness: OK | Readiness: {r_ready_json}")


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

        print(f"    - Assigned Courier: {order_data['courier_id']}")

        # 6. Full Order Lifecycle (State Machine)
        print("\n--- 5. Full Kitchen & Courier State Machine Transitions ---")
        # 5.1 Kitchen Accepts Order
        acc_res = client.post(f"http://localhost:8020/api/v1/merchant/orders/{order_id}/accept")
        assert acc_res.status_code == 200
        assert acc_res.json()["status"] == "ACCEPTED"
        print("  ✓ [ACCEPTED] Merchant accepted the order")

        # 5.2 Chef Starts Cooking
        cook_res = client.post(f"http://localhost:8020/api/v1/merchant/orders/{order_id}/cooking")
        assert cook_res.status_code == 200
        assert cook_res.json()["status"] == "COOKING"
        print("  ✓ [COOKING] Chef started preparing the meal")

        # 5.3 Order Packed and Ready
        ready_res = client.post(f"http://localhost:8020/api/v1/merchant/orders/{order_id}/ready")
        assert ready_res.status_code == 200
        assert ready_res.json()["status"] == "READY_FOR_PICKUP"
        print("  ✓ [READY_FOR_PICKUP] Order packed and waiting for courier")

        # 5.4 Courier Picks Up Order
        pickup_res = client.post(f"http://localhost:8021/api/v1/courier/orders/{order_id}/pickup")
        assert pickup_res.status_code == 200
        assert pickup_res.json()["status"] == "PICKED_UP"
        print("  ✓ [PICKED_UP] Courier took the package and is in transit")

        # 5.5 Courier Delivers Order
        deliver_res = client.post(f"http://localhost:8021/api/v1/courier/orders/{order_id}/deliver")
        assert deliver_res.status_code == 200
        assert deliver_res.json()["status"] == "DELIVERED"
        print("  ✓ [DELIVERED] Courier handed meal to customer & courier released")

        # 7. Customer Track Order Details
        print("\n--- 6. Customer Track Order Details ---")
        track_res = client.get(f"http://localhost:8022/api/v1/orders/{order_id}")
        assert track_res.status_code == 200
        details = track_res.json()
        print(f"  ✓ Verified tracked order: status={details['status']}, courier_loc={details.get('courier_location')}")

        # 8. Order Cancellation & Refund Business Logic
        print("\n--- 7. Order Cancellation & Refund Policies ---")
        # 7.1 Case A: Cancellation before cooking -> 100% refund
        client.post(
            "http://localhost:8022/api/v1/cart/items",
            headers={"x-user-id": user_info["user_id"]},
            json={
                "restaurant_id": restaurant_id,
                "item_id": first_item["id"],
                "name": first_item["name"],
                "price_cents": first_item["price_cents"],
                "quantity": 1
            }
        )
        ord2_res = client.post(
            "http://localhost:8022/api/v1/checkout",
            headers={"x-user-id": user_info["user_id"]},
            json={"delivery_address": "Maidan Nezalezhnosti, Kyiv"}
        )
        ord2_id = ord2_res.json()["order_id"]
        ord2_total = ord2_res.json()["total_cents"]
        
        cancel2_res = client.post(f"http://localhost:8022/api/v1/orders/{ord2_id}/cancel", json={"reason": "Changed my mind"})
        assert cancel2_res.status_code == 200
        cancel2_data = cancel2_res.json()
        assert cancel2_data["refund_percentage"] == 100
        assert cancel2_data["refund_amount_cents"] == ord2_total
        print(f"  ✓ Case A passed: Order {ord2_id} cancelled prior to cooking -> 100% refund ({cancel2_data['refund_amount_cents']} cents)")

        # 7.2 Case B: Cancellation during COOKING -> 50% refund
        client.post(
            "http://localhost:8022/api/v1/cart/items",
            headers={"x-user-id": user_info["user_id"]},
            json={
                "restaurant_id": restaurant_id,
                "item_id": first_item["id"],
                "name": first_item["name"],
                "price_cents": first_item["price_cents"],
                "quantity": 1
            }
        )
        ord3_res = client.post(
            "http://localhost:8022/api/v1/checkout",
            headers={"x-user-id": user_info["user_id"]},
            json={"delivery_address": "Podil, Kyiv"}
        )
        ord3_id = ord3_res.json()["order_id"]
        ord3_total = ord3_res.json()["total_cents"]
        # Merchant moves to COOKING
        client.post(f"http://localhost:8020/api/v1/merchant/orders/{ord3_id}/accept")
        client.post(f"http://localhost:8020/api/v1/merchant/orders/{ord3_id}/cooking")

        cancel3_res = client.post(f"http://localhost:8022/api/v1/orders/{ord3_id}/cancel", json={"reason": "Took too long"})
        assert cancel3_res.status_code == 200
        cancel3_data = cancel3_res.json()
        assert cancel3_data["refund_percentage"] == 50
        assert cancel3_data["refund_amount_cents"] == int(ord3_total * 0.5)
        print(f"  ✓ Case B passed: Order {ord3_id} cancelled during COOKING -> 50% refund ({cancel3_data['refund_amount_cents']} cents)")

        # 7.3 Case C: Reject cancellation of DELIVERED order
        cancel1_res = client.post(f"http://localhost:8022/api/v1/orders/{order_id}/cancel")
        assert cancel1_res.status_code == 400
        print(f"  ✓ Case C passed: Attempt to cancel DELIVERED order {order_id} was rejected with HTTP 400")

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

        print("\n🎉 ALL 17 PURE FASTAPI SERVICES PASSED END-TO-END TEST WITH FULL STATE MACHINE & REFUND RULES 100%!")
        return 0


    except Exception as e:
        print(f"\n❌ Test failed: {e}", file=sys.stderr)
        return 1
    finally:
        cleanup()

if __name__ == "__main__":
    sys.exit(main())

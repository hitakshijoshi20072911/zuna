"""Tests for Member 3's modules: pricing engine, negotiation rules and Razorpay webhook."""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
_database_file = Path(tempfile.gettempdir()) / "zuna-api-tests.sqlite3"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_database_file.as_posix()}")
os.environ.setdefault("ZUNA_TOKEN_SECRET", "test-only-signing-key-that-is-never-deployed")

from app import main as main_module  # noqa: E402
from app import pricing  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.models import Offer, Order  # noqa: E402
from app.seed import seed_data  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


class PricingEngineTests(unittest.TestCase):
    def test_project_document_example(self):
        result = pricing.calculate_price(
            total_cost=250, cost_breakdown={"material": 120, "labour": 100, "packaging": 20, "other": 10},
            target_margin_percent=30, inventory_age_days=45, demand_index=50,
        )
        self.assertEqual(result["basePrice"], 357)  # 250 / 0.70
        self.assertEqual(result["suggestedPrice"], 370)
        self.assertEqual(result["negotiationFloor"], 290)
        self.assertEqual(result["stockAge"]["recommendation"], "Consider a small discount.")
        self.assertIn("not an AI prediction", result["explanation"])

    def test_stock_age_bands(self):
        self.assertEqual(pricing.stock_age_band(10)["recommendation"], "Normal recommended price.")
        self.assertEqual(pricing.stock_age_band(20)["recommendation"], "Monitor demand.")
        self.assertEqual(pricing.stock_age_band(45)["recommendation"], "Consider a small discount.")
        self.assertEqual(pricing.stock_age_band(75)["recommendation"], "Consider a clearance offer.")

    def test_floor_never_below_cost_or_above_price(self):
        for price, cost, age in [(1500, 900, 0), (1500, 900, 90), (500, 600, 10), (800, 0, 5)]:
            floor = pricing.default_negotiation_floor(price, cost, age)
            self.assertLessEqual(floor, price)
            self.assertGreaterEqual(floor, min(cost, price))

    def test_ai_text_with_an_invented_price_is_rejected(self):
        allowed = {250, 357, 370, 290, 120}
        self.assertTrue(pricing._only_known_amounts("List it at ₹370 and accept ₹290 or more.", allowed))
        self.assertFalse(pricing._only_known_amounts("Actually list it at ₹999.", allowed))

    def test_without_api_key_the_rules_explanation_is_used(self):
        old = os.environ.pop("GEMINI_API_KEY", None)
        try:
            result = pricing.calculate_price(
                total_cost=250, cost_breakdown=None, target_margin_percent=30,
                inventory_age_days=0, demand_index=50,
            )
            self.assertEqual(pricing.with_ai_explanation(result)["explanationSource"], "rules")
        finally:
            if old is not None:
                os.environ["GEMINI_API_KEY"] = old

    def test_gemini_wording_never_changes_the_price(self):
        original = pricing.gemini_explanation
        pricing.gemini_explanation = lambda result: "List at ₹370; accept ₹290 or more. You decide."
        try:
            result = pricing.calculate_price(
                total_cost=250, cost_breakdown=None, target_margin_percent=30,
                inventory_age_days=45, demand_index=50,
            )
            price_before = result["suggestedPrice"]
            result = pricing.with_ai_explanation(result)
            self.assertEqual(result["suggestedPrice"], price_before)
            self.assertEqual(result["explanationSource"], "gemini")
            self.assertIn("not an AI prediction", result["explanation"])
        finally:
            pricing.gemini_explanation = original


class NegotiationAndPaymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main_module.RAZORPAY_KEY_ID = ""
        main_module.RAZORPAY_KEY_SECRET = ""
        cls.client_context = TestClient(main_module.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        _database_file.unlink(missing_ok=True)

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with Session(engine) as db:
            seed_data(db)

    def register(self, role, email):
        response = self.client.post("/api/v1/auth/register", json={
            "name": f"{role.title()} User", "email": email,
            "password": "correct horse battery", "role": role,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json(), {"Authorization": f"Bearer {response.json()['access_token']}"}

    def make_product(self, seller_headers, **overrides):
        payload = {
            "name": "Bag", "category": "Style & Accessories", "price": 1500, "cost": 700,
            "stockQty": 3, "age": 75, "image": "./assets/images/jewellery.webp",
            "offers": True, "description": "A handmade bag.", "minPrice": 1100,
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/products", json=payload, headers=seller_headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_pricing_endpoint_accepts_cost_components_and_old_payload(self):
        _, seller = self.register("seller", "p@example.com")
        response = self.client.post("/api/v1/seller/pricing/suggest", headers=seller, json={
            "material_cost": 120, "labour_cost": 100, "packaging_cost": 20, "other_cost": 10,
            "target_margin_percent": 30, "inventory_age_days": 45, "demand": "medium",
        })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["totalCost"], body["suggestedPrice"], body["negotiationFloor"]), (250, 370, 290))
        old_style = self.client.post("/api/v1/seller/pricing/suggest", headers=seller, json={
            "unit_cost": 820, "target_margin_percent": 35, "inventory_age_days": 0, "demand_index": 50,
        })
        self.assertEqual(old_style.status_code, 200)
        self.assertIn("suggestedPrice", old_style.json())
        no_cost = self.client.post("/api/v1/seller/pricing/suggest", headers=seller, json={
            "target_margin_percent": 35, "inventory_age_days": 0, "demand_index": 50,
        })
        self.assertEqual(no_cost.status_code, 422)

    def test_minimum_price_is_enforced_by_the_backend(self):
        _, seller = self.register("seller", "s@example.com")
        _, buyer = self.register("buyer", "b@example.com")
        product = self.make_product(seller)
        self.assertEqual(product["minPrice"], 1100)
        offer = self.client.post(f"/api/v1/products/{product['id']}/offers", json={"amount": 900}, headers=buyer).json()
        accept_low = self.client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller)
        self.assertEqual(accept_low.status_code, 422)
        self.assertIn("minimum acceptable price", accept_low.json()["detail"])
        counter_low = self.client.post(f"/api/v1/offers/{offer['id']}/counter", json={"amount": 1000}, headers=seller)
        self.assertEqual(counter_low.status_code, 422)
        counter_ok = self.client.post(f"/api/v1/offers/{offer['id']}/counter", json={"amount": 1250}, headers=seller)
        self.assertEqual(counter_ok.status_code, 200, counter_ok.text)
        accepted = self.client.post(f"/api/v1/offers/{offer['id']}/accept", headers=buyer)
        self.assertEqual(accepted.json()["acceptedPrice"], 1250)

    def test_automatic_floor_and_min_price_edit_rules(self):
        _, seller = self.register("seller", "auto@example.com")
        product = self.make_product(seller, minPrice=None, age=0)
        self.assertFalse(product["minPriceIsCustom"])
        self.assertGreaterEqual(product["minPrice"], 700)
        self.assertLessEqual(product["minPrice"], 1500)
        too_high = self.client.put(f"/api/v1/products/{product['id']}", headers=seller, json={
            "name": "Bag", "category": "Style & Accessories", "price": 1500, "cost": 700, "stockQty": 3,
            "age": 0, "image": "./assets/images/jewellery.webp", "offers": True,
            "description": "A handmade bag.", "minPrice": 1600,
        })
        self.assertEqual(too_high.status_code, 422)
        # An edit from the existing form (no minPrice field) must not wipe a seller-set minimum.
        custom = self.make_product(seller, minPrice=1200)
        edited = self.client.put(f"/api/v1/products/{custom['id']}", headers=seller, json={
            "name": "Bag v2", "category": "Style & Accessories", "price": 1500, "cost": 700, "stockQty": 3,
            "age": 75, "image": "./assets/images/jewellery.webp", "offers": True, "description": "A handmade bag.",
        })
        self.assertEqual(edited.json()["minPrice"], 1200)

    def test_long_unsold_stock_insight_for_the_seller_only(self):
        _, seller = self.register("seller", "i@example.com")
        _, buyer = self.register("buyer", "ib@example.com")
        product = self.make_product(seller)  # listed 75 days, price 1500, minimum 1100
        offer = self.client.post(f"/api/v1/products/{product['id']}/offers", json={"amount": 1150}, headers=buyer)
        self.assertIsNone(offer.json()["insight"])  # buyers never see seller insight
        inbox = self.client.get("/api/v1/offers", headers=seller).json()
        insight = inbox[0]["insight"]
        self.assertEqual(insight["type"], "consider_accepting")
        self.assertIn("75 days", insight["message"])
        self.assertIn("Consider accepting", insight["message"])

    def test_acceptance_starts_a_limited_checkout_window(self):
        _, seller = self.register("seller", "w@example.com")
        _, buyer = self.register("buyer", "wb@example.com")
        product = self.make_product(seller)
        offer = self.client.post(f"/api/v1/products/{product['id']}/offers", json={"amount": 1200}, headers=buyer).json()
        accepted = self.client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller).json()
        expires = datetime.fromisoformat(accepted["expiresAt"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        hours = (expires - datetime.now(timezone.utc)).total_seconds() / 3600
        self.assertTrue(23 < hours <= 24.1, hours)
        # Make the window lapse: the offer expires and checkout is refused.
        with Session(engine) as db:
            row = db.get(Offer, offer["id"])
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        refused = self.client.post("/api/v1/checkout/sessions", headers=buyer, json={
            "accepted_offer_id": offer["id"], "payment_method": "cod",
            "delivery_name": "Test Buyer", "delivery_phone": "9999999999", "delivery_address": "12 Test Street, Delhi",
        })
        self.assertEqual(refused.status_code, 409)

    def test_webhook_marks_paid_once_and_checks_signature(self):
        _, seller = self.register("seller", "h@example.com")
        _, buyer = self.register("buyer", "hb@example.com")
        product = self.make_product(seller)
        offer = self.client.post(f"/api/v1/products/{product['id']}/offers", json={"amount": 1200}, headers=buyer).json()
        self.client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller)
        original_request = main_module._razorpay_request
        main_module.RAZORPAY_KEY_ID, main_module.RAZORPAY_KEY_SECRET = "rzp_test_x", "secret"
        main_module.RAZORPAY_WEBHOOK_SECRET = "hook-secret"
        main_module._razorpay_request = lambda path, payload=None: {"id": "order_hook_1"}
        try:
            session = self.client.post("/api/v1/checkout/sessions", headers=buyer, json={
                "accepted_offer_id": offer["id"], "payment_method": "razorpay",
                "delivery_name": "Test Buyer", "delivery_phone": "9999999999", "delivery_address": "12 Test Street, Delhi",
            })
            self.assertEqual(session.status_code, 201, session.text)
            event = {"event": "payment.captured", "payload": {"payment": {"entity": {
                "id": "pay_hook_1", "order_id": "order_hook_1", "status": "captured", "amount": 120000, "currency": "INR",
            }}}}
            body = json.dumps(event).encode()
            good = hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
            bad = self.client.post("/api/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "nope"})
            self.assertEqual(bad.status_code, 400)
            first = self.client.post("/api/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": good})
            self.assertEqual(first.json()["status"], "paid")
            second = self.client.post("/api/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": good})
            self.assertEqual(second.json()["status"], "already_paid")
            order = self.client.get(f"/api/v1/orders/{session.json()['order_id']}", headers=buyer).json()
            self.assertEqual(order["paymentStatus"], "paid")
            self.assertEqual(self.client.get(f"/api/v1/products/{product['id']}").json()["stockQty"], 2)
            # An amount that does not match the order is never marked paid.
            event["payload"]["payment"]["entity"]["amount"] = 1
            tampered = json.dumps(event).encode()
            sig = hmac.new(b"hook-secret", tampered, hashlib.sha256).hexdigest()
            self.assertIn(
                self.client.post("/api/v1/payments/webhook", content=tampered, headers={"X-Razorpay-Signature": sig}).json()["status"],
                {"already_paid", "mismatch"},
            )
        finally:
            main_module._razorpay_request = original_request
            main_module.RAZORPAY_KEY_ID = main_module.RAZORPAY_KEY_SECRET = main_module.RAZORPAY_WEBHOOK_SECRET = ""


if __name__ == "__main__":
    unittest.main()

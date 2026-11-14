import hashlib
import hmac
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
_database_file = Path(tempfile.gettempdir()) / "zuna-api-tests.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{_database_file.as_posix()}"
os.environ["ZUNA_TOKEN_SECRET"] = "test-only-signing-key-that-is-never-deployed"

from app import main as main_module  # noqa: E402
from app.db import Base, engine, ensure_order_checkout_columns  # noqa: E402
from app.models import Product  # noqa: E402
from app.seed import SAMPLE_PRODUCTS, seed_data  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


class MarketplaceApiTests(unittest.TestCase):
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

    def test_existing_order_tables_gain_checkout_columns(self):
        legacy_engine = create_engine("sqlite://")
        try:
            with legacy_engine.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE orders (id VARCHAR(36) PRIMARY KEY)")
                connection.exec_driver_sql("CREATE TABLE product_orders (id VARCHAR(36) PRIMARY KEY)")
            ensure_order_checkout_columns(legacy_engine)
            columns = {column["name"] for column in inspect(legacy_engine).get_columns("orders")}
            product_order_columns = {
                column["name"] for column in inspect(legacy_engine).get_columns("product_orders")
            }
            self.assertTrue({
                "payment_method",
                "delivery_name",
                "delivery_phone",
                "delivery_address",
                "size",
            }.issubset(columns))
            self.assertIn("size", product_order_columns)
        finally:
            legacy_engine.dispose()

    def register(self, role, email):
        response = self.client.post("/api/v1/auth/register", json={
            "name": f"{role.title()} User",
            "email": email,
            "password": "correct horse battery",
            "role": role,
        })
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        return data, {"Authorization": f"Bearer {data['access_token']}"}

    def test_authentication_and_marketplace_data(self):
        response = self.client.get("/api/v1/products")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), len(SAMPLE_PRODUCTS))
        self.assertEqual(response.json()[0]["id"], "statement-jewellery")
        self.assertNotIn("cost", response.json()[0])

        user, headers = self.register("buyer", "buyer@example.com")
        self.assertEqual(user["user"]["role"], "buyer")
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).json()["email"], "buyer@example.com")
        login = self.client.post("/api/v1/auth/login", json={
            "email": "buyer@example.com",
            "password": "correct horse battery",
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={
            "email": "buyer@example.com",
            "password": "incorrect password",
        }).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_each_buyer_category_has_multiple_sample_products(self):
        categories = {entry[4] for entry in SAMPLE_PRODUCTS}
        for category in categories:
            with self.subTest(category=category):
                response = self.client.get("/api/v1/products", params={"category": category})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertGreaterEqual(len(response.json()), 3)

    def test_saree_variants_are_grouped_as_available_stock(self):
        response = self.client.get("/api/v1/products")
        self.assertEqual(response.status_code, 200)
        sarees = [product for product in response.json() if product["variantGroup"] == "Sarees"]
        self.assertEqual(len(sarees), 4)
        self.assertTrue(all(product["available"] and product["stockQty"] > 0 for product in sarees))

    def test_headphone_samples_use_separate_pictures_and_share_a_family(self):
        response = self.client.get("/api/v1/products")
        self.assertEqual(response.status_code, 200)
        headphones = [product for product in response.json() if product["variantGroup"] == "Headphones And Earbuds"]
        self.assertEqual(len(headphones), 6)
        self.assertEqual(len({product["image"] for product in headphones}), 6)
        self.assertTrue(all(product["available"] and product["stockQty"] > 0 for product in headphones))

    def test_pic_category_samples_are_grouped_and_available(self):
        response = self.client.get("/api/v1/products")
        self.assertEqual(response.status_code, 200)
        products = response.json()
        groups = {
            "Jewellery": (10, "Jewellery"),
            "Scarves": (7, "Style & Accessories"),
            "Clothing": (6, "Fashion & Footwear"),
            "Bags": (6, "Style & Accessories"),
        }
        for variant_group, (count, category) in groups.items():
            with self.subTest(variant_group=variant_group):
                samples = [product for product in products if product["variantGroup"] == variant_group]
                self.assertEqual(len(samples), count)
                self.assertTrue(all(product["category"] == category for product in samples))
                self.assertEqual(len({product["image"] for product in samples}), count)
                self.assertTrue(all(product["available"] and product["stockQty"] > 0 for product in samples))

    def test_new_collage_samples_are_individual_grouped_products(self):
        response = self.client.get("/api/v1/products")
        self.assertEqual(response.status_code, 200)
        products = response.json()
        groups = {
            "Stationery": (21, "Gifts & Stationery"),
            "Collectibles": (8, "Art & Collectibles"),
            "Food Storage": (3, "Everyday Finds"),
        }
        for variant_group, (count, category) in groups.items():
            with self.subTest(variant_group=variant_group):
                samples = [product for product in products if product["variantGroup"] == variant_group]
                self.assertEqual(len(samples), count)
                self.assertTrue(all(product["category"] == category for product in samples))
                self.assertEqual(len({product["image"] for product in samples}), count)
                self.assertTrue(all(product["available"] and product["stockQty"] > 0 for product in samples))

    def test_each_sample_uses_a_distinct_existing_picture(self):
        image_paths = [entry[7] for entry in SAMPLE_PRODUCTS]
        self.assertEqual(len(image_paths), len(set(image_paths)))
        for image_path in image_paths:
            path = BACKEND_DIR.parent / "frontend" / image_path.removeprefix("./")
            with self.subTest(image=image_path):
                self.assertTrue(path.is_file())

    def test_product_stock_and_size_options_are_serialized(self):
        out_of_stock = self.client.get("/api/v1/products/custom-phone-case").json()
        self.assertEqual(out_of_stock["stockQty"], 0)
        self.assertFalse(out_of_stock["available"])
        self.assertEqual(out_of_stock["stock"], "Out of stock")
        self.assertEqual(out_of_stock["sizes"], ["One size"])
        unavailable = self.client.get("/api/v1/products", params={"available": "false"}).json()
        self.assertIn("custom-phone-case", [product["id"] for product in unavailable])
        available = self.client.get("/api/v1/products", params={"available": "true"}).json()
        self.assertTrue(all(product["stockQty"] > 0 for product in available))

        sneakers = self.client.get("/api/v1/products/custom-sneakers").json()
        self.assertEqual(sneakers["sizes"], ["UK 6", "UK 7", "UK 8", "UK 9", "UK 10"])

    def test_expected_delivery_skips_weekends(self):
        expected = main_module._expected_delivery(datetime(2026, 11, 13, 20, tzinfo=timezone.utc))
        self.assertEqual(expected["date"], "2026-11-20")

    def test_seeding_refreshes_picture_paths_for_existing_samples(self):
        with Session(engine) as db:
            product = db.get(Product, "brass-cuff-bracelet")
            product.image = "./assets/generated/products/statement-jewellery.svg"
            headphones = db.get(Product, "studio-headphones")
            headphones.image = "./assets/generated/products/studio-headphones.jpg"
            headphones.tags = "headphones,audio,electronics"
            db.commit()
            seed_data(db)
            self.assertEqual(product.image, "./assets/generated/products/brass-cuff-bracelet.svg")
            self.assertEqual(headphones.image, "./assets/generated/products/headphones-wireless-black.png")
            self.assertEqual(headphones.name, "Studio headphones · matte black")
            self.assertTrue(headphones.tags.startswith("family:headphones-and-earbuds,"))

    def test_seller_listing_and_buyer_negotiation_flow(self):
        _, seller_headers = self.register("seller", "seller@example.com")
        _, buyer_headers = self.register("buyer", "buyer@example.com")
        payload = {
            "name": "Handmade brass bowl",
            "category": "Home, Living & Objects",
            "price": 2000,
            "cost": 900,
            "stockQty": 4,
            "age": 1,
            "image": "./assets/images/jewellery.webp",
            "offers": True,
            "description": "A handmade bowl for daily use.",
        }
        created = self.client.post("/api/v1/products", json=payload, headers=seller_headers)
        self.assertEqual(created.status_code, 201, created.text)
        product = created.json()
        self.assertEqual(product["seller"], "Seller User's studio")
        seller_products = self.client.get("/api/v1/seller/products", headers=seller_headers).json()
        self.assertEqual(len(seller_products), 1)
        self.assertEqual(seller_products[0]["cost"], 900)

        offer = self.client.post(
            f"/api/v1/products/{product['id']}/offers",
            json={"amount": 1500},
            headers=buyer_headers,
        )
        self.assertEqual(offer.status_code, 201, offer.text)
        offer_id = offer.json()["id"]
        counter = self.client.post(
            f"/api/v1/offers/{offer_id}/counter",
            json={"amount": 1800},
            headers=seller_headers,
        )
        self.assertEqual(counter.status_code, 200, counter.text)
        self.assertEqual(counter.json()["status"], "countered")
        accepted = self.client.post(f"/api/v1/offers/{offer_id}/accept", headers=buyer_headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["acceptedPrice"], 1800)

        checkout = self.client.post(
            "/api/v1/checkout/sessions",
            json={"accepted_offer_id": offer_id},
            headers=buyer_headers,
        )
        self.assertEqual(checkout.status_code, 503)
        self.assertIn("Razorpay is not configured", checkout.json()["detail"])

    def test_sample_product_negotiation_and_checkout_use_the_accepted_price(self):
        _, seller_headers = self.register("seller", "sample.seller@example.com")
        _, buyer_headers = self.register("buyer", "sample.buyer@example.com")
        product = self.client.get("/api/v1/products/studio-headphones").json()
        self.assertTrue(product["isSample"])
        self.assertTrue(product["offers"])
        self.assertIn(
            product["id"],
            [item["id"] for item in self.client.get("/api/v1/products", params={"offers": True}).json()],
        )
        self.assertNotIn(
            product["id"],
            [item["id"] for item in self.client.get("/api/v1/products", params={"offers": False}).json()],
        )
        over_price_offer = self.client.post(
            f"/api/v1/products/{product['id']}/offers",
            json={"amount": product["price"] + 1},
            headers=buyer_headers,
        )
        self.assertEqual(over_price_offer.status_code, 422)

        offer = self.client.post(
            f"/api/v1/products/{product['id']}/offers",
            json={"amount": 2500},
            headers=buyer_headers,
        )
        self.assertEqual(offer.status_code, 201, offer.text)
        offer_id = offer.json()["id"]
        inbox = self.client.get("/api/v1/offers", headers=seller_headers)
        self.assertEqual(inbox.status_code, 200, inbox.text)
        self.assertEqual(len(inbox.json()), 1)
        self.assertTrue(inbox.json()[0]["product"]["isSample"])

        counter = self.client.post(
            f"/api/v1/offers/{offer_id}/counter",
            json={"amount": 2800},
            headers=seller_headers,
        )
        self.assertEqual(counter.status_code, 200, counter.text)
        accepted = self.client.post(f"/api/v1/offers/{offer_id}/accept", headers=buyer_headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["acceptedPrice"], 2800)

        _, second_buyer_headers = self.register("buyer", "sample.seller-accepted@example.com")
        seller_offer = self.client.post(
            f"/api/v1/products/{product['id']}/offers",
            json={"amount": 2200},
            headers=second_buyer_headers,
        )
        self.assertEqual(seller_offer.status_code, 201, seller_offer.text)
        seller_accepted = self.client.post(
            f"/api/v1/offers/{seller_offer.json()['id']}/accept",
            headers=seller_headers,
        )
        self.assertEqual(seller_accepted.status_code, 200, seller_accepted.text)
        self.assertEqual(seller_accepted.json()["acceptedPrice"], 2200)

        original_request = main_module._razorpay_request
        original_key_id = main_module.RAZORPAY_KEY_ID
        original_key_secret = main_module.RAZORPAY_KEY_SECRET
        main_module.RAZORPAY_KEY_ID = "rzp_test_public"
        main_module.RAZORPAY_KEY_SECRET = "sample-test-secret"
        main_module._razorpay_request = lambda path, payload=None: {"id": f"order_{payload['receipt']}"}
        try:
            checkout = self.client.post(
                "/api/v1/checkout/sessions",
                json={"accepted_offer_id": offer_id},
                headers=buyer_headers,
            )
            self.assertEqual(checkout.status_code, 201, checkout.text)
            self.assertEqual(checkout.json()["amount"], 2800)

            missing_cod_delivery = self.client.post(
                "/api/v1/checkout/sessions",
                json={
                    "accepted_offer_id": seller_offer.json()["id"],
                    "payment_method": "cod",
                },
                headers=second_buyer_headers,
            )
            self.assertEqual(missing_cod_delivery.status_code, 422, missing_cod_delivery.text)

            seller_accepted_checkout = self.client.post(
                "/api/v1/checkout/sessions",
                json={
                    "accepted_offer_id": seller_offer.json()["id"],
                    "payment_method": "cod",
                    "delivery_name": "Second Buyer",
                    "delivery_phone": "+91 9876543210",
                    "delivery_address": "12 Market Road, Jaipur",
                },
                headers=second_buyer_headers,
            )
            self.assertEqual(seller_accepted_checkout.status_code, 201, seller_accepted_checkout.text)
            self.assertEqual(seller_accepted_checkout.json()["amount"], 2200)
            self.assertEqual(seller_accepted_checkout.json()["payment_status"], "cod_pending")
        finally:
            main_module._razorpay_request = original_request
            main_module.RAZORPAY_KEY_ID = original_key_id
            main_module.RAZORPAY_KEY_SECRET = original_key_secret

        cod_order = self.client.get(
            f"/api/v1/orders/{seller_accepted_checkout.json()['order_id']}",
            headers=second_buyer_headers,
        )
        self.assertEqual(cod_order.status_code, 200, cod_order.text)
        self.assertEqual(cod_order.json()["paymentMethod"], "cod")
        self.assertEqual(cod_order.json()["paymentStatus"], "cod_pending")
        self.assertEqual(cod_order.json()["size"], "One size")
        self.assertEqual(cod_order.json()["offerId"], seller_offer.json()["id"])
        self.assertEqual(cod_order.json()["delivery"]["address"], "12 Market Road, Jaipur")
        stock_after_cod = self.client.get(f"/api/v1/products/{product['id']}").json()["stockQty"]
        repeated_checkout = self.client.post(
            "/api/v1/checkout/sessions",
            json={
                "accepted_offer_id": seller_offer.json()["id"],
                "payment_method": "cod",
                "delivery_name": "Second Buyer",
                "delivery_phone": "+91 9876543210",
                "delivery_address": "12 Market Road, Jaipur",
            },
            headers=second_buyer_headers,
        )
        self.assertEqual(repeated_checkout.status_code, 201, repeated_checkout.text)
        self.assertEqual(repeated_checkout.json()["order_id"], cod_order.json()["id"])
        self.assertEqual(self.client.get(f"/api/v1/products/{product['id']}").json()["stockQty"], stock_after_cod)
        verify_cod_payment = self.client.post(
            "/api/v1/payments/verify",
            headers=second_buyer_headers,
            json={
                "order_id": cod_order.json()["id"],
                "razorpay_order_id": "not-a-razorpay-order",
                "razorpay_payment_id": "not-a-payment",
                "razorpay_signature": "not-a-signature",
            },
        )
        self.assertEqual(verify_cod_payment.status_code, 409, verify_cod_payment.text)

        direct_checkout = self.client.post("/api/v1/checkout/products", headers=buyer_headers, json={
            "product_id": product["id"],
            "payment_method": "cod",
            "delivery_name": "Buyer User",
            "delivery_phone": "+91 9876543210",
            "delivery_address": "12 Market Road, Jaipur",
        })
        self.assertEqual(direct_checkout.status_code, 201, direct_checkout.text)
        self.assertEqual(direct_checkout.json()["amount"], product["price"])
        self.assertEqual(direct_checkout.json()["paymentStatus"], "cod_pending")

    def test_collaboration_request_referral_and_ownership(self):
        _, seller_headers = self.register("seller", "seller@example.com")
        _, creator_headers = self.register("creator", "creator@example.com")
        _, buyer_headers = self.register("buyer", "buyer@example.com")
        payload = {
            "name": "Handmade journal",
            "category": "Gifts & Stationery",
            "price": 800,
            "cost": 200,
            "stockQty": 12,
            "age": 0,
            "image": "./assets/images/textile.webp",
            "offers": True,
            "description": "A hand-bound paper journal.",
        }
        product = self.client.post("/api/v1/products", json=payload, headers=seller_headers).json()
        opportunity = self.client.post("/api/v1/collaborations", headers=seller_headers, json={
            "product_id": product["id"],
            "collaboration_type": "Editorial feature",
            "brief": "Share the story of this handmade journal.",
            "terms": "One editorial post.",
        })
        self.assertEqual(opportunity.status_code, 201, opportunity.text)
        public_id = opportunity.json()["id"]
        self.assertEqual(len(self.client.get("/api/v1/collaborations/opportunities", headers=creator_headers).json()), 1)
        request = self.client.post(
            f"/api/v1/collaborations/{public_id}/requests",
            headers=creator_headers,
        )
        self.assertEqual(request.status_code, 201, request.text)
        request_id = request.json()["id"]
        self.assertEqual(
            self.client.get(f"/api/v1/collaborations/{public_id}/requests", headers=creator_headers).status_code,
            403,
        )
        accepted = self.client.post(
            f"/api/v1/collaborations/{public_id}/requests/{request_id}/accept",
            headers=seller_headers,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertIn("?ref=", accepted.json()["referralLink"])
        code = accepted.json()["referralLink"].split("?ref=", 1)[1].split("#", 1)[0]
        self.assertEqual(self.client.post(f"/api/v1/referrals/{code}/visit").status_code, 200)
        offer = self.client.post(
            f"/api/v1/products/{product['id']}/offers",
            headers=buyer_headers,
            json={"amount": 700},
        ).json()
        self.assertEqual(self.client.post(
            f"/api/v1/offers/{offer['id']}/accept",
            headers=seller_headers,
        ).status_code, 200)

        original_request = main_module._razorpay_request
        main_module.RAZORPAY_KEY_ID = "rzp_test_public"
        main_module.RAZORPAY_KEY_SECRET = "test-payment-secret"
        main_module._razorpay_request = lambda path, payload=None: (
            {"id": "order_test_123"} if payload else {
                "id": "pay_test_123",
                "order_id": "order_test_123",
                "status": "captured",
                "amount": 70000,
                "currency": "INR",
            }
        )
        try:
            checkout = self.client.post("/api/v1/checkout/sessions", headers=buyer_headers, json={
                "accepted_offer_id": offer["id"],
                "referral_code": code,
            })
            self.assertEqual(checkout.status_code, 201, checkout.text)
            session = checkout.json()
            signed_data = f"{session['razorpay_order_id']}|pay_test_123".encode("utf-8")
            signature = hmac.new(b"test-payment-secret", signed_data, hashlib.sha256).hexdigest()
            verified = self.client.post("/api/v1/payments/verify", headers=buyer_headers, json={
                "order_id": session["order_id"],
                "razorpay_order_id": session["razorpay_order_id"],
                "razorpay_payment_id": "pay_test_123",
                "razorpay_signature": signature,
            })
            self.assertEqual(verified.status_code, 200, verified.text)
            self.assertEqual(verified.json()["paymentStatus"], "paid")
            referral = self.client.get("/api/v1/creator/referrals", headers=creator_headers).json()[0]
            self.assertEqual(referral["clicks"], 1)
            self.assertEqual(referral["conversions"], 1)
        finally:
            main_module._razorpay_request = original_request
            main_module.RAZORPAY_KEY_ID = ""
            main_module.RAZORPAY_KEY_SECRET = ""

    def test_cash_on_delivery_creates_an_unpaid_product_order(self):
        _, buyer_headers = self.register("buyer", "cod.buyer@example.com")
        products = self.client.get("/api/v1/products").json()
        product = products[0]
        invalid_size = self.client.post("/api/v1/checkout/products", headers=buyer_headers, json={
            "product_id": product["id"],
            "size": "XL",
            "payment_method": "cod",
            "delivery_name": "Buyer User",
            "delivery_phone": "+91 9876543210",
            "delivery_address": "12 Market Road, Jaipur",
        })
        self.assertEqual(invalid_size.status_code, 422)
        checkout = self.client.post("/api/v1/checkout/products", headers=buyer_headers, json={
            "product_id": product["id"],
            "payment_method": "cod",
            "delivery_name": "Buyer User",
            "delivery_phone": "+91 9876543210",
            "delivery_address": "12 Market Road, Jaipur",
        })
        self.assertEqual(checkout.status_code, 201, checkout.text)
        order = checkout.json()
        self.assertEqual(order["paymentMethod"], "cod")
        self.assertEqual(order["paymentStatus"], "cod_pending")
        self.assertEqual(order["amount"], product["price"])
        self.assertEqual(order["size"], "One size")
        self.assertEqual(order["expectedDelivery"]["window"], "9:00 AM–6:00 PM IST")
        self.assertRegex(order["expectedDelivery"]["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(self.client.get("/api/v1/orders", headers=buyer_headers).json()[0]["id"], order["id"])
        updated_product = self.client.get(f"/api/v1/products/{product['id']}").json()
        self.assertEqual(updated_product["stockQty"], product["stockQty"] - 1)
        self.assertTrue(updated_product["available"])
        self.assertEqual(
            self.client.get(f"/api/v1/orders/{order['id']}", headers=buyer_headers).json()["delivery"]["address"],
            "12 Market Road, Jaipur",
        )
        self.assertEqual(self.client.post("/api/v1/checkout/products", headers=buyer_headers, json={
            "product_id": "custom-phone-case",
            "payment_method": "cod",
            "delivery_name": "Buyer User",
            "delivery_phone": "9876543210",
            "delivery_address": "12 Market Road, Jaipur",
        }).status_code, 409)

    def test_direct_online_checkout_without_razorpay_keys_creates_no_order(self):
        _, buyer_headers = self.register("buyer", "unconfigured.direct@example.com")
        product = self.client.get("/api/v1/products").json()[0]
        original_key_id = main_module.RAZORPAY_KEY_ID
        original_key_secret = main_module.RAZORPAY_KEY_SECRET
        main_module.RAZORPAY_KEY_ID = ""
        main_module.RAZORPAY_KEY_SECRET = ""
        try:
            response = self.client.post("/api/v1/checkout/products", headers=buyer_headers, json={
                "product_id": product["id"],
                "payment_method": "razorpay",
                "delivery_name": "Buyer User",
                "delivery_phone": "9876543210",
                "delivery_address": "12 Market Road, Jaipur",
            })
            self.assertEqual(response.status_code, 503)
            self.assertEqual(self.client.get("/api/v1/orders", headers=buyer_headers).json(), [])
        finally:
            main_module.RAZORPAY_KEY_ID = original_key_id
            main_module.RAZORPAY_KEY_SECRET = original_key_secret

    def test_direct_online_checkout_verifies_razorpay_before_marking_paid(self):
        _, buyer_headers = self.register("buyer", "direct.buyer@example.com")
        product = self.client.get("/api/v1/products").json()[0]
        original_request = main_module._razorpay_request
        main_module.RAZORPAY_KEY_ID = "rzp_test_public"
        main_module.RAZORPAY_KEY_SECRET = "test-payment-secret"
        main_module._razorpay_request = lambda path, payload=None: (
            {"id": "order_direct_123"} if payload else {
                "id": "pay_direct_123",
                "order_id": "order_direct_123",
                "status": "captured",
                "amount": product["price"] * 100,
                "currency": "INR",
            }
        )
        try:
            checkout = self.client.post("/api/v1/checkout/products", headers=buyer_headers, json={
                "product_id": product["id"],
                "payment_method": "razorpay",
                "delivery_name": "Buyer User",
                "delivery_phone": "9876543210",
                "delivery_address": "12 Market Road, Jaipur",
            })
            self.assertEqual(checkout.status_code, 201, checkout.text)
            session = checkout.json()
            signed_data = f"{session['razorpay_order_id']}|pay_direct_123".encode("utf-8")
            signature = hmac.new(b"test-payment-secret", signed_data, hashlib.sha256).hexdigest()
            verified = self.client.post("/api/v1/payments/verify", headers=buyer_headers, json={
                "order_id": session["id"],
                "razorpay_order_id": session["razorpay_order_id"],
                "razorpay_payment_id": "pay_direct_123",
                "razorpay_signature": signature,
            })
            self.assertEqual(verified.status_code, 200, verified.text)
            self.assertEqual(verified.json()["paymentStatus"], "paid")
            self.assertEqual(verified.json()["paymentMethod"], "razorpay")
            self.assertEqual(verified.json()["size"], "One size")
            self.assertEqual(verified.json()["expectedDelivery"]["window"], "9:00 AM–6:00 PM IST")
            self.assertEqual(self.client.get(f"/api/v1/orders/{session['id']}", headers=buyer_headers).json()["paymentStatus"], "paid")
            updated_product = self.client.get(f"/api/v1/products/{product['id']}").json()
            self.assertEqual(updated_product["stockQty"], product["stockQty"] - 1)
        finally:
            main_module._razorpay_request = original_request
            main_module.RAZORPAY_KEY_ID = ""
            main_module.RAZORPAY_KEY_SECRET = ""

    def test_seller_pricing_estimate_is_bounded_and_explainable(self):
        _, seller_headers = self.register("seller", "pricing.seller@example.com")
        response = self.client.post("/api/v1/seller/pricing/suggest", headers=seller_headers, json={
            "unit_cost": 820,
            "target_margin_percent": 35,
            "inventory_age_days": 90,
            "demand_index": 75,
        })
        self.assertEqual(response.status_code, 200, response.text)
        estimate = response.json()
        self.assertGreaterEqual(estimate["suggestedPrice"], 820)
        self.assertIn("not an AI prediction", estimate["explanation"])
        self.assertEqual(self.client.post("/api/v1/seller/pricing/suggest", json={
            "unit_cost": 820,
            "target_margin_percent": 35,
            "inventory_age_days": 90,
            "demand_index": 75,
        }).status_code, 401)


if __name__ == "__main__":
    unittest.main()

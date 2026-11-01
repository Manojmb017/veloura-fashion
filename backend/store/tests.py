from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from django.db import DatabaseError, connection
from django.db.utils import OperationalError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from .models import Address, Order, OrderItem, Product


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/auth/register/"
        self.login_url = "/api/auth/login/"
        self.refresh_url = "/api/auth/token/refresh/"
        self.me_url = "/api/auth/me/"

    def test_register_success(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "strongpassword123",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "jane@example.com")
        self.assertEqual(response.data["user"]["name"], "Jane Doe")
        self.assertTrue(User.objects.filter(username="jane@example.com").exists())
        user = User.objects.get(email="jane@example.com")
        self.assertNotEqual(user.password, "strongpassword123")
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertTrue(user.check_password("strongpassword123"))

    def test_register_duplicate_email(self):
        User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="password123",
            first_name="Existing User",
        )
        payload = {
            "name": "Another User",
            "email": "existing@example.com",
            "password": "password123",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_me_endpoint(self):
        User.objects.create_user(
            username="loginuser@example.com",
            email="loginuser@example.com",
            password="mysecretpassword",
            first_name="Login User",
        )
        response = self.client.post(
            self.login_url,
            {"email": "loginuser@example.com", "password": "mysecretpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]
        self.assertEqual(response.data["user"]["name"], "Login User")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_resp = self.client.get(self.me_url)
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["user"]["email"], "loginuser@example.com")

        self.client.credentials()
        ref_resp = self.client.post(self.refresh_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(ref_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", ref_resp.data)

    def test_login_wrong_password(self):
        User.objects.create_user(
            username="wrongpass@example.com",
            email="wrongpass@example.com",
            password="correctpassword",
        )
        response = self.client.post(
            self.login_url,
            {"email": "wrongpass@example.com", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_unknown_email_rejected(self):
        response = self.client.post(
            self.login_url,
            {"email": "nobody@example.com", "password": "somepassword123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_case_insensitive_email(self):
        User.objects.create_user(
            username="casetest@example.com",
            email="casetest@example.com",
            password="casepassword123",
            first_name="Case User",
        )
        # Test all uppercase
        resp_upper = self.client.post(
            self.login_url,
            {"email": "CASETEST@EXAMPLE.COM", "password": "casepassword123"},
            format="json",
        )
        self.assertEqual(resp_upper.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_upper.data["user"]["email"], "casetest@example.com")

        # Test mixed case with whitespace
        resp_mixed = self.client.post(
            self.login_url,
            {"email": "  CaseTest@Example.Com  ", "password": "casepassword123"},
            format="json",
        )
        self.assertEqual(resp_mixed.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_mixed.data["user"]["email"], "casetest@example.com")

    def test_login_multiple_distinct_users_and_isolation(self):
        user_a = User.objects.create_user(
            username="user_alpha@example.com",
            email="user_alpha@example.com",
            password="PasswordAlpha123!",
            first_name="Alpha",
        )
        user_b = User.objects.create_user(
            username="user_beta@example.com",
            email="user_beta@example.com",
            password="PasswordBeta456!",
            first_name="Beta",
        )

        # User A logs in with their credentials
        resp_a = self.client.post(
            self.login_url,
            {"email": "user_alpha@example.com", "password": "PasswordAlpha123!"},
            format="json",
        )
        self.assertEqual(resp_a.status_code, status.HTTP_200_OK)
        token_a = resp_a.data["access"]
        self.assertIn("refresh", resp_a.data)
        self.assertEqual(resp_a.data["user"]["id"], user_a.id)
        self.assertEqual(resp_a.data["user"]["email"], "user_alpha@example.com")
        self.assertEqual(resp_a.data["user"]["name"], "Alpha")

        # User B logs in with their credentials
        resp_b = self.client.post(
            self.login_url,
            {"email": "user_beta@example.com", "password": "PasswordBeta456!"},
            format="json",
        )
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)
        token_b = resp_b.data["access"]
        self.assertIn("refresh", resp_b.data)
        self.assertEqual(resp_b.data["user"]["id"], user_b.id)
        self.assertEqual(resp_b.data["user"]["email"], "user_beta@example.com")
        self.assertEqual(resp_b.data["user"]["name"], "Beta")

        # Ensure tokens are distinct
        self.assertNotEqual(token_a, token_b)

        # Profile endpoint with User A token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}")
        me_a = self.client.get(self.me_url)
        self.assertEqual(me_a.status_code, status.HTTP_200_OK)
        self.assertEqual(me_a.data["user"]["id"], user_a.id)
        self.assertEqual(me_a.data["user"]["email"], "user_alpha@example.com")
        self.assertEqual(me_a.data["user"]["name"], "Alpha")

        # Profile endpoint with User B token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_b}")
        me_b = self.client.get(self.me_url)
        self.assertEqual(me_b.status_code, status.HTTP_200_OK)
        self.assertEqual(me_b.data["user"]["id"], user_b.id)
        self.assertEqual(me_b.data["user"]["email"], "user_beta@example.com")
        self.assertEqual(me_b.data["user"]["name"], "Beta")

        # Cross credentials must fail
        self.client.credentials()
        cross_a = self.client.post(
            self.login_url,
            {"email": "user_alpha@example.com", "password": "PasswordBeta456!"},
            format="json",
        )
        self.assertEqual(cross_a.status_code, status.HTTP_400_BAD_REQUEST)

        cross_b = self.client.post(
            self.login_url,
            {"email": "user_beta@example.com", "password": "PasswordAlpha123!"},
            format="json",
        )
        self.assertEqual(cross_b.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_me_succeeds_when_address_lookup_raises_operational_error(self):
        User.objects.create_user(
            username="operroruser@example.com",
            email="operroruser@example.com",
            password="mysecretpassword",
            first_name="OpError User",
        )
        with patch("store.serializers.Address.objects.filter", side_effect=OperationalError("Unknown column 'addresses.full_name' in 'field list'")), \
             patch("store.views.Address.objects.filter", side_effect=OperationalError("Unknown column 'addresses.full_name' in 'field list'")):
            response = self.client.post(
                self.login_url,
                {"email": "operroruser@example.com", "password": "mysecretpassword"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("access", response.data)
            self.assertIn("refresh", response.data)
            self.assertEqual(response.data["user"]["name"], "OpError User")
            self.assertEqual(response.data["user"]["phone"], "")
            self.assertEqual(response.data["user"]["address"], "")

            access_token = response.data["access"]
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
            me_resp = self.client.get(self.me_url)
            self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
            self.assertEqual(me_resp.data["user"]["email"], "operroruser@example.com")
            self.assertEqual(me_resp.data["user"]["phone"], "")
            self.assertEqual(me_resp.data["user"]["address"], "")

    def test_me_unauthenticated(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_get_and_patch_profile_details(self):
        user = User.objects.create_user(
            username="profiletest@example.com",
            email="profiletest@example.com",
            password="password123",
            first_name="Initial Name",
        )
        self.client.force_authenticate(user=user)

        # Initially, no phone or address
        get_res = self.client.get(self.me_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["user"]["phone"], "")
        self.assertEqual(get_res.data["user"]["address"], "")

        # Patch name, phone, address
        patch_res = self.client.patch(
            self.me_url,
            {
                "name": "Updated Name",
                "phone": "9876543210",
                "address": "42 MG Road, Indiranagar, Bengaluru, Karnataka, 560038",
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["user"]["name"], "Updated Name")
        self.assertEqual(patch_res.data["user"]["phone"], "9876543210")
        self.assertIn("42 MG Road", patch_res.data["user"]["address"])

        # Verify persisted in MySQL models
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated Name")
        saved_addr = Address.objects.filter(user=user, is_default=True).first()
        self.assertIsNotNone(saved_addr)
        self.assertEqual(saved_addr.phone, "9876543210")
        self.assertEqual(saved_addr.address_line1, "42 MG Road")

        # GET request again returns saved data
        get_res2 = self.client.get(self.me_url)
        self.assertEqual(get_res2.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res2.data["user"]["phone"], "9876543210")
        self.assertIn("42 MG Road", get_res2.data["user"]["address"])

        # Edit address a second time - verify existing record is updated in place with no duplicates
        patch_res2 = self.client.patch(
            self.me_url,
            {
                "phone": "9998887776",
                "address": "12 MG Road, Bengaluru, Karnataka - 560001",
            },
            format="json",
        )
        self.assertEqual(patch_res2.status_code, status.HTTP_200_OK)
        saved_addr.refresh_from_db()
        self.assertEqual(saved_addr.phone, "9998887776")
        self.assertEqual(saved_addr.address_line1, "12 MG Road")
        self.assertEqual(saved_addr.address_line2, "")
        self.assertEqual(saved_addr.city, "Bengaluru")
        self.assertEqual(saved_addr.postal_code, "560001")
        # Ensure only 1 default address and no duplicate address objects
        self.assertEqual(Address.objects.filter(user=user, is_default=True).count(), 1)
        self.assertEqual(Address.objects.filter(user=user).count(), 1)

        # Edit address to "btm" - verify all absent fields are cleared and exact text is retained
        patch_res3 = self.client.patch(
            self.me_url,
            {"address": "btm"},
            format="json",
        )
        self.assertEqual(patch_res3.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res3.data["user"]["address"], "btm")
        saved_addr.refresh_from_db()
        self.assertEqual(saved_addr.address_line1, "btm")
        self.assertEqual(saved_addr.address_line2, "")
        self.assertEqual(saved_addr.city, "")
        self.assertEqual(saved_addr.state, "")
        self.assertEqual(saved_addr.postal_code, "")
        self.assertEqual(Address.objects.filter(user=user, is_default=True).count(), 1)
        self.assertEqual(Address.objects.filter(user=user).count(), 1)

        get_res3 = self.client.get(self.me_url)
        self.assertEqual(get_res3.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res3.data["user"]["address"], "btm")

        # Edit address to "12 MG Road, Bengaluru" - verify only explicitly given city is saved
        patch_res4 = self.client.patch(
            self.me_url,
            {"address": "12 MG Road, Bengaluru"},
            format="json",
        )
        self.assertEqual(patch_res4.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res4.data["user"]["address"], "12 MG Road, Bengaluru")
        saved_addr.refresh_from_db()
        self.assertEqual(saved_addr.address_line1, "12 MG Road")
        self.assertEqual(saved_addr.address_line2, "")
        self.assertEqual(saved_addr.city, "Bengaluru")
        self.assertEqual(saved_addr.state, "")
        self.assertEqual(saved_addr.postal_code, "")
        self.assertEqual(Address.objects.filter(user=user, is_default=True).count(), 1)
        self.assertEqual(Address.objects.filter(user=user).count(), 1)

        get_res4 = self.client.get(self.me_url)
        self.assertEqual(get_res4.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res4.data["user"]["address"], "12 MG Road, Bengaluru")

    def test_me_user_isolation(self):
        user1 = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
            password="password123",
            first_name="User One",
        )
        user2 = User.objects.create_user(
            username="user2@example.com",
            email="user2@example.com",
            password="password123",
            first_name="User Two",
        )
        Address.objects.create(
            user=user1,
            full_name="User One",
            phone="1111111111",
            address_line1="111 Secret Lane",
            city="Bengaluru",
            state="Karnataka",
            postal_code="560001",
            is_default=True,
        )

        # Authenticate as user2
        self.client.force_authenticate(user=user2)
        get_res = self.client.get(self.me_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["user"]["phone"], "")
        self.assertEqual(get_res.data["user"]["address"], "")
        self.assertNotIn("1111111111", get_res.data["user"]["phone"])
        self.assertNotIn("Secret", get_res.data["user"]["address"])


class AddressAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            username="usera@example.com",
            email="usera@example.com",
            password="password123",
            first_name="User A",
        )
        self.user_b = User.objects.create_user(
            username="userb@example.com",
            email="userb@example.com",
            password="password123",
            first_name="User B",
        )
        self.url = "/api/addresses/"

    def test_unauthenticated_address_access_denied(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post(self.url, {"full_name": "Test"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_address_crud_and_isolation(self):
        # User A logs in and creates an address
        self.client.force_authenticate(user=self.user_a)
        payload = {
            "full_name": "User A Delivery",
            "phone": "9876543210",
            "address_line1": "100 MG Road",
            "address_line2": "Suite 4B",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
            "country": "India",
            "label": "Home",
            "is_default": True,
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        addr_id = res.data["id"]
        self.assertEqual(res.data["full_name"], "User A Delivery")
        self.assertTrue(res.data["is_default"])

        # User A retrieves address list
        list_res = self.client.get(self.url)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["id"], addr_id)

        # User A updates address
        patch_res = self.client.patch(
            f"{self.url}{addr_id}/",
            {"address_line1": "101 MG Road Updated"},
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["address_line1"], "101 MG Road Updated")

        # User B logs in and should NOT see User A's address
        self.client.force_authenticate(user=self.user_b)
        b_list = self.client.get(self.url)
        self.assertEqual(b_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(b_list.data), 0)

        # User B attempts to access, patch, or delete User A's address -> 404
        b_get = self.client.get(f"{self.url}{addr_id}/")
        self.assertEqual(b_get.status_code, status.HTTP_404_NOT_FOUND)

        b_patch = self.client.patch(
            f"{self.url}{addr_id}/",
            {"full_name": "Hacked Name"},
            format="json",
        )
        self.assertEqual(b_patch.status_code, status.HTTP_404_NOT_FOUND)

        b_del = self.client.delete(f"{self.url}{addr_id}/")
        self.assertEqual(b_del.status_code, status.HTTP_404_NOT_FOUND)

        # User A deletes their address -> 204
        self.client.force_authenticate(user=self.user_a)
        a_del = self.client.delete(f"{self.url}{addr_id}/")
        self.assertEqual(a_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Address.objects.filter(id=addr_id).count(), 0)


class OrderAPITests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(180) NOT NULL,
                    slug VARCHAR(200) NOT NULL UNIQUE,
                    description TEXT NULL,
                    category VARCHAR(50) NOT NULL,
                    product_type VARCHAR(80) NOT NULL DEFAULT 'Clothing',
                    price DECIMAL(10,2) NOT NULL,
                    compare_at_price DECIMAL(10,2) NULL,
                    image_url VARCHAR(1000) NULL,
                    color VARCHAR(80) NULL,
                    stock_quantity INT UNSIGNED NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    available_sizes JSON NULL,
                    gallery_images JSON NULL
                );
            """)

    @classmethod
    def tearDownClass(cls):
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS products;")
        except Exception:
            pass
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            username="buyer_a@example.com",
            email="buyer_a@example.com",
            password="password123",
            first_name="Buyer A",
        )
        self.user_b = User.objects.create_user(
            username="buyer_b@example.com",
            email="buyer_b@example.com",
            password="password123",
            first_name="Buyer B",
        )

        self.product1 = Product.objects.create(
            name="Silk Kurta",
            slug="silk-kurta",
            price=Decimal("1500.00"),
            category="Men",
            product_type="Clothing",
            color="Gold",
            stock_quantity=10,
            is_active=True,
            created_at=timezone.now(),
            available_sizes=["M", "L"],
        )
        self.product2 = Product.objects.create(
            name="Cotton Trousers",
            slug="cotton-trousers",
            price=Decimal("1000.00"),
            category="Men",
            product_type="Clothing",
            color="Navy",
            stock_quantity=5,
            is_active=True,
            created_at=timezone.now(),
            available_sizes=["32", "34"],
        )
        self.inactive_product = Product.objects.create(
            name="Archived Item",
            slug="archived-item",
            price=Decimal("500.00"),
            category="Sale",
            product_type="Clothing",
            is_active=False,
            created_at=timezone.now(),
        )

        self.address_a = Address.objects.create(
            user=self.user_a,
            full_name="Buyer A Delivery",
            phone="9876543210",
            address_line1="123 Avenue",
            city="Bengaluru",
            state="Karnataka",
            postal_code="560001",
            is_default=True,
        )
        self.address_b = Address.objects.create(
            user=self.user_b,
            full_name="Buyer B Delivery",
            phone="9123456789",
            address_line1="456 Boulevard",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            is_default=True,
        )

        self.orders_url = "/api/orders/"

    def test_unauthenticated_order_creation_rejected(self):
        payload = {
            "address_id": self.address_a.id,
            "items": [{"product_id": self.product1.id, "quantity": 1}],
        }
        res = self.client.post(self.orders_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejection_of_another_users_address(self):
        # User A tries to use User B's address
        self.client.force_authenticate(user=self.user_a)
        payload = {
            "address_id": self.address_b.id,
            "items": [{"product_id": self.product1.id, "quantity": 1}],
        }
        res = self.client.post(self.orders_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("address_id", res.data)

    def test_order_creation_calculates_totals_and_ignores_frontend_prices(self):
        # Product 1 is ₹1500.00. Subtotal < ₹1999, so shipping is ₹99. Total should be ₹1599.00.
        # Frontend maliciously submits price: 1.00 and total: 1.00
        self.client.force_authenticate(user=self.user_a)
        payload = {
            "address_id": self.address_a.id,
            "price": "1.00",
            "total": "1.00",
            "items": [
                {
                    "product_id": self.product1.id,
                    "quantity": 1,
                    "price": "1.00",
                    "size": "M",
                }
            ],
        }
        res = self.client.post(self.orders_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order_data = res.data

        self.assertEqual(order_data["status"], "Pending")
        self.assertEqual(order_data["subtotal"], "1500.00")
        self.assertEqual(order_data["shipping_charge"], "99.00")
        self.assertEqual(order_data["total"], "1599.00")
        self.assertEqual(len(order_data["items"]), 1)
        self.assertEqual(order_data["items"][0]["price"], "1500.00")
        self.assertEqual(order_data["items"][0]["line_total"], "1500.00")

    def test_complimentary_shipping_over_threshold(self):
        # Product 1 (1500) + Product 2 (1000) = 2500 >= 1999 -> shipping = 0.00
        self.client.force_authenticate(user=self.user_a)
        payload = {
            "address_id": self.address_a.id,
            "items": [
                {"product_id": self.product1.id, "quantity": 1},
                {"product_id": self.product2.id, "quantity": 1},
            ],
        }
        res = self.client.post(self.orders_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["subtotal"], "2500.00")
        self.assertEqual(res.data["shipping_charge"], "0.00")
        self.assertEqual(res.data["total"], "2500.00")

    def test_rejection_of_invalid_product_and_quantity(self):
        self.client.force_authenticate(user=self.user_a)

        # Invalid non-existent product ID
        res1 = self.client.post(
            self.orders_url,
            {"address_id": self.address_a.id, "items": [{"product_id": 999999, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Inactive product
        res2 = self.client.post(
            self.orders_url,
            {"address_id": self.address_a.id, "items": [{"product_id": self.inactive_product.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Quantity 0
        res3 = self.client.post(
            self.orders_url,
            {"address_id": self.address_a.id, "items": [{"product_id": self.product1.id, "quantity": 0}]},
            format="json",
        )
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)

        # Empty items list
        res4 = self.client.post(
            self.orders_url,
            {"address_id": self.address_a.id, "items": []},
            format="json",
        )
        self.assertEqual(res4.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_history_isolation_between_users(self):
        # User A places order
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.post(
            self.orders_url,
            {"address_id": self.address_a.id, "items": [{"product_id": self.product1.id, "quantity": 1}]},
            format="json",
        )
        order_a_num = res_a.data["order_number"]

        # User B places order
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.post(
            self.orders_url,
            {"address_id": self.address_b.id, "items": [{"product_id": self.product2.id, "quantity": 2}]},
            format="json",
        )
        order_b_num = res_b.data["order_number"]

        # User A list orders: should only see Order A
        self.client.force_authenticate(user=self.user_a)
        a_orders = self.client.get(self.orders_url)
        self.assertEqual(a_orders.status_code, status.HTTP_200_OK)
        self.assertEqual(len(a_orders.data), 1)
        self.assertEqual(a_orders.data[0]["order_number"], order_a_num)

        # User A cannot retrieve Order B via detail endpoint
        lookup_b = self.client.get(f"{self.orders_url}{order_b_num}/")
        self.assertEqual(lookup_b.status_code, status.HTTP_404_NOT_FOUND)

        # User B list orders: should only see Order B
        self.client.force_authenticate(user=self.user_b)
        b_orders = self.client.get(self.orders_url)
        self.assertEqual(b_orders.status_code, status.HTTP_200_OK)
        self.assertEqual(len(b_orders.data), 1)
        self.assertEqual(b_orders.data[0]["order_number"], order_b_num)

    def test_transaction_rollback_when_order_creation_fails(self):
        self.client.force_authenticate(user=self.user_a)
        initial_order_count = Order.objects.count()

        with patch("store.serializers.OrderItem.objects.bulk_create", side_effect=DatabaseError("Simulated failure")):
            with self.assertRaises(DatabaseError):
                self.client.post(
                    self.orders_url,
                    {"address_id": self.address_a.id, "items": [{"product_id": self.product1.id, "quantity": 1}]},
                    format="json",
                )

        # Due to transaction.atomic(), no order should have been persisted
        self.assertEqual(Order.objects.count(), initial_order_count)

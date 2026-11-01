import time
from decimal import Decimal
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Address, Order, OrderItem, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "description", "category", "product_type",
            "price", "compare_at_price", "image_url", "color", "stock_quantity",
            "is_active", "created_at", "available_sizes", "gallery_images",
        ]


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="first_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email"]


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=190)
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(username=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def create(self, validated_data):
        email = validated_data["email"].lower().strip()
        name = validated_data["name"].strip()
        password = validated_data["password"]
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name,
        )
        return user


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField()
        if "username" in self.fields:
            del self.fields["username"]

    def validate(self, attrs):
        email = attrs.get("email", "").lower().strip()
        password = attrs.get("password", "")

        user = authenticate(self.context.get("request"), username=email, password=password)
        if not user:
            matching_user = User.objects.filter(email__iexact=email).first()
            if matching_user and matching_user.check_password(password):
                user = matching_user

        if not user:
            raise serializers.ValidationError({"detail": "Email or password is incorrect."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "This user account is inactive."})

        try:
            default_addr = Address.objects.filter(user=user, is_default=True).first() or Address.objects.filter(user=user).first()
        except (OperationalError, ProgrammingError):
            default_addr = None
        phone_val = default_addr.phone if default_addr else ""
        address_val = ""
        if default_addr and default_addr.address_line1 and default_addr.address_line1 != "Address not specified":
            parts = [default_addr.address_line1]
            if default_addr.address_line2:
                parts.append(default_addr.address_line2)
            if default_addr.city:
                parts.append(default_addr.city)
            state_pin = f"{default_addr.state} - {default_addr.postal_code}" if default_addr.state and default_addr.postal_code else (default_addr.state or default_addr.postal_code or "")
            if state_pin:
                parts.append(state_pin)
            address_val = ", ".join([p for p in parts if p])

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "name": user.first_name or user.email.split("@")[0],
                "email": user.email,
                "phone": phone_val,
                "address": address_val,
            },
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=190)

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "full_name", "phone", "address_line1", "address_line2",
            "city", "state", "postal_code", "country", "label",
            "is_default", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_full_name(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Full name is required.")
        return val

    def validate_phone(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Phone number is required.")
        return val

    def validate_address_line1(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Street address line 1 is required.")
        return val

    def validate_city(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("City is required.")
        return val

    def validate_state(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("State is required.")
        return val

    def validate_postal_code(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Postal code is required.")
        return val

    def create(self, validated_data):
        user = self.context["request"].user
        is_default = validated_data.get("is_default", False)
        # If this is the user's first address, make it default automatically
        if not Address.objects.filter(user=user).exists():
            is_default = True
            validated_data["is_default"] = True
        elif is_default:
            Address.objects.filter(user=user).update(is_default=False)
        return Address.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        user = instance.user
        is_default = validated_data.get("is_default", instance.is_default)
        if is_default and not instance.is_default:
            Address.objects.filter(user=user).exclude(id=instance.id).update(is_default=False)
        return super().update(instance, validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(source="unit_price", max_digits=10, decimal_places=2, read_only=True)
    qty = serializers.IntegerField(source="quantity", read_only=True)
    name = serializers.CharField(source="product_name", read_only=True)
    image = serializers.CharField(source="product_image", read_only=True)
    image_url = serializers.CharField(source="product_image", read_only=True)
    size = serializers.CharField(source="selected_size", read_only=True)
    color = serializers.CharField(source="selected_color", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id", "product_id_snapshot", "product_name", "product_image",
            "selected_size", "selected_color", "unit_price", "quantity",
            "line_total", "price", "qty", "name", "image", "image_url",
            "size", "color",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    number = serializers.CharField(source="order_number", read_only=True)
    date = serializers.SerializerMethodField()
    delivery_address = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "number", "status", "customer_name_snapshot",
            "customer_email_snapshot", "delivery_address_snapshot", "delivery_address",
            "subtotal", "shipping_charge", "discount", "total", "created_at",
            "date", "timeline", "items", "payment_method", "payment_status",
        ]

    def get_payment_method(self, obj):
        snap = obj.delivery_address_snapshot or {}
        return snap.get("payment_method") or "COD"

    def get_payment_status(self, obj):
        snap = obj.delivery_address_snapshot or {}
        return snap.get("payment_status") or "Unpaid"

    def get_date(self, obj):
        return obj.created_at.strftime("%d %b %Y")

    def get_delivery_address(self, obj):
        snap = obj.delivery_address_snapshot or {}
        parts = [
            snap.get("full_name") or obj.customer_name_snapshot,
            snap.get("phone") or "",
            snap.get("address_line1") or "",
            snap.get("address_line2") or "",
            f"{snap.get('city') or ''}, {snap.get('state') or ''} - {snap.get('postal_code') or ''}".strip(" ,-"),
            snap.get("country") or "India",
        ]
        return ", ".join(p for p in parts if p)

    def get_timeline(self, obj):
        return ["Order placed", "Confirmed", "Packed", "Out for delivery", "Delivered"]


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False)
    id = serializers.IntegerField(required=False)
    quantity = serializers.IntegerField(required=False, default=1)
    qty = serializers.IntegerField(required=False, default=1)
    size = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    selected_size = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    color = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    selected_color = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        pid = attrs.get("product_id") if attrs.get("product_id") is not None else attrs.get("id")
        if not pid:
            raise serializers.ValidationError({"product_id": "Product ID is required."})
        attrs["product_id"] = pid

        q = attrs.get("quantity")
        if q is None:
            q = attrs.get("qty")
        if q is None:
            q = 1

        if q <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be at least 1."})
        if q > 100:
            raise serializers.ValidationError({"quantity": "Quantity cannot exceed 100."})
        attrs["quantity"] = q

        attrs["size"] = (attrs.get("size") or attrs.get("selected_size") or "").strip()
        attrs["color"] = (attrs.get("color") or attrs.get("selected_color") or "").strip()
        return attrs


class OrderCreateSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(required=False, allow_null=True)
    address = AddressSerializer(required=False, allow_null=True)
    items = OrderItemInputSerializer(many=True, required=True)

    def validate(self, attrs):
        user = self.context["request"].user
        address_id = attrs.get("address_id")
        address_data = attrs.get("address")

        if not address_id and not address_data:
            raise serializers.ValidationError(
                {"address": "Please select a saved address or provide delivery address details."}
            )

        delivery_address_obj = None
        delivery_snapshot = {}

        if address_id:
            delivery_address_obj = Address.objects.filter(id=address_id, user=user).first()
            if not delivery_address_obj:
                raise serializers.ValidationError(
                    {"address_id": "Delivery address was not found or does not belong to you."}
                )
            delivery_snapshot = {
                "id": delivery_address_obj.id,
                "full_name": delivery_address_obj.full_name,
                "phone": delivery_address_obj.phone,
                "address_line1": delivery_address_obj.address_line1,
                "address_line2": delivery_address_obj.address_line2,
                "city": delivery_address_obj.city,
                "state": delivery_address_obj.state,
                "postal_code": delivery_address_obj.postal_code,
                "country": delivery_address_obj.country,
                "label": delivery_address_obj.label,
                "payment_method": "COD",
                "payment_status": "Unpaid",
            }
        else:
            full_name = address_data.get("full_name", "").strip() or user.first_name or user.email.split("@")[0]
            phone = address_data.get("phone", "").strip()
            address_line1 = address_data.get("address_line1", "").strip()
            city = address_data.get("city", "").strip()
            state = address_data.get("state", "").strip()
            postal_code = address_data.get("postal_code", "").strip()

            if not full_name or not phone or not address_line1 or not city or not state or not postal_code:
                raise serializers.ValidationError(
                    {"address": "Please fill in all required address fields (Name, Phone, Address, City, State, Postal code)."}
                )

            # Auto-save address if user opted in or has no saved addresses
            save_to_user = address_data.get("save_address", True)
            if save_to_user:
                is_first = not Address.objects.filter(user=user).exists()
                delivery_address_obj = Address.objects.create(
                    user=user,
                    full_name=full_name,
                    phone=phone,
                    address_line1=address_line1,
                    address_line2=address_data.get("address_line2", "").strip(),
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    country=address_data.get("country", "India").strip() or "India",
                    label=address_data.get("label", "Home").strip() or "Home",
                    is_default=is_first,
                )

            delivery_snapshot = {
                "id": delivery_address_obj.id if delivery_address_obj else None,
                "full_name": full_name,
                "phone": phone,
                "address_line1": address_line1,
                "address_line2": address_data.get("address_line2", "").strip(),
                "city": city,
                "state": state,
                "postal_code": postal_code,
                "country": address_data.get("country", "India").strip() or "India",
                "label": address_data.get("label", "Home").strip() or "Home",
                "payment_method": "COD",
                "payment_status": "Unpaid",
            }

        raw_items = attrs.get("items", [])
        if not raw_items:
            raise serializers.ValidationError({"items": "Your bag is empty. Please add items to checkout."})

        product_ids = [item["product_id"] for item in raw_items]
        products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids, is_active=True)}

        validated_items = []
        subtotal = Decimal("0.00")

        for item in raw_items:
            pid = item["product_id"]
            product = products_by_id.get(pid)
            if not product:
                raise serializers.ValidationError(
                    {"items": f"Product with ID {pid} was not found or is no longer available."}
                )

            qty = item["quantity"]
            unit_price = Decimal(str(product.price))
            line_total = unit_price * qty
            subtotal += line_total

            validated_items.append({
                "product": product,
                "product_id_snapshot": product.id,
                "product_name": product.name,
                "product_image": product.image_url or "",
                "selected_size": item["size"] or (product.available_sizes[0] if product.available_sizes else "S"),
                "selected_color": item["color"] or product.color or "Neutral",
                "unit_price": unit_price,
                "quantity": qty,
                "line_total": line_total,
            })

        shipping = Decimal("0.00") if subtotal >= Decimal("1999.00") else Decimal("99.00")
        discount = Decimal("0.00")
        total = subtotal + shipping - discount

        attrs["delivery_address_obj"] = delivery_address_obj
        attrs["delivery_snapshot"] = delivery_snapshot
        attrs["validated_items"] = validated_items
        attrs["subtotal"] = subtotal
        attrs["shipping_charge"] = shipping
        attrs["discount"] = discount
        attrs["total"] = total
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user

        while True:
            order_number = f"LM{int(time.time() * 1000) % 100000000:08d}"
            if not Order.objects.filter(order_number=order_number).exists():
                break

        customer_name = (user.first_name or user.email.split("@")[0]).strip()

        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                order_number=order_number,
                status=Order.Status.PENDING,
                address=validated_data["delivery_address_obj"],
                customer_name_snapshot=customer_name,
                customer_email_snapshot=user.email,
                delivery_address_snapshot=validated_data["delivery_snapshot"],
                subtotal=validated_data["subtotal"],
                shipping_charge=validated_data["shipping_charge"],
                discount=validated_data["discount"],
                total=validated_data["total"],
            )

            order_items = [
                OrderItem(
                    order=order,
                    product=item["product"],
                    product_id_snapshot=item["product_id_snapshot"],
                    product_name=item["product_name"],
                    product_image=item["product_image"],
                    selected_size=item["selected_size"],
                    selected_color=item["selected_color"],
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                    line_total=item["line_total"],
                )
                for item in validated_data["validated_items"]
            ]
            OrderItem.objects.bulk_create(order_items)

        return order

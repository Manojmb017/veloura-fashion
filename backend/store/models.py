from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models


class Product(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=180)
    slug = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=11)
    product_type = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    image_url = models.CharField(max_length=1000, blank=True, null=True)
    color = models.CharField(max_length=80, blank=True, null=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    available_sizes = models.JSONField(blank=True, null=True)
    gallery_images = models.JSONField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "products"
        ordering = ["-created_at", "id"]

    def __str__(self):
        return self.name


class Address(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")
    label = models.CharField(max_length=50, blank=True, default="Home")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.city}, {self.postal_code})"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PLACED = "Order placed", "Order placed"
        CONFIRMED = "Confirmed", "Confirmed"
        PACKED = "Packed", "Packed"
        OUT_FOR_DELIVERY = "Out for delivery", "Out for delivery"
        DELIVERED = "Delivered", "Delivered"
        CANCELLED = "Cancelled", "Cancelled"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=40, unique=True, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name_snapshot = models.CharField(max_length=120)
    customer_email_snapshot = models.EmailField(max_length=190)
    delivery_address_snapshot = models.JSONField(default=dict)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if hasattr(self.status, "value"):
            self.status = str(self.status.value)
        elif self.status is not None and not isinstance(self.status, str):
            self.status = str(self.status)
        super().save(*args, **kwargs)


    def __str__(self):
        return f"Order {self.order_number} ({self.status}) - ₹{self.total}"


class OrderItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        db_constraint=False,
    )
    product_id_snapshot = models.BigIntegerField(null=True, blank=True)
    product_name = models.CharField(max_length=180)
    product_image = models.CharField(max_length=1000, blank=True, default="")
    selected_size = models.CharField(max_length=30, blank=True, default="")
    selected_color = models.CharField(max_length=80, blank=True, default="")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity}x {self.product_name} in Order {self.order.order_number}"

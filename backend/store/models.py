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

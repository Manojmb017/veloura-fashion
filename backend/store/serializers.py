from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "description", "category", "product_type",
            "price", "compare_at_price", "image_url", "color", "stock_quantity",
            "is_active", "created_at", "available_sizes", "gallery_images",
        ]

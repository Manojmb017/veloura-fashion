from django.db.models import Q
from django.http import JsonResponse
from rest_framework import generics
from .models import Product
from .serializers import ProductSerializer


def health_check(request):
    return JsonResponse({"status": "ok", "service": "Fashion Store Django API"})


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)
        category = self.request.query_params.get("category", "").strip()
        if category and category.lower() != "all products":
            queryset = queryset.filter(category__iexact=category)
        search = (self.request.query_params.get("q") or self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search) |
                Q(category__icontains=search) | Q(product_type__icontains=search) |
                Q(color__icontains=search)
            )
        sort = self.request.query_params.get("sort", "newest")
        if sort == "price-low": queryset = queryset.order_by("price", "id")
        elif sort == "price-high": queryset = queryset.order_by("-price", "id")
        elif sort == "name": queryset = queryset.order_by("name")
        else: queryset = queryset.order_by("-created_at", "id")
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_field = "slug"
    lookup_url_kwarg = "slug"

    def get_queryset(self):
        return Product.objects.filter(is_active=True)

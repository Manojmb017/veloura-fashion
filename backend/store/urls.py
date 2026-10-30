from django.urls import path
from .views import ProductDetailView, ProductListView, health_check

app_name = "store"
urlpatterns = [
    path("health/", health_check, name="health"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
]

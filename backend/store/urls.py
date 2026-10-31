from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CurrentUserView,
    EmailTokenObtainPairView,
    ProductDetailView,
    ProductListView,
    RegisterView,
    health_check,
)

app_name = "store"
urlpatterns = [
    path("health/", health_check, name="health"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", EmailTokenObtainPairView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me/", CurrentUserView.as_view(), name="auth-me"),
]

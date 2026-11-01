from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    AddressDetailView,
    AddressListCreateView,
    CurrentUserView,
    EmailTokenObtainPairView,
    OrderDetailView,
    OrderListCreateView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
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
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me/", CurrentUserView.as_view(), name="auth-me"),
    path("addresses/", AddressListCreateView.as_view(), name="address-list-create"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address-detail"),
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<str:lookup>/", OrderDetailView.as_view(), name="order-detail"),
]

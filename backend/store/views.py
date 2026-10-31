from django.db.models import Q
from django.http import JsonResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Product
from .serializers import (
    EmailTokenObtainPairSerializer,
    ProductSerializer,
    RegisterSerializer,
    UserSerializer,
)


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


class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_data,
                "message": "Account created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [AllowAny]


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({"user": serializer.data})

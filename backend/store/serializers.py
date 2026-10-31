from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Product


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

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "name": user.first_name or user.email.split("@")[0],
                "email": user.email,
            },
        }

import logging
import re
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Address, Order, Product
from .serializers import (
    AddressSerializer,
    EmailTokenObtainPairSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
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


logger = logging.getLogger(__name__)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except (ValidationError, AuthenticationFailed):
            raise
        except Exception as exc:
            raw_email = request.data.get("email") if isinstance(request.data, dict) else None
            masked_email = (
                f"{raw_email[:2]}***@{raw_email.split('@')[-1]}"
                if raw_email and "@" in str(raw_email)
                else "unknown"
            )
            logger.error(
                "Login endpoint server exception for user [%s]: %s: %s",
                masked_email,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()

        user = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()

        if user and user.is_active:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            frontend_url = getattr(settings, "FRONTEND_URL", "")
            if not frontend_url:
                origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
                if origin:
                    frontend_url = origin.rstrip("/")
                else:
                    frontend_url = "http://localhost:5173"
            else:
                frontend_url = frontend_url.rstrip("/")

            reset_url = f"{frontend_url}/?uid={uid}&token={token}"

            subject = "Reset your Veloura Fashion password"
            name = user.first_name or "there"
            body = (
                f"Hello {name},\n\n"
                f"We received a request to reset the password for your Veloura Fashion account ({user.email}).\n\n"
                f"To choose a new password, please click the link below (or copy and paste it into your browser):\n"
                f"{reset_url}\n\n"
                f"This link is valid for a limited time and can only be used once.\n\n"
                f"If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.\n\n"
                f"Warm regards,\n"
                f"Veloura Fashion Team\n"
            )

            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "Veloura Fashion <noreply@veloura.example>"),
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                pass

        return Response(
            {
                "detail": "If an account exists with that email address, password reset instructions have been sent."
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        try:
            uid_int = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid_int)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response(
                {
                    "detail": "Your password has been successfully reset. You can now sign in with your new password."
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "detail": "This password reset link is invalid or has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


def parse_address_string(raw_address):
    raw = (raw_address or "").strip()
    if not raw:
        return {
            "address_line1": "Address not specified",
            "address_line2": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "has_explicit_pin": False,
            "has_explicit_city": False,
            "has_explicit_state": False,
        }

    pin_match = re.search(r"\b(\d{6})\b", raw)
    has_explicit_pin = bool(pin_match)
    postal_code = pin_match.group(1) if pin_match else ""

    cleaned = re.sub(r"\b\d{6}\b", "", raw).strip(" ,-\n\r")
    parts = [p.strip() for p in re.split(r"[,\n]+", cleaned) if p.strip()]

    known_states = {
        "karnataka", "maharashtra", "delhi", "tamil nadu", "telangana",
        "kerala", "andhra pradesh", "gujarat", "west bengal", "rajasthan",
        "uttar pradesh", "haryana", "punjab", "goa", "madhya pradesh"
    }

    state = ""
    has_explicit_state = False
    city = ""
    has_explicit_city = False
    address_line1 = raw
    address_line2 = ""

    if len(parts) >= 3:
        if parts[-1].lower() in known_states:
            state = parts[-1].title()
            has_explicit_state = True
            city = parts[-2]
            has_explicit_city = True
            address_line1 = parts[0]
            address_line2 = ", ".join(parts[1:-2])
        else:
            city = parts[-1]
            has_explicit_city = True
            address_line1 = parts[0]
            address_line2 = ", ".join(parts[1:-1])
    elif len(parts) == 2:
        if parts[-1].lower() in known_states:
            state = parts[-1].title()
            has_explicit_state = True
            address_line1 = parts[0]
        else:
            address_line1 = parts[0]
            city = parts[1]
            has_explicit_city = True
    elif len(parts) == 1:
        address_line1 = parts[0]

    return {
        "address_line1": address_line1[:255] or "Address line",
        "address_line2": address_line2[:255],
        "city": city[:100] if has_explicit_city else "",
        "state": state[:100] if has_explicit_state else "",
        "postal_code": postal_code[:20],
        "has_explicit_pin": has_explicit_pin,
        "has_explicit_city": has_explicit_city,
        "has_explicit_state": has_explicit_state,
    }


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_user_data(self, user):
        data = UserSerializer(user).data
        try:
            default_addr = Address.objects.filter(user=user, is_default=True).first() or Address.objects.filter(user=user).first()
        except (OperationalError, ProgrammingError):
            default_addr = None
        if default_addr:
            data["phone"] = default_addr.phone or ""
            if default_addr.address_line1 and default_addr.address_line1 != "Address not specified":
                addr_parts = [default_addr.address_line1]
                if default_addr.address_line2:
                    addr_parts.append(default_addr.address_line2)
                if default_addr.city:
                    addr_parts.append(default_addr.city)
                state_pin = f"{default_addr.state} - {default_addr.postal_code}" if default_addr.state and default_addr.postal_code else (default_addr.state or default_addr.postal_code or "")
                if state_pin:
                    addr_parts.append(state_pin)
                data["address"] = ", ".join([p for p in addr_parts if p])
            else:
                data["address"] = ""
            data["address_id"] = default_addr.id
        else:
            data["phone"] = ""
            data["address"] = ""
            data["address_id"] = None
        return data

    def get(self, request):
        return Response({"user": self._get_user_data(request.user)})

    def patch(self, request):
        name = request.data.get("name")
        phone = request.data.get("phone")
        address_text = request.data.get("address")

        if name is not None:
            clean_name = str(name).strip()
            if clean_name:
                request.user.first_name = clean_name
                request.user.save(update_fields=["first_name"])

        clean_phone = str(phone).strip() if phone is not None else ""
        clean_address = str(address_text).strip() if address_text is not None else ""

        if phone is not None or address_text is not None:
            default_addr = Address.objects.filter(user=request.user, is_default=True).first() or Address.objects.filter(user=request.user).first()
            parsed = parse_address_string(clean_address) if clean_address else None

            if default_addr:
                if phone is not None:
                    default_addr.phone = clean_phone
                if clean_address:
                    default_addr.address_line1 = parsed["address_line1"]
                    default_addr.address_line2 = parsed["address_line2"]
                    default_addr.city = parsed["city"]
                    default_addr.state = parsed["state"]
                    default_addr.postal_code = parsed["postal_code"]
                elif address_text is not None and not clean_address:
                    default_addr.address_line1 = "Address not specified"
                    default_addr.address_line2 = ""
                    default_addr.city = ""
                    default_addr.state = ""
                    default_addr.postal_code = ""
                if request.user.first_name:
                    default_addr.full_name = request.user.first_name
                default_addr.is_default = True
                default_addr.save()
                # Ensure no duplicate default addresses exist for this user
                Address.objects.filter(user=request.user).exclude(id=default_addr.id).update(is_default=False)
            elif clean_phone or clean_address:
                # Ensure existing addresses are not marked default
                Address.objects.filter(user=request.user).update(is_default=False)
                Address.objects.create(
                    user=request.user,
                    full_name=request.user.first_name or request.user.email.split("@")[0],
                    phone=clean_phone or "Not provided",
                    address_line1=parsed["address_line1"] if parsed else "Address not specified",
                    address_line2=parsed["address_line2"] if parsed else "",
                    city=parsed["city"] if parsed else "",
                    state=parsed["state"] if parsed else "",
                    postal_code=parsed["postal_code"] if parsed else "",
                    country="India",
                    label="Home",
                    is_default=True,
                )

        return Response({
            "user": self._get_user_data(request.user),
            "message": "Profile details updated successfully.",
        })


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class OrderListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer
        return OrderSerializer

    def get(self, request, *args, **kwargs):
        queryset = Order.objects.filter(user=request.user).prefetch_related("items")
        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        response_serializer = OrderSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        lookup = self.kwargs.get("lookup", "").strip()
        queryset = Order.objects.filter(user=self.request.user).prefetch_related("items")
        order = None
        if str(lookup).isdigit():
            order = queryset.filter(id=lookup).first()
        if not order:
            order = queryset.filter(order_number__iexact=lookup).first()
        if not order:
            raise Http404("Order not found.")
        return order

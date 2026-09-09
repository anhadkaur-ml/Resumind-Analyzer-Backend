from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Notification


User = get_user_model()


class NotificationSerializer(serializers.ModelSerializer):
    """Return notification data without allowing clients to edit protected fields."""

    class Meta:
        model = Notification
        fields = ("id", "title", "message", "kind", "link", "is_read", "created_at")
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """Expose the small set of user fields required by employee and HR headers."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "full_name", "email", "role")

    def get_full_name(self, user):
        # Fall back to username for accounts created without first/last names.
        return user.get_full_name() or user.username


class SignupSerializer(serializers.Serializer):
    """Validate registration input and create a role-aware Django user."""

    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_email(self, value):
        # Normalize email casing and prevent duplicate accounts.
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate(self, attrs):
        # Cross-field validation belongs here because it compares two passwords.
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "The passwords do not match."}
            )

        # Reuse Django's configured password-strength validators.
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)}) from error

        return attrs

    def create(self, validated_data):
        # Split the display name into the fields expected by Django's user model.
        validated_data.pop("password_confirm")
        full_name = validated_data.pop("full_name").strip()
        password = validated_data.pop("password")
        email = validated_data["email"]

        name_parts = full_name.split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Authentication uses email in the API, but Django still requires a
        # unique username, so derive one and add a suffix when necessary.
        username_base = email.split("@", maxsplit=1)[0][:120] or "user"
        username = username_base
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{username_base[:140 - len(str(suffix))]}-{suffix}"

        return User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            **validated_data,
        )


class LoginSerializer(serializers.Serializer):
    """Authenticate an email/password pair and issue JWT access/refresh tokens."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        # Look up by email, then authenticate using Django's username backend.
        try:
            user_record = User.objects.get(email__iexact=attrs["email"].strip())
        except User.DoesNotExist as error:
            raise serializers.ValidationError("Invalid email or password.") from error

        user = authenticate(
            request=self.context.get("request"),
            username=user_record.username,
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid email or password.")

        # The short-lived access token authenticates API calls; the refresh
        # token can later issue a new access token without another login.
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "role": user.role,
            },
        }

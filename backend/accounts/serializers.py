from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import User


class RegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователя."""

    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True
    )

    token = serializers.CharField(max_length=255, read_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'token', 'role']

    def create(self, validated_data):
        """Создание нового пользователя."""
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Сериализатор для входа пользователя."""

    email = serializers.CharField(max_length=255)
    username = serializers.CharField(max_length=255, read_only=True)
    password = serializers.CharField(max_length=128, write_only=True)
    token = serializers.CharField(max_length=255, read_only=True)
    role = serializers.CharField(max_length=20, read_only=True)
    doctor_id = serializers.IntegerField(read_only=True, required=False)

    def validate(self, data):
        """Валидация данных для входа."""
        from django.contrib.auth import get_user_model

        email = data.get('email', None)
        password = data.get('password', None)

        if email is None:
            raise serializers.ValidationError(
                'An email address is required to log in.'
            )
        if password is None:
            raise serializers.ValidationError(
                'A password is required to log in.'
            )

        User = get_user_model()
        email = email.strip().lower()

        try:
            user = User.objects.get(email__iexact=email)

            if not user.check_password(password):
                raise serializers.ValidationError(
                    'A user with this email and password was not found.'
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    'This user has been deactivated.'
                )

            result = {
                'email': user.email,
                'username': user.username,
                'role': user.role,
                'token': user.token
            }

            if user.role == 'doctor' and hasattr(user, 'doctor_profile'):
                result['doctor_id'] = user.doctor_profile.id

            return result
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'A user with this email and password was not found.'
            )

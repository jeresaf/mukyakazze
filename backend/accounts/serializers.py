from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import User, AuditEvent
from .services import ROLES

class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not hasattr(data, "keys"):
            return super().to_internal_value(data)
        unknown = set(data.keys()) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Unknown or protected field.' for key in sorted(unknown)})
        return super().to_internal_value(data)

class LoginSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, max_length=1024, write_only=True)

class UserOutput(serializers.ModelSerializer):
    roles = serializers.SlugRelatedField(source='groups', slug_field='name', many=True, read_only=True)
    class Meta:
        model = User
        fields = ('id', 'email', 'display_name', 'is_active', 'roles', 'date_joined', 'session_version')

class UserCreate(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    display_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=ROLES), allow_empty=False)
    def validate(self, attrs):
        attrs['email'] = attrs['email'].strip().lower()
        if User.objects.filter(email__iexact=attrs['email']).exists():
            raise serializers.ValidationError({'email': 'Account already exists.'})
        try:
            validate_password(attrs['password'], User(email=attrs['email'], display_name=attrs['display_name']))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages}) from exc
        if not Group.objects.filter(name__in=set(attrs['roles'])).count() == len(set(attrs['roles'])):
            raise serializers.ValidationError({'roles': 'Roles not provisioned.'})
        return attrs

class UserChange(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    display_name = serializers.CharField(max_length=150, required=False)
    is_active = serializers.BooleanField(required=False)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=ROLES), allow_empty=False, required=False)
    def validate(self, attrs):
        if len(attrs) == 1:
            raise serializers.ValidationError('No changes supplied.')
        return attrs

class RevokeSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)

class AuditOutput(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ('id', 'actor_id', 'action', 'target_id', 'details', 'created_at')

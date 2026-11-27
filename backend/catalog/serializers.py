from rest_framework import serializers
from accounts.serializers import StrictSerializer
from .models import Category


class CategoryOutput(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'code', 'label', 'colour', 'display_order', 'is_active', 'version', 'created_at', 'updated_at')


class CategoryFields(StrictSerializer):
    label = serializers.CharField(max_length=100)
    colour = serializers.RegexField(r'\A#[0-9a-fA-F]{6}\Z')
    display_order = serializers.IntegerField(min_value=0, max_value=2147483647)

    def validate_colour(self, value):
        return value.upper()


class CategoryCreate(CategoryFields):
    code = serializers.RegexField(r'\A[A-Z][A-Z0-9_]*\Z', max_length=64)


class CategoryChange(CategoryFields):
    expected_version = serializers.IntegerField(min_value=1)
    label = serializers.CharField(max_length=100, required=False)
    colour = serializers.RegexField(r'\A#[0-9a-fA-F]{6}\Z', required=False)
    display_order = serializers.IntegerField(min_value=0, max_value=2147483647, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if len(attrs) == 1:
            raise serializers.ValidationError('No changes supplied.')
        return attrs

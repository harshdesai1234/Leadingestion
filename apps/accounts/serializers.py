"""
Serializers for Accounts App
"""
from rest_framework import serializers
from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    """
    Serializer for Plan model
    """
    class Meta:
        model = Plan
        fields = [
            'id',
            'service_name',
            'plan_type',
            'billing_cycle',
            'price',
            'minutes_included',
            'credits',
            'description',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

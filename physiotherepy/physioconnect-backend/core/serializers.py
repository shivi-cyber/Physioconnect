from rest_framework import serializers

from .models import Service


class ServiceSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', default=None)
    price = serializers.DecimalField(source='default_price', max_digits=8, decimal_places=2)

    class Meta:
        model = Service
        fields = ('id', 'name', 'slug', 'description', 'duration_minutes', 'price', 'category')

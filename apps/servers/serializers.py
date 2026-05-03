from rest_framework import serializers
from .models import Server

class ServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        fields = ['id', 'name', 'ip_address', 'status', 'environment', 'is_deleted']
        read_only_fields = ['is_deleted']


from rest_framework import serializers
from .models import Job


class JobSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = Job
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "root_job",
        ]

    def update(self, instance, validated_data):
        if not instance.can_edit():
            raise serializers.ValidationError(
                "작업 생성 30분 이후에는 수정할 수 없습니다. 정정 작업으로 등록하세요."
            )

        return super().update(instance, validated_data)
from django.utils import timezone
from rest_framework import serializers

from .models import Ad, AdClick, Advertiser, AdView, Transaction


class CreditSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)


class AdvertiserSerializer(serializers.ModelSerializer):
    ads = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    credit = serializers.IntegerField(read_only=True)

    class Meta:
        model = Advertiser
        fields = [
            "id",
            "created_at",
            "name",
            "ads",
            "credit",
            "remaining_hours",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    advertiser = serializers.PrimaryKeyRelatedField(queryset=Advertiser.objects.all())
    ad = serializers.PrimaryKeyRelatedField(queryset=Ad.objects.all())

    class Meta:
        model = Transaction
        fields = [
            "id",
            "ad",
            "advertiser",
            "created_at",
            "transaction_type",
            "amount",
        ]


class AdSerializer(serializers.ModelSerializer):
    advertiser = serializers.PrimaryKeyRelatedField(queryset=Advertiser.objects.all())
    views_hourly = serializers.SerializerMethodField()
    clicks_hourly = serializers.SerializerMethodField()
    click_rate_hourly = serializers.SerializerMethodField()
    avg_click_time = serializers.SerializerMethodField()
    click_rate = serializers.SerializerMethodField()

    class Meta:
        model = Ad
        fields = [
            "id",
            "created_at",
            "title",
            "image_url",
            "link",
            "advertiser",
            "approve",
            "views_hourly",
            "clicks_hourly",
            "click_rate_hourly",
            "avg_click_time",
            "click_rate",
            "cost_type",
            "cost",
            "hourly_cost",
        ]

    def get_views_hourly(self, obj):
        return obj.hourly_views

    def get_clicks_hourly(self, obj):
        return obj.hourly_clicks

    def get_click_rate_hourly(self, obj):
        return obj.hourly_click_rate

    def get_avg_click_time(self, obj):
        return obj.avg_click_time

    def get_click_rate(self, obj):
        return obj.click_rate


class AdClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdClick
        fields = ["id", "ad", "ip", "created_at"]


class AdViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdView
        fields = ["id", "ad", "ip", "created_at"]


class ReporterSerializer(serializers.ModelSerializer):
    spending = serializers.IntegerField(read_only=True)
    life_time_hours = serializers.SerializerMethodField()

    class Meta:
        model = Ad
        fields = [
            "id",
            "title",
            "created_at",
            "life_time_hours",
            "cost_type",
            "cost",
            "spending",
        ]

    def get_life_time_hours(self, obj):
        current_time = timezone.localtime(timezone.now())
        created_at = timezone.localtime(obj.created_at)
        duration = (current_time - created_at) / 3600
        return duration

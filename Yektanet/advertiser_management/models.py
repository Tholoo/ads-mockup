from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
    fields,
)
from django.db.models.functions import ExtractHour
from django.utils import timezone


class Transaction(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    advertiser = models.ForeignKey(
        "advertiser_management.Advertiser",
        related_name="transactions",
        on_delete=models.CASCADE,
    )

    ad = models.ForeignKey(
        "advertiser_management.Ad",
        on_delete=models.CASCADE,
        null=True,
        related_name="transactions",
    )

    TRANSACTION_TYPE_CHOICES = (
        ("INCREASE", "increase"),
        ("DECREASE", "decrease"),
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(0)]
    )

    def __str__(self):
        return f"({self.id}) {self.advertiser.name} - {self.transaction_type} {self.amount}"


class Advertiser(models.Model):
    name = models.CharField(max_length=200)
    credit = models.DecimalField(max_digits=9, default=0, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"({self.id}) {self.name}"

    def remaining_hours(self):
        ads_hourly_cost = sum(ad.hourly_cost for ad in self.ads.all())
        if ads_hourly_cost == 0:
            return None  # or float('inf')

        return self.credit / ads_hourly_cost


class Ad(models.Model):
    title = models.CharField(max_length=200)
    image_url = models.CharField(max_length=200)
    link = models.CharField(max_length=200)
    advertiser = models.ForeignKey(
        Advertiser, related_name="ads", on_delete=models.CASCADE
    )
    approve = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    COST_TYPE_CHOICES = [
        ("CPM", "Cost Per Mille"),
        ("CPC", "Cost Per Click"),
    ]

    cost_type = models.CharField(max_length=5, choices=COST_TYPE_CHOICES, default="CPM")
    cost = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(0)]
    )

    def __str__(self):
        return f"({self.id}) {self.title} - {self.advertiser.name}"

    def get_hourly_stats(self, queryset):
        return (
            queryset.annotate(hour=ExtractHour("created_at"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

    @property
    def avg_hourly_views(self):
        total_views = len(self.views.all())
        if not total_views:
            return 0

        hours_count = (timezone.now() - self.created_at).seconds // 3600
        avg_hourly_clicks = 0
        if hours_count > 0:
            avg_hourly_clicks = fields.decimal.Decimal(total_views / hours_count)

        return avg_hourly_clicks

    @property
    def avg_hourly_clicks(self):
        total_clicks = len(self.clicks.all())
        if not total_clicks:
            return 0

        hours_count = (timezone.now() - self.created_at).seconds // 3600
        avg_hourly_clicks = 0
        if hours_count > 0:
            avg_hourly_clicks = fields.decimal.Decimal(total_clicks / hours_count)

        return avg_hourly_clicks

    @property
    def hourly_cost(self):
        hourly_cost = 0
        if self.cost_type == "CPM":
            hourly_cost = self.avg_hourly_views * self.cost / 1000
        elif self.cost_type == "CPC":
            hourly_cost = self.avg_hourly_clicks * self.cost

        return hourly_cost

    @property
    def hourly_views(self):
        return self.get_hourly_stats(self.views)

    @property
    def hourly_clicks(self):
        return self.get_hourly_stats(self.clicks)

    @property
    def click_rate(self):
        clicks = self.clicks.count()
        views = self.views.count()
        return clicks / views if views > 0 else 0

    @property
    def hourly_click_rate(self):
        views_hourly = self.hourly_views
        clicks_hourly = self.hourly_clicks
        return [
            {"hour": view["hour"], "click_rate": click["count"] / view["count"]}
            for view, click in zip(views_hourly, clicks_hourly)
        ]

    @property
    def avg_click_time(self):
        last_view_before_click = (
            self.views.filter(ip=OuterRef("ip"), created_at__lte=OuterRef("created_at"))
            .order_by("-created_at")
            .values("created_at")[:1]
        )
        annotated_clicks = self.clicks.annotate(
            last_view_time=Subquery(last_view_before_click)
        )
        aggregated = annotated_clicks.aggregate(
            avg_click_time=Avg(
                ExpressionWrapper(
                    F("created_at") - F("last_view_time"),
                    output_field=fields.DurationField(),
                )
            )
        )
        return (
            aggregated["avg_click_time"].total_seconds()
            if aggregated["avg_click_time"]
            else 0
        )


class AdClick(models.Model):
    ad = models.ForeignKey(
        "advertiser_management.Ad", related_name="clicks", on_delete=models.CASCADE
    )
    ip = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"({self.id}) {self.ad.title}"


class AdView(models.Model):
    ad = models.ForeignKey(
        "advertiser_management.Ad", related_name="views", on_delete=models.CASCADE
    )
    ip = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"({self.id}) {self.ad.title}"


class AdHourlyStat(models.Model):
    ad = models.ForeignKey(
        "advertiser_management.Ad",
        on_delete=models.CASCADE,
        related_name="hourly_stats",
    )
    date = models.DateField()
    hour = models.IntegerField()
    clicks = models.IntegerField(default=0)
    views = models.IntegerField(default=0)

    class Meta:
        unique_together = ("ad", "date", "hour")

    def __str__(self):
        return f"({self.id}) {self.ad.title} - {self.date} {self.hour}:00"

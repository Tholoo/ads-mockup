from datetime import timedelta

from celery import shared_task
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Ad, AdHourlyStat


@shared_task
def calculate_hourly_stats():
    end = timezone.now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=1)

    # get the clicks and views of each ad in the past hour
    stats = Ad.objects.annotate(
        past_hour_clicks=Count(
            "clicks", filter=Q(clicks__created_at__range=[start, end])
        ),
        past_hour_views=Count("views", filter=Q(views__created_at__range=[start, end])),
    ).values("id", "past_hour_clicks", "past_hour_views")

    # prepare data to bulk create
    to_create = [
        AdHourlyStat(
            ad_id=stat["id"],
            date=start.date(),
            hour=start.hour,
            clicks=stat["past_hour_clicks"],
            views=stat["past_hour_views"],
        )
        for stat in stats
    ]

    AdHourlyStat.objects.bulk_create(to_create)


@shared_task
def calculate_daily_stats():
    end = timezone.now().date()

    # since this task runs at midnight, we need the previous day's date
    start = end - timedelta(days=1)

    # get the clicks and views of each ad in the past day based on hourly stats
    stats = (
        AdHourlyStat.objects.filter(date__range=[start, end])
        .values("ad_id")
        .annotate(total_clicks=Sum("clicks"), total_views=Sum("views"))
    )

    # prepare the results
    result = {
        stat["ad_id"]: {
            "total_clicks": stat["total_clicks"],
            "total_views": stat["total_views"],
        }
        for stat in stats
    }

    return result

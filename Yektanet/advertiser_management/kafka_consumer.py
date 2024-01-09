import json

from django.db import transaction
from django.db.models import F, Count
from django.db.models.functions import Mod
from kafka import KafkaConsumer

from .events import Event
from .kafka_config import KAFKA_AD_TOPIC, KAFKA_BROKER_URL
from .models import Ad, AdClick, Advertiser, AdView, Transaction


def consume():
    consumer = KafkaConsumer(KAFKA_AD_TOPIC, bootstrap_servers=KAFKA_BROKER_URL)

    for message in consumer:
        message = json.loads(message.value.decode())

        event: Event = message["event"]
        data = message["data"]
        match event:
            case Event.CLICK:
                pk, ip = data["pk"], data["ip"]
                print(pk, ip)
                with transaction.atomic():
                    # create a click
                    AdClick.objects.create(ad_id=pk, ip=ip)

                    # handle cpc transaction
                    ad = Ad.objects.get(pk=pk)
                    if ad.cost_type == "CPC":
                        ad.advertiser.credit = F("credit") - ad.cost
                        ad.advertiser.save()

                        Transaction.objects.create(
                            advertiser=ad.advertiser,
                            transaction_type="SUBTRACT",
                            amount=ad.cost,
                        )

            case Event.VIEW_ALL:
                ip = data["ip"]
                with transaction.atomic():
                    # create views
                    AdView.objects.bulk_create(
                        [AdView(ad=ad, ip=ip) for ad in Ad.objects.all()]
                    )

                    # handle cpm transaction
                    ads_to_update = (
                        Ad.objects.filter(cost_type="CPM")
                        .annotate(
                            views_count=Count("views"),
                            mod_views=Mod(F("views_count"), 1000),
                        )
                        .filter(mod_views=0)
                    )

                    # decrease credit of advertisers
                    Advertiser.objects.filter(
                        id__in=ads_to_update.values("advertiser_id")
                    ).update(credit=F("credit") - ads_to_update.values("cost"))

                    transactions = [
                        Transaction(
                            advertiser=ad.advertiser,
                            transaction_type="SUBTRACT",
                            amount=ad.cost,
                        )
                        for ad in ads_to_update
                    ]
                    Transaction.objects.bulk_create(transactions)

            case Event.ADD_CREDIT:
                pk, amount = data["pk"], data["amount"]
                advertiser = Advertiser.objects.get(pk=pk)
                advertiser.credit = F("credit") + amount

                Transaction.objects.create(
                    advertiser=advertiser, transaction_type="ADD", amount=amount
                )

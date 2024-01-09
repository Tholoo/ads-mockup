from django.core.management.base import BaseCommand
from advertiser_management.kafka_consumer import consume


class Command(BaseCommand):
    help = "Runs the consumer"

    def handle(self, *args, **options):
        consume()
        self.stdout.write(self.style.SUCCESS("Successfully started the consumer"))

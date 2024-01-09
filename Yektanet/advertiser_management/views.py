from datetime import datetime, timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .events import Event
from .kafka_producer import produce_message
from .models import Ad, Advertiser
from .serializers import (
    AdSerializer,
    AdvertiserSerializer,
    CreditSerializer,
    TransactionSerializer,
    ReporterSerializer,
)


class AdvertiserViewSet(ModelViewSet):
    queryset = Advertiser.objects.all()
    serializer_class = AdvertiserSerializer

    def get_time_range(self, request, model):
        # Get query parameters
        # start_date should be model's creation date if not provided
        start_date_str = request.query_params.get("start_date") or str(
            timezone.localtime(model.created_at).date()
        )
        # end_date should be now if not provided
        end_date_str = request.query_params.get("end_date") or str(
            timezone.localtime(timezone.now()).date()
        )

        # Convert string dates to datetime objects
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            end_date = end_date + timedelta(days=1)
        except (TypeError, ValueError):
            start_date, end_date = None, None

        return start_date, end_date

    def create(self, request, *args, **kwargs):
        if "credit" in request.data:
            return Response(
                {"detail": "Modifying credit is not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if "credit" in request.data:
            return Response(
                {"detail": "Modifying credit is not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if "credit" in request.data:
            return Response(
                {"detail": "Modifying credit is not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="credit")
    def credit(self, request, pk=None):
        """Add credits to advertiser"""
        if pk is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            _ = self.get_object()
        except Advertiser.DoesNotExist:
            return Response({"error": "Advertiser not found"}, status=404)

        credit_serializer = CreditSerializer(data=request.data)
        if not credit_serializer.is_valid():
            return Response(
                credit_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        amount = credit_serializer.validated_data["amount"]
        produce_message(
            Event.ADD_CREDIT,
            {"pk": pk, "amount": amount},
        )

        return Response(
            {"message": f"Added {amount} credits to {pk}"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        """show advertiser's report"""
        try:
            advertiser = self.get_object()
        except Advertiser.DoesNotExist:
            return Response({"error": "Advertiser not found"}, status=404)

        start_date, end_date = self.get_time_range(request, advertiser)
        if not start_date or not end_date:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        # sum of DECREASE transactions' amount, grouped by ad
        ads_with_costs = (
            Ad.objects.filter(
                transactions__advertiser_id=pk,
                transactions__created_at__gte=start_date,
                transactions__created_at__lte=end_date,
                transactions__transaction_type="DECREASE",
            )
            .annotate(spending=Sum("transactions__amount"))
            .distinct()
        )

        total_spending = ads_with_costs.aggregate(total_spending=Sum("spending"))[
            "total_spending"
        ]

        serialized = ReporterSerializer(ads_with_costs, many=True)
        response = {"total_spending": total_spending, "ads": serialized.data}
        return Response(response)

    @action(detail=True, methods=["get"], url_path="transactions")
    def transactions(self, request, pk=None):
        """show advertiser's transactions"""
        try:
            advertiser = Advertiser.objects.get(pk=pk)
        except Advertiser.DoesNotExist:
            return Response({"error": "Advertiser not found"}, status=404)

        start_date, end_date = self.get_time_range(request, advertiser)
        if not start_date or not end_date:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        transactions = advertiser.transactions.filter(
            created_at__gte=start_date, created_at__lte=end_date
        )

        serializer = TransactionSerializer(transactions, many=True)

        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="alerts")
    def alert(self, request, pk=None):
        remaining_hours = self.get_object().remaining_hours()
        return Response(
            {"remaining_hours": remaining_hours},
        )


class AdViewSet(ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer

    # redirect on /ads/<pk>/click/
    @action(detail=True, methods=["get"], url_path="click")
    def click(self, request, pk=None):
        if pk is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        ad = self.get_object()

        # Record a click for the ad
        produce_message(
            Event.CLICK,
            {"pk": pk, "ip": request.META.get("REMOTE_ADDR")},
        )

        return Response({"redirect_to": ad.link}, status=status.HTTP_302_FOUND)

    def list(self, request, *args, **kwargs):
        # add a view for each ad
        produce_message(
            Event.VIEW_ALL,
            {"ip": request.META.get("REMOTE_ADDR")},
        )

        return super().list(request, *args, **kwargs)

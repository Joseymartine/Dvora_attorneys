from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from core.access import accessible_clients, accessible_cases, accessible_appointments, is_administrator, is_lawyer
from clients.models import Client
from cases.models import Case
from appointments.models import Appointment
from appointments.services import save_appointment
from .permissions import RecordPermissions
from .serializers import ClientSerializer, CaseSerializer, AppointmentSerializer, model_errors


class ProtectedDeleteMixin:
    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise serializers.ValidationError({'detail': 'This record has linked cases or appointments and cannot be deleted.'}) from error


class ClientViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, RecordPermissions]

    def get_queryset(self):
        return accessible_clients(self.request.user, super().get_queryset())


class CaseViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Case.objects.select_related('client', 'assigned_lawyer')
    serializer_class = CaseSerializer
    permission_classes = [IsAuthenticated, RecordPermissions]

    def get_queryset(self):
        return accessible_cases(self.request.user, super().get_queryset())


class AppointmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Appointment.objects.select_related('client', 'assigned_lawyer')
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated, RecordPermissions]

    def get_queryset(self):
        return accessible_appointments(self.request.user, super().get_queryset())

    def save_validated(self, serializer):
        instance = serializer.instance or Appointment()
        for name, value in serializer.validated_data.items():
            setattr(instance, name, value)
        if not is_administrator(self.request.user) and not is_lawyer(self.request.user):
            instance.client = Client.objects.get(user=self.request.user)
            instance.assigned_lawyer = None
            instance.status = Appointment.Status.REQUESTED
        try:
            serializer.instance = save_appointment(instance)
        except DjangoValidationError as error:
            raise serializers.ValidationError(model_errors(error)) from error

    def perform_create(self, serializer):
        self.save_validated(serializer)

    def perform_update(self, serializer):
        self.save_validated(serializer)

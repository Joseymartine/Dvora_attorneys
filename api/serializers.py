from copy import copy
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from core.access import is_administrator, is_lawyer
from clients.models import Client
from cases.models import Case
from appointments.models import Appointment


def model_errors(error):
    if hasattr(error, 'message_dict'):
        return {('non_field_errors' if key == '__all__' else key): value
                for key, value in error.message_dict.items()}
    return {'non_field_errors': error.messages}


class ValidatedModelSerializer(serializers.ModelSerializer):
    restricted_fields = ()

    def get_fields(self):
        fields = super().get_fields()
        if not is_administrator(self.context['request'].user):
            for name in self.restricted_fields:
                if name in ['client', 'assigned_lawyer']:
                    fields[name] = serializers.PrimaryKeyRelatedField(read_only=True)
                else:
                    fields[name].read_only = True
        return fields

    def validate(self, attrs):
        user = self.context['request'].user
        if not is_administrator(user):
            forbidden = set(self.initial_data) & set(self.restricted_fields)
            if forbidden:
                raise serializers.ValidationError({name: 'You cannot set this field.' for name in sorted(forbidden)})
        instance = copy(self.instance) if self.instance is not None else self.Meta.model()
        for name, value in attrs.items():
            setattr(instance, name, value)
        self.prepare_instance(instance)
        try:
            instance.full_clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(model_errors(error)) from error
        return attrs

    def prepare_instance(self, instance):
        pass


class ClientSerializer(ValidatedModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'address', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        if 'user' in self.initial_data:
            raise serializers.ValidationError({'user': 'Client login links are managed in superuser admin.'})
        return super().validate(attrs)


class CaseSerializer(ValidatedModelSerializer):
    assigned_lawyer = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.filter(is_active=True, groups__name='Lawyers').distinct())
    restricted_fields = ('case_number', 'client', 'assigned_lawyer', 'date_opened')

    class Meta:
        model = Case
        fields = ['id', 'case_number', 'title', 'client', 'assigned_lawyer', 'status', 'date_opened', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppointmentSerializer(ValidatedModelSerializer):
    assigned_lawyer = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_active=True, groups__name='Lawyers').distinct(),
        allow_null=True, required=False)

    class Meta:
        model = Appointment
        fields = ['id', 'title', 'client', 'assigned_lawyer', 'starts_at', 'ends_at', 'status', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    @property
    def restricted_fields(self):
        return ('client', 'assigned_lawyer') if is_lawyer(self.context['request'].user) else ('client', 'assigned_lawyer', 'status')

    def prepare_instance(self, instance):
        user = self.context['request'].user
        if not is_administrator(user) and not is_lawyer(user):
            instance.client = Client.objects.get(user=user)
            instance.assigned_lawyer = None
            instance.status = Appointment.Status.REQUESTED

    def validate(self, attrs):
        start = attrs.get('starts_at')
        if start is not None and (self.instance is None or start != self.instance.starts_at) and start <= timezone.now():
            raise serializers.ValidationError({'starts_at': 'Choose a future start time.'})
        return super().validate(attrs)

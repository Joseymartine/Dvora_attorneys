from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django.urls import reverse


class Appointment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        CONFIRMED = 'confirmed', 'Confirmed'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    title = models.CharField(max_length=200)
    client = models.ForeignKey('clients.Client', on_delete=models.PROTECT, related_name='appointments')
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='appointments',
        blank=True, null=True, limit_choices_to={'is_active': True, 'groups__name': 'Lawyers'},
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    notes = models.TextField(blank=True, help_text='Visible to the client as well as the assigned lawyer.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at', 'pk']
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')), name='appointment_positive_duration')]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('appointments:detail', args=[self.pk])

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'End time must be after start time.'})
        if self.status in [self.Status.CONFIRMED, self.Status.COMPLETED] and not self.assigned_lawyer_id:
            raise ValidationError({'assigned_lawyer': 'Assign a lawyer before confirming or completing an appointment.'})
        if not self.starts_at or not self.ends_at or self.status not in [self.Status.REQUESTED, self.Status.CONFIRMED]:
            return
        if self.assigned_lawyer_id:
            conflict = Appointment.objects.filter(
                assigned_lawyer_id=self.assigned_lawyer_id,
                status__in=[self.Status.REQUESTED, self.Status.CONFIRMED],
                starts_at__lt=self.ends_at, ends_at__gt=self.starts_at,
            ).exclude(pk=self.pk)
            if conflict.exists():
                raise ValidationError('This lawyer already has an appointment during that time. Choose another time or lawyer.')

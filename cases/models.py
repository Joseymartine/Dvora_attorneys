from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Case(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In progress'
        ON_HOLD = 'on_hold', 'On hold'
        CLOSED = 'closed', 'Closed'

    case_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    client = models.ForeignKey('clients.Client', on_delete=models.PROTECT, related_name='cases')
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_cases',
        limit_choices_to={'is_active': True, 'groups__name': 'Lawyers'},
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    date_opened = models.DateField(default=timezone.localdate)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_opened', '-pk']

    def __str__(self):
        return f'{self.case_number} — {self.title}'

    def get_absolute_url(self):
        return reverse('cases:detail', args=[self.pk])

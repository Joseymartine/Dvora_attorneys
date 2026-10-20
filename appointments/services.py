from django.contrib.auth import get_user_model
from django.db import transaction


def save_appointment(instance):
    """Validate and save while serializing bookings for the assigned lawyer."""
    with transaction.atomic():
        if instance.assigned_lawyer_id:
            get_user_model().objects.select_for_update().get(pk=instance.assigned_lawyer_id)
        instance.full_clean()
        instance.save()
    return instance

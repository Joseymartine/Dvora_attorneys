from django import forms
from django.utils import timezone
from .models import Appointment


class ScheduleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_start = self.instance.starts_at
        for name in ['starts_at', 'ends_at']:
            if name in self.fields:
                self.fields[name].widget = forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})
                self.fields[name].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_starts_at(self):
        value = self.cleaned_data['starts_at']
        if (not self.instance.pk or value != self.original_start) and value <= timezone.now():
            raise forms.ValidationError('Choose a future start time.')
        return value

    class Meta:
        model = Appointment
        fields = ['title', 'client', 'assigned_lawyer', 'starts_at', 'ends_at', 'status', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 4})}


class LawyerScheduleForm(ScheduleForm):
    class Meta(ScheduleForm.Meta):
        fields = ['title', 'starts_at', 'ends_at', 'status', 'notes']


class ConsultationRequestForm(ScheduleForm):
    class Meta(ScheduleForm.Meta):
        fields = ['title', 'starts_at', 'ends_at', 'notes']

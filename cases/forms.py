from django import forms
from .models import Case


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ['case_number', 'title', 'client', 'assigned_lawyer', 'status', 'date_opened', 'description']
        widgets = {'date_opened': forms.DateInput(attrs={'type': 'date'}), 'description': forms.Textarea(attrs={'rows': 5})}


class LawyerCaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ['title', 'status', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

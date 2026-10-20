from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']
        widgets = {'address': forms.Textarea(attrs={'rows': 4})}

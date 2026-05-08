from django import forms
from .models import TicketResponse

class TicketResponseForm(forms.ModelForm):
    class Meta:
        model = TicketResponse
        fields = ['message',]
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'w-full border rounded-md p-2',
                'rows': 4,
                'placeholder': 'Enter your response here...'
            }),
        }
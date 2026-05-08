from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import ObjectDoesNotExist

#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
User = get_user_model()

class EmailPhoneBackend(BaseBackend):
    def authenticate(self, request, email_or_phone_number=None, password=None, **kwargs):
        if not email_or_phone_number or not password:  # Ensure both identifier and password are provided
            return None

        user = None
        
        # Check if the input is an email
        if '@' in email_or_phone_number:  
            try:
                user = User.objects.get(email=email_or_phone_number)
            except ObjectDoesNotExist:
                return None
        
        # Check if the input is a phone number
        elif  '@' in email_or_phone_number:  # Assuming phone numbers are digits only
            try:
                user = User.objects.get(phone_number=email_or_phone_number)
            except ObjectDoesNotExist:
                return None

        # If it's neither email nor phone_number, return None
        else:
            return None

        # Check password
        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except ObjectDoesNotExist:
            return None
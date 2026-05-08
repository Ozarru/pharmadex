# Accounts middleware.py

from django.shortcuts import redirect
from pharmadex.context import (set_current_user, set_current_organization, set_current_request,
    set_current_user_type, set_current_profile
    )
from pharmadex.context import set_tenancy_disabled

EXEMPT_PATHS = (
    '/login/',
    '/logout/',
    '/admin/',
    '/static/',
    '/media/',
)


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT_PATHS):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")

        return self.get_response(request)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user if request.user.is_authenticated else None

        organization = getattr(request, 'current_organization', None)
        set_current_organization(organization)

        set_tenancy_disabled(getattr(request, "tenancy_disabled", False))

        set_current_user(user)
        set_current_request(request)

        if user:
            user_type = user.get_current_user_type()
            profile = user.get_current_profile(user_type, organization)

            set_current_user_type(user_type)
            set_current_profile(profile)

        return self.get_response(request)


from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        if not request.session.get("force_password_change", False):
            return self.get_response(request)

        exempt = (
            reverse("accounts:password-change"),
            reverse("accounts:logout"),
        )
        if request.path in exempt or request.path.startswith("/admin/"):
            return self.get_response(request)

        return redirect("accounts:password-change")


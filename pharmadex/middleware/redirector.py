from django.shortcuts import redirect


class CurrentOrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        if user.is_superuser or (hasattr(user, "is_platform_admin") and callable(user.is_platform_admin) and user.is_platform_admin()):
            return self.get_response(request)

        if getattr(request, "current_organization", None):
            return self.get_response(request)

        if (
            request.path == "/"
            or request.path.startswith("/admin/")
            or request.path.startswith("/accounts/")
            or request.path.startswith("/organizations/organization/list/")
            or request.path.startswith("/organizations/organization/create/")
        ):
            return self.get_response(request)

        return redirect("organizations:organization-list")


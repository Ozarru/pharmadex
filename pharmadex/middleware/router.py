from django.urls import set_urlconf


class HostRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        host = request.get_host().split(":")[0]

        request.is_app = host.startswith("app.")

        if request.is_app:
            set_urlconf("pharmadex.config.app_urls")
        else:
            set_urlconf("pharmadex.config.website_urls")

        return self.get_response(request)
    

class SubdomainRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0]

        request.is_app = host.startswith("app.")

        return self.get_response(request)
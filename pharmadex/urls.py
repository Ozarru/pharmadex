"""
URL configuration for pharmadex project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('base.urls', 'base'), namespace='base')),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('organizations/', include(('organizations.urls', 'organizations'), namespace='organizations')),
    path('pharmacies/', include(('pharmacies.urls', 'pharmacies'), namespace='pharmacies')),
    path('clinics/', include(('clinics.urls', 'clinics'), namespace='clinics')),
    path('finances/', include(('finances.urls', 'finances'), namespace='finances')),
    path('support/', include(('support.urls', 'support'), namespace='support')),
    # path('hr/', include(('hr.urls', 'hr'), namespace='hr')),
    path('api/v1/', include(('api.urls', 'api'), namespace='api')),
    path('rosetta/', include('rosetta.urls')),
    path("i18n/", include("django.conf.urls.i18n")),
    
    path('website/', include(('website.urls', 'website'), namespace='website')),


]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
# Production static/media fallback (whitenoise handles static, but media needs this)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'base.views.not_found'

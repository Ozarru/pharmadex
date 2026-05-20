from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # admin urls ------------------------------
    path('admin/', admin.site.urls),
    
    # translation urls ------------------------------
    path('rosetta/', include('rosetta.urls')),
    path("i18n/", include("django.conf.urls.i18n")),
    
    # custom urls ------------------------------
    path('', include(('base.urls', 'base'), namespace='base')),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('organizations/', include(('organizations.urls', 'organizations'), namespace='organizations')),
    path('pharmacies/', include(('pharmacies.urls', 'pharmacies'), namespace='pharmacies')),
    path('clinics/', include(('clinics.urls', 'clinics'), namespace='clinics')),
    path('finances/', include(('finances.urls', 'finances'), namespace='finances')),
    path('support/', include(('support.urls', 'support'), namespace='support')),
    path('website/', include(('website.urls', 'website'), namespace='website')),
    # path('hr/', include(('hr.urls', 'hr'), namespace='hr')),
    path('api/v1/', include('api.urls')),
    

]

handler404 = 'base.views.not_found'
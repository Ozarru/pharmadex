from django.urls import path
from .views import *

urlpatterns = [
    # Organization URLs
    path('dashboard/', organization_dashboard, name='organization-dashboard'),
    path('organization/list/', OrganizationListView.as_view(), name='organization-list'),
    path('organization/create/', OrganizationCreateView.as_view(), name='organization-create'),
    path('organization/<uuid:pk>/detail/', OrganizationDetailView.as_view(), name='organization-detail'),
    path('organization/<uuid:pk>/update/', OrganizationUpdateView.as_view(), name='organization-update'),
    path("export/", export_finances, name="export-finances"),
]

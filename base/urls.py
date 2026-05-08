from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('trigger-export-email/', trigger_export_email, name='export-email-trigger'),
    path("set-language/", set_language, name="set-language"),

    # File Upload (Drag & Drop) ------------------------------
    path('generic-file-upload/', generic_file_upload, name='generic-file-upload'),

    # Generic Delete (for any model)
    path('toggle-status/<str:model_name>/<uuid:pk>/',
         ToggleStatusView.as_view(), name='toggle-status'),
    
    # Activation ------------------------------
    path('toggle-activity/<str:model_name>/<uuid:pk>/',
         ToggleActivityView.as_view(), name='toggle-activity'),
    path("bulk-toggle-activity/<str:model_name>/",
         BulkToggleActivityView.as_view(), name="bulk-toggle-activity"),
    
    # Verification ------------------------------
    path('toggle-verification/<str:model_name>/<uuid:pk>/',
         ToggleVerificationView.as_view(), name='toggle-verification'),
    path("bulk-toggle-verification/<str:model_name>/",
         BulkToggleVerificationView.as_view(), name="bulk-toggle-verification"),
    
    # Archival ------------------------------
    path('toggle-archival/<str:model_name>/<uuid:pk>/',
         ToggleVerificationView.as_view(), name='toggle-archival'),
    path("bulk-toggle-archival/<str:model_name>/",
         BulkToggleVerificationView.as_view(), name="bulk-toggle-archival"),

    # Deletion ------------------------------
    path('delete-objects/<str:model_name>/',
         BaseDeleteView.as_view(), name='delete-objects'),
    path('delete-objects/<str:model_name>/<str:pk>/',
         BaseDeleteView.as_view(), name='delete-object'),
    path('delete-objects/<str:model_name>/<uuid:pk>/',
         BaseDeleteView.as_view(), name='delete-object'),
    path("htmx/delete/<str:model_name>/",
         HTMXDeleteView.as_view(),  name="htmx-delete-objects"),
    path("htmx/delete/<str:model_name>/<uuid:pk>/",
         HTMXDeleteView.as_view(), name="htmx-delete-object"),

    # Import!Export ------------------------------
    path("export-objects/<str:app_name>/<str:model_name>/<str:format_type>/",
         BaseExportView.as_view(), name="export-data"),
    path("import-objects/<str:app_name>/<str:model_name>/",
         BaseImportView.as_view(), name="import-data"),

    # Platform Parameters ------------------------------
    path('user-parameters/', user_parameters, name='user-parameters'),
    path('system-parameters/', system_parameters, name='system-parameters'),
    path('security-parameters/', security_parameters, name='security-parameters'),
    path('error-404-page/', not_found, name='not-found'),

]

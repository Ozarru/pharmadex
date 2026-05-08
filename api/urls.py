from django.urls import path
from api import views


urlpatterns = [
    path("health/", views.health, name="health"),
]


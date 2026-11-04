"""Routes du front."""
from django.contrib.auth import views as auth_views
from django.urls import path

from dashboard import views

urlpatterns = [
    path("", views.ordres_ouverts, name="ordres"),
    path("logs/", views.logs, name="logs"),
    path("connexion/", auth_views.LoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
]

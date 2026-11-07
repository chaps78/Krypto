"""Routes du front."""
from django.contrib.auth import views as auth_views
from django.urls import path, re_path

from dashboard import views

urlpatterns = [
    path("", views.kpi, name="kpi"),
    path("grille/", views.grille, name="grille"),
    path("logs/", views.logs, name="logs"),
    re_path(r"^bot/(?P<action>arreter|demarrer)/$", views.piloter_bot, name="piloter_bot"),
    path("connexion/", auth_views.LoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
]

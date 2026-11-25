from django.urls import path

from .views import HomeView, RuLoginView, RuLogoutView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", RuLoginView.as_view(), name="login"),
    path("logout/", RuLogoutView.as_view(), name="logout"),
]

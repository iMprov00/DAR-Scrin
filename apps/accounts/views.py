"""Представления входа (заготовка этапа 1)."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View


class RuLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class RuLogoutView(LogoutView):
    next_page = reverse_lazy("login")


@method_decorator(login_required, name="dispatch")
class HomeView(View):
    """Простая заглушка после входа (полный UI — этапы 2–3)."""

    def get(self, request):
        return render(request, "home.html")

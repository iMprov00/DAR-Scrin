"""Представления входа и главной."""
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
    """Главная: ссылки по ролям, без пустых разделов."""

    def get(self, request):
        return render(
            request,
            "home.html",
            {
                "layout": (
                    "therapist"
                    if request.user.is_therapist
                    else "employee"
                    if request.user.is_employee
                    else "default"
                ),
            },
        )

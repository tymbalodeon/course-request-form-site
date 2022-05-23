from typing import cast
from django.views.generic import DetailView, ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from config.config import PROD_URL

from form.canvas import get_user_canvas_sites

from .models import Section, User


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "form/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = cast(User, self.request.user)
        context["email"] = user.email
        context["courses"] = Section.objects.filter(instructors=user)
        context["canvas_sites"] = get_user_canvas_sites(user.username)
        context["canvas_url"] = f"{PROD_URL}/courses"
        return context


class SectionListView(ListView):
    model = Section

    def get_queryset(self):
        return Section.objects.filter(primary_section__isnull=True)


class SectionDetailView(DetailView):
    model = Section

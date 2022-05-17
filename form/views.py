from django.views.generic import DetailView, ListView, TemplateView

from .models import Section


class HomePageView(TemplateView):
    template_name = "form/home.html"


class SectionListView(ListView):
    model = Section


class SectionDetailView(DetailView):
    model = Section

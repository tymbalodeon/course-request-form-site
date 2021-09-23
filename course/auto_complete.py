from dal import autocomplete
from django.contrib.auth.models import User
from django.db.models import Q

from course.models import CanvasSite, Subject


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        print(
            f"{self.request.user} is"
            f" {'' if self.request.user.is_authenticated else 'not'} authenticated."
        )

        if not self.request.user.is_authenticated:
            return User.objects.none()

        query_set = User.objects.all()

        if self.q:
            return query_set.filter(username__istartswith=self.q)[:8]
        else:
            return User.objects.none()

    def get_result_value(self, result):
        return str(result.username)


class SubjectAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Subject.objects.none()

        query_set = Subject.objects.all()

        if self.q:
            return query_set.filter(abbreviation__istartswith=self.q)[:8]
        else:
            return Subject.objects.none()

    def get_result_value(self, result):
        return str(result.abbreviation)


class CanvasSiteAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        print(
            f"{self.request.user} is"
            f" {'' if self.request.user.is_authenticated else 'not'} authenticated."
        )

        if not self.request.user.is_authenticated:
            return CanvasSite.objects.none()

        masquerade = self.request.session["on_behalf_of"]

        if masquerade:
            query_set = CanvasSite.objects.filter(
                Q(owners=User.objects.get(username=masquerade))
                | Q(added_permissions=self.request.user)
            )
        else:
            query_set = CanvasSite.objects.filter(
                Q(owners=self.request.user) | Q(added_permissions=self.request.user)
            )

        if self.q:
            return query_set.filter(name__istartswith=self.q)[:8]
        else:
            return query_set

    def get_result_value(self, result):
        return str(result.canvas_id)

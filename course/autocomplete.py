from logging import getLogger

from dal.autocomplete import Select2QuerySetView
from django.db.models import Q

from .models import CanvasCourse, Subject, User

logger = getLogger(__name__)


class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return User.objects.none()
        query_set = User.objects.all()
        if self.q:
            return query_set.filter(username__contains=self.q)
        else:
            return User.objects.none()

    def get_result_value(self, result):
        return str(result.username)


class SubjectAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Subject.objects.none()
        query_set = Subject.objects.all()
        if self.q:
            return query_set.filter(abbreviation__contains=self.q)
        else:
            return Subject.objects.none()

    def get_result_value(self, result):
        return str(result.abbreviation)


class CanvasSiteAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        logger.info(
            f"{self.request.user} is"
            f"{'' if self.request.user.is_authenticated else 'not'} authenticated."
        )
        if not self.request.user.is_authenticated:
            return CanvasCourse.objects.none()
        masquerade = self.request.session["on_behalf_of"]
        user = (
            User.objects.get(username=masquerade) if masquerade else self.request.user
        )
        query_set = CanvasCourse.objects.filter(
            Q(owners=user) | Q(added_permissions=self.request.user)
        ).order_by("-canvas_id")
        query_set = query_set.filter(~Q(workflow_state="deleted"))
        return query_set.filter(name__contains=self.q) if self.q else query_set

    def get_result_value(self, result):
        return str(result.canvas_id)

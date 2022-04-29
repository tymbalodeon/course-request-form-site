from logging import getLogger

from dal.autocomplete import Select2QuerySetView

from .models import Subject, User

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

from django.contrib.admin import site

from form.models import ScheduleType, School, Section, Subject, User

site.register(User)
site.register(ScheduleType)
site.register(School)
site.register(Subject)
site.register(Section)

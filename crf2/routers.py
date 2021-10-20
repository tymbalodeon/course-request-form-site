from course.views import CourseViewSet
from rest_framework import routers

router = routers.DefaultRouter()
router.register("course", CourseViewSet)

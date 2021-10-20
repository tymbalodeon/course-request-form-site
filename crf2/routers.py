from rest_framework import routers

from course.views import CourseViewSet

router = routers.DefaultRouter()
router.register("course", CourseViewSet)

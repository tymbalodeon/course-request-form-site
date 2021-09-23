from rest_framework import routers

from course.viewsets import CourseViewSet

router = routers.DefaultRouter()
router.register("course", CourseViewSet)

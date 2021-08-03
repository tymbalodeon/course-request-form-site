from course.viewsets import CourseViewSet
from rest_framework import routers

# from article.viewsets import ArticleViewSet


router = routers.DefaultRouter()
router.register("course", CourseViewSet)

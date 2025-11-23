from django.urls import path
from .views import LoginAPIView, RegistrationAPIView, RegisterTemplateView, LoginTemplateView

urlpatterns = [
    path('users/', RegistrationAPIView.as_view()),
    path('users/login/', LoginAPIView.as_view()),
    path('users/register_html/', RegisterTemplateView.as_view(), name='register_html'),
    path('users/login_html/', LoginTemplateView.as_view(), name='login_html'),
]
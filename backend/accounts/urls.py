from django.urls import path
from .views import (
    RegisterTemplateView, LoginTemplateView,
    LogoutTemplateView, ProfileTemplateView, SettingsTemplateView,
    ChangeLoginView, DeleteAccountView, EditFamilyMemberView
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterTemplateView.as_view(), name='register'),
    path('login/', LoginTemplateView.as_view(), name='login'),
    path('logout/', LogoutTemplateView.as_view(), name='logout'),
    path('profile/', ProfileTemplateView.as_view(), name='profile'),
    path('settings/', SettingsTemplateView.as_view(), name='settings'),
    path('change-login/', ChangeLoginView.as_view(), name='change_login'),
    path('delete-account/', DeleteAccountView.as_view(), name='delete_account'),
    path('edit-family-member/<int:member_id>/', EditFamilyMemberView.as_view(), name='edit_family_member'),
]
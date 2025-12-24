from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientViewSet,
    CreatePatientTemplateView, ManageFamilyTemplateView,
    FamilyInviteView, FamilyRedeemView, RemoveFamilyMemberView
)

app_name = 'patients'

# API Router
router = DefaultRouter()
router.register(r'api', PatientViewSet, basename='patient')

urlpatterns = [
    # API routes
    path('', include(router.urls)),
    
    # HTML template routes
    path('create_html/', CreatePatientTemplateView.as_view(), name='patient_create_html'),
    path('manage_html/', ManageFamilyTemplateView.as_view(), name='patient_manage_html'),
    path('family/invite/', FamilyInviteView.as_view(), name='family_invite'),
    path('family/redeem/', FamilyRedeemView.as_view(), name='family_redeem'),
    path('family/remove/', RemoveFamilyMemberView.as_view(), name='remove_family'),
]
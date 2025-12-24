from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'staff'

# API Router
router = DefaultRouter()
router.register(r'api/doctors', views.DoctorViewSet, basename='doctor')
router.register(r'api/specializations', views.SpecializationViewSet, basename='specialization')

urlpatterns = [
    # API routes
    path('', include(router.urls)),
    
    # HTML template routes
    path('home/', views.DoctorHomeView.as_view(), name='doctor_home'),
    path('profile/', views.DoctorProfileView.as_view(), name='doctor_profile'),
    path('patients/', views.DoctorPatientsListView.as_view(), name='doctor_patients'),
    path('patients/<int:pk>/', views.DoctorPatientDetailView.as_view(), name='doctor_patient_detail'),
    path('doctors/', views.DoctorsListView.as_view(), name='doctors_list'),
    path('doctors/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor_detail'),
]
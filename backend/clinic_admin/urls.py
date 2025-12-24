from django.urls import path
from . import views

app_name = 'clinic_admin'

urlpatterns = [

    path('', views.AdminDashboardView.as_view(), name='dashboard'),


    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),


    path('patients/', views.PatientListView.as_view(), name='patient_list'),
    path('patients/create/', views.PatientCreateView.as_view(), name='patient_create'),
    path('patients/<int:pk>/', views.PatientDetailView.as_view(), name='patient_detail'),
    path('patients/<int:pk>/edit/', views.PatientEditView.as_view(), name='patient_edit'),
    path('patients/<int:pk>/delete/', views.PatientDeleteView.as_view(), name='patient_delete'),
    path('patients/<int:pk>/book/', views.PatientBookView.as_view(), name='patient_book'),


    path('families/', views.FamilyListView.as_view(), name='family_list'),
    path('families/create/', views.FamilyCreateView.as_view(), name='family_create'),
    path('families/<int:pk>/', views.FamilyDetailView.as_view(), name='family_detail'),
    path('families/<int:pk>/add-member/', views.FamilyAddMemberView.as_view(), name='family_add_member'),
    path('families/<int:pk>/remove-member/', views.FamilyRemoveMemberView.as_view(), name='family_remove_member'),


    path('doctors/', views.DoctorListView.as_view(), name='doctor_list'),
    path('doctors/create/', views.DoctorCreateView.as_view(), name='doctor_create'),
    path('doctors/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor_detail'),
    path('doctors/<int:pk>/edit/', views.DoctorEditView.as_view(), name='doctor_edit'),
    path('doctors/<int:pk>/delete/', views.DoctorDeleteView.as_view(), name='doctor_delete'),


    path('schedule/', views.ClinicScheduleView.as_view(), name='clinic_schedule'),
    path('appointments/update-status/', views.AppointmentUpdateStatusView.as_view(), name='appointment_update_status'),
    path('appointments/<int:pk>/results/', views.AppointmentResultsView.as_view(), name='appointment_results'),
]

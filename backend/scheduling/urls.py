from django.urls import path
from . import views

app_name = 'scheduling'

urlpatterns = [
    path('book/', views.BookAppointmentView.as_view(), name='book_appointment'),
    path('doctor/<int:doctor_id>/', views.DoctorScheduleView.as_view(), name='doctor_schedule'),
    path('doctor/<int:doctor_id>/add-timeslot/', views.AddTimeSlotView.as_view(), name='add_timeslot'),
    path('book-for-other/', views.BookForOtherDoctorView.as_view(), name='book_for_other'),
    path('appointment/<int:pk>/status/', views.UpdateAppointmentStatusView.as_view(), name='update_status'),
    path('appointment/<int:pk>/', views.AppointmentDetailView.as_view(), name='appointment_detail'),
    path('referral-slots/<int:doctor_id>/', views.GetReferralSlotsView.as_view(), name='get_referral_slots'),
    path('appointment/<int:pk>/offer-account/', views.OfferAccountCreationView.as_view(), name='offer_account_creation'),
    path('appointment/<int:pk>/info/', views.AppointmentInfoView.as_view(), name='appointment_info'),
    path('appointment/<int:pk>/cancel/', views.CancelAppointmentView.as_view(), name='cancel_appointment'),
    path('appointment/<int:pk>/update-patient/', views.UpdateAppointmentPatientView.as_view(), name='update_appointment_patient'),
    path('slot/<int:slot_id>/book/', views.BookSlotView.as_view(), name='book_slot'),
    path('appointment/<int:appointment_id>/change-patient/', views.ChangeBookedAppointmentPatientView.as_view(), name='change_appointment_patient'),
]
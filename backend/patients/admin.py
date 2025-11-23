from django.contrib import admin
from .models import Patient, PatientGroup

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('id','fname','lname','bdate','phone_number','email','snils','oms')
    search_fields = ('fname','lname','snils','oms','email')

@admin.register(PatientGroup)
class PatientGroupAdmin(admin.ModelAdmin):
    list_display = ('id','parent','child')
    search_fields = ('parent__fname','parent__lname','child__fname','child__lname')
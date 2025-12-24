from django.contrib import admin
from django.urls import path, include
from core.views import IndexView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('scheduling/', include('scheduling.urls')),
    path('admin-panel/', include('clinic_admin.urls')),
    path('accounts/', include('accounts.urls')),
    path('staff/', include('staff.urls')),
    path('patients/', include('patients.urls')),
    path('', IndexView.as_view(), name='index'),
]
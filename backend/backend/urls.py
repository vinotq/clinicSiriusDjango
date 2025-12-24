from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.static import serve
from core.views import IndexView, handler400, handler403, handler404, handler500, handler503

urlpatterns = [
    path('admin/', admin.site.urls),
    path('scheduling/', include('scheduling.urls')),
    path('admin-panel/', include('clinic_admin.urls')),
    path('accounts/', include('accounts.urls')),
    path('staff/', include('staff.urls')),
    path('patients/', include('patients.urls')),
    path('', IndexView.as_view(), name='index'),
]

handler400 = handler400
handler403 = handler403
handler404 = handler404
handler500 = handler500
handler503 = handler503

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
else:
    if settings.STATICFILES_DIRS:
        static_root = settings.STATICFILES_DIRS[0]
        urlpatterns += [
            re_path(r'^static/(?P<path>.*)$', serve, {'document_root': static_root}),
        ]
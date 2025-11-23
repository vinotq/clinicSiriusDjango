from django.urls import path
from .views import PatientViewSet, CreatePatientTemplateView, ManageFamilyTemplateView

patient_list = PatientViewSet.as_view({
	'get': 'list',
	'post': 'create'
})

patient_detail = PatientViewSet.as_view({
	'get': 'retrieve',
	'put': 'update',
	'patch': 'partial_update',
	'delete': 'destroy'
})

patient_parents = PatientViewSet.as_view({
	'get': 'parents'
})

patient_children = PatientViewSet.as_view({
	'get': 'children'
})

patient_add_parent = PatientViewSet.as_view({
	'post': 'add_parent'
})

patient_remove_parent = PatientViewSet.as_view({
	'post': 'remove_parent'
})

patient_me = PatientViewSet.as_view({
	'get': 'me'
})

patient_create_family = PatientViewSet.as_view({
	'post': 'create_family_member'
})

urlpatterns = [
	path('patients/', patient_list, name='patient-list'),
	path('patients/<int:pk>/', patient_detail, name='patient-detail'),
	path('patients/<int:pk>/parents/', patient_parents, name='patient-parents'),
	path('patients/<int:pk>/children/', patient_children, name='patient-children'),
	path('patients/<int:pk>/add-parent/', patient_add_parent, name='patient-add-parent'),
	path('patients/<int:pk>/remove-parent/', patient_remove_parent, name='patient-remove-parent'),
	path('patients/create_html/', CreatePatientTemplateView.as_view(), name='patient-create-html'),
	path('patients/manage_html/', ManageFamilyTemplateView.as_view(), name='patient-manage-html'),
	path('patients/me/', patient_me, name='patient-me'),
	path('patients/create-family-member/', patient_create_family, name='patient-create-family'),
]
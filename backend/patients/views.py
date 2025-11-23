from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Patient, PatientGroup
from .serializers import PatientSerializer
from .permissions import IsOwnerOrStaff
from django.views.generic import TemplateView

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsOwnerOrStaff]

    @action(detail=True, methods=['get'], permission_classes=[IsOwnerOrStaff])
    def parents(self, request, pk=None):
        patient = self.get_object()
        serializer = PatientSerializer(patient.parents(), many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsOwnerOrStaff])
    def children(self, request, pk=None):
        patient = self.get_object()
        serializer = PatientSerializer(patient.children(), many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add-parent', permission_classes=[IsOwnerOrStaff])
    def add_parent(self, request, pk=None):
        patient = self.get_object()
        parent_id = request.data.get('parent_id')
        if not parent_id:
            return Response({'detail': 'parent_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            parent = Patient.objects.get(pk=parent_id)
        except Patient.DoesNotExist:
            return Response({'detail': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)
        if parent.pk == patient.pk:
            return Response({'detail':'Parent and child must be different'}, status=status.HTTP_400_BAD_REQUEST)
        PatientGroup.objects.get_or_create(parent=parent, child=patient)
        return Response({'detail':'parent added'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='remove-parent', permission_classes=[IsOwnerOrStaff])
    def remove_parent(self, request, pk=None):
        patient = self.get_object()
        parent_id = request.data.get('parent_id')
        if not parent_id:
            return Response({'detail': 'parent_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = PatientGroup.objects.filter(parent_id=parent_id, child=patient).delete()
        if deleted:
            return Response({'detail':'parent removed'}, status=status.HTTP_200_OK)
        return Response({'detail':'relationship not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        parent_patient = getattr(request.user, 'patient_profile', None)
        if not parent_patient:
            return Response({'detail':'No patient profile for current user'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PatientSerializer(parent_patient, context={'request': request})
        data = serializer.data
        data['parents'] = PatientSerializer(parent_patient.parents(), many=True, context={'request': request}).data
        data['children'] = PatientSerializer(parent_patient.children(), many=True, context={'request': request}).data
        return Response(data)

    @action(detail=False, methods=['post'], url_path='create-family-member', permission_classes=[IsAuthenticated])
    def create_family_member(self, request):
        parent_patient = getattr(request.user, 'patient_profile', None)
        if not parent_patient:
            return Response({'detail':'Parent has no patient profile'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PatientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = serializer.save()
        PatientGroup.objects.get_or_create(parent=parent_patient, child=child)
        return Response(PatientSerializer(child, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CreatePatientTemplateView(TemplateView):
    template_name = 'patients/create_patient.html'


class ManageFamilyTemplateView(TemplateView):
    template_name = 'patients/manage_family.html'
    
    @action(detail=False, methods=['post'], url_path='create-family-member', permission_classes=[IsAuthenticated])
    def create_family_member(self, request):
        parent_patient = getattr(request.user, 'patient_profile', None)
        if not parent_patient:
            return Response({'detail':'Parent has no patient profile'}, status=400)
        serializer = PatientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = serializer.save()
        PatientGroup.objects.get_or_create(parent=parent_patient, child=child)
        return Response(PatientSerializer(child).data, status=201)
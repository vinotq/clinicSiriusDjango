from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Patient, PatientGroup
from .serializers import PatientSerializer
from .permissions import IsOwnerOrStaff
from django.views.generic import TemplateView
from django.views import View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from core.mixins import PatientRequiredMixin
import secrets

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


class ManageFamilyTemplateView(PatientRequiredMixin, TemplateView):
    template_name = 'patients/manage_family.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.request.user.patient_profile
        
        family = patient.children()
        context['family_members'] = family
        context['children_ids'] = set(family.values_list('id', flat=True))
        
        try:
            from patients.models import FamilyInvite
            context['invites'] = list(FamilyInvite.objects.filter(patient=patient, used=False))
        except:
            context['invites'] = []
        
        return context

class FamilyInviteView(PatientRequiredMixin, View):
    def post(self, request):
        patient = request.user.patient_profile
        
        try:
            from patients.models import FamilyInvite
            import secrets
            
            code = secrets.token_hex(3).upper()[:6]
            invite = FamilyInvite.objects.create(patient=patient, code=code)
            
            return redirect(f"{reverse('patients:patient_manage_html')}?invite={code}")
        except Exception as e:
            messages.error(request, f'Ошибка при создании кода: {str(e)}')
            return redirect('patients:patient_manage_html')

class FamilyRedeemView(PatientRequiredMixin, View):
    def post(self, request):
        patient = request.user.patient_profile
        invite_code = request.POST.get('invite_code', '').strip().upper()
        
        if not invite_code:
            messages.error(request, 'Введите код приглашения')
            return redirect('patients:patient_manage_html')
        
        try:
            from patients.models import FamilyInvite
            invite = FamilyInvite.objects.get(code=invite_code, used=False)
            
            if invite.patient == patient:
                messages.error(request, 'Нельзя использовать свой собственный код')
                return redirect('patients:patient_manage_html')
            
            PatientGroup.objects.get_or_create(parent=invite.patient, child=patient)
            invite.used = True
            invite.save()
            
            messages.success(request, 'Профиль успешно привязан к семье')
            return redirect('patients:patient_manage_html')
        except FamilyInvite.DoesNotExist:
            messages.error(request, 'Неверный или уже использованный код')
            return redirect('patients:patient_manage_html')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
            return redirect('patients:patient_manage_html')

class RemoveFamilyMemberView(PatientRequiredMixin, View):
    def post(self, request):
        patient = request.user.patient_profile
        member_id = request.POST.get('member_id')
        
        if not member_id:
            messages.error(request, 'Не указан ID члена семьи')
            return redirect('patients:patient_manage_html')
        
        try:
            member = get_object_or_404(Patient, pk=member_id)
            
            PatientGroup.objects.filter(
                parent=patient, child=member
            ).delete()
            
            PatientGroup.objects.filter(
                parent=member, child=patient
            ).delete()
            
            messages.success(request, 'Член семьи успешно удален')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
        
        return redirect('patients:patient_manage_html')
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Doctor, Specialization

User = get_user_model()

class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialization
        fields = ['id', 'name']


class DoctorSerializer(serializers.ModelSerializer):
    specialization = SpecializationSerializer(read_only=True)
    specialization_id = serializers.IntegerField(write_only=True)
    specialization_name = serializers.CharField(source='specialization.name', read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    
    class Meta:
        model = Doctor
        fields = ['id', 'fname', 'lname', 'tname', 'bdate', 'phone_number', 'email', 
                  'specialization', 'specialization_id', 'specialization_name', 'user']
    
    def create(self, validated_data):
        specialization_id = validated_data.pop('specialization_id')
        specialization = Specialization.objects.get(id=specialization_id)
        doctor = Doctor.objects.create(specialization=specialization, **validated_data)
        return doctor
    
    def update(self, instance, validated_data):
        specialization_id = validated_data.pop('specialization_id', None)
        if specialization_id:
            specialization = Specialization.objects.get(id=specialization_id)
            instance.specialization = specialization
        return super().update(instance, validated_data)

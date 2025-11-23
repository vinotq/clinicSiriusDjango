from rest_framework import serializers
from .models import Patient, PatientGroup

class SimplePatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ('id', 'fname', 'lname', 'tname', 'bdate', 'phone_number', 'email', 'snils', 'oms')

class PatientSerializer(serializers.ModelSerializer):
    parents = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ('id', 'fname', 'lname', 'tname', 'bdate', 'phone_number', 'email', 'snils', 'oms', 'parents', 'children')

    def get_parents(self, obj):
        qs = obj.parents()
        return SimplePatientSerializer(qs, many=True, context=self.context).data

    def get_children(self, obj):
        qs = obj.children()
        return SimplePatientSerializer(qs, many=True, context=self.context).data

class PatientGroupSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all())
    child = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all())

    class Meta:
        model = PatientGroup
        fields = ('id', 'parent', 'child')
    
    def validate(self, data):
        if data['parent'] == data['child']:
            raise serializers.ValidationError("Parent and child must be different patients.")
        return data
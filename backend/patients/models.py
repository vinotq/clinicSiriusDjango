from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

class Patient(models.Model):
    fname = models.CharField(max_length=100)
    lname = models.CharField(max_length=100)
    tname = models.CharField(max_length=100, blank=True, null=True)
    bdate = models.DateField()
    phone_number = models.CharField(max_length=11, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    snils = models.CharField(max_length=11, unique=True)
    oms = models.CharField(max_length=16, unique=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='patient_profile')

    def __str__(self):
        return f"{self.fname} {self.lname}"

    def parents(self):
        return Patient.objects.filter(parents_rel__child=self)

    def children(self):
        return Patient.objects.filter(children_rel__parent=self)

    def add_parent(self, parent_patient):
        if parent_patient.pk == self.pk:
            raise ValidationError("Patient cannot be parent of themself.")
        PatientGroup.objects.get_or_create(parent=parent_patient, child=self)

    def remove_parent(self, parent_patient):
        PatientGroup.objects.filter(parent=parent_patient, child=self).delete()

    def ancestors(self, max_depth=10):
        results = set()
        current = {self}
        depth = 0
        while current and depth < max_depth:
            parents = Patient.objects.filter(children__child__in=current)
            new = set(parents) - results
            results.update(new)
            current = new
            depth += 1
        return list(results)

    def descendants(self, max_depth=10):
        results = set()
        current = {self}
        depth = 0
        while current and depth < max_depth:
            kids = Patient.objects.filter(parents__parent__in=current)
            new = set(kids) - results
            results.update(new)
            current = new
            depth += 1
        return list(results)


class PatientGroup(models.Model):
    parent = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='parents_rel')
    child = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='children_rel')

    class Meta:
        unique_together = ('parent', 'child')

    def clean(self):
        if self.parent_id == self.child_id:
            raise ValidationError("Parent and child must be different patients.")

    def __str__(self):
        return f"{self.parent} -> {self.child}"
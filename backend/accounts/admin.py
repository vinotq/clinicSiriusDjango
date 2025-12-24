from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'username',
        'email',
        'role',
        'is_active',
        'created_at',
        'updated_at',
        )
    
    def get_queryset(self, request):
        if request.user.is_superuser:
            return User.objects.all()
        else:
            return User.objects.filter(id=request.user.id)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.save()
        else:
            obj.updated_by = request.user
            obj.save()
        
    
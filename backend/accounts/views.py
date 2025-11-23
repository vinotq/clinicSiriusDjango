from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import LoginSerializer, RegistrationSerializer
from django.views.generic import TemplateView
from django.contrib.auth import authenticate, login


class RegistrationAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = RegistrationSerializer

    def post(self, request):
        user = request.data.get('user', {})
        
        serializer = self.serializer_class(data=user, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class LoginAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        user = request.data.get('user', {})

        serializer = self.serializer_class(data=user)
        serializer.is_valid(raise_exception=True)

        email = user.get('email')
        password = user.get('password')
        user_obj = authenticate(username=email, password=password)
        if user_obj is not None:
            login(request, user_obj)

        return Response(serializer.data, status=status.HTTP_200_OK)


class RegisterTemplateView(TemplateView):
    template_name = 'accounts/register.html'


class LoginTemplateView(TemplateView):
    template_name = 'accounts/login.html'
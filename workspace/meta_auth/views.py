from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login

from .models import MetaUser
from .serializers import UserRegistrationSerializer, UserSerializer


class UserViewSet(viewsets.GenericViewSet):
    """
    ViewSet for user management.
    
    register: Register a new user
    me: Get current user details
    """
    queryset = MetaUser.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'register':
            return UserRegistrationSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'register':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new meta platform user."""
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Auto-login after registration
        login(request, user)
        
        user_serializer = UserSerializer(user)
        return Response(
            {
                'message': 'User registered successfully',
                'user': user_serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user details."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

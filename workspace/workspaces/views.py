from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Workspace, WorkspaceOTP, ProvisioningLog
from .serializers import (
    WorkspaceSerializer,
    WorkspaceCreateSerializer,
    OTPSerializer,
    OTPValidationSerializer,
    ProvisioningLogSerializer
)


class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing workspaces.
    
    list: Get all workspaces for the authenticated user
    create: Create a new workspace
    retrieve: Get details of a specific workspace
    update/partial_update: Update workspace details
    destroy: Decommission a workspace
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return WorkspaceCreateSerializer
        return WorkspaceSerializer
    
    def get_queryset(self):
        # Users can only see their own workspaces
        return Workspace.objects.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        """Create workspace and generate OTP."""
        workspace = serializer.save()
        
        # Generate OTP for the new workspace
        otp = WorkspaceOTP.objects.create(
            workspace=workspace,
            max_uses=0  # Unlimited uses for workspace OTP
        )
        
        # Log provisioning start
        ProvisioningLog.objects.create(
            workspace=workspace,
            level='info',
            message=f'Workspace {workspace.workspace_id} created by {self.request.user.email}',
            data={'otp': otp.otp_code}
        )
        
        # TODO: Trigger provisioning task here
        # provision_workspace.delay(workspace.id)
    
    @action(detail=True, methods=['post'])
    def generate_otp(self, request, pk=None):
        """Generate a new OTP for the workspace."""
        workspace = self.get_object()
        
        otp = WorkspaceOTP.objects.create(
            workspace=workspace,
            max_uses=0  # Unlimited uses
        )
        
        serializer = OTPSerializer(otp)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def otps(self, request, pk=None):
        """Get all OTPs for the workspace."""
        workspace = self.get_object()
        otps = workspace.otps.all()
        serializer = OTPSerializer(otps, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get provisioning logs for the workspace."""
        workspace = self.get_object()
        logs = workspace.logs.all()[:50]  # Last 50 logs
        serializer = ProvisioningLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_active(self, request, pk=None):
        """Mark workspace as active (after provisioning)."""
        workspace = self.get_object()
        workspace.mark_provisioned()
        
        ProvisioningLog.objects.create(
            workspace=workspace,
            level='info',
            message='Workspace marked as active'
        )
        
        serializer = self.get_serializer(workspace)
        return Response(serializer.data)


class OTPViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing OTPs.
    
    list: Get all OTPs for user's workspaces
    retrieve: Get details of a specific OTP
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OTPSerializer
    
    def get_queryset(self):
        # Users can only see OTPs for their own workspaces
        return WorkspaceOTP.objects.filter(workspace__owner=self.request.user)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def validate(self, request):
        """
        Validate an OTP and return workspace connection details.
        
        This is the key endpoint that client apps use to discover workspaces.
        Similar to the discovery API mentioned in deploy-pipeline.txt.
        """
        serializer = OTPValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        otp_code = serializer.validated_data['otp']
        otp = get_object_or_404(WorkspaceOTP, otp_code=otp_code)
        
        if not otp.is_valid:
            return Response(
                {'error': 'OTP is invalid or has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark OTP as used
        client_ip = request.META.get('REMOTE_ADDR')
        otp.mark_used(ip_address=client_ip)
        
        # Log the connection
        ProvisioningLog.objects.create(
            workspace=otp.workspace,
            level='info',
            message=f'OTP validated from IP {client_ip}',
            data={'otp': otp_code}
        )
        
        # Return connection details
        connection_details = otp.get_connection_details()
        return Response(connection_details, status=status.HTTP_200_OK)

"""
API Views for Accounts App
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Plan
from .serializers import PlanSerializer


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing plans
    """
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Optionally filter plans by service_name or plan_type
        """
        queryset = Plan.objects.all()
        service_name = self.request.query_params.get('service_name', None)
        plan_type = self.request.query_params.get('plan_type', None)
        
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        if plan_type:
            queryset = queryset.filter(plan_type=plan_type)
            
        return queryset


import os
import django
import sys
import json

# Setup Django environment
sys.path.append(r'C:\Techproject\Agentyne\agentynebdr\agentyne_asoc_27feb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asoc_core.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from crm.models import Deal
from django.test import RequestFactory
from django.urls import reverse
from dashboard.api_opportunities import opportunities_bulk_update_api
from dashboard.opportunity_views import update_opportunity_owner

def test_opportunity_assignment():
    print("Testing Opportunity Assignment Logic...")
    
    # 1. Setup Test Data
    email1 = "admin_test@example.com"
    email2 = "new_owner_test@example.com"
    
    # Cleanup
    User.objects.filter(email__in=[email1, email2]).delete()
    Organization.objects.filter(name="Test Opp Org").delete()
    
    # Create Org and Users
    admin = User.objects.create(username=email1, email=email1, is_staff=True)
    new_owner = User.objects.create(username=email2, email=email2)
    org = Organization.objects.create(name="Test Opp Org", owner=admin)
    UserProfile.objects.create(user=admin, organization=org)
    UserProfile.objects.create(user=new_owner, organization=org)
    
    # Create Deal owned by admin
    deal = Deal.objects.create(name="Test Deal", owner=admin, amount=1000, probability=50)
    
    # 2. Test Bulk Update API
    print("Testing Bulk Update API...")
    rf = RequestFactory()
    request = rf.post('/api/opportunities/bulk-update/', 
                     data=json.dumps({'ids': [deal.id], 'updates': {'owner_id': new_owner.id}}),
                     content_type='application/json')
    request.user = admin
    request.org_user_ids = [admin.id, new_owner.id]
    
    response = opportunities_bulk_update_api(request)
    print(f"Bulk Update Response: {response.content}")
    
    deal.refresh_from_db()
    if deal.owner_id == new_owner.id:
        print("SUCCESS: Bulk update assignment worked.")
    else:
        print(f"FAILURE: Bulk update failed. Owner is {deal.owner_id}, expected {new_owner.id}")
        return
        
    # 3. Test update_opportunity_owner (AJAX view)
    print("Testing update_opportunity_owner AJAX view...")
    # Reset deal owner
    deal.owner = admin
    deal.save()
    
    request = rf.post(f'/opportunities/{deal.id}/update-owner/',
                     data=json.dumps({'owner_id': new_owner.id}),
                     content_type='application/json')
    request.user = admin
    request.org_user_ids = [admin.id, new_owner.id]
    request.organization = org
    
    response = update_opportunity_owner(request, deal.id)
    print(f"AJAX View Response: {response.content}")
    
    deal.refresh_from_db()
    if deal.owner_id == new_owner.id:
        print("SUCCESS: AJAX view assignment worked.")
    else:
        print(f"FAILURE: AJAX view failed. Owner is {deal.owner_id}, expected {new_owner.id}")
        return

    # 4. Cleanup
    User.objects.filter(email__in=[email1, email2]).delete()
    org.delete()
    print("Verification script finished successfully.")

if __name__ == "__main__":
    test_opportunity_assignment()

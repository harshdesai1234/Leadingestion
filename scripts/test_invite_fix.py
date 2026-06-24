
import os
import django
import sys

# Setup Django environment
sys.path.append(r'C:\Techproject\Agentyne\agentynebdr\agentyne_asoc_27feb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asoc_core.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from accounts.invite_views import _handle_send_invite
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from rbac_roles.models import Role

def test_invitation_block():
    print("Testing Invitation Block Logic...")
    
    # 1. Setup Test Data
    email = "test_already_exists@example.com"
    
    # Cleanup if exists
    User.objects.filter(email=email).delete()
    Organization.objects.filter(name="Test Org 1").delete()
    Organization.objects.filter(name="Test Org 2").delete()
    
    # Create Org 1 and User
    org1 = Organization.objects.create(name="Test Org 1", owner=User.objects.first())
    user = User.objects.create(username=email, email=email)
    UserProfile.objects.get_or_create(user=user, defaults={'organization': org1})
    
    # Create Org 2 (the one trying to invite)
    org2 = Organization.objects.create(name="Test Org 2", owner=User.objects.first())
    
    # 2. Simulate Request
    rf = RequestFactory()
    request = rf.post('/accounts/invite/', {'email': email})
    request.user = User.objects.first() # Admin doing the inviting
    
    # Mock session and messages to avoid middleware errors
    request.session = {}
    from unittest.mock import MagicMock
    request._messages = MagicMock()
    
    # 3. Call the handler
    response = _handle_send_invite(request, org2)
    
    # 4. Verify results
    # Inspect calls to request._messages.add
    messages = [args[1] for args, kwargs in request._messages.add.call_args_list]
    
    print(f"Response status code: {response.status_code}")
    print(f"Messages: {messages}")
    
    if any("is already registered in the database" in m for m in messages):
        print("SUCCESS: Invitation was blocked correctly.")
    else:
        print("FAILURE: Invitation was NOT blocked or message was incorrect.")
        sys.exit(1)

    # 5. Cleanup
    User.objects.filter(email=email).delete()
    org1.delete()
    org2.delete()

if __name__ == "__main__":
    test_invitation_block()

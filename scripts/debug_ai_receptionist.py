import os
import sys
from pathlib import Path
import django

# Add project root and apps directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asoc_core.settings')
django.setup()

from ai_receptionist.models import AIReceptionist
from admin_dashboard.models_ai_receptionist import AIReceptionistAgent, AIReceptionistLicense
from dashboard.models import BdrPitch
from django.contrib.auth import get_user_model

User = get_user_model()

def debug_data():
    print("--- Debugging AI Receptionist Data ---")
    
    # 1. Check Users
    print(f"\nUsers: {User.objects.count()}")
    for user in User.objects.all():
        print(f"User: {user.email} (ID: {user.id})")
        
        # 2. Check Licenses for this user
        licenses = AIReceptionistLicense.objects.filter(user=user)
        print(f"  Licenses: {licenses.count()}")
        for lic in licenses:
            print(f"    License ID: {lic.id}")
            
            # 3. Check Agents for this license
            agents = AIReceptionistAgent.objects.filter(license=lic)
            print(f"    Agents: {agents.count()}")
            for agent in agents:
                print(f"      - Name: {agent.agent_name}, Phone: {agent.phone_number}, ID: {agent.agent_id}")

        # 4. Check AIReceptionist (Frontend Config)
        receptions = AIReceptionist.objects.filter(user=user)
        print(f"  Receptionists: {receptions.count()}")
        for rec in receptions:
            print(f"    - Title: {rec.title}")
            print(f"      Inbound Phone: {rec.inbound_phone}")
            print(f"      Inbound Agent: {rec.inbound_agent}")
            print(f"      Option: {rec.option}")
            
    print("\n--- All AIReceptionists ---")
    for rec in AIReceptionist.objects.all():
        print(f"Title: {rec.title}, User: {rec.user.email}, Phone: {rec.inbound_phone}, Agent: {rec.inbound_agent}")
            
        # 5. Check Pitches
        pitches = BdrPitch.objects.filter(user=user)
        print(f"  Pitches: {pitches.count()}")
        for p in pitches:
            print(f"    - {p.title}")

if __name__ == '__main__':
    debug_data()

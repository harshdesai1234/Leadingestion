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

from admin_dashboard.models_ai_receptionist import AIReceptionistAgent, AIReceptionistLicense
from django.contrib.auth import get_user_model

User = get_user_model()

def update_data():
    # 1. Update/Create Callista Agent
    agent_id = "d8da14d0-b250-4dda-b18a-2abbfd38f812"
    phone_number = "+912269976710"
    agent_name = "Callista"

    # Find a license to attach to if we need to create
    # Try finding an existing agent first
    agent = AIReceptionistAgent.objects.filter(agent_id=agent_id).first()
    
    if agent:
        print(f"Found existing agent: {agent}")
        agent.phone_number = phone_number
        agent.agent_name = agent_name
        agent.save()
        print(f"Updated agent {agent_name} with phone {phone_number}")
    else:
        print(f"Agent {agent_name} not found. Creating...")
        # Need a license. usage 'amogh' from path suggests user might be 'amogh'
        # Let's try to find a license for any user
        license = AIReceptionistLicense.objects.first()
        if not license:
            print("No AIReceptionistLicense found. Creating one for first user.")
            user = User.objects.first()
            if user:
                # Check if license exists for user before creating (OneToOneField constraint)
                license = AIReceptionistLicense.objects.filter(user=user).first()
                if not license:
                    license = AIReceptionistLicense.objects.create(
                        user=user,
                        total_minutes=100,
                        expiry_date='2025-12-31',
                        api_key='placeholder',
                        api_base_url='https://api.vapi.ai'
                    )
            else:
                print("No users found! Cannot create license.")
                return

        agent = AIReceptionistAgent.objects.create(
            license=license,
            agent_id=agent_id,
            agent_name=agent_name,
            phone_number=phone_number,
            agent_system_message="You are Callista, a helpful receptionist.",
            agent_transfer_prompt="Transferring call now."
        )
        print(f"Created agent {agent_name} with phone {phone_number} on license {license}")

if __name__ == '__main__':
    update_data()

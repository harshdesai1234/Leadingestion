import os
import django
import sys

# Add project root to path
sys.path.append(r'C:\Techproject\Agentyne\agentynebdr\agentyne_asoc_27feb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asoc_core.settings')
django.setup()

from dashboard.api_utils import calculate_task_metrics, get_recent_calls
from dashboard.models import CallRecord
from tasks.models import Task
from django.contrib.auth.models import User
from django.utils import timezone

def verify():
    print("Verifying refined data fetching...")
    # Get a user
    user = User.objects.first()
    if not user:
        print("No users found in database.")
        return
        
    print(f"Testing for User: {user.username} (ID: {user.id})")
    
    # CASE 1: Org user IDs provided (working case)
    org_user_ids = [user.id]
    print("\n--- CASE 1: Org User IDs provided ---")
    metrics = calculate_task_metrics(user=user, org_user_ids=org_user_ids)
    print(f"Task Metrics Counts: active={metrics['active_count']}, overdue={metrics['overdue']}")
    print(f"Due Tasks List Count: {len(metrics['due_tasks_list'])}")
    
    recent_calls = get_recent_calls(user=user, org_user_ids=org_user_ids)
    print(f"Recent Calls Count: {len(recent_calls)}")

    # CASE 2: No Org IDs, fallback to User
    print("\n--- CASE 2: No Org IDs, fallback to User ---")
    metrics_fallback = calculate_task_metrics(user=user, org_user_ids=None)
    print(f"Task Metrics (Fallback): active={metrics_fallback['active_count']}")
    print(f"Due Tasks List Count (Fallback): {len(metrics_fallback['due_tasks_list'])}")
    
    recent_calls_fallback = get_recent_calls(user=user, org_user_ids=None)
    print(f"Recent Calls Count (Fallback): {len(recent_calls_fallback)}")

if __name__ == "__main__":
    verify()

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import random
import string
from .models import UserProfile
from admin_dashboard.models import Coupon
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from datetime import datetime
from payment.models import Payment
from accounts.models import Plan
from django.utils import timezone
def appsumo_signup_page(request):
    """
    Render the AppSumo signup page
    """
    return render(request, 'account/appsumo_signup.html')

@require_POST
@csrf_exempt
def check_email(request):
    """
    Check if an email already exists in the system
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Email is required'
            }, status=400)
        
        # Check if email exists
        exists = User.objects.filter(email=email).exists()
        
        return JsonResponse({
            'success': True,
            'exists': exists,
            'message': 'User already exists' if exists else 'Email is available'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@require_POST
@csrf_exempt 
def send_verification(request):
    """
    Send verification code to email
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Email is required'
            }, status=400)
        
        # Generate verification code
        verification_code = ''.join(random.choices(string.digits, k=6))
        
        # Store in session
        request.session['appsumo_email'] = email
        request.session['appsumo_verification_code'] = verification_code
        
        # Send email
        subject = 'Verify Your Email - Agentyne AppSumo Signup'
        
        # Get current timestamp
        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        try:
            username = email.split('@')[0]
        except:
            username = 'user'
        context = {
            'user': {"username": username},
            'verification_code': verification_code,
            'timestamp': timestamp
        }
        
        html_message = render_to_string('email/email_verification_code.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=html_message,
            fail_silently=False
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Verification code sent successfully',
            # 'verification_code': verification_code  # Remove in production
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@require_POST
def verify_code(request):
    """
    Verify the email verification code
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')
        verification_code = data.get('verification_code')
        
        if not email or not verification_code:
            return JsonResponse({
                'success': False,
                'message': 'Email and verification code are required'
            }, status=400)
        
        # Get stored values from session
        stored_email = request.session.get('appsumo_email')
        stored_code = request.session.get('appsumo_verification_code')
        
        if email != stored_email:
            return JsonResponse({
                'success': False,
                'message': 'Email mismatch'
            })
        
        if verification_code != stored_code:
            return JsonResponse({
                'success': False,
                'message': 'Invalid verification code'
            })
        
        # Code is valid
        request.session['appsumo_email_verified'] = True
        
        return JsonResponse({
            'success': True,
            'message': 'Email verified successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@require_POST
def register_user(request):
    """
    Register a new AppSumo user
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        password1 = data.get('password1')
        password2 = data.get('password2')
        coupon_code = data.get('coupon_code')
        
        # Validate required fields
        if not all([email, first_name, last_name, password1, password2, coupon_code]):
            return JsonResponse({
                'success': False,
                'message': 'All fields are required',
                'errors': {
                    'form': 'All fields are required'
                }
            }, status=400)
        
        # Check if email was verified in the session
        stored_email = request.session.get('appsumo_email')
        email_verified = request.session.get('appsumo_email_verified', False)
        
        if email != stored_email or not email_verified:
            return JsonResponse({
                'success': False,
                'message': 'Email verification required',
                'errors': {
                    'email': 'Please verify your email first'
                }
            })
        
        # Validate passwords match
        if password1 != password2:
            return JsonResponse({
                'success': False,
                'message': 'Passwords do not match',
                'errors': {
                    'password': 'Passwords do not match'
                }
            })
        
        # Validate coupon code
        try:
            coupon = Coupon.objects.get(coupon_code=coupon_code)
            if coupon.used:
                return JsonResponse({
                    'success': False,
                    'message': 'Coupon code has already been used',
                    'errors': {
                        'coupon_code': 'This coupon code has already been used'
                    }
                }, status=400)
        except Coupon.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid coupon code',
                'errors': {
                    'coupon_code': 'Invalid coupon code'
                }
            }, status=404)
        
        # Check if user already exists
        # if User.objects.filter(email=email).exists():
        #     return JsonResponse({
        #         'success': False,
        #         'message': 'User with this email already exists',
        #         'errors': {
        #             'email': 'User with this email already exists'
        #         }
        #     }, status=400)
        
        # Create user
        username = email.split('@')[0] + str(random.randint(1000, 9999))
        # Check if user with this email exists
        user, created = User.objects.update_or_create(
            email=email,  # lookup field
            defaults={
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'is_superuser': False,
            }
        )
        # If you're setting/changing the password
        user.set_password(password1)
        user.save()
        
        # Create or update user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.email_verified = True
        profile.org_name = 'appsumo'
        profile.save()
        
        # Mark coupon as used
        coupon.used = True
        coupon.associated_user_id = user
        coupon.save()

        # Create payment
        # Payment.objects.create(
        #     user=user,
        #     plan_type=Plan.objects.get(service_name='transcription', plan_type='PRO'),
        #     billing_cycle='YEARLY',
        #     payment_status='completed',
        #     validity_till=timezone.now() + timezone.timedelta(days=365)
        # )
        # Get the plan
        plan = Plan.objects.filter(
            service_name = 'transcription',
            plan_type="PRO",
            billing_cycle='YEARLY'
        ).first()

        total_credit = plan.minutes_included * 60

        Payment.objects.create(
            user=user,
            product_name='transcription',
            plan_type="PRO",
            subscribed_product='transcription',
            amount=0,
            stripe_payment_id=None,
            validity_till=timezone.now() + timezone.timedelta(days=365),
            payment_status="completed",
            credits=total_credit,
            billing_cycle='YEARLY',
            amount_in_cent= 0,
            payment_type='appsumo'
        )
        
        # Clean up session
        if 'appsumo_email' in request.session:
            del request.session['appsumo_email']
        if 'appsumo_email_verified' in request.session:
            del request.session['appsumo_email_verified']
        
        # Log the user in
        # login(request, user)
        
        return JsonResponse({
            'success': True,
            'message': 'User Created Successfully, login to use the service',
            'redirect_url': '/accounts/login/',
            'show_success': True
        }, status=200)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e),
            'errors': {
                'form': str(e)
            }
        }, status=500)

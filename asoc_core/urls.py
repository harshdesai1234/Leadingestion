"""
URL configuration for asoc_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as accounts_views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Custom signup request flow (overrides allauth signup)
    path('accounts/signup/', accounts_views.signup_request, name='account_signup'),
    
    # Django Allauth authentication URLs
    path('accounts/', include('allauth.urls')),
    
    # Supporting Apps
    path('accounts/', include('accounts.urls')),

    # Proposal Builder
    path('proposals/', include('proposals.urls', namespace='proposals')),
    path('', include('proposals.urls', namespace='proposals_home')), # Redirect root to proposals

    # Lead Ingestion Module
    path('', include('lead_ingestion.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

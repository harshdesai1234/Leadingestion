# Agentyne ASOC - All-in-One Sales & Operations Center

## Overview

Agentyne ASOC is a comprehensive platform that integrates:
- **CRM** - Customer Relationship Management
- **AI BDR** - AI-powered Business Development Representative
- **AI Receptionist** - Intelligent inbound call handling
- **Analytics** - Sales funnel and performance tracking
- **Payment Processing** - Stripe integration

## Project Structure

```
agentyne_asoc/
├── asoc_core/              # Django project settings
├── apps/                   # All Django apps
│   ├── accounts/          # User authentication & profiles
│   ├── crm/               # CRM core (leads, deals, contacts)
│   ├── ai_bdr/            # AI BDR campaigns & calls
│   ├── ai_receptionist/   # AI Receptionist features
│   ├── payment/           # Stripe payment processing
│   ├── admin_dashboard/   # Admin features
│   ├── transcription/     # Call transcription
│   ├── analytics/         # Reports & analytics
│   ├── tasks/             # Task management
│   └── common/            # Shared utilities
├── static/                # Static files (CSS, JS, images)
├── templates/             # HTML templates
├── media/                 # User uploaded files
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
└── .env.example          # Environment variables template
```

## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- Virtual environment (already created at `C:\Techproject\Agentyne\agentynebdr\agentynevenv`)
- SQLite (for development) or PostgreSQL (for production)
- Redis (for Celery tasks)

### 2. Activate Virtual Environment

```bash
C:\Techproject\Agentyne\agentynebdr\agentynevenv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and update with your credentials:

```bash
copy .env.example .env
```

Edit `.env` and add your API keys and credentials.

### 5. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver
```

Visit: http://localhost:8000

## Implementation Phases

### ✅ Phase 1: Project Setup (Week 1) - COMPLETED
- [x] Create project directory
- [x] Set up Git repository
- [x] Create virtual environment
- [x] Install base dependencies
- [x] Create Django project
- [x] Create apps directory structure
- [x] Set up .env file

### 📋 Phase 2: Copy Existing Code (Week 1-2)
- [ ] Copy user_dashboard apps
- [ ] Copy django-crm apps
- [ ] Adapt templates with Agentyne branding

### 📋 Phase 3: CRM Integration (Week 2-3)
- [ ] Create CRM models
- [ ] Create CRM views
- [ ] Create integration layer
- [ ] Connect AI BDR to CRM
- [ ] Connect AI Receptionist to CRM

### 📋 Phase 4: Unified Dashboard (Week 4)
- [ ] Create unified navigation
- [ ] Create unified dashboard view
- [ ] Update URL configuration

### 📋 Phase 5: Data Migration (Week 5)
- [ ] Export existing data
- [ ] Import to new system
- [ ] Verify data integrity

### 📋 Phase 6: Testing (Week 6)
- [ ] Unit tests
- [ ] Integration tests
- [ ] End-to-end tests
- [ ] Performance tests

### 📋 Phase 7: Deployment (Week 7)
- [ ] Staging deployment
- [ ] Production deployment
- [ ] Monitoring setup

## Key Features

### CRM Module
- Lead management with multiple sources (AI BDR, AI Receptionist, Web Forms, API)
- Deal/Opportunity tracking
- Contact & Company management
- Sales funnel visualization

### AI BDR Module
- Outbound call campaigns
- AI-powered conversations
- Automatic lead creation in CRM
- Call analytics and metrics

### AI Receptionist Module
- Inbound call handling
- Intelligent routing
- Follow-up management
- CRM integration

### Analytics Module
- Sales funnel reports
- Income summaries
- Campaign performance
- Call metrics

## Technology Stack

- **Backend**: Django 5.1.7
- **API**: Django REST Framework
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Task Queue**: Celery + Redis
- **Payment**: Stripe
- **AI Services**: OpenAI, Deepgram
- **Authentication**: Django Allauth

## Development Guidelines

1. Follow Django best practices
2. Use apps for modular organization
3. Keep business logic in models/services
4. Use class-based views where appropriate
5. Write tests for critical functionality
6. Document API endpoints
7. Use environment variables for secrets

## API Endpoints

```
/api/v1/crm/leads/              # Lead management
/api/v1/crm/deals/              # Deal management
/api/v1/crm/contacts/           # Contact management
/api/v1/ai-bdr/campaigns/       # BDR campaigns
/api/v1/ai-bdr/calls/           # BDR calls
/api/v1/ai-receptionist/calls/  # Receptionist calls
/api/v1/analytics/reports/      # Analytics reports
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Submit a pull request

## Support

For issues and questions, contact the development team.

## License

Proprietary - Agentyne Inc.

---

**Version**: 1.0.0  
**Last Updated**: February 11, 2026  
**Status**: Day 1 Setup Complete ✅

# ADIM Meta Platform API Documentation

## Overview

This is the **Meta Platform** for ADIM - the central authentication and workspace provisioning system. It manages user accounts, workspace instances, and OTP-based discovery. The API is implemented with FastAPI in `meta_platform/` and mirrors the endpoints described below.

## Architecture

Based on the specifications in `deploy-pipeline.txt`, this platform provides:

1. **User Management** - Meta platform users who own workspaces
2. **Workspace Management** - Create and manage workspace instances
3. **OTP System** - One-Time Passwords for client apps to discover workspaces
4. **Provisioning** - Automated deployment to DigitalOcean or bare metal

## API Endpoints

### Authentication

#### Register New User
```http
POST /api/auth/users/register/
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!"
}
```

**Response:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "johndoe",
    "subscription_tier": "free",
    "max_workspaces": 1,
    "workspace_count": 0,
    "can_create_workspace": true,
    "email_verified": false
  }
}
```

#### Get Current User
```http
GET /api/auth/users/me/
Authorization: Session / Basic Auth
```

### Workspaces

#### List User's Workspaces
```http
GET /api/workspaces/
Authorization: Session / Basic Auth
```

**Response:**
```json
[
  {
    "id": 1,
    "workspace_id": "ws7x2k4",
    "name": "My Workspace",
    "owner": 1,
    "owner_email": "user@example.com",
    "deployment_type": "cloud",
    "status": "active",
    "instance_url": "https://ws7x2k4.adim.ai",
    "tailscale_url": "",
    "ip_address": "192.0.2.1",
    "vcpu": 2,
    "ram_gb": 4,
    "storage_gb": 50,
    "monthly_cost": "24.00",
    "created_at": "2025-11-15T10:00:00Z",
    "port_allocation": {
      "daphne": 8420,
      "redis": 6799,
      "qdrant_http": 6753,
      "qdrant_grpc": 6754,
      "neo4j": 8107
    }
  }
]
```

#### Create New Workspace
```http
POST /api/workspaces/
Authorization: Session / Basic Auth
Content-Type: application/json

{
  "name": "Production Workspace",
  "deployment_type": "cloud",
  "region": "nyc3",
  "vcpu": 2,
  "ram_gb": 4,
  "storage_gb": 50
}
```

**Response:**
```json
{
  "id": 2,
  "workspace_id": "ws3a9f1",
  "name": "Production Workspace",
  "deployment_type": "cloud",
  "status": "provisioning",
  ...
}
```

#### Get Workspace Details
```http
GET /api/workspaces/{id}/
Authorization: Session / Basic Auth
```

#### Generate OTP for Workspace
```http
POST /api/workspaces/{id}/generate_otp/
Authorization: Session / Basic Auth
```

**Response:**
```json
{
  "id": 5,
  "workspace": 2,
  "workspace_id": "ws3a9f1",
  "workspace_name": "Production Workspace",
  "otp_code": "A7F2D8",
  "created_at": "2025-11-15T10:30:00Z",
  "expires_at": "2025-11-16T10:30:00Z",
  "is_active": true,
  "is_valid": true,
  "max_uses": 0
}
```

#### Get Workspace OTPs
```http
GET /api/workspaces/{id}/otps/
Authorization: Session / Basic Auth
```

#### Get Provisioning Logs
```http
GET /api/workspaces/{id}/logs/
Authorization: Session / Basic Auth
```

### OTP Validation (Public Endpoint)

This is the **KEY ENDPOINT** that client apps use to discover workspaces.

#### Validate OTP
```http
POST /api/otps/validate/
Content-Type: application/json

{
  "otp": "A7F2D8"
}
```

**Response:**
```json
{
  "workspace_id": "ws3a9f1",
  "name": "Production Workspace",
  "otp": "A7F2D8",
  "endpoints": {
    "cloud": "https://ws3a9f1.adim.ai",
    "tailscale": "https://ws3a9f1.tail-scale.ts.net",
    "ip": "192.0.2.5"
  },
  "status": "active",
  "subscription": "pro",
  "created_at": "2025-11-15T10:00:00Z",
  "features": {
    "rag_enabled": true,
    "max_users": 10
  }
}
```

**Error Response (Invalid OTP):**
```json
{
  "error": "OTP is invalid or has expired"
}
```

## Database Models

### MetaUser
- Custom user model extending Django's AbstractUser
- Fields: email (unique), subscription_tier, max_workspaces
- Manages workspace ownership limits

### Workspace
- Represents a deployed ADIM instance
- Tracks deployment type (cloud/bare_metal), status, endpoints
- Auto-generates unique workspace_id on creation
- Calculates port allocations for isolated services

### WorkspaceOTP
- One-Time Passwords for workspace discovery
- Auto-expires after 24 hours
- Tracks usage count and IP addresses
- Can be single-use or unlimited

### ProvisioningLog
- Audit trail for workspace provisioning
- Tracks all deployment steps and errors

## Running the Platform

### With Docker (Recommended)
```bash
# Start services
docker compose up -d

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Access admin
http://localhost:8000/admin/
```

### Local Development
```bash
# Start database services
docker compose up -d db redis

# Activate virtualenv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install psycopg[binary] django-redis qdrant-client djangorestframework

# Run migrations
POSTGRES_HOST=localhost python manage.py migrate

# Run dev server
POSTGRES_HOST=localhost python manage.py runserver
```

## Next Steps (Not Yet Implemented)

Based on `deploy-pipeline.txt`, the following features are planned:

1. **Digital Ocean Integration** (`provisioning/digital_ocean.py`)
   - Automated droplet provisioning via DO API
   - DNS configuration
   - Firewall rules

2. **Ansible Playbooks** (`ansible/deploy_workspace.yml`)
   - Full stack deployment automation
   - Service configuration templates
   - SSL certificate generation

3. **Bare Metal Registration** (`provisioning/bare_metal.py`)
   - Self-hosted instance registration
   - Migration tools (cloud → bare metal)

4. **Billing Integration**
   - Stripe/payment processing
   - Subscription tier management
   - Usage tracking

5. **Email Notifications**
   - Welcome emails with OTPs
   - Provisioning status updates
   - Subscription notifications

## Testing the API

### Using cURL

**Register a user:**
```bash
curl -X POST http://localhost:8000/api/auth/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!"
  }'
```

**Create a workspace (after login):**
```bash
curl -X POST http://localhost:8000/api/workspaces/ \
  -H "Content-Type: application/json" \
  -u test@example.com:SecurePass123! \
  -d '{
    "name": "Test Workspace",
    "deployment_type": "cloud",
    "region": "nyc3"
  }'
```

**Validate an OTP:**
```bash
curl -X POST http://localhost:8000/api/otps/validate/ \
  -H "Content-Type: application/json" \
  -d '{"otp": "A7F2D8"}'
```

## Security Notes

- All endpoints except `/api/otps/validate/` require authentication
- OTPs expire after 24 hours by default
- Workspace access is restricted to owners only
- Admin interface available at `/admin/` for superusers
- Production deployment should use HTTPS and proper SECRET_KEY

## File Structure

```
AdimScalability/
├── meta_auth/          # User authentication & management
│   ├── models.py       # MetaUser model
│   ├── views.py        # Registration, user profile
│   ├── serializers.py  # User serializers
│   └── admin.py        # Admin configuration
│
├── workspaces/         # Workspace management
│   ├── models.py       # Workspace, WorkspaceOTP, ProvisioningLog
│   ├── views.py        # CRUD operations, OTP validation
│   ├── serializers.py  # Workspace serializers
│   └── admin.py        # Admin configuration
│
├── provisioning/       # Deployment automation (future)
│
└── project/            # Django project settings
    ├── settings.py     # Configuration
    └── urls.py         # URL routing
```

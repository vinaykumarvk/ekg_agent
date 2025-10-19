# Secrets Management Guide

## Overview

The EKG Agent requires an OpenAI API key to function. This guide covers different ways to provide secrets depending on your environment.

## ✅ Option 1: `.env` File (Local Development - RECOMMENDED)

**Best for:** Local development, testing

### Setup:

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your actual key:
   ```bash
   # .env
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
   MODEL_DEFAULT=gpt-4o
   ```

3. The server will automatically load it:
   ```bash
   ./run_server.sh
   # or
   uvicorn api.main:app --reload
   ```

**How it works:** The `pydantic-settings` library automatically loads `.env` files thanks to this configuration in `api/settings.py`:

```python
class Settings(BaseSettings):
    OPENAI_API_KEY: str
    MODEL_DEFAULT: str = "gpt-4o"
    
    class Config:
        env_file = ".env"  # ← Automatically loads .env
```

**Security:** 
- ✅ `.env` is in `.gitignore` (never committed)
- ✅ `.env.example` provides a template (safe to commit)

---

## Option 2: Environment Variables (CI/CD, Production)

**Best for:** Docker, Kubernetes, CI/CD pipelines, production servers

### Setup:

```bash
# Set in your shell
export OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
export MODEL_DEFAULT=gpt-4o

# Run the server
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Docker Example:

```bash
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx \
  -e MODEL_DEFAULT=gpt-4o \
  -v $(pwd)/data:/app/data \
  ekg-agent
```

### Docker Compose:

```yaml
version: '3.8'
services:
  ekg-agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MODEL_DEFAULT=gpt-4o
    volumes:
      - ./data:/app/data
```

Then run with:
```bash
export OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
docker-compose up
```

---

## Option 3: Cloud Secret Managers (Production)

**Best for:** Production deployments on AWS, GCP, Azure

### Google Cloud Secret Manager

1. **Store the secret:**
   ```bash
   echo -n "sk-proj-xxxxxxxxxxxxxxxxxxxx" | \
     gcloud secrets create openai-api-key --data-file=-
   ```

2. **Update `api/settings.py`** to fetch from Secret Manager:
   ```python
   from google.cloud import secretmanager
   import os
   
   def get_secret(secret_id: str) -> str:
       """Fetch secret from Google Secret Manager"""
       if os.getenv("ENV") == "local":
           return os.getenv(secret_id, "")
       
       client = secretmanager.SecretManagerServiceClient()
       project_id = os.getenv("GCP_PROJECT_ID")
       name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
       response = client.access_secret_version(request={"name": name})
       return response.payload.data.decode("UTF-8")
   
   class Settings(BaseSettings):
       OPENAI_API_KEY: str = ""
       MODEL_DEFAULT: str = "gpt-4o"
       
       def __init__(self, **kwargs):
           super().__init__(**kwargs)
           if not self.OPENAI_API_KEY:
               self.OPENAI_API_KEY = get_secret("openai-api-key")
   ```

3. **Deploy with permissions:**
   ```bash
   gcloud run deploy ekg-agent \
     --image gcr.io/PROJECT/ekg-agent \
     --set-env-vars GCP_PROJECT_ID=your-project-id \
     --service-account ekg-agent@PROJECT.iam.gserviceaccount.com
   ```

### AWS Secrets Manager

```python
import boto3
from botocore.exceptions import ClientError

def get_aws_secret(secret_name: str) -> str:
    """Fetch secret from AWS Secrets Manager"""
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager')
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise Exception(f"Failed to fetch secret: {e}")
```

---

## Option 4: Kubernetes Secrets

**Best for:** Kubernetes deployments

1. **Create a secret:**
   ```bash
   kubectl create secret generic ekg-secrets \
     --from-literal=OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
   ```

2. **Reference in deployment:**
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: ekg-agent
   spec:
     template:
       spec:
         containers:
         - name: ekg-agent
           image: ekg-agent:latest
           env:
           - name: OPENAI_API_KEY
             valueFrom:
               secretKeyRef:
                 name: ekg-secrets
                 key: OPENAI_API_KEY
   ```

---

## Current Implementation

Your `api/settings.py` currently uses **pydantic-settings** which automatically supports:

✅ `.env` files (loaded automatically)  
✅ Environment variables (higher priority than `.env`)  
✅ Easy to extend for cloud secret managers

```python
# api/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str          # Required
    MODEL_DEFAULT: str = "gpt-4o" # Optional with default
    KG_PATH: str = ""             # Optional
    
    class Config:
        env_file = ".env"         # Loads .env automatically
```

**Priority Order:**
1. Environment variables (highest priority)
2. `.env` file
3. Default values in code

---

## Quick Start

**For local development:**

```bash
# Create .env file
cat > .env << 'EOF'
OPENAI_API_KEY=sk-proj-your-key-here
MODEL_DEFAULT=gpt-4o
EOF

# Run server
./run_server.sh
```

**For production:**

```bash
# Set environment variable
export OPENAI_API_KEY=sk-proj-your-key-here

# Run server
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Security Best Practices

1. ✅ **Never commit secrets to git**
   - `.env` is already in `.gitignore`
   - Use `.env.example` for templates

2. ✅ **Rotate keys regularly**
   - OpenAI allows multiple API keys
   - Rotate before sharing code or after exposure

3. ✅ **Use different keys per environment**
   - Development: One key
   - Staging: Different key
   - Production: Separate key

4. ✅ **Restrict key permissions**
   - In OpenAI dashboard, limit key permissions
   - Set usage limits/quotas

5. ✅ **Use secret managers in production**
   - AWS Secrets Manager
   - Google Secret Manager
   - Azure Key Vault
   - HashiCorp Vault

6. ✅ **Monitor usage**
   - Check OpenAI usage dashboard
   - Set up alerts for unusual activity

---

## Troubleshooting

### Error: "OPENAI_API_KEY Field required"

**Solution 1:** Create `.env` file
```bash
echo "OPENAI_API_KEY=sk-your-key" > .env
```

**Solution 2:** Export environment variable
```bash
export OPENAI_API_KEY=sk-your-key
```

**Solution 3:** Pass inline
```bash
OPENAI_API_KEY=sk-your-key uvicorn api.main:app
```

### Verify key is loaded:

```bash
source .venv/bin/activate
python -c "from api.settings import settings; print(f'Key loaded: {settings.OPENAI_API_KEY[:10]}...')"
```

---

## Testing Without Real API Key

For testing the API structure without making OpenAI calls:

```bash
# Use dummy key for local tests
export OPENAI_API_KEY=dummy

# Run tests (uses mocked OpenAI client)
pytest -v
```

**Note:** The `/v1/answer` endpoint will fail with a dummy key, but `/health` will work fine.

---

## Summary

| Environment | Method | Command |
|------------|--------|---------|
| **Local Dev** | `.env` file | `cp .env.example .env` then edit |
| **Docker** | `-e` flag | `docker run -e OPENAI_API_KEY=sk-...` |
| **K8s** | Secrets | `kubectl create secret generic ...` |
| **Cloud** | Secret Manager | See cloud provider sections above |
| **CI/CD** | Env vars | Set in GitHub/GitLab/Jenkins settings |

**Recommendation:** Use `.env` file locally, cloud secret managers in production.




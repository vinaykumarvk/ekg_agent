# Deploying EKG Agent to Google Cloud Run

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **Docker** installed locally (for building)
4. **OpenAI API Key**
5. **Knowledge Graph files** in `data/kg/`

## Quick Deployment (5 Steps)

### Step 1: Set Up Google Cloud Project

```bash
# Set your project ID
export PROJECT_ID=your-gcp-project-id

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com
```

### Step 2: Store OpenAI API Key in Secret Manager

```bash
# Create secret
echo -n "sk-proj-your-openai-api-key" | \
  gcloud secrets create openai-api-key \
  --data-file=- \
  --replication-policy=automatic

# Verify
gcloud secrets describe openai-api-key
```

### Step 3: Build and Push Docker Image

```bash
# Set region
export REGION=us-central1

# Build and push using Cloud Build
gcloud builds submit --tag gcr.io/$PROJECT_ID/ekg-agent

# Or build locally and push
docker build -t gcr.io/$PROJECT_ID/ekg-agent .
docker push gcr.io/$PROJECT_ID/ekg-agent
```

### Step 4: Deploy to Cloud Run

```bash
# Deploy with secret and data
gcloud run deploy ekg-agent \
  --image gcr.io/$PROJECT_ID/ekg-agent \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800 \
  --max-instances 10 \
  --min-instances 0

# Get the service URL
gcloud run services describe ekg-agent --region $REGION --format 'value(status.url)'
```

### Step 5: Test Deployment

```bash
# Get service URL
export SERVICE_URL=$(gcloud run services describe ekg-agent --region $REGION --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Test domains
curl $SERVICE_URL/domains

# Test answer
curl -X POST $SERVICE_URL/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is OTP?",
    "domain": "wealth_management"
  }'
```

## Alternative: One-Command Deployment Script

Create `deploy.sh`:

```bash
#!/bin/bash
set -e

PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
SERVICE_NAME="ekg-agent"

echo "🚀 Deploying EKG Agent to Cloud Run..."

# Build and deploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo "✅ Deployed successfully!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test commands:"
echo "  curl $SERVICE_URL/health"
echo "  curl $SERVICE_URL/domains"
```

## Configuration for Cloud Run

### Environment Variables

Set in Cloud Run deployment:

```bash
# Required
OPENAI_API_KEY=<from Secret Manager>

# Optional
MODEL_DEFAULT=gpt-4o
EKG_EXPORT_DIR=/tmp/outputs
```

### Memory and CPU

Recommended settings:
- **Memory:** 2Gi (for both KGs in cache)
- **CPU:** 2
- **Timeout:** 1800s (30 min for complex queries)
- **Max Instances:** 10 (adjust based on traffic)
- **Min Instances:** 0 (cost-saving) or 1 (low latency)

### Secrets Management

**Using Secret Manager (Recommended):**

```bash
# Deploy with secret reference
gcloud run deploy ekg-agent \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest
```

**Using Environment Variables (Less Secure):**

```bash
gcloud run deploy ekg-agent \
  --set-env-vars OPENAI_API_KEY=sk-proj-xxx
```

## CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [ main ]

env:
  PROJECT_ID: your-gcp-project-id
  SERVICE_NAME: ekg-agent
  REGION: us-central1

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    permissions:
      contents: read
      id-token: write
    
    steps:
      - uses: actions/checkout@v3
      
      - id: auth
        uses: google-github-actions/auth@v1
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER'
          service_account: 'github-actions@PROJECT_ID.iam.gserviceaccount.com'
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
      
      - name: Build and Push
        run: |
          gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy $SERVICE_NAME \
            --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
            --region $REGION \
            --platform managed \
            --allow-unauthenticated \
            --set-secrets OPENAI_API_KEY=openai-api-key:latest \
            --memory 2Gi \
            --cpu 2
      
      - name: Test Deployment
        run: |
          SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
          curl -f $SERVICE_URL/health || exit 1
```

## Authentication Options

### Option 1: Public Access (for testing)
```bash
gcloud run deploy ekg-agent --allow-unauthenticated
```

### Option 2: Authenticated Access (production)
```bash
# Deploy with authentication required
gcloud run deploy ekg-agent --no-allow-unauthenticated

# Grant access to specific service accounts
gcloud run services add-iam-policy-binding ekg-agent \
  --region=$REGION \
  --member="serviceAccount:your-app@project.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Your client app needs to get ID token:
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" $SERVICE_URL/health
```

### Option 3: API Key Authentication (custom)

Add to `api/main.py`:

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.post("/v1/answer", dependencies=[Depends(verify_api_key)])
def answer(req: AskRequest) -> AskResponse:
    # ... existing code
```

## Monitoring and Logging

### View Logs

```bash
# Stream logs
gcloud run services logs tail ekg-agent --region $REGION

# View in console
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ekg-agent" --limit 50
```

### Set Up Monitoring

```bash
# Create uptime check
gcloud monitoring uptime-checks create http \
  --display-name="EKG Agent Health Check" \
  --resource-type=uptime-url \
  --host=$SERVICE_URL \
  --path=/health
```

## Cost Optimization

### Pricing Factors
- CPU/Memory allocation
- Request count
- Request duration
- Minimum instances

### Optimize for Cost
```bash
gcloud run deploy ekg-agent \
  --cpu 1 \                      # Lower CPU
  --memory 1Gi \                 # Lower memory
  --min-instances 0 \            # Scale to zero
  --max-instances 3 \            # Limit max
  --concurrency 80 \             # Handle multiple requests per instance
  --cpu-throttling \             # Throttle CPU when idle
  --execution-environment gen2   # Faster cold starts
```

### Estimated Costs
- **Cold starts:** Free
- **Active time:** ~$0.00002400/second for 2Gi/2CPU
- **Requests:** $0.40 per million requests
- **Typical:** $10-50/month for moderate usage

## Troubleshooting

### Issue: Container fails to start

**Check logs:**
```bash
gcloud run services logs tail ekg-agent --region $REGION
```

**Common issues:**
- Missing `OPENAI_API_KEY` secret
- KG files not included in Docker image
- Port mismatch (Cloud Run uses $PORT, default 8080)

### Issue: Timeout errors

**Increase timeout:**
```bash
gcloud run services update ekg-agent \
  --region $REGION \
  --timeout 1800

If you are deploying via Cloud Build triggers or CI/CD pipelines, make sure the `gcloud run deploy` or `gcloud run services update` command in your pipeline also includes `--timeout 1800`; setting the build step `timeout:` field alone does not change the Cloud Run service timeout.
```

### Issue: Memory errors

**Increase memory:**
```bash
gcloud run services update ekg-agent \
  --region $REGION \
  --memory 4Gi
```

## Next Steps

After deployment:
1. Test all endpoints
2. Set up monitoring/alerting
3. Configure custom domain (optional)
4. Add authentication
5. Integrate with your UI application

See `CLIENT_INTEGRATION.md` for connecting from Python, Replit, or other applications.




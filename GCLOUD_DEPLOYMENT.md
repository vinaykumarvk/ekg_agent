# 🚀 GCloud Deployment Guide

## Prerequisites

1. **Google Cloud SDK** installed and configured
2. **Docker** installed locally
3. **OpenAI API Key** ready

## Quick Deployment

### 1. Set Environment Variables

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="sk-your-actual-key-here"

# Optional: Set other production variables
export CACHE_DIR="/tmp/ekg_cache"
export LOG_LEVEL="INFO"
export MAX_CACHE_SIZE="1000"
export CACHE_TTL="3600"
```

### 2. Build and Deploy

```bash
# Build the Docker image
docker build -t gcr.io/YOUR_PROJECT_ID/ekg-agent .

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT_ID/ekg-agent

# Deploy to Cloud Run
gcloud run deploy ekg-agent \
  --image gcr.io/YOUR_PROJECT_ID/ekg-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars "OPENAI_API_KEY=$OPENAI_API_KEY,CACHE_DIR=/tmp/ekg_cache,LOG_LEVEL=INFO"
```

### 3. Verify Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe ekg-agent --region=us-central1 --format="value(status.url)")

# Test health endpoint
curl $SERVICE_URL/health

# Test the API
curl -X POST $SERVICE_URL/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is OTP?",
    "domain": "wealth_management"
  }'
```

## Production Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | Required | Your OpenAI API key |
| `CACHE_DIR` | `/tmp/ekg_cache` | Cache directory |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_CACHE_SIZE` | `1000` | Maximum cache size |
| `CACHE_TTL` | `3600` | Cache TTL in seconds |

### Cloud Run Settings

- **Memory**: 2Gi (recommended for deep mode)
- **CPU**: 2 (for better performance)
- **Timeout**: 300s (5 minutes for deep mode)
- **Max Instances**: 10 (adjust based on usage)
- **Min Instances**: 0 (scale to zero when idle)

## Monitoring

### View Logs

```bash
# Stream logs
gcloud run services logs tail ekg-agent --region us-central1

# View recent logs
gcloud run services logs read ekg-agent --region us-central1 --limit 50
```

### Health Checks

```bash
# Check service health
curl $SERVICE_URL/health

# Check metrics
curl $SERVICE_URL/metrics
```

## Cost Optimization

### For Testing Phase

```bash
# Lower resource allocation for testing
gcloud run deploy ekg-agent \
  --image gcr.io/YOUR_PROJECT_ID/ekg-agent \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 3 \
  --min-instances 0
```

### Production Settings

```bash
# Higher resources for production
gcloud run deploy ekg-agent \
  --image gcr.io/YOUR_PROJECT_ID/ekg-agent \
  --memory 4Gi \
  --cpu 4 \
  --max-instances 20 \
  --min-instances 1
```

## Troubleshooting

### Common Issues

1. **Container fails to start**
   - Check logs: `gcloud run services logs tail ekg-agent --region us-central1`
   - Verify environment variables are set correctly

2. **Timeout errors**
   - Deep mode can take up to 5 minutes
   - Ensure timeout is set to 300s or higher

3. **Memory issues**
   - Increase memory allocation
   - Check cache size limits

### Debug Commands

```bash
# Check service status
gcloud run services describe ekg-agent --region us-central1

# View detailed logs
gcloud run services logs read ekg-agent --region us-central1 --limit 100

# Test locally
docker run -p 8080:8080 -e OPENAI_API_KEY=$OPENAI_API_KEY gcr.io/YOUR_PROJECT_ID/ekg-agent
```

## Security Notes

⚠️ **For Testing Phase Only**: The current configuration allows unauthenticated access. For production, implement proper authentication.

## Next Steps

1. Deploy to GCloud using the commands above
2. Test all endpoints
3. Monitor performance and costs
4. Implement authentication when ready for production use

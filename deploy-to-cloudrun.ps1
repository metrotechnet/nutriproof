# PowerShell script to deploy to Google Cloud Run

# Set variables
$PROJECT_ID = "nutriproof"
$SERVICE_NAME = "nutriproof-dev"
$REGION = "us-east4" # e.g. us-central1
$IMAGE = "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"



# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME `
  --image $IMAGE `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --project $PROJECT_ID

Write-Host "Deployment to Cloud Run complete."

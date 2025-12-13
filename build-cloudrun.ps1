# PowerShell build script for Google Cloud Build

# Set variables
$PROJECT_ID = "nutriproof"
$SERVICE_NAME = "nutriproof-dev"
$REGION = "us-east4"
$IMAGE_NAME = "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

Write-Host "Project: $PROJECT_ID"
Write-Host "Image: $IMAGE_NAME"

# Validate project structure
if (!(Test-Path "Dockerfile")) {
    Write-Host "ERROR: Dockerfile not found!"
    exit 1
}
if (!(Test-Path "requirements.txt")) {
    Write-Host "ERROR: requirements.txt not found!"
    exit 1
}
if (!(Test-Path "app.py")) {
    Write-Host "ERROR: app.py not found!"
    exit 1
}

# Set GCP project
Write-Host "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to set GCP project"
    exit 1
}

# Enable required APIs
Write-Host "Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com containerregistry.googleapis.com run.googleapis.com --project=$PROJECT_ID --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to enable APIs"
    exit 1
}

# Get project number
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
if (-not $PROJECT_NUMBER) {
    Write-Host "ERROR: Failed to get project number"
    exit 1
}

# Grant IAM roles to Cloud Build service account
Write-Host "Granting IAM roles to Cloud Build service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" --role="roles/run.admin" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to add run.admin role"
    exit 1
}
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" --role="roles/iam.serviceAccountUser" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to add serviceAccountUser role"
    exit 1
}

# Build with Google Cloud Build
Write-Host "Building with Google Cloud Build..."
gcloud builds submit --tag $IMAGE_NAME --timeout=20m --machine-type=e2-highcpu-8 --project=$PROJECT_ID
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cloud Build failed!"
    Write-Host "Troubleshooting steps:"
    Write-Host "1. Check if you have Cloud Build API enabled"
    Write-Host "2. Verify IAM permissions (Cloud Build Editor role)"
    Write-Host "3. Check if billing is enabled for the project"
    Write-Host "4. Try: gcloud auth login --update-adc"
    exit 1
}

Write-Host "Build completed successfully!"
Write-Host "Docker image ready: $IMAGE_NAME"
Write-Host "Next step: Run deploy-to-cloudrun.ps1 to deploy to Cloud Run"

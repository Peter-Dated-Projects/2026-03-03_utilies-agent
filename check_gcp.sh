#!/bin/bash

echo "--- GCP Cost & Free Tier Investigation ---"

# 1. Identity & Project
echo "Active Account:"
gcloud auth list --filter=status:ACTIVE --format="value(account)"

echo -e "\nProject ID:"
gcloud config get-value project

# 2. Free Tier & Spot Audit
echo -e "\n--- Free Tier & Spot Audit ---"
INSTANCE_NAME=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name 2>/dev/null)

if [ -n "$INSTANCE_NAME" ]; then
    ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{print $NF}')
    MACHINE_TYPE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/machine-type | awk -F/ '{print $NF}')
    IS_SPOT=$(gcloud compute instances describe "$INSTANCE_NAME" --format="value(scheduling.provisioningModel)")
    
    echo "Instance: $INSTANCE_NAME ($MACHINE_TYPE)"
    echo "Region/Zone: $ZONE"
    
    # Check for Free Tier Region eligibility
    if [[ "$ZONE" =~ ^(us-west1|us-central1|us-east1) ]]; then
        echo "✅ Region: ELIGIBLE for Free Tier (us-west1, us-central1, us-east1)"
    else
        echo "⚠️ Region: NOT ELIGIBLE for Free Tier (Switch to us-central1 for $0 cost)"
    fi

    # Check for Machine Type eligibility
    if [ "$MACHINE_TYPE" == "e2-micro" ]; then
        echo "✅ Machine: ELIGIBLE for Free Tier (e2-micro)"
    else
        echo "⚠️ Machine: NOT ELIGIBLE (Switch to e2-micro)"
    fi

    echo "Provisioning: $IS_SPOT (Spot is cheapest if Free Tier limit is exceeded)"
else
    echo "Metadata check failed: Run this script inside your VM."
fi

# 3. Environment Readiness
echo -e "\n--- Bot Environment Readiness ---"
command -v python3 &>/dev/null && echo "Python3: Installed" || echo "Python3: MISSING"
[ -d "$HOME/.cache/ms-playwright" ] && echo "Playwright Browsers: Found" || echo "Playwright Browsers: MISSING"

# 4. The "$0/Month" Checklist
echo -e "\n--- The \$0/Month Strategy (Free Tier Constraints) ---"
echo "1. Region: Must be us-west1, us-central1, or us-east1."
echo "2. Machine: Must be e2-micro (2 vCPUs, 1 GB RAM)."
echo "3. Disk: Use 'Standard Persistent Disk' (not SSD). Max 30GB total for the project."
echo "4. External IP: Use an 'Ephemeral' IP. Static IPs cost money if the VM is off."
echo "5. Egress: 1 GB network egress per month (Perfect for small PDF transfers)."
echo "6. Snapshots: Delete all snapshots; they are not part of the free disk allowance."

echo -e "\n--- End of Investigation ---"
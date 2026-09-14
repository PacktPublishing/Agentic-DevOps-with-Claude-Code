#!/usr/bin/env bash
# ABOUTME: Ordered teardown. Releases the load balancers and volumes the cluster owns, then destroys.
# ABOUTME: `terraform destroy` alone either hangs on network interfaces or leaks billing resources.
#
# In-cluster controllers create AWS resources Terraform does not know about: the AWS Load
# Balancer Controller creates load balancers, and the EBS CSI driver creates volumes. Destroying
# the VPC underneath them either blocks on their network interfaces or completes and leaves them
# billing. So: delete the workloads, wait for AWS to release what they held, then destroy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVISION_DIR="${REPO_ROOT}/provision"
TAG_KEY="Workshop"
TAG_VALUE="packt"

REGION="$(terraform -chdir="${PROVISION_DIR}" output -raw region 2>/dev/null || echo "${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}")"

echo "Teardown, region ${REGION}."
echo

# --- 1. Applications, so finalizers prune the workloads holding load balancers ---------------
if kubectl version >/dev/null 2>&1; then
    echo "[1/5] Deleting ArgoCD Applications and waiting for pruning..."
    kubectl delete applications -n argocd --all --ignore-not-found --timeout=10m || true

    echo "[2/5] Deleting PersistentVolumeClaims so the CSI driver releases its volumes..."
    kubectl delete pvc --all --all-namespaces --ignore-not-found --timeout=10m || true

    echo "      Waiting up to 5 minutes for load balancers to be released..."
    for i in $(seq 1 30); do
        count="$(aws elbv2 describe-load-balancers --region "${REGION}" \
            --query 'length(LoadBalancers)' --output text 2>/dev/null || echo 0)"
        if [ "${count}" = "0" ]; then echo "      released."; break; fi
        printf '      still %s load balancer(s), %ds elapsed\r' "${count}" "$((i * 10))"
        sleep 10
    done
    echo
else
    echo "[1/5] kubectl cannot reach the cluster; skipping Application and PVC cleanup."
    echo "[2/5] skipped."
    echo "      If the cluster was already gone this is fine. The tag sweep at the end still runs."
fi

# --- 3. Confirm no volumes are left detached --------------------------------------------------
echo "[3/5] Checking for volumes the CSI driver left behind..."
orphan_vols="$(aws ec2 describe-volumes --region "${REGION}" \
    --filters "Name=tag:${TAG_KEY},Values=${TAG_VALUE}" "Name=status,Values=available" \
    --query 'Volumes[].VolumeId' --output text 2>/dev/null || true)"
if [ -n "${orphan_vols}" ]; then
    echo "      detached volumes still tagged ${TAG_KEY}=${TAG_VALUE}: ${orphan_vols}"
    echo "      they are reported, not deleted. Remove them yourself once you are sure."
else
    echo "      none."
fi

# --- 4. Destroy -------------------------------------------------------------------------------
echo "[4/5] terraform destroy..."
terraform -chdir="${PROVISION_DIR}" destroy -auto-approve

# --- 5. Sweep by tag, report rather than delete -----------------------------------------------
# Tag indexes lag by up to an hour after a delete, so entries here are not necessarily live.
echo "[5/5] Sweeping for anything still tagged ${TAG_KEY}=${TAG_VALUE}..."
leftovers="$(aws resourcegroupstaggingapi get-resources --region "${REGION}" \
    --tag-filters "Key=${TAG_KEY},Values=${TAG_VALUE}" \
    --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null || true)"

# EKS auto-creates the control-plane log group and it survives destroy, because this module
# deliberately does not manage it (so re-provisioning with the same name is idempotent).
CLUSTER_NAME="$(terraform -chdir="${PROVISION_DIR}" output -raw cluster_name 2>/dev/null || true)"
if [ -n "${CLUSTER_NAME}" ]; then
    aws logs delete-log-group --region "${REGION}" \
        --log-group-name "/aws/eks/${CLUSTER_NAME}/cluster" 2>/dev/null \
        && echo "      deleted the control-plane log group." || true
fi

if [ -n "${leftovers}" ]; then
    echo
    echo "Resources still carrying the tag:"
    printf '%s\n' "${leftovers}" | tr '\t' '\n' | sed 's/^/  /'
    echo
    echo "Tag indexes lag up to an hour after a delete, so some of these may already be gone."
    echo "Re-run this script, or check the console, before assuming you are billed for them."
    exit 1
fi

echo "      nothing left."
echo
echo "Teardown complete."

#!/usr/bin/env bash
# ABOUTME: Substitutes this cluster's name, VPC id and region into the working copy under platform/.
# ABOUTME: Reads them from terraform outputs, falls back to the AWS API, and refuses to touch solution/.
#
# Run once after `terraform apply` and after you have a platform/ directory, in either order.
# It is idempotent, so re-run it whenever you regenerate platform/.
#
# solution/ is the reference build and keeps its placeholders on purpose. Substituting there
# would bake one cluster's identity into the answer key, which is what
# tests/test_platform_contract.py asserts against.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVISION_DIR="${REPO_ROOT}/provision"
TARGET="${REPO_ROOT}/platform"

if [ ! -d "${TARGET}" ]; then
    cat >&2 <<EOF
ERROR: ${TARGET} does not exist.

platform/ is your working copy: the tree your agent builds, and the one ArgoCD reads once
you push it. Either let the agent generate it, or start from the reference:

    cp -a solution/platform/. platform/

Then run this script again.
EOF
    exit 2
fi

# --- Resolve the three facts -----------------------------------------------------------------
# Terraform knows all three. Fall back to the AWS API for anyone working from someone else's
# cluster, or who has lost their state file.
# Highest priority: values you pass in. Useful when you are working against a cluster someone
# else created, or when you already know all three and do not want an AWS round trip.
CLUSTER_NAME="${CLUSTER_NAME:-}"; VPC_ID="${VPC_ID:-}"; REGION="${REGION:-}"

if [ -n "${CLUSTER_NAME}" ] && [ -n "${VPC_ID}" ] && [ -n "${REGION}" ]; then
    echo "Using the cluster facts already set in the environment."
elif [ -f "${PROVISION_DIR}/terraform.tfstate" ] && command -v terraform >/dev/null 2>&1; then
    echo "Reading cluster facts from terraform outputs..."
    CLUSTER_NAME="$(terraform -chdir="${PROVISION_DIR}" output -raw cluster_name 2>/dev/null || true)"
    VPC_ID="$(terraform -chdir="${PROVISION_DIR}" output -raw vpc_id 2>/dev/null || true)"
    REGION="$(terraform -chdir="${PROVISION_DIR}" output -raw region 2>/dev/null || true)"
fi

if [ -z "${CLUSTER_NAME}" ]; then
    echo "No terraform state; falling back to the AWS API."
    CLUSTER_NAME="${CLUSTER_NAME:-${EXPECTED_CONTEXT:-}}"
    if [ -z "${CLUSTER_NAME}" ]; then
        echo "ERROR: set EXPECTED_CONTEXT to your cluster name, or run this from a tree with terraform state." >&2
        exit 2
    fi
    REGION="${REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
    if [ -z "${REGION}" ]; then
        echo "ERROR: set AWS_REGION so the cluster can be described." >&2
        exit 2
    fi
    VPC_ID="$(aws eks describe-cluster --name "${CLUSTER_NAME}" --region "${REGION}" \
        --query 'cluster.resourcesVpcConfig.vpcId' --output text)"
fi

for pair in "cluster name:${CLUSTER_NAME}" "VPC id:${VPC_ID}" "region:${REGION}"; do
    if [ -z "${pair#*:}" ]; then
        echo "ERROR: could not resolve the ${pair%%:*}." >&2
        exit 1
    fi
done

echo "  cluster name : ${CLUSTER_NAME}"
echo "  VPC id       : ${VPC_ID}"
echo "  region       : ${REGION}"

# --- Record them in the cluster ----------------------------------------------------------------
# The AWS Load Balancer Controller manifest cites this ConfigMap by name, so anything that needs
# these facts later can read them from the cluster rather than from a state file.
if kubectl version >/dev/null 2>&1; then
    echo "Writing the platform-cluster-facts ConfigMap..."
    kubectl create configmap platform-cluster-facts \
        --namespace kube-system \
        --from-literal=clusterName="${CLUSTER_NAME}" \
        --from-literal=vpcId="${VPC_ID}" \
        --from-literal=region="${REGION}" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null
else
    echo "kubectl cannot reach a cluster; skipping the ConfigMap and substituting files only."
fi

# --- Substitute --------------------------------------------------------------------------------
echo "Substituting into ${TARGET}..."
while IFS= read -r -d '' file; do
    sed -i \
        -e "s|REPLACE_WITH_CLUSTER_NAME|${CLUSTER_NAME}|g" \
        -e "s|REPLACE_WITH_VPC_ID|${VPC_ID}|g" \
        -e "s|REPLACE_WITH_REGION|${REGION}|g" \
        "${file}"
done < <(grep -rlZ 'REPLACE_WITH_' "${TARGET}" 2>/dev/null || true)

# --- Verify, loudly ----------------------------------------------------------------------------
# An unsubstituted placeholder leaves the Application Degraded forever, and the sync reports
# success while it happens. Fail here instead.
if remaining="$(grep -rn 'REPLACE_WITH_' "${TARGET}" 2>/dev/null)"; then
    echo >&2
    echo "ERROR: placeholders survived substitution:" >&2
    echo "${remaining}" >&2
    exit 1
fi

echo "Done. No placeholders remain under platform/."

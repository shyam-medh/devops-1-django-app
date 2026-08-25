FROM amazon/aws-cli:2.27.0

# Avoid interactive prompts and reduce layer noise
ENV DEBIAN_FRONTEND=noninteractive

# Install system tools needed by helm installer (single layer, clean cache)
RUN yum install -y --quiet tar gzip curl \
    && yum clean all \
    && rm -rf /var/cache/yum

# Install Helm (pinned version)
ARG HELM_VERSION=v3.21.4
RUN curl -fsSL -o get_helm.sh \
      https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \
    && chmod 700 get_helm.sh \
    && VERIFY_CHECKSUM=false DESIRED_VERSION=${HELM_VERSION} ./get_helm.sh \
    && rm -f get_helm.sh

# Install kubectl (pinned to stable at build time)
RUN KUBECTL_VERSION=$(curl -Ls https://dl.k8s.io/release/stable.txt) \
    && curl -fsSL -o /usr/local/bin/kubectl \
       https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl \
    && chmod +x /usr/local/bin/kubectl

# Verify all tools are present
RUN aws --version \
    && helm version --short \
    && kubectl version --client --short

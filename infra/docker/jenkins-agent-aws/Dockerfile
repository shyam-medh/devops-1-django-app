FROM amazon/aws-cli:latest

# Install system tools needed by helm installer
RUN yum install -y tar gzip curl && yum clean all

# Install Helm
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \
    && chmod 700 get_helm.sh \
    && VERIFY_CHECKSUM=false ./get_helm.sh \
    && rm get_helm.sh

# Install kubectl (pinned to stable)
RUN KUBECTL_VERSION=$(curl -Ls https://dl.k8s.io/release/stable.txt) \
    && curl -fsSL -o /usr/local/bin/kubectl \
       https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl \
    && chmod +x /usr/local/bin/kubectl

# Verify installations
RUN helm version && kubectl version --client && aws --version

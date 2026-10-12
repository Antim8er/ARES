# syntax=docker/dockerfile:1
FROM kalilinux/kali-rolling:latest

LABEL maintainer="Antim8er"
LABEL description="A.R.E.S. - Autonomous Reconnaissance & Exploitation System (Containerized Environment)"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install core networking, security tools, and Python build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-setuptools \
    git \
    curl \
    wget \
    ca-certificates \
    nmap \
    sqlmap \
    nikto \
    gobuster \
    whois \
    dnsutils \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications first to leverage layer caching
COPY pyproject.toml README.md ./
COPY ares/ ./ares/

# Install A.R.E.S. in editable mode
RUN python3 -m pip install --no-cache-dir --break-system-packages -e .

# Create workspace directory for reports and sessions
VOLUME ["/workspace"]
WORKDIR /workspace

# Set default entrypoint to ares-cli
ENTRYPOINT ["ares-cli"]
CMD ["--help"]

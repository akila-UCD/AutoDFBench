FROM mambaorg/micromamba:1.5.10

ENV MAMBA_DOCKERFILE_ACTIVATE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    build-essential \
    gcc g++ make \
    git \
    pkg-config \
    autoconf automake libtool \
    zlib1g-dev libbz2-dev liblzma-dev \
    libssl-dev libffi-dev \
    libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Create conda env (minimal, always solvable)
COPY environment.yml /tmp/environment.yml
RUN micromamba create -y -n autodfbench -f /tmp/environment.yml && \
    micromamba clean --all --yes

ENV CONDA_DEFAULT_ENV=autodfbench
ENV PATH=/opt/conda/envs/autodfbench/bin:$PATH

# Copy only requirements first for cache
COPY requirements.txt /tmp/requirements.txt

# Upgrade build tooling and install pip requirements
RUN /opt/conda/envs/autodfbench/bin/python -m pip install --upgrade pip setuptools wheel && \
    /opt/conda/envs/autodfbench/bin/pip install -r /tmp/requirements.txt

# Now copy the project code
COPY . /app

# Supervisor config + entrypoint
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 8001 8002 8003 8004

ENTRYPOINT ["/entrypoint.sh"]

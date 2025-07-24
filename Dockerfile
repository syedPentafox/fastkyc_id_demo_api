# Dockerfile for Red Hat Enterprise Linux 9.6 (UBI)
# Python 3.11.9, project setup, zip venv+project, export zip


FROM registry.access.redhat.com/ubi9/python-311:latest

# Switch to root for package installation
USER root


RUN dnf install -y zip curl --allowerasing && dnf clean all \
    && curl -sSL https://install.python-poetry.org | python3.11 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Set workdir
WORKDIR /app

# Copy project files
COPY . /app



# Remove existing venv if it exists, then create and activate venv
RUN if [ -d venv ]; then rm -rf venv; fi \
    && python3.11 -m venv venv \
    && . venv/bin/activate \
    && poetry config virtualenvs.in-project true \
    && poetry install --no-interaction --no-ansi --no-root




# Entrypoint: zip project and venv at container startup, then exit
CMD bash -c "mkdir -p /output && zip -r /output/project_with_venv.zip /app"

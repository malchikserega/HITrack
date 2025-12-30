FROM python:3.12-slim

RUN apt update
RUN apt install python3-dev -y
RUN apt install gcc -y
RUN apt install build-essential -y
RUN mkdir -p /opt/src
RUN apt install python3-cffi libcairo2 libpango-1.0-0 libgdk-pixbuf-xlib-2.0-0 libffi-dev shared-mime-info -y
RUN apt install curl lsb-release gnupg -y

RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

# Install Docker CLI
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Helm via APT (current repo)
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends curl ca-certificates gnupg; \
  curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/helm.gpg; \
  echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" \
    > /etc/apt/sources.list.d/helm-stable-debian.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends helm; \
  rm -rf /var/lib/apt/lists/*

WORKDIR /opt/src

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN mkdir -p /var/www/static

WORKDIR /opt/src

COPY . .
COPY ./docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 80
EXPOSE 81

ENTRYPOINT ["docker-entrypoint.sh"]

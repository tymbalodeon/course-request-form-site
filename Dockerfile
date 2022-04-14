# Global Build Args ----------------------------------
# Image tag
ARG IMAGE_TAG=3.9-slim

# Project home
ARG PROJECT_ROOT=/home/app

# Build Stage ----------------------------------------
FROM python:${IMAGE_TAG} as base

ARG PROJECT_ROOT
ENV PROJECT_ROOT=${PROJECT_ROOT}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR ${PROJECT_ROOT}

COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ git libpq-dev && \
    pip wheel --no-cache-dir --no-deps --wheel-dir=${PROJECT_ROOT}/wheels -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*;


# Production Stage -----------------------------------
FROM python:${IMAGE_TAG} as production

ARG GUNICORN_PORT=5000
ENV GUNICORN_PORT=${GUNICORN_PORT}

ARG ORACLE_INSTANT_CLIENT_VERSION=21.5.0.0.0
ARG ORACLE_INSTANT_CLIENT_LINK=https://download.oracle.com/otn_software/linux/instantclient/215000/instantclient-basiclite-linux.x64-${ORACLE_INSTANT_CLIENT_VERSION}dbru.zip
ARG ORACLE_SQL_PLUS_LINK=https://download.oracle.com/otn_software/linux/instantclient/215000/instantclient-sqlplus-linux.x64-${ORACLE_INSTANT_CLIENT_VERSION}dbru.zip

ARG PROJECT_ROOT
ENV PROJECT_ROOT=${PROJECT_ROOT}

# create user
RUN groupadd -g 1000 app && useradd -g app -u 1000 -m -d /home/app app

# install gosu
RUN set -eux; \
    apt-get update; \
    apt-get install -y gosu; \
    rm -rf /var/lib/apt/lists/*; \
    # verify that the binary works
    gosu nobody true

# install oracle instantclient and sql plus
WORKDIR /opt/oracle

RUN apt-get update && apt-get install -y --no-install-recommends unzip wget && \
    wget ${ORACLE_INSTANT_CLIENT_LINK} -O instantclient-basic-linux.zip && \
    wget ${ORACLE_SQL_PLUS_LINK} -O instantclient-sqlplus-linux.zip && \
    unzip '*.zip' -d instantclient && \
    mv -f $(find * -type d -name instantclient_*)/* instantclient/ && \
    rm -fr $(find * -type d -name instantclient_*) && \
    rm -fr *.zip && \
    echo /opt/oracle/instantclient > /etc/ld.so.conf.d/oracle-instantclient.conf && \
    ldconfig && \
    apt-get -y autoremove && \
    apt-get clean autoclean && \
    rm -rf /var/lib/apt/lists/*;

WORKDIR ${PROJECT_ROOT}

COPY --from=base ${PROJECT_ROOT}/wheels /wheels
COPY --from=base ${PROJECT_ROOT}/requirements.txt .
COPY . ${PROJECT_ROOT}

RUN apt-get update && apt-get install -y --no-install-recommends libaio1 libpq-dev make && \
    pip install --upgrade pip && \
    pip install --no-cache /wheels/* && \
    mv docker-entrypoint.sh /usr/local/bin/ && \
    chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chown -R app:app . && \
    rm -rf /var/lib/apt/lists/*;

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE ${GUNICORN_PORT}

CMD [ "gunicorn", "--bind 0.0.0.0:${GUNICORN_PORT}", "manage:app" ]

FROM python:3.11-slim AS base

LABEL org.opencontainers.image.source=https://github.com/ReachTalent/reachtalent-app
LABEL org.opencontainers.image.description="ReachTalent Backend and API"

ENV FLASK_APP=reachtalent
WORKDIR /app
EXPOSE 8000

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt update -y && apt upgrade -y && apt-get install --assume-yes libpq5

FROM base as builder

# System Update
RUN apt install --assume-yes libpq-dev build-essential

# Create virtualenv to isolate app deps from system deps and be
# copyable into production stage (if using a build stage)
RUN python3 -m venv $VIRTUAL_ENV

# Intentionally copying only requirements.txt so that `pip install` will be cached
COPY requirements.txt .
# Need to specify --no-deps because of sqlalchemy/greenlet issue
# See: https://github.com/sqlalchemy/sqlalchemy/issues/6136
RUN pip install --no-deps -r requirements.txt


FROM base as local
COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV

ENV FLASK_ENV=development
ENV FLASK_DEBUG=1

COPY dev-requirements.txt .
RUN pip install --no-deps -r dev-requirements.txt

WORKDIR /src/reachtalent-app

CMD ./compose_entrypoint.sh

FROM base as deploy
COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV

ENV FLASK_ENV=production
ENV FLASK_DEBUG=0

COPY . .

CMD gunicorn --access-logfile=- --worker-tmp-dir /dev/shm -w 2 --threads 5 -b 0.0.0.0 'reachtalent:create_app()'
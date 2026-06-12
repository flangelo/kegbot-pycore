# Stage 1: install dependencies and the package into a venv
FROM python:3.11-alpine AS builder

WORKDIR /app
RUN pip install --no-cache-dir "pipenv<2024"

COPY Pipfile Pipfile.lock ./
RUN pipenv requirements > /tmp/requirements.txt

RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY kegbot ./kegbot
COPY bin ./bin
COPY setup.py ./
RUN /venv/bin/pip install --no-cache-dir .


# Stage 2: lean runtime image — no pipenv, no curl, no build cache
FROM python:3.11-alpine

WORKDIR /app

ENV PATH="/venv/bin:$PATH" \
    KEGBOT_IN_DOCKER=True \
    KEGBOT_ENV=debug

RUN apk add --no-cache bash

COPY --from=builder /venv /venv
COPY bin ./bin

ARG GIT_SHORT_SHA="unknown"
ARG VERSION="unknown"
ARG BUILD_DATE="unknown"
RUN printf "GIT_SHORT_SHA=%s\nVERSION=%s\nBUILD_DATE=%s\n" \
    "${GIT_SHORT_SHA}" "${VERSION}" "${BUILD_DATE}" \
    > /etc/kegbot-pycore-version

CMD ["python", "bin/kegbot_core.py"]

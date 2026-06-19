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


# Stage: test — layers test tooling on top of the builder venv so the suite runs
# against the same installed deps as production. Never part of the runtime image
# (`docker build` defaults to the final stage). Build/run it explicitly:
#   docker build --target test -t kegbot/pycore:test . && docker run --rm kegbot/pycore:test
# The suite mocks all I/O (Redis, the Kegbot API, threads), so no services are needed.
FROM builder AS test

ENV PATH="/venv/bin:$PATH" \
    KEGBOT_ENV=test

# Install test tooling, then re-install the package editable so coverage measures
# the source tree at /app/kegbot/pycore rather than the copy in site-packages.
RUN /venv/bin/pip install --no-cache-dir pytest coverage && \
    /venv/bin/pip install --no-cache-dir -e .

COPY pytest.ini .coveragerc ./

# Default to the full suite with coverage and the CI gate; override to scope down.
CMD ["sh", "-c", "coverage run -m pytest && coverage report -m --fail-under=80"]


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

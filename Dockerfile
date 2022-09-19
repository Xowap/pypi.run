FROM nikolaik/python-nodejs:latest

RUN useradd -ms /bin/bash app

RUN mkdir -p /code/front \
    && mkdir -p /code/src/pypi_run  \
    && touch /code/src/pypi_run/__init__.py \
    && chown -R app: /code

USER app

WORKDIR /code/front
ADD --chown=app front/package.json .
ADD --chown=app front/package-lock.json .
RUN npm install

WORKDIR /code
ADD --chown=app pyproject.toml .
ADD --chown=app poetry.lock .
RUN poetry install

WORKDIR /code/front
ADD --chown=app . .
RUN npm run generate

WORKDIR /code
ADD --chown=app . .

ENV PORT 8000
EXPOSE ${PORT}

CMD [ \
    "bash", "-c", \
    "poetry run python -m uvicorn pypi_run.server:app --port $PORT --host 0.0.0.0" \
]

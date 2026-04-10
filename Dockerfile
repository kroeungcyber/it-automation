FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[dev]"
RUN python -m spacy download en_core_web_sm
COPY . .

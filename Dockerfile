FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

FROM python:3.12-slim
RUN useradd -m -u 10001 charlie
COPY --from=builder --chown=charlie:charlie /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER charlie
WORKDIR /app
EXPOSE 8000
ENTRYPOINT ["charlie-work-mcp"]
CMD ["--http"]

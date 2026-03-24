FROM python:3.12-slim

WORKDIR /app

COPY vendor/ vendor/
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir vendor/*.whl && pip install --no-cache-dir .

# Cloud Run 用 PORT 環境變數
ENV PORT=8080
ENV MCP_TRANSPORT=sse

CMD ["python", "-m", "zenos.interface.tools"]

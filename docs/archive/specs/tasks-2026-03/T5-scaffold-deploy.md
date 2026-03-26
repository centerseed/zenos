# T5 — Project Scaffold + Deploy Config

> 指派：Developer | 預估：2 小時
> 依賴：無
> 技術設計：`docs/decisions/ADR-003-phase1-mvp-architecture.md`

---

## 目標

建立 Python 專案結構、依賴管理、Docker 設定、Cloud Run 部署設定。

## 產出檔案

```
src/
  zenos/
    __init__.py
    domain/
      __init__.py
    application/
      __init__.py
    infrastructure/
      __init__.py
    interface/
      __init__.py
  tests/
    __init__.py
    domain/
      __init__.py
    integration/
      __init__.py

pyproject.toml
Dockerfile
.env.example
.gitignore          # 更新（加 Python + Firebase 相關）
```

---

## pyproject.toml

```toml
[project]
name = "zenos"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0",
    "google-cloud-firestore>=2.19",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

# Cloud Run 用 PORT 環境變數
ENV PORT=8080

# FastMCP HTTP SSE transport
CMD ["python", "-m", "zenos.interface.tools", "--transport", "sse", "--port", "8080"]
```

---

## .env.example

```
# Firebase
GOOGLE_CLOUD_PROJECT=zenos-naruvia

# GitHub Adapter
GITHUB_TOKEN=ghp_your_token_here
GITHUB_DEFAULT_OWNER=havital

# MCP Server（本地開發用 stdio，部署用 sse）
MCP_TRANSPORT=stdio
```

---

## .gitignore 更新

追加以下項目：
```
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/

# Environment
.env

# Firebase
firebase-debug.log
```

---

## Done Criteria

- [ ] 專案結構建立完成（所有 __init__.py）
- [ ] pyproject.toml 能 `pip install -e .`
- [ ] Dockerfile 能 build
- [ ] .env.example 包含所有需要的環境變數
- [ ] .gitignore 涵蓋 Python + Firebase
- [ ] /simplify 執行完畢

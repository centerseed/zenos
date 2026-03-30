FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY skills/ skills/
RUN pip install --no-cache-dir .
RUN python -c "from pathlib import Path; import shutil, sysconfig; target = Path(sysconfig.get_paths()['stdlib']) / 'skills'; target.parent.mkdir(parents=True, exist_ok=True); (target.unlink() if (target.exists() or target.is_symlink()) and (target.is_symlink() or target.is_file()) else shutil.rmtree(target) if target.exists() else None); target.symlink_to(Path('/app/skills'), target_is_directory=True); print(f'Linked {target} -> /app/skills')"

# Cloud Run 用 PORT 環境變數
ENV PORT=8080
ENV MCP_TRANSPORT=sse

CMD ["python", "-m", "zenos.interface.tools"]

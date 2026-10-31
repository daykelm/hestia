FROM python:3.12-slim

WORKDIR /app
COPY app.py deals.py sources.py diligence.py ./
COPY static ./static

# shortcut: runs as root so the Umbrel data folder stays writable, switch to a fixed uid if this port is reachable past the home network
ENV HOST=0.0.0.0
ENV PORT=8080
ENV HESTIA_DB=/data/hestia.db
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["python3", "app.py"]

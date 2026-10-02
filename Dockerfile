FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin soc
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY static ./static
COPY templates ./templates

ENV SOC_CUSTOMERS_DIR=/app/customers SOC_DATA_DIR=/app/data SOC_DEFAULT_TEMPLATE=/app/templates/incident-ticket.md
USER soc
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/healthz',timeout=4).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--proxy-headers", "--no-server-header"]

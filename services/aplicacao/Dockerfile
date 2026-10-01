FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# A base so muda quando dependencias ou sistema mudam. O codigo de cada SHA
# pode ser montado em /app pelo publicador sem reconstruir a imagem.
COPY services/aplicacao/requirements.txt /tmp/requirements.txt
COPY packages/site_errors /tmp/packages/site_errors
COPY packages/outbox-relay /tmp/packages/outbox-relay
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir /tmp/packages/site_errors /tmp/packages/outbox-relay

COPY services/aplicacao/ /app/
COPY services/ /tmp/services/
RUN python preparar.py --origem /tmp/services --destino /app/modules \
    && rm -rf /tmp/services

EXPOSE 8000
CMD ["python", "entrypoint.py"]

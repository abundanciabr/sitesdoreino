FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends blender python3-pil python3-numpy ca-certificates && rm -rf /var/lib/apt/lists/*
COPY examinar.py blender_examinar.py /analisador/
ENV HOME=/tmp OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
USER 65534:65534
ENTRYPOINT ["python3", "/analisador/examinar.py"]

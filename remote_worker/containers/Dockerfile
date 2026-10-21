# Build with scripts/build-rapid-image.sh; source-only private build context.
# CUDA driver compatibility and actual SM120 execution require NVIDIA tests.
FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04@sha256:6a0e31b59e70890446f2c17356d6efc0d54260090a8c63d6ca7c2ad049db95d2 AS core
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates openssh-server && rm -rf /var/lib/apt/lists/*
COPY release /opt/fold-rapid-release
RUN python3 -m venv /opt/fold-rapid && /opt/fold-rapid/bin/pip install --require-hashes -r /opt/fold-rapid-release/worker/environments/core.lock && /opt/fold-rapid/bin/pip install --no-deps --no-build-isolation /opt/fold-rapid-release/worker
ENV PATH=/opt/fold-rapid/bin:$PATH RAPID_ROOT=/data/rapid RAPID_RELEASE_DIR=/opt/fold-rapid-release
RUN mkdir -p /data/rapid /models /root/.ssh /run/sshd && chmod 700 /root/.ssh
COPY startup.sh /usr/local/bin/rapid-start
HEALTHCHECK --interval=60s --timeout=15s CMD ["fold-rapid", "health"]
WORKDIR /data
ENTRYPOINT ["/usr/local/bin/rapid-start"]
CMD ["serve-ssh"]

FROM core AS bindcraft2
RUN fold-rapid-install --root /opt/fold-rapid-defaults --engine bindcraft2 --approve
RUN /opt/fold-rapid-defaults/runtimes/bindcraft2/bin/python /opt/fold-rapid-release/worker/fold_rapid/runtime_probe.py --engine bindcraft2
ENV RAPID_DEFAULT_CONFIG=/opt/fold-rapid-defaults/config.json

FROM core AS boltzgen
RUN fold-rapid-install --root /opt/fold-rapid-defaults --engine boltzgen --approve
RUN /opt/fold-rapid-defaults/runtimes/boltzgen/bin/python /opt/fold-rapid-release/worker/fold_rapid/runtime_probe.py --engine boltzgen
RUN /opt/fold-rapid-defaults/runtimes/esmfold2/bin/python /opt/fold-rapid-release/worker/fold_rapid/runtime_probe.py --engine esmfold2
ENV RAPID_DEFAULT_CONFIG=/opt/fold-rapid-defaults/config.json

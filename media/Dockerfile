# Runtime pinned to the user's requested v2.9.1 image (linux/amd64).
FROM 19970688/nastools-bt@sha256:ddddf9438000e43545e7b85cbed0f73fdcf26ef49dc0ac47ee98a38398a265a9
WORKDIR /nas-tools
ENV NASTOOL_AUTO_UPDATE=false NASTOOL_CONFIG=/config/config.yaml TZ=Asia/Shanghai
RUN pip3 install --no-cache-dir waitress==3.0.2
COPY . /nas-tools/
RUN chmod +x /nas-tools/docker/entrypoint.sh /nas-tools/film-entrypoint.sh \
    && python3 -m compileall -q app web run.py media_profile.py \
    && python3 scripts/create_source_archive.py /nas-tools /opt/film-index-source.zip
LABEL org.opencontainers.image.title="Film and Television Index" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.description="Local media-organization edition based on NAStools v2.9.1"
EXPOSE 3000
ENTRYPOINT ["/bin/sh", "/nas-tools/hub-entrypoint.sh"]

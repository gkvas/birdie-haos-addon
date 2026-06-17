ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

# Runtime: python + ttyd (web terminal for Ingress).
# build-base/dev libs are only needed if a dependency lacks a musllinux wheel;
# install them as a virtual package and drop them afterwards to keep the image lean.
RUN apk add --no-cache python3 py3-pip ttyd jq \
    && apk add --no-cache --virtual .build-deps build-base python3-dev libffi-dev \
    && pip3 install --no-cache-dir "birdie-agent[mcp]" \
    && apk del .build-deps

COPY rootfs /
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]

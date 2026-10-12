FROM python:3.13-slim-bookworm

ENV TERM=xterm-256color
SHELL ["/bin/bash", "-lc"]
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir \
    pytest \
    pytest-json-ctrf==0.5.2

RUN mkdir -p /logs/agent /logs/verifier /logs/artifacts

COPY app/ /app/

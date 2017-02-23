FROM python:3.5

MAINTAINER Ulrich Petri <ulrich@gridsingularity.com>

ADD . /app

WORKDIR /app

RUN pip install --upgrade pip virtualenv setuptools && \
    virtualenv /venv && \
    /venv/bin/pip install pip-tools && \
    /venv/bin/pip-sync /app/requirements/*.txt && \
    /venv/bin/pip install -e .

ENTRYPOINT ["/venv/bin/d3a"]

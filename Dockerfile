FROM python:3.5

MAINTAINER Ulrich Petri <ulrich@gridsingularity.com>

ADD . /app

WORKDIR /app

# Ensure newest pip to avoid https://github.com/pypa/setuptools/issues/951
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

RUN pip install --upgrade virtualenv setuptools && \
    virtualenv /venv && \
    /venv/bin/pip install pip-tools && \
    /venv/bin/pip-sync /app/requirements/*.txt && \
    /venv/bin/pip install -e .

ENTRYPOINT ["/venv/bin/d3a"]

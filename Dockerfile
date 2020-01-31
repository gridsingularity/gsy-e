FROM python:3.6

ADD . /app

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
RUN pip install -e .

ENTRYPOINT ["/venv/bin/d3a"]

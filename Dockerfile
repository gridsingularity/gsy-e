FROM python:3.11

ADD . /app

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install -e .

ENTRYPOINT ["gsy-e"]

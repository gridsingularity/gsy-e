FROM python:3.10-slim

RUN mkdir /app
WORKDIR /app
ENV TZ="Europe/Berlin"

ADD ./requirements /app/requirements
ADD ./gsy-framework /app/gsy-framework

ADD ./src /app/src
ADD ./setup.cfg ./README.rst ./setup.py /app/
RUN pip install -e . -e gsy-framework
ENTRYPOINT ["gsy-e"]

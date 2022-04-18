FROM python:3.8

RUN mkdir gsy-e
WORKDIR /gsy-e
ADD . /gsy-e

RUN pip install --upgrade pip
RUN pip install -r requirements/pandapower.txt
RUN pip install -e .

ENTRYPOINT ["gsy-e"]

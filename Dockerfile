FROM python:3.10-slim

RUN mkdir /app
WORKDIR /app

ADD ./requirements /app/requirements
ADD ./gsy-framework /app/gsy-framework
RUN pip install --upgrade pip && pip install -r requirements/pandapower.txt 
#&& pip install -r requirements/blockchain.in # gsy-e-dex broken

ADD ./src /app/src
ADD ./setup.cfg ./README.rst ./setup.py /app/
RUN pip install -e .
RUN cd gsy-framework && pip install -e . && cd ..

ENTRYPOINT ["gsy-e"]

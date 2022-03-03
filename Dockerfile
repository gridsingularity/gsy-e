FROM python:3.9

RUN mkdir /app
WORKDIR /app

ADD ./requirements /app/requirements
RUN pip install --upgrade pip && pip install -r requirements/pandapower.txt && pip install -r requirements/blockchain.in

ADD ./src /app/src
ADD ./setup.cfg ./README.rst ./setup.py /app/
#ADD ./setup.py /app/
RUN pip install -e .

ENTRYPOINT ["gsy-e"]

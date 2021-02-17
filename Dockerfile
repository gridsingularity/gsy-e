FROM python:3.8

ADD . /app

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install -r requirements/pandapower.txt
RUN pip install -e .

ENTRYPOINT ["d3a"]

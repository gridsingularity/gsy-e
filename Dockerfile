FROM python:3.6

ADD . /app

WORKDIR /app

RUN pip install --upgrade pip ptpython
RUN pip install -r requirements/pandapower.txt
RUN pip install -e .

ENTRYPOINT ["d3a"]

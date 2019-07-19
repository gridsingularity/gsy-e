FROM python:3.6

ADD . /app

WORKDIR /app

# Ensure newest pip to avoid https://github.com/pypa/setuptools/issues/951
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

RUN pip install --upgrade virtualenv setuptools && \
    virtualenv /venv && \
    /venv/bin/pip install pip-tools && \
    /venv/bin/pip-sync /app/requirements/*.txt && \
    /venv/bin/pip install -e . && \
    /venv/bin/pip install git+https://github.com/Jonasmpi/py-solc.git && \
    /venv/bin/pip install \
        git+https://github.com/gridsingularity/d3a-interface.git#egg=d3a-interface

ENTRYPOINT ["/venv/bin/d3a"]

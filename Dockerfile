FROM python:3.13.11

WORKDIR /usr/src/app
#ENV DOCKER_HOST unix:///run/docker.sock
COPY requirements.txt ./
RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

CMD python3 -m main

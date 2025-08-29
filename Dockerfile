FROM python:3.14.0rc1-slim

WORKDIR /src

RUN apt-get update && apt-get install -y \
    net-tools iproute2 iputils-ping curl \
    && rm -rf /var/lib/apt/lists/*

COPY . /src

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "src/main.py"]
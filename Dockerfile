FROM python:3.14.2-slim-bookworm

WORKDIR /src

RUN apt-get update && apt-get install -y \
    net-tools iproute2 iputils-ping curl \
    dbus libdbus-1-dev libglib2.0-dev \
    bluez \
    && rm -rf /var/lib/apt/lists/*

COPY . /src

RUN pip install --upgrade pip
# Vendored Esse-ti BLE SDK — see vendor/nexyhub-ble-sdk/NOTICE.md
COPY vendor/nexyhub-ble-sdk /tmp/nexyhub-ble-sdk
RUN pip install /tmp/nexyhub-ble-sdk
RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "src/main.py"]

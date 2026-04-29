from setuptools import setup, find_packages

setup(
    name="nexyhub_ble",
    version="0.7.0",
    description="BLE GATT Server framework for NexyHub on OpenWRT",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "bless>=0.3.0",
    ],
)

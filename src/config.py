from pathlib import Path

class Config:
    CONNECTION_STRING: str = 'test'
    PROVISIONING_HOST: str = 'global.azure-devices-provisioning.net'
    DEVICE_NAME: str = 'GW-dev-test'
    SCOPE_ID: str = '0ne0007D5F7'
    
    # Certificate paths resolved relative to this file's location (src/)
    _SRC_DIR = Path(__file__).parent
    TT_CERT: str = str(_SRC_DIR / 'GW-dev-test.fullchain.pem')
    TT_KEY: str = str(_SRC_DIR / 'GW-dev-test.key.pem')
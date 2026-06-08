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

    # Download (ca.download-file) — see EG-64 spec §9
    DOWNLOAD_ROOT: str = "/data/downloads"
    DOWNLOAD_TYPE_DIRS: dict[str, str] = {
        "0x07": "up",
        "0x08": "liftAgent",
        "0x0B": "script",
    }
    DOWNLOAD_HOST_ALLOWLIST: list[str] = ["*.blob.core.windows.net"]
    DOWNLOAD_MAX_BYTES_DEFAULT: int = 50 * 1024 * 1024  # 50 MiB
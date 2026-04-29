"""Custom exceptions for nexyhub_ble."""


class NexyHubBLEError(Exception):
    """Base exception."""
    pass

class AdapterNotFoundError(NexyHubBLEError):
    pass

class ServerAlreadyRunningError(NexyHubBLEError):
    pass

class ServerNotRunningError(NexyHubBLEError):
    pass

class ServiceRegistrationError(NexyHubBLEError):
    pass

class AdvertisementError(NexyHubBLEError):
    pass

class InvalidUUIDError(NexyHubBLEError):
    pass

class CharacteristicError(NexyHubBLEError):
    pass

"""serial.Serial subclass that toggles an RS485 DE GPIO around write().

The gateway's RS485 transceiver has its Driver Enable pin on a regular GPIO
line rather than UART RTS, so the kernel cannot flip direction automatically.

gpiod is Linux-only and imported lazily so this module can be loaded for
unit tests on hosts without libgpiod installed.
"""
from __future__ import annotations

import time
from collections.abc import Buffer
from typing import Any

import serial


class RS485Serial(serial.Serial):
    """serial.Serial that drives a GPIO line as RS485 DE around write().

    Args:
        gpio_chip: gpiochip device path (e.g. /dev/gpiochip1).
        de_line: GPIO line offset wired to the transceiver DE pin.
        Other args forwarded to serial.Serial.
    """

    def __init__(
        self,
        *args: Any,
        gpio_chip: str,
        de_line: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        import gpiod  # pylint: disable=import-outside-toplevel
        self._gpiod = gpiod
        self._de_line = de_line
        chip = gpiod.Chip(gpio_chip)
        self._line_req = chip.request_lines(
            config={
                de_line: gpiod.LineSettings(
                    direction=gpiod.line.Direction.OUTPUT,
                    output_value=gpiod.line.Value.INACTIVE,
                )
            },
            consumer="modbus-rs485-de",
        )
        self._drain_safety_s = 2e-3

    def write(self, data: Buffer) -> int | None:
        """Drive DE active, write, drain, drop DE."""
        if not bytes(data):
            return 0
        self._line_req.set_value(self._de_line, self._gpiod.line.Value.ACTIVE)
        try:
            n = super().write(data)
            super().flush()
            time.sleep(self._drain_safety_s)
        finally:
            self._line_req.set_value(self._de_line, self._gpiod.line.Value.INACTIVE)
        return n

    def close(self) -> None:
        try:
            self._line_req.release()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        super().close()

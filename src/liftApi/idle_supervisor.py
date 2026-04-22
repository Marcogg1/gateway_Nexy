"""IdleSupervisor — observes lift parameter updates and logs them.

Future: evaluate criteria and initiate triggered functionality.
"""

from dataclasses import dataclass

from lib.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ParamChange:
    """A single parameter update detected during a poll cycle."""

    param_id: int
    new_value: object | None


class IdleSupervisor:
    """Receives parameter updates from LiftProxy and logs them."""

    def on_param_changes(self, changes: list[ParamChange]) -> None:
        """Log each parameter change at INFO level.

        Args:
            changes: List of ParamChange entries from the latest poll.
        """
        for c in changes:
            logger.info(
                "Param update: id=%s new=%s",
                c.param_id, c.new_value,
            )

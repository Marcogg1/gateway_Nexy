#!/usr/bin/env python3

import asyncio
import os
import sys
from enum import Enum
from typing import Any, Type
from collections.abc import KeysView

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from lib.error_signals import MbCode
from lib.logging_config import setup_logging, get_logger

# Setup logging at module level
setup_logging()
logger = get_logger(__name__)


class AhlLib:
    """Database and functionality for AHL (Aritco Home Lift) series parameters."""

    _OLD_POLLING_TABLE: dict[int, list[int]] = {
        0: [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        1: list(range(16, 32)),
        2: list(range(32, 48)),
        3: list(range(48, 64)),
        4: list(range(64, 80)),
        5: list(range(80, 94)),
        6: list(range(94, 110)),
        7: list(range(110, 126)),
        8: [126] + list(range(353, 368)),
        **{bit: list(range(224 + bit * 16, 224 + bit * 16 + 16)) for bit in range(9, 31)},
    }

    _NEW_POLLING_TABLE: dict[int, list[int]] = {
        0: [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        1: list(range(16, 32)),
        2: list(range(32, 48)),
        3: list(range(48, 64)),
        4: list(range(64, 80)),
        5: list(range(80, 94)),
        6: list(range(94, 110)),
        7: list(range(110, 126)),
        8: [126, 127, 128, 129] + list(range(353, 365)),
        **{bit: list(range(-14 + bit * 16, -14 + bit * 16 + 16)) for bit in range(9, 21)},
        21: list(range(322, 334)) + [335, 336, 338, 339],
        22: [340, 344, 345] + list(range(347, 353)) + list(range(365, 372)),
        **{bit: list(range(4 + bit * 16, 4 + bit * 16 + 16)) for bit in range(23, 31)},
    }

    DEFAULT_ON_CHANGE_PARAMS: list[int] = [
        5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 25,
        32, 33, 34, 37, 38, 39, 40, 41, 42, 43, 60, 97, 99, 100, 101,
        107, 108, 109, 111, 353, 357, 360, 362, 364,
        375, 376, 377, 378, 379, 380, 381,
        127, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140,
        143, 147, 151, 155, 159, 163, 167, 171, 175, 179, 183, 187, 191,
        195, 199, 203, 207, 211, 215, 219, 223, 227, 231, 235, 239, 243,
        247, 251, 255, 259, 263, 267, 271, 275, 279, 283, 287, 291, 295,
        299, 303, 307, 311, 315, 319, 323, 327, 329, 330, 331, 332, 333,
        335, 336, 347, 348, 349, 350, 351,
    ]

    DEFAULT_DAILY_PARAMS: list[int] = [
        18, 19, 46, 48, 50, 52, 54, 56, 58, 59, 88, 89, 352,
    ]

    def __init__(self) -> None:
        self.name: str = 'AhlLib'
        self.logger = logger
        self.database: dict[int, AhlParam] = {}
        self.params_system: Type[AhlParamSystem] = AhlParamSystem
        self.params_settings: Type[AhlParamSettings] = AhlParamSettings
        self.params_information: Type[AhlParamInformation] = AhlParamInformation
        self.params_configuration: Type[AhlParamConfiguration] = AhlParamConfiguration
        self.params_lighting: Type[AhlParamLighting] = AhlParamLighting
        self.params_power: Type[AhlParamPower] = AhlParamPower
        self.params_alarms: Type[AhlParamAlarms] = AhlParamAlarms
        self.params_hardware: Type[AhlParamHardware] = AhlParamHardware
        self.params_software: Type[AhlParamSoftware] = AhlParamSoftware
        self.params_network: Type[AhlParamNetwork] = AhlParamNetwork
        self.params_alarm_details: Type[AhlParamAlarmDetails] = AhlParamAlarmDetails
        self.__init_database()
        self.error_codes = MbCode
        self._polling_table: dict[int, list[int]] = self._OLD_POLLING_TABLE

    def get_param(self, param: int) -> tuple[Any, str]:
        """Return a parameter if it exists in the database.

        Args:
            param: Parameter number for wanted param.

        Returns:
            Tuple of (value, error_code_name).
        """
        if param not in self.database:
            self.logger.error(f"Param {param} not in AHL database")
            return -1, self.error_codes.PARAM_NOT_IN_DB.name

        val = self.database[param].value
        if val is None:
            self.logger.error(f"Value for param {param} not set. Has the param been polled?")
            return -1, self.error_codes.PARAM_NOT_SET.name

        return val, self.error_codes.NO_ERR.name

    def set_param(self, param: int, value: int) -> tuple[list[int], str]:
        """Set a parameter value.

        Args:
            param: Parameter number to set.
            value: New value.

        Returns:
            Tuple of ([param] if changed else [], error_code_name).
        """
        if param not in self.database:
            self.logger.error(f"Param {param} not in AHL database")
            return [], self.error_codes.PARAM_NOT_IN_DB.name

        if self.database[param].value == value:
            return [], self.error_codes.NO_ERR.name

        self.database[param].value = value
        return [param], self.error_codes.NO_ERR.name

    def set_polling_table(self, new_table: bool) -> None:
        """Select which polling table to use based on firmware version.

        Args:
            new_table: True for new firmware (param 127 readable), False for old.
        """
        self._polling_table = self._NEW_POLLING_TABLE if new_table else self._OLD_POLLING_TABLE

    def decode_change_flags(self, bitmask: int) -> list[int]:
        """Decode the 31-bit PARAM_POLLING bitmask into parameter IDs.

        Args:
            bitmask: Integer value read from PARAM_POLLING (register 2).

        Returns:
            List of parameter IDs that have changed, ordered by bit index.
        """
        changed: list[int] = []
        for bit in range(31):
            if bitmask & (1 << bit):
                changed.extend(self._polling_table.get(bit, []))
        return changed

    async def poll_params(self, handler: Any) -> list[int]:
        """Poll AHL lift for changed parameters via bitmask.

        Reads PARAM_POLLING (register 2), decodes the bitmask to find
        which parameter groups changed, reads each changed param from
        hardware, and updates the local database.

        Args:
            handler: ModBusHandler instance for hardware communication.

        Returns:
            List of parameter IDs whose values actually changed.
        """
        # Read the change-flags bitmask (param 2)
        value, _, code = await asyncio.to_thread(
            handler.read_parameter, ["2"]
        )
        if code != MbCode.NO_ERR.name:
            self.logger.warning("Failed to read PARAM_POLLING: %s", code)
            return []

        bitmask = int(value)
        if bitmask == 0:
            return []

        candidate_params = self.decode_change_flags(bitmask)
        changed: list[int] = []

        for param_id in candidate_params:
            if param_id not in self.database:
                continue
            val, _, read_code = await asyncio.to_thread(
                handler.read_parameter, [str(param_id)]
            )
            if read_code != MbCode.NO_ERR.name:
                continue
            updated, _ = self.set_param(param_id, int(val))
            changed.extend(updated)

        return changed

    def available_params(self) -> KeysView[int]:
        """Get list of all available parameters.

        Returns:
            All param IDs in the database.
        """
        return self.database.keys()

    def get_writable_params(self) -> list[int]:
        """Get list of writable parameter IDs (access='RW').

        Returns:
            List of param IDs with RW access.
        """
        return [pid for pid, p in self.database.items() if p.access == 'RW']

    def get_readable_params(self) -> list[int]:
        """Get list of readable parameter IDs (access='R' or 'RW').

        Returns:
            List of param IDs with R or RW access.
        """
        return [pid for pid, p in self.database.items() if p.access in ('R', 'RW')]

    def __init_database(self) -> None:
        """Populate the database with all AHL parameters from the specification."""
        self.database[self.params_system.PARAM_LIFT_INTERFACE_USED.value] = AhlParam(0, 'PARAM_LIFT_INTERFACE_USED', 'Lift interface used', 'R', '')
        self.database[self.params_system.PARAM_LIFT_SUPPORTED_INTERFACE_VERSIONS.value] = AhlParam(1, 'PARAM_LIFT_SUPPORTED_INTERFACE_VERSIONS', 'Lift supported interface versions', 'R', '')
        self.database[self.params_system.PARAM_POLLING.value] = AhlParam(2, 'PARAM_POLLING', 'Polling registers', 'R', '')
        self.database[self.params_system.PARAM_GATEWAY_STATUS.value] = AhlParam(3, 'PARAM_GATEWAY_STATUS', 'Gateway status', 'R', '')
        self.database[self.params_system.PARAM_TIME.value] = AhlParam(4, 'PARAM_TIME', 'Network time', 'R', '')
        self.database[self.params_lighting.PARAM_PLATFORM_LIGHT_ON_TIME.value] = AhlParam(5, 'PARAM_PLATFORM_LIGHT_ON_TIME', 'Platform light on time', 'RW', 'min')
        self.database[self.params_lighting.PARAM_LIGHT_DIM_TIME.value] = AhlParam(6, 'PARAM_LIGHT_DIM_TIME', 'Light dim time', 'RW', 'min')
        self.database[self.params_lighting.PARAM_LIGHT_SWITCH.value] = AhlParam(7, 'PARAM_LIGHT_SWITCH', 'Light switch', 'RW', 'bool')
        self.database[self.params_settings.PARAM_DOOR_DWELL_TIME.value] = AhlParam(8, 'PARAM_DOOR_DWELL_TIME', 'Door Dwell Time', 'RW', 's')
        self.database[self.params_settings.PARAM_EXTENDED_DOOR_DWELL_TIME.value] = AhlParam(9, 'PARAM_EXTENDED_DOOR_DWELL_TIME', 'Extended Door Dwell Time', 'RW', 's')
        self.database[self.params_settings.PARAM_FIRE_DRIVE_POLARITY.value] = AhlParam(10, 'PARAM_FIRE_DRIVE_POLARITY', 'Fire Drive Polarity', 'R', 'Bool')
        self.database[self.params_settings.PARAM_FIRE_DRIVE_FLOOR.value] = AhlParam(11, 'PARAM_FIRE_DRIVE_FLOOR', 'Fire Drive Floor', 'R', '#')
        self.database[self.params_settings.PARAM_FLOOR1_LEVEL_ADJUST.value] = AhlParam(12, 'PARAM_FLOOR1_LEVEL_ADJUST', 'Floor1 Level Adjust', 'RW', 'mm')
        self.database[self.params_settings.PARAM_FLOOR2_LEVEL_ADJUST.value] = AhlParam(13, 'PARAM_FLOOR2_LEVEL_ADJUST', 'Floor2 Level Adjust', 'RW', 'mm')
        self.database[self.params_settings.PARAM_FLOOR3_LEVEL_ADJUST.value] = AhlParam(14, 'PARAM_FLOOR3_LEVEL_ADJUST', 'Floor3 Level Adjust', 'RW', 'mm')
        self.database[self.params_settings.PARAM_FLOOR4_LEVEL_ADJUST.value] = AhlParam(15, 'PARAM_FLOOR4_LEVEL_ADJUST', 'Floor4 Level Adjust', 'RW', 'mm')
        self.database[self.params_settings.PARAM_FLOOR5_LEVEL_ADJUST.value] = AhlParam(16, 'PARAM_FLOOR5_LEVEL_ADJUST', 'Floor5 Level Adjust', 'RW', 'mm')
        self.database[self.params_settings.PARAM_FLOOR6_LEVEL_ADJUST.value] = AhlParam(17, 'PARAM_FLOOR6_LEVEL_ADJUST', 'Floor6 Level Adjust', 'RW', 'mm')
        self.database[self.params_information.PARAM_TOTAL_RUNTIME.value] = AhlParam(18, 'PARAM_TOTAL_RUNTIME', 'Total Runtime', 'R', 's')
        self.database[self.params_information.PARAM_TOTAL_RUN_TRAVEL.value] = AhlParam(19, 'PARAM_TOTAL_RUN_TRAVEL', 'Total Run Travel', 'R', 'm')
        self.database[self.params_information.PARAM_SAFETY_CHAIN_STATUS.value] = AhlParam(20, 'PARAM_SAFETY_CHAIN_STATUS', 'Safety chain status', 'R', 'bool')
        self.database[self.params_information.PARAM_LOAD_SENSOR.value] = AhlParam(21, 'PARAM_LOAD_SENSOR', 'Load sensor', 'R', 'kg')
        self.database[self.params_information.PARAM_CURRENT_POSITION.value] = AhlParam(22, 'PARAM_CURRENT_POSITION', 'Current position', 'R', 'mm')
        self.database[self.params_information.PARAM_LAST_POSITION_SYNC.value] = AhlParam(23, 'PARAM_LAST_POSITION_SYNC', 'Last position sync', 'R', 'm')
        self.database[self.params_information.PARAM_LAST_SYNC_DIFFERENCE.value] = AhlParam(24, 'PARAM_LAST_SYNC_DIFFERENCE', 'Last sync difference', 'R', 'mm')
        self.database[self.params_information.PARAM_EMERGENCY_STOP_STATUS.value] = AhlParam(25, 'PARAM_EMERGENCY_STOP_STATUS', 'Emergency stop status', 'R', 'bool')
        self.database[self.params_information.PARAM_RUN_SIGNAL.value] = AhlParam(26, 'PARAM_RUN_SIGNAL', 'Run signal', 'R', 'bool')
        self.database[self.params_network.PARAM_NUM_OF_DCMS.value] = AhlParam(27, 'PARAM_NUM_OF_DCMS', 'Num of DCMs', 'R', '#')
        self.database[self.params_network.PARAM_ONLINE_UNITS.value] = AhlParam(28, 'PARAM_ONLINE_UNITS', 'Online units', 'R', '#')
        self.database[self.params_information.PARAM_PLATFORM_SIZE.value] = AhlParam(29, 'PARAM_PLATFORM_SIZE', 'Platform size', 'R', '')
        self.database[self.params_configuration.PARAM_RATED_SPEED.value] = AhlParam(30, 'PARAM_RATED_SPEED', 'Rated Speed', 'R', 'mm/s')
        self.database[self.params_configuration.PARAM_AUTOMATIC_RUN.value] = AhlParam(31, 'PARAM_AUTOMATIC_RUN', 'Automatic run', 'R', '')
        self.database[self.params_settings.PARAM_LUBRICATION_TIME.value] = AhlParam(32, 'PARAM_LUBRICATION_TIME', 'Lubrication time', 'RW', 's')
        self.database[self.params_settings.PARAM_LUBRICATION_INTERVAL.value] = AhlParam(33, 'PARAM_LUBRICATION_INTERVAL', 'Lubrication interval', 'RW', 'h')
        self.database[self.params_settings.PARAM_ACCUMULATED_LUBRICATION_TIME_SINCE_REFILL.value] = AhlParam(34, 'PARAM_ACCUMULATED_LUBRICATION_TIME_SINCE_REFILL', 'Accumulated lubrication time since refill', 'R', 's')
        self.database[self.params_settings.PARAM_TOTAL_LUBRICATION_TIME_FOR_FULL_CONTAINER.value] = AhlParam(35, 'PARAM_TOTAL_LUBRICATION_TIME_FOR_FULL_CONTAINER', 'Total lubrication time for full container', 'RW', 's')
        self.database[self.params_lighting.PARAM_SHAFT_COLOUR.value] = AhlParam(37, 'PARAM_SHAFT_COLOUR', 'Shaft Colour', 'RW', '#')
        self.database[self.params_lighting.PARAM_SHAFT_WHITE_LEVEL.value] = AhlParam(38, 'PARAM_SHAFT_WHITE_LEVEL', 'Shaft White Level', 'RW', '#')
        self.database[self.params_lighting.PARAM_SHAFT_LED_TYPE.value] = AhlParam(39, 'PARAM_SHAFT_LED_TYPE', 'Shaft Led Type', 'RW', '#')
        self.database[self.params_lighting.PARAM_PLATFORM_WHITE_DIM_LEVEL.value] = AhlParam(40, 'PARAM_PLATFORM_WHITE_DIM_LEVEL', 'Platform White Dim level', 'RW', '')
        self.database[self.params_lighting.PARAM_DIM_SHAFT_COLOUR_OBSOLETE.value] = AhlParam(41, 'PARAM_DIM_SHAFT_COLOUR_OBSOLETE', 'Dim Shaft Colour', 'RW', '')
        self.database[self.params_lighting.PARAM_SHAFT_WHITE_DIM_LEVEL_OBSOLETE.value] = AhlParam(42, 'PARAM_SHAFT_WHITE_DIM_LEVEL_OBSOLETE', 'Shaft White Dim Level', 'R', '#')
        self.database[self.params_configuration.PARAM_NUM_OF_FLOORS.value] = AhlParam(43, 'PARAM_NUM_OF_FLOORS', 'Num of Floors', 'R', '#')
        self.database[self.params_lighting.PARAM_LIGHT_RAMP_UP_TIME.value] = AhlParam(44, 'PARAM_LIGHT_RAMP_UP_TIME', 'Light ramp up time', 'RW', 's')
        self.database[self.params_lighting.PARAM_LIGHT_RAMP_DOWN_TIME.value] = AhlParam(45, 'PARAM_LIGHT_RAMP_DOWN_TIME', 'Light ramp down time', 'RW', 's')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_1.value] = AhlParam(46, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_1', 'Total number door opened 1', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_2.value] = AhlParam(47, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_2', 'Total number door opened 2', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_3.value] = AhlParam(48, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_3', 'Total number door opened 3', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_4.value] = AhlParam(49, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_4', 'Total number door opened 4', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_5.value] = AhlParam(50, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_5', 'Total number door opened 5', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_6.value] = AhlParam(51, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_6', 'Total number door opened 6', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_7.value] = AhlParam(52, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_7', 'Total number door opened 7', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_8.value] = AhlParam(53, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_8', 'Total number door opened 8', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_9.value] = AhlParam(54, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_9', 'Total number door opened 9', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_10.value] = AhlParam(55, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_10', 'Total number door opened 10', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_11.value] = AhlParam(56, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_11', 'Total number door opened 11', 'R', '#')
        self.database[self.params_information.PARAM_TOTAL_NUMBER_DOOR_OPENED_12.value] = AhlParam(57, 'PARAM_TOTAL_NUMBER_DOOR_OPENED_12', 'Total number door opened 12', 'R', '#')
        self.database[self.params_power.PARAM_BATTERY_VOLTAGE.value] = AhlParam(58, 'PARAM_BATTERY_VOLTAGE', 'Battery voltage', 'R', 'mV')
        self.database[self.params_power.PARAM_BATTERY_CURRENT.value] = AhlParam(59, 'PARAM_BATTERY_CURRENT', 'Battery current', 'R', 'mA')
        self.database[self.params_power.PARAM_BATTERY_CONDITION.value] = AhlParam(60, 'PARAM_BATTERY_CONDITION', 'Battery condition', 'R', 'bool')
        self.database[self.params_power.PARAM_BATTERY_CHARGER_STATUS.value] = AhlParam(61, 'PARAM_BATTERY_CHARGER_STATUS', 'Battery charger status', 'R', 'bool')
        self.database[self.params_settings.PARAM_SERVICE_INTERVAL.value] = AhlParam(62, 'PARAM_SERVICE_INTERVAL', 'Service interval', 'R', 'month')
        self.database[self.params_settings.PARAM_SERVICE_INDICATOR_RESET.value] = AhlParam(63, 'PARAM_SERVICE_INDICATOR_RESET', 'Service indicator reset', 'R', 'bool')
        self.database[self.params_information.PARAM_LATEST_LCM_BOOT.value] = AhlParam(64, 'PARAM_LATEST_LCM_BOOT', 'Latest LCM boot', 'R', 's')
        self.database[self.params_information.PARAM_LATEST_TEACH.value] = AhlParam(65, 'PARAM_LATEST_TEACH', 'Latest teach', 'R', 's')
        self.database[self.params_information.PARAM_LATEST_DC_MOTOR_START.value] = AhlParam(66, 'PARAM_LATEST_DC_MOTOR_START', 'Latest DC motor start', 'R', 's')
        self.database[self.params_hardware.PARAM_LCM_HARDWARE_VERSION.value] = AhlParam(67, 'PARAM_LCM_HARDWARE_VERSION', 'LCM hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_SPM_HARDWARE_VERSION.value] = AhlParam(68, 'PARAM_SPM_HARDWARE_VERSION', 'SPM hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_CPM_HARDWARE_VERSION.value] = AhlParam(69, 'PARAM_CPM_HARDWARE_VERSION', 'CPM hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_DCM1_HARDWARE_VERSION.value] = AhlParam(70, 'PARAM_DCM1_HARDWARE_VERSION', 'DCM1 hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_DCM2_HARDWARE_VERSION.value] = AhlParam(71, 'PARAM_DCM2_HARDWARE_VERSION', 'DCM2 hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_DCM3_HARDWARE_VERSION.value] = AhlParam(72, 'PARAM_DCM3_HARDWARE_VERSION', 'DCM3 hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_DCM4_HARDWARE_VERSION.value] = AhlParam(73, 'PARAM_DCM4_HARDWARE_VERSION', 'DCM4 hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_DCM5_HARDWARE_VERSION.value] = AhlParam(74, 'PARAM_DCM5_HARDWARE_VERSION', 'DCM5 hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_DCM6_HARDWARE_VERSION.value] = AhlParam(75, 'PARAM_DCM6_HARDWARE_VERSION', 'DCM6 hardware version', 'R', '#')
        self.database[self.params_hardware.PARAM_LMM_HARDWARE_VERSION.value] = AhlParam(76, 'PARAM_LMM_HARDWARE_VERSION', 'LMM hardware version', 'R', '#')
        self.database[self.params_software.PARAM_LCM_SOFTWARE_VERSION.value] = AhlParam(77, 'PARAM_LCM_SOFTWARE_VERSION', 'LCM software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_SPM_SOFTWARE_VERSION.value] = AhlParam(78, 'PARAM_SPM_SOFTWARE_VERSION', 'SPM software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_CPM_SOFTWARE_VERSION.value] = AhlParam(79, 'PARAM_CPM_SOFTWARE_VERSION', 'CPM software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_DCM1_SOFTWARE_VERSION.value] = AhlParam(80, 'PARAM_DCM1_SOFTWARE_VERSION', 'DCM1 software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_DCM2_SOFTWARE_VERSION.value] = AhlParam(81, 'PARAM_DCM2_SOFTWARE_VERSION', 'DCM2 software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_DCM3_SOFTWARE_VERSION.value] = AhlParam(82, 'PARAM_DCM3_SOFTWARE_VERSION', 'DCM3 software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_DCM4_SOFTWARE_VERSION.value] = AhlParam(83, 'PARAM_DCM4_SOFTWARE_VERSION', 'DCM4 software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_DCM5_SOFTWARE_VERSION.value] = AhlParam(84, 'PARAM_DCM5_SOFTWARE_VERSION', 'DCM5 software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_DCM6_SOFTWARE_VERSION.value] = AhlParam(85, 'PARAM_DCM6_SOFTWARE_VERSION', 'DCM6 software version', 'R', 'XYZ')
        self.database[self.params_software.PARAM_LMM_SOFTWARE_VERSION.value] = AhlParam(86, 'PARAM_LMM_SOFTWARE_VERSION', 'LMM software version', 'R', 'XYZ')
        self.database[self.params_information.PARAM_EMERGENCY_MODE_STATUS.value] = AhlParam(87, 'PARAM_EMERGENCY_MODE_STATUS', 'Emergency mode status', 'R', 'bool')
        self.database[self.params_information.PARAM_NUMBER_OF_STARTS_ON_AC_MOTOR.value] = AhlParam(88, 'PARAM_NUMBER_OF_STARTS_ON_AC_MOTOR', 'Number of starts on AC motor', 'R', '#')
        self.database[self.params_information.PARAM_NUMBER_OF_STARTS_DC_MOTOR.value] = AhlParam(89, 'PARAM_NUMBER_OF_STARTS_DC_MOTOR', 'Number of starts DC motor', 'R', '#')
        self.database[self.params_power.PARAM_BATTERY_RUNTIME.value] = AhlParam(90, 'PARAM_BATTERY_RUNTIME', 'Battery runtime', 'R', 's')
        self.database[self.params_settings.PARAM_LIFT_BLOCK.value] = AhlParam(91, 'PARAM_LIFT_BLOCK', 'Lift block', 'R', '#')
        self.database[self.params_settings.PARAM_SEND_LIFT_TO_LANDING.value] = AhlParam(92, 'PARAM_SEND_LIFT_TO_LANDING', 'Send lift to landing', 'R', '#')
        self.database[self.params_settings.PARAM_REMOTE_CONTROL_ENABLE.value] = AhlParam(93, 'PARAM_REMOTE_CONTROL_ENABLE', 'Remote control enable', 'R', 'bool')
        self.database[self.params_information.PARAM_LOAD_SENSOR_CAL_0.value] = AhlParam(94, 'PARAM_LOAD_SENSOR_CAL_0', 'Load sensor cal 0', 'R', '')
        self.database[self.params_settings.PARAM_LOAD_SENSOR_CAL_LOAD.value] = AhlParam(95, 'PARAM_LOAD_SENSOR_CAL_LOAD', 'Load sensor cal load', 'R', '')
        self.database[self.params_information.PARAM_AR_NUMBER.value] = AhlParam(96, 'PARAM_AR_NUMBER', 'AR number', 'R', '#')
        self.database[self.params_information.PARAM_LIGHT_ALWAYS_ON.value] = AhlParam(97, 'PARAM_LIGHT_ALWAYS_ON', 'Light always on', 'R', '#')
        self.database[self.params_system.PARAM_RESET_PARAMETERS.value] = AhlParam(98, 'PARAM_RESET_PARAMETERS', 'Reset parameters', 'RW', '#')
        self.database[self.params_alarms.PARAM_ACTIVE_ALARM_LEVEL_1.value] = AhlParam(99, 'PARAM_ACTIVE_ALARM_LEVEL_1', 'Active alarm level 1', 'R', '#')
        self.database[self.params_alarms.PARAM_ACTIVE_ALARM_LEVEL_2.value] = AhlParam(100, 'PARAM_ACTIVE_ALARM_LEVEL_2', 'Active alarm level 2', 'R', '#')
        self.database[self.params_alarms.ACTIVE_ALARM_LEVEL_3.value] = AhlParam(101, '', 'Active alarm level 3', 'R', '#')
        self.database[self.params_alarms.PARAM_RESET_ALARM_LEVEL_1.value] = AhlParam(102, 'PARAM_RESET_ALARM_LEVEL_1', 'Reset alarm level 1', 'R', '#')
        self.database[self.params_alarms.PARAM_RESET_ALARM_LEVEL_2.value] = AhlParam(103, 'PARAM_RESET_ALARM_LEVEL_2', 'Reset alarm level 2', 'R', '#')
        self.database[self.params_alarms.PARAM_RESET_ALARM_LEVEL_3.value] = AhlParam(104, 'PARAM_RESET_ALARM_LEVEL_3', 'Reset alarm level 3', 'R', '#')
        self.database[self.params_information.PARAM_ELEVATOR_TYPE.value] = AhlParam(105, 'PARAM_ELEVATOR_TYPE', 'Elevator type', 'R', '#')
        self.database[self.params_settings.PARAM_VFD_TYPE.value] = AhlParam(106, 'PARAM_VFD_TYPE', 'VFD type', 'R', '#')
        self.database[self.params_software.PARAM_FILE_DOWNLOAD_STATUS.value] = AhlParam(107, 'PARAM_FILE_DOWNLOAD_STATUS', 'File download status', 'RW', '#')
        self.database[self.params_software.PARAM_SW_INSTALLATION_CMD.value] = AhlParam(108, 'PARAM_SW_INSTALLATION_CMD', 'SW installation cmd', 'RW', '#')
        self.database[self.params_lighting.PARAM_SERVICE_LIGHT.value] = AhlParam(109, 'PARAM_SERVICE_LIGHT', 'Service Light', 'RW', '#')
        self.database[self.params_software.PARAM_UP_VERSION.value] = AhlParam(110, 'PARAM_UP_VERSION', 'UP Version', 'R', '')
        self.database[self.params_software.PARAM_SW_UPGRADE_ERROR_CODE.value] = AhlParam(111, 'PARAM_SW_UPGRADE_ERROR_CODE', 'SW upgrade error code', 'R', '')
        self.database[self.params_network.PARAM_REGISTERED_UNITS.value] = AhlParam(112, 'PARAM_REGISTERED_UNITS', 'Registered units', 'R', '#')
        self.database[self.params_hardware.PARAM_LCM_SERIAL_NUMBER.value] = AhlParam(113, 'PARAM_LCM_SERIAL_NUMBER', 'LCM serial number', 'R', '')
        self.database[self.params_hardware.PARAM_SPM_SERIAL_NUMBER.value] = AhlParam(114, 'PARAM_SPM_SERIAL_NUMBER', 'SPM serial number', 'R', '')
        self.database[self.params_hardware.PARAM_CPM_SERIAL_NUMBER.value] = AhlParam(115, 'PARAM_CPM_SERIAL_NUMBER', 'CPM serial number', 'R', '')
        self.database[self.params_hardware.PARAM_DCM1_SERIAL_NUMBER.value] = AhlParam(116, 'PARAM_DCM1_SERIAL_NUMBER', 'DCM1 serial number', 'R', '')
        self.database[self.params_hardware.PARAM_DCM2_SERIAL_NUMBER.value] = AhlParam(117, 'PARAM_DCM2_SERIAL_NUMBER', 'DCM2 serial number', 'R', '')
        self.database[self.params_hardware.PARAM_DCM3_SERIAL_NUMBER.value] = AhlParam(118, 'PARAM_DCM3_SERIAL_NUMBER', 'DCM3 serial number', 'R', '')
        self.database[self.params_hardware.PARAM_DCM4_SERIAL_NUMBER.value] = AhlParam(119, 'PARAM_DCM4_SERIAL_NUMBER', 'DCM4 serial number', 'R', '')
        self.database[self.params_hardware.PARAM_DCM5_SERIAL_NUMBER.value] = AhlParam(120, 'PARAM_DCM5_SERIAL_NUMBER', 'DCM5 serial number', 'R', '')
        self.database[self.params_hardware.PARAM_DCM6_SERIAL_NUMBER.value] = AhlParam(121, 'PARAM_DCM6_SERIAL_NUMBER', 'DCM6 serial number', 'R', '')
        self.database[self.params_hardware.PARAM_LMM_SERIAL_NUMBER.value] = AhlParam(122, 'PARAM_LMM_SERIAL_NUMBER', 'LMM serial number', 'R', '')
        self.database[self.params_system.PARAM_REGISTER_HASH_1.value] = AhlParam(123, 'PARAM_REGISTER_HASH_1', 'Register hash 1', 'RW', '')
        self.database[self.params_system.PARAM_REGISTER_HASH_2.value] = AhlParam(124, 'PARAM_REGISTER_HASH_2', 'Register hash 2', 'RW', '')
        self.database[self.params_system.PARAM_REGISTER_HASH_3.value] = AhlParam(125, 'PARAM_REGISTER_HASH_3', 'Register hash 3', 'RW', '')
        self.database[self.params_system.PARAM_REGISTER_HASH_4.value] = AhlParam(126, 'PARAM_REGISTER_HASH_4', 'Register hash 4', 'RW', '')
        self.database[self.params_system.PARAM_REFERENCE_POSITION.value] = AhlParam(127, 'PARAM_REFERENCE_POSITION', 'Reference position', 'R', '')
        self.database[self.params_system.PARAM_REFERENCE_DELTA.value] = AhlParam(128, 'PARAM_REFERENCE_DELTA', 'Reference delta', 'R', '')
        self.database[self.params_configuration.PARAM_DCM_1_ADDRESS.value] = AhlParam(129, 'PARAM_DCM_1_ADDRESS', 'DCM 1 address', 'R', '')
        self.database[self.params_configuration.PARAM_DCM_2_ADDRESS.value] = AhlParam(130, 'PARAM_DCM_2_ADDRESS', 'DCM 2 address', 'R', '')
        self.database[self.params_configuration.PARAM_DCM_3_ADDRESS.value] = AhlParam(131, 'PARAM_DCM_3_ADDRESS', 'DCM 3 address', 'R', '')
        self.database[self.params_configuration.PARAM_DCM_4_ADDRESS.value] = AhlParam(132, 'PARAM_DCM_4_ADDRESS', 'DCM 4 address', 'R', '')
        self.database[self.params_configuration.PARAM_DCM_5_ADDRESS.value] = AhlParam(133, 'PARAM_DCM_5_ADDRESS', 'DCM 5 address', 'R', '')
        self.database[self.params_configuration.PARAM_DCM_6_ADDRESS.value] = AhlParam(134, 'PARAM_DCM_6_ADDRESS', 'DCM 6 address', 'R', '')
        self.database[self.params_configuration.PARAM_FLOOR_1_POSITION.value] = AhlParam(135, 'PARAM_FLOOR_1_POSITION', 'Floor 1 position', 'R', '')
        self.database[self.params_configuration.PARAM_FLOOR_2_POSITION.value] = AhlParam(136, 'PARAM_FLOOR_2_POSITION', 'Floor 2 position', 'R', '')
        self.database[self.params_configuration.PARAM_FLOOR_3_POSITION.value] = AhlParam(137, 'PARAM_FLOOR_3_POSITION', 'Floor 3 position', 'R', '')
        self.database[self.params_configuration.PARAM_FLOOR_4_POSITION.value] = AhlParam(138, 'PARAM_FLOOR_4_POSITION', 'Floor 4 position', 'R', '')
        self.database[self.params_configuration.PARAM_FLOOR_5_POSITION.value] = AhlParam(139, 'PARAM_FLOOR_5_POSITION', 'Floor 5 position', 'R', '')
        self.database[self.params_configuration.PARAM_FLOOR_6_POSITION.value] = AhlParam(140, 'PARAM_FLOOR_6_POSITION', 'Floor 6 position', 'R', '')
        self.database[self.params_alarm_details.PARAM_DOOR_STUCK_OPEN.value] = AhlParam(141, 'PARAM_DOOR_STUCK_OPEN', 'Door stuck open', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_1.value] = AhlParam(142, 'PARAM_TIME_OCCURRENCE_1', 'Lastest Door stuck open alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_1.value] = AhlParam(143, 'PARAM_NUM_OF_OCCURENCES_1', 'Number of Door stuck open alams', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_1.value] = AhlParam(144, 'PARAM_TIME_ACKNOWLEDGE_1', 'Latest Door stuck open alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_DOOR_STUCK_CLOSED.value] = AhlParam(145, 'PARAM_DOOR_STUCK_CLOSED', 'Door stuck closed', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_2.value] = AhlParam(146, 'PARAM_TIME_OCCURRENCE_2', 'Latest Door stuck closed alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_2.value] = AhlParam(147, 'PARAM_NUM_OF_OCCURENCES_2', 'Number of Door stuck closed alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_2.value] = AhlParam(148, 'PARAM_TIME_ACKNOWLEDGE_2', 'Latest Door stuck closed alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_LOCK_STUCK_OPEN.value] = AhlParam(149, 'PARAM_LOCK_STUCK_OPEN', 'Lock stuck open', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_3.value] = AhlParam(150, 'PARAM_TIME_OCCURRENCE_3', 'Latest Lock stuck open alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_3.value] = AhlParam(151, 'PARAM_NUM_OF_OCCURENCES_3', 'Number of Lock stuck open alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_3.value] = AhlParam(152, 'PARAM_TIME_ACKNOWLEDGE_3', 'Latest Lock stuck open alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_LOCK_STUCK_CLOSED.value] = AhlParam(153, 'PARAM_LOCK_STUCK_CLOSED', 'Lock stuck closed', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_4.value] = AhlParam(154, 'PARAM_TIME_OCCURRENCE_4', 'Latest Lock stuck closed alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_4.value] = AhlParam(155, 'PARAM_NUM_OF_OCCURENCES_4', 'Number of Lock stuck closed alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_4.value] = AhlParam(156, 'PARAM_TIME_ACKNOWLEDGE_4', 'Latest Lock stuck closed alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_POWER_FAILURE.value] = AhlParam(157, 'PARAM_POWER_FAILURE', 'Power failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_5.value] = AhlParam(158, 'PARAM_TIME_OCCURRENCE_5', 'Latest Power failure alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_5.value] = AhlParam(159, 'PARAM_NUM_OF_OCCURENCES_5', 'Number of Power failure alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_5.value] = AhlParam(160, 'PARAM_TIME_ACKNOWLEDGE_5', 'Latest Power failure alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_SC_OPENED.value] = AhlParam(161, 'PARAM_SC_OPENED', 'SC opened', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_6.value] = AhlParam(162, 'PARAM_TIME_OCCURRENCE_6', 'Latest Safty circuit open alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_6.value] = AhlParam(163, 'PARAM_NUM_OF_OCCURENCES_6', 'Number of Safty circuit open alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_6.value] = AhlParam(164, 'PARAM_TIME_ACKNOWLEDGE_6', 'Latest Safty Circuit open alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_1.value] = AhlParam(165, 'PARAM_NOT_USED_ALARM_1', 'NOT USED ALARM 1', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_7.value] = AhlParam(166, 'PARAM_TIME_OCCURRENCE_7', 'Time occurrence 7', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_7.value] = AhlParam(167, 'PARAM_NUM_OF_OCCURENCES_7', 'Num of occurences 7', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_7.value] = AhlParam(168, 'PARAM_TIME_ACKNOWLEDGE_7', 'Time acknowledge 7', 'R', '')
        self.database[self.params_alarm_details.PARAM_CHARGE_TERMINATION_FAILURE.value] = AhlParam(169, 'PARAM_CHARGE_TERMINATION_FAILURE', 'Charge termination failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_8.value] = AhlParam(170, 'PARAM_TIME_OCCURRENCE_8', 'Latest Charge termination failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_8.value] = AhlParam(171, 'PARAM_NUM_OF_OCCURENCES_8', 'Number of Charge termination failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_8.value] = AhlParam(172, 'PARAM_TIME_ACKNOWLEDGE_8', 'Latest Charge termination failure acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_OVERLOAD.value] = AhlParam(173, 'PARAM_OVERLOAD', 'Overload', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_9.value] = AhlParam(174, 'PARAM_TIME_OCCURRENCE_9', 'Latest Overload alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_9.value] = AhlParam(175, 'PARAM_NUM_OF_OCCURENCES_9', 'Number of Overload alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_9.value] = AhlParam(176, 'PARAM_TIME_ACKNOWLEDGE_9', 'Latest Overload alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_EMERGENCY_MODE.value] = AhlParam(177, 'PARAM_EMERGENCY_MODE', 'Emergency mode', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_10.value] = AhlParam(178, 'PARAM_TIME_OCCURRENCE_10', 'Latest Emergency mode', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_10.value] = AhlParam(179, 'PARAM_NUM_OF_OCCURENCES_10', 'Number of Emergency mode', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_10.value] = AhlParam(180, 'PARAM_TIME_ACKNOWLEDGE_10', 'Latest Emergency mode acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_CONTACTOR_FAILURE_MINOR.value] = AhlParam(181, 'PARAM_CONTACTOR_FAILURE_MINOR', 'Contactor failure minor', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_11.value] = AhlParam(182, 'PARAM_TIME_OCCURRENCE_11', 'Latest Contact failure minor alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_11.value] = AhlParam(183, 'PARAM_NUM_OF_OCCURENCES_11', 'Number of Contact failure minor alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_11.value] = AhlParam(184, 'PARAM_TIME_ACKNOWLEDGE_11', 'Latest Contact failure minor alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_BRAKE_SENSOR_MINOR.value] = AhlParam(185, 'PARAM_BRAKE_SENSOR_MINOR', 'Brake sensor minor', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_12.value] = AhlParam(186, 'PARAM_TIME_OCCURRENCE_12', 'Latest Break sensor minor alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_12.value] = AhlParam(187, 'PARAM_NUM_OF_OCCURENCES_12', 'Number of Break sensor minor alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_12.value] = AhlParam(188, 'PARAM_TIME_ACKNOWLEDGE_12', 'Latest Break sensor minor alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_LOSS_OF_POSITION.value] = AhlParam(189, 'PARAM_LOSS_OF_POSITION', 'Loss of position', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_13.value] = AhlParam(190, 'PARAM_TIME_OCCURRENCE_13', 'Latest Loss of position alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_13.value] = AhlParam(191, 'PARAM_NUM_OF_OCCURENCES_13', 'Number of Loss of position alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_13.value] = AhlParam(192, 'PARAM_TIME_ACKNOWLEDGE_13', 'Latest Loss of position alarm  acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_REFERENCE_DRIFT.value] = AhlParam(193, 'PARAM_REFERENCE_DRIFT', 'Reference drift', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_14.value] = AhlParam(194, 'PARAM_TIME_OCCURRENCE_14', 'Latest Reference drift alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_14.value] = AhlParam(195, 'PARAM_NUM_OF_OCCURENCES_14', 'Number of Reference drift alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_14.value] = AhlParam(196, 'PARAM_TIME_ACKNOWLEDGE_14', 'Latest Reference drift alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_REFERENCE_UPDATE_FAILURE.value] = AhlParam(197, 'PARAM_REFERENCE_UPDATE_FAILURE', 'Reference update failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_15.value] = AhlParam(198, 'PARAM_TIME_OCCURRENCE_15', 'Latest Reference update failure alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_15.value] = AhlParam(199, 'PARAM_NUM_OF_OCCURENCES_15', 'Number of Reference updated failure alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_15.value] = AhlParam(200, 'PARAM_TIME_ACKNOWLEDGE_15', 'Latest Reference update failure alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_FIRE_DETECTED.value] = AhlParam(201, 'PARAM_FIRE_DETECTED', 'Fire detected', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_16.value] = AhlParam(202, 'PARAM_TIME_OCCURRENCE_16', 'Latest Fire detected alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_16.value] = AhlParam(203, 'PARAM_NUM_OF_OCCURENCES_16', 'Number of Fire detected alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_16.value] = AhlParam(204, 'PARAM_TIME_ACKNOWLEDGE_16', 'Latest Fire detected alarm  acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_OIL_LEVEL_LOW.value] = AhlParam(205, 'PARAM_OIL_LEVEL_LOW', 'Oil level low', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_17.value] = AhlParam(206, 'PARAM_TIME_OCCURRENCE_17', 'Latest Oil level low alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_17.value] = AhlParam(207, 'PARAM_NUM_OF_OCCURENCES_17', 'Number of Oil level low alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_17.value] = AhlParam(208, 'PARAM_TIME_ACKNOWLEDGE_17', 'Latest Oil level low alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_HIGH_BATTERY_CURRENT.value] = AhlParam(209, 'PARAM_HIGH_BATTERY_CURRENT', 'High battery current', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_18.value] = AhlParam(210, 'PARAM_TIME_OCCURRENCE_18', 'Latest High battery current alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_18.value] = AhlParam(211, 'PARAM_NUM_OF_OCCURENCES_18', 'Number of High battery current alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_18.value] = AhlParam(212, 'PARAM_TIME_ACKNOWLEDGE_18', 'Latest High battery current alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_LIGHT_FAILURE.value] = AhlParam(213, 'PARAM_LIGHT_FAILURE', 'Light failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_19.value] = AhlParam(214, 'PARAM_TIME_OCCURRENCE_19', 'Latest Light failure alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_19.value] = AhlParam(215, 'PARAM_NUM_OF_OCCURENCES_19', 'Number of Light failure alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_19.value] = AhlParam(216, 'PARAM_TIME_ACKNOWLEDGE_19', 'Latest Light failure alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_4.value] = AhlParam(217, 'PARAM_NOT_USED_ALARM_4', 'NOT USED ALARM 4', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_20.value] = AhlParam(218, 'PARAM_TIME_OCCURRENCE_20', 'Time occurrence 20', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_20.value] = AhlParam(219, 'PARAM_NUM_OF_OCCURENCES_20', 'Num of occurences 20', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_20.value] = AhlParam(220, 'PARAM_TIME_ACKNOWLEDGE_20', 'Time acknowledge 20', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_5.value] = AhlParam(221, 'PARAM_NOT_USED_ALARM_5', 'NOT USED ALARM 5', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_21.value] = AhlParam(222, 'PARAM_TIME_OCCURRENCE_21', 'Time occurrence 21', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_21.value] = AhlParam(223, 'PARAM_NUM_OF_OCCURENCES_21', 'Num of occurences 21', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_21.value] = AhlParam(224, 'PARAM_TIME_ACKNOWLEDGE_21', 'Time acknowledge 21', 'R', '')
        self.database[self.params_alarm_details.PARAM_OIL_LEVEL_CRITICAL.value] = AhlParam(225, 'PARAM_OIL_LEVEL_CRITICAL', 'Oil level critical', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_22.value] = AhlParam(226, 'PARAM_TIME_OCCURRENCE_22', 'Latest Oil level critical alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_22.value] = AhlParam(227, 'PARAM_NUM_OF_OCCURENCES_22', 'Number of Oil level critical alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_22.value] = AhlParam(228, 'PARAM_TIME_ACKNOWLEDGE_22', 'Latest Oil level critical alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_VERSION_ERROR.value] = AhlParam(229, 'PARAM_VERSION_ERROR', 'Version error', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_23.value] = AhlParam(230, 'PARAM_TIME_OCCURRENCE_23', 'Latest Version error alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_23.value] = AhlParam(231, 'PARAM_NUM_OF_OCCURENCES_23', 'Number of Version error alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_23.value] = AhlParam(232, 'PARAM_TIME_ACKNOWLEDGE_23', 'Latest Version error alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NETWORK_FAILURE.value] = AhlParam(233, 'PARAM_NETWORK_FAILURE', 'Network failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_24.value] = AhlParam(234, 'PARAM_TIME_OCCURRENCE_24', 'Latest Network failure alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_24.value] = AhlParam(235, 'PARAM_NUM_OF_OCCURENCES_24', 'Number of Network failure alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_24.value] = AhlParam(236, 'PARAM_TIME_ACKNOWLEDGE_24', 'Latest Network failure alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_OSM_WRONG_TYPE.value] = AhlParam(237, 'PARAM_OSM_WRONG_TYPE', 'OSM wrong type', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_25.value] = AhlParam(238, 'PARAM_TIME_OCCURRENCE_25', 'Latest OSM wrong type alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_25.value] = AhlParam(239, 'PARAM_NUM_OF_OCCURENCES_25', 'Number of OSM wrong type alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_25.value] = AhlParam(240, 'PARAM_TIME_ACKNOWLEDGE_25', 'Latest OSM wrong type alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_7.value] = AhlParam(241, 'PARAM_NOT_USED_ALARM_7', 'NOT USED ALARM 7', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_26.value] = AhlParam(242, 'PARAM_TIME_OCCURRENCE_26', 'Time occurrence 26', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_26.value] = AhlParam(243, 'PARAM_NUM_OF_OCCURENCES_26', 'Num of occurences 26', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_26.value] = AhlParam(244, 'PARAM_TIME_ACKNOWLEDGE_26', 'Time acknowledge 26', 'R', '')
        self.database[self.params_alarm_details.PARAM_SHORT_CIRCUIT_CRITICAL.value] = AhlParam(245, 'PARAM_SHORT_CIRCUIT_CRITICAL', 'Short circuit critical', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_27.value] = AhlParam(246, 'PARAM_TIME_OCCURRENCE_27', 'Latest Short circuit critical alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_27.value] = AhlParam(247, 'PARAM_NUM_OF_OCCURENCES_27', 'Number of Short curcuit citical alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_27.value] = AhlParam(248, 'PARAM_TIME_ACKNOWLEDGE_27', 'Latest Short circuit critical alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_BATTERY_CONDITION_FAILURE.value] = AhlParam(249, 'PARAM_BATTERY_CONDITION_FAILURE', 'Battery condition failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_28.value] = AhlParam(250, 'PARAM_TIME_OCCURRENCE_28', 'Latest Battery condition failure alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_28.value] = AhlParam(251, 'PARAM_NUM_OF_OCCURENCES_28', 'Number of Battery condition failure alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_28.value] = AhlParam(252, 'PARAM_TIME_ACKNOWLEDGE_28', 'Latest Battery condition failure alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_LOW_BATTERY_VOLTAGE.value] = AhlParam(253, 'PARAM_LOW_BATTERY_VOLTAGE', 'Low battery voltage', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_29.value] = AhlParam(254, 'PARAM_TIME_OCCURRENCE_29', 'Latest Low battery alarm voltage', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_29.value] = AhlParam(255, 'PARAM_NUM_OF_OCCURENCES_29', 'Number of Low battery voltage alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_29.value] = AhlParam(256, 'PARAM_TIME_ACKNOWLEDGE_29', 'Latest Low battery voltage alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_10.value] = AhlParam(257, 'PARAM_NOT_USED_ALARM_10', 'NOT USED ALARM 10', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_30.value] = AhlParam(258, 'PARAM_TIME_OCCURRENCE_30', 'Time occurrence 30', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_30.value] = AhlParam(259, 'PARAM_NUM_OF_OCCURENCES_30', 'Num of occurences 30', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_30.value] = AhlParam(260, 'PARAM_TIME_ACKNOWLEDGE_30', 'Time acknowledge 30', 'R', '')
        self.database[self.params_alarm_details.PARAM_FINAL_LIMIT.value] = AhlParam(261, 'PARAM_FINAL_LIMIT', 'Final limit', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_31.value] = AhlParam(262, 'PARAM_TIME_OCCURRENCE_31', 'Latest Final limit alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_31.value] = AhlParam(263, 'PARAM_NUM_OF_OCCURENCES_31', 'Number of Final limit alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_31.value] = AhlParam(264, 'PARAM_TIME_ACKNOWLEDGE_31', 'Latest Final limit alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_STARTUP_FAILURE_CRITICAL.value] = AhlParam(265, 'PARAM_STARTUP_FAILURE_CRITICAL', 'Startup failure critical', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_32.value] = AhlParam(266, 'PARAM_TIME_OCCURRENCE_32', 'Latest Startup failure critical alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_32.value] = AhlParam(267, 'PARAM_NUM_OF_OCCURENCES_32', 'Number of Startup failure critical alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_32.value] = AhlParam(268, 'PARAM_TIME_ACKNOWLEDGE_32', 'Latest Startup failure critical alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_11.value] = AhlParam(269, 'PARAM_NOT_USED_ALARM_11', 'NOT USED ALARM 11', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_33.value] = AhlParam(270, 'PARAM_TIME_OCCURRENCE_33', 'Time occurrence 33', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_33.value] = AhlParam(271, 'PARAM_NUM_OF_OCCURENCES_33', 'Num of occurences 33', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_33.value] = AhlParam(272, 'PARAM_TIME_ACKNOWLEDGE_33', 'Time acknowledge 33', 'R', '')
        self.database[self.params_alarm_details.PARAM_REFERENCE_DRIFT_CRITICAL.value] = AhlParam(273, 'PARAM_REFERENCE_DRIFT_CRITICAL', 'Reference drift critical', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_34.value] = AhlParam(274, 'PARAM_TIME_OCCURRENCE_34', 'Latest Reference drift critical alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_34.value] = AhlParam(275, 'PARAM_NUM_OF_OCCURENCES_34', 'Number of Reference drift critical alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_34.value] = AhlParam(276, 'PARAM_TIME_ACKNOWLEDGE_34', 'Latest Reference drift critical alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_13.value] = AhlParam(277, 'PARAM_NOT_USED_ALARM_13', 'NOT USED ALARM 13', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_35.value] = AhlParam(278, 'PARAM_TIME_OCCURRENCE_35', 'Time occurrence 35', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_35.value] = AhlParam(279, 'PARAM_NUM_OF_OCCURENCES_35', 'Num of occurences 35', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_35.value] = AhlParam(280, 'PARAM_TIME_ACKNOWLEDGE_35', 'Time acknowledge 35', 'R', '')
        self.database[self.params_alarm_details.PARAM_BRAKE_SENSOR_CRITICAL.value] = AhlParam(281, 'PARAM_BRAKE_SENSOR_CRITICAL', 'Brake sensor critical', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_36.value] = AhlParam(282, 'PARAM_TIME_OCCURRENCE_36', 'Latest Brake sensor critical alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_36.value] = AhlParam(283, 'PARAM_NUM_OF_OCCURENCES_36', 'Number of Brake sensor critical alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_36.value] = AhlParam(284, 'PARAM_TIME_ACKNOWLEDGE_36', 'Latest Brake sensor critical alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_NOT_USED_ALARM_14.value] = AhlParam(285, 'PARAM_NOT_USED_ALARM_14', 'NOT USED ALARM 14', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_37.value] = AhlParam(286, 'PARAM_TIME_OCCURRENCE_37', 'Time occurrence 37', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_37.value] = AhlParam(287, 'PARAM_NUM_OF_OCCURENCES_37', 'Num of occurences 37', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_37.value] = AhlParam(288, 'PARAM_TIME_ACKNOWLEDGE_37', 'Time acknowledge 37', 'R', '')
        self.database[self.params_alarm_details.PARAM_OSM_TRIP.value] = AhlParam(289, 'PARAM_OSM_TRIP', 'OSM trip', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_38.value] = AhlParam(290, 'PARAM_TIME_OCCURRENCE_38', 'Latest OSM trip alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_38.value] = AhlParam(291, 'PARAM_NUM_OF_OCCURENCES_38', 'Number of OSM trip alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_38.value] = AhlParam(292, 'PARAM_TIME_ACKNOWLEDGE_38', 'Latest OSM trip alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_VFD_COM_FAILURE.value] = AhlParam(293, 'PARAM_VFD_COM_FAILURE', 'VFD COM failure', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_39.value] = AhlParam(294, 'PARAM_TIME_OCCURRENCE_39', 'Latest VFD COM failure alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_39.value] = AhlParam(295, 'PARAM_NUM_OF_OCCURENCES_39', 'Number of VFD COM failure alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_39.value] = AhlParam(296, 'PARAM_TIME_ACKNOWLEDGE_39', 'Latest VFD COM failure alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_REVERSE_MOTION_DETECTED.value] = AhlParam(297, 'PARAM_REVERSE_MOTION_DETECTED', 'Reverse motion detected', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_40.value] = AhlParam(298, 'PARAM_TIME_OCCURRENCE_40', 'Latest Reverse motion detected alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_40.value] = AhlParam(299, 'PARAM_NUM_OF_OCCURENCES_40', 'Number of Reverse motion detected alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_40.value] = AhlParam(300, 'PARAM_TIME_ACKNOWLEDGE_40', 'Latest Reverse motion detected alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_VFD_INTERNAL_ERROR.value] = AhlParam(301, 'PARAM_VFD_INTERNAL_ERROR', 'VFD internal error', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_41.value] = AhlParam(302, 'PARAM_TIME_OCCURRENCE_41', 'Latest VFD internal error alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_41.value] = AhlParam(303, 'PARAM_NUM_OF_OCCURENCES_41', 'Number of VFD internal error alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_41.value] = AhlParam(304, 'PARAM_TIME_ACKNOWLEDGE_41', 'Latest VFD internal error alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_BELT_SLIP.value] = AhlParam(305, 'PARAM_BELT_SLIP', 'Belt slip', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_42.value] = AhlParam(306, 'PARAM_TIME_OCCURRENCE_42', 'Latest Belt slip alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_42.value] = AhlParam(307, 'PARAM_NUM_OF_OCCURENCES_42', 'Number of Belt slip alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_42.value] = AhlParam(308, 'PARAM_TIME_ACKNOWLEDGE_42', 'Latest Belt slip alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_BRAKE_RESISTOR_TEMP.value] = AhlParam(309, 'PARAM_BRAKE_RESISTOR_TEMP', 'Brake resistor temp', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_43.value] = AhlParam(310, 'PARAM_TIME_OCCURRENCE_43', 'Latest Brake resistor temp alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_43.value] = AhlParam(311, 'PARAM_NUM_OF_OCCURENCES_43', 'Number of Brake resistor temp alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_43.value] = AhlParam(312, 'PARAM_TIME_ACKNOWLEDGE_43', 'Latest Brake resistor temp alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_PULSE_SENSOR_POSITION.value] = AhlParam(313, 'PARAM_PULSE_SENSOR_POSITION', 'Pulse sensor position', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_44.value] = AhlParam(314, 'PARAM_TIME_OCCURRENCE_44', 'Latest Pulse sensor position alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_44.value] = AhlParam(315, 'PARAM_NUM_OF_OCCURENCES_44', 'Number of Pulse sensor position alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_44.value] = AhlParam(316, 'PARAM_TIME_ACKNOWLEDGE_44', 'Latest Pulse sensor position alarm acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_DC_DRIVE_FAIL.value] = AhlParam(317, 'PARAM_DC_DRIVE_FAIL', 'DC drive fail', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_45.value] = AhlParam(318, 'PARAM_TIME_OCCURRENCE_45', 'Latest DC drive fail error', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_45.value] = AhlParam(319, 'PARAM_NUM_OF_OCCURENCES_45', 'Number of DC drive fail errors', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_45.value] = AhlParam(320, 'PARAM_TIME_ACKNOWLEDGE_45', 'Latest DC drive fail error acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_EXTERNAL_FLASH_FAIL.value] = AhlParam(321, 'PARAM_EXTERNAL_FLASH_FAIL', 'External flash fail', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_46.value] = AhlParam(322, 'PARAM_TIME_OCCURRENCE_46', 'Latest External flash fail error', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_46.value] = AhlParam(323, 'PARAM_NUM_OF_OCCURENCES_46', 'Number of External flash fail errors', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_46.value] = AhlParam(324, 'PARAM_TIME_ACKNOWLEDGE_46', 'Latest External flash fail error  acknowledge', 'R', '')
        self.database[self.params_alarm_details.PARAM_PIM_TRIP.value] = AhlParam(325, 'PARAM_PIM_TRIP', 'PIM trip', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_OCCURRENCE_47.value] = AhlParam(326, 'PARAM_TIME_OCCURRENCE_47', 'Latest PIM trip alarm', 'R', '')
        self.database[self.params_alarm_details.PARAM_NUM_OF_OCCURENCES_47.value] = AhlParam(327, 'PARAM_NUM_OF_OCCURENCES_47', 'Number of PIM trip alarms', 'R', '')
        self.database[self.params_alarm_details.PARAM_TIME_ACKNOWLEDGE_47.value] = AhlParam(328, 'PARAM_TIME_ACKNOWLEDGE_47', 'Latest PIM trip alarm acknowledge', 'R', '')
        self.database[self.params_configuration.PARAM_CALIBRATION_LOAD.value] = AhlParam(329, 'PARAM_CALIBRATION_LOAD', 'Calibration Load', 'R', '')
        self.database[self.params_configuration.PARAM_LOAD_SENSOR_POTENTIOMETER.value] = AhlParam(330, 'PARAM_LOAD_SENSOR_POTENTIOMETER', 'Load sensor potentiometer', 'R', '')
        self.database[self.params_configuration.PARAM_LOAD_SENSOR_DAC.value] = AhlParam(331, 'PARAM_LOAD_SENSOR_DAC', 'Load sensor DAC', 'R', '')
        self.database[self.params_configuration.PARAM_LOAD_SENSOR_CALIBRATED.value] = AhlParam(332, 'PARAM_LOAD_SENSOR_CALIBRATED', 'Load sensor calibrated', 'R', '')
        self.database[self.params_configuration.PARAM_ELEVATOR_CONFIGURED.value] = AhlParam(333, 'PARAM_ELEVATOR_CONFIGURED', 'Elevator configured', 'R', '')
        self.database[self.params_information.PARAM_TRIPPED_SENSOR.value] = AhlParam(334, 'PARAM_TRIPPED_SENSOR', 'Tripped sensor', 'R', '')
        self.database[self.params_power.PARAM_DC_DRIVE_ACTIVE.value] = AhlParam(335, 'PARAM_DC_DRIVE_ACTIVE', 'Dc drive active', 'R', '')
        self.database[self.params_information.PARAM_NEED_UPDATE_POSITION.value] = AhlParam(336, 'PARAM_NEED_UPDATE_POSITION', 'Need update position', 'R', '')
        self.database[self.params_information.PARAM_ELEVATOR_RUNNING.value] = AhlParam(338, 'PARAM_ELEVATOR_RUNNING', 'Elevator running', 'R', '')
        self.database[self.params_information.PARAM_CURRENT_FLOOR.value] = AhlParam(339, 'PARAM_CURRENT_FLOOR', 'Current floor', 'R', '')
        self.database[self.params_information.PARAM_LIGHT_STATUS.value] = AhlParam(340, 'PARAM_LIGHT_STATUS', 'Light status', 'R', '')
        self.database[self.params_information.PARAM_TEMP_ACCUMULATED_LUBRICATION_TIME_SINCE_REFILL.value] = AhlParam(341, 'PARAM_TEMP_ACCUMULATED_LUBRICATION_TIME_SINCE_REFILL', 'Temp Accumulated lubrication time since refill', 'R', '')
        self.database[self.params_information.PARAM_TEMP_BATTERY_VOLTAGE.value] = AhlParam(342, 'PARAM_TEMP_BATTERY_VOLTAGE', 'Temp Battery voltage', 'R', '')
        self.database[self.params_information.PARAM_TEMP_BATTERY_CURRENT.value] = AhlParam(343, 'PARAM_TEMP_BATTERY_CURRENT', 'Temp Battery current', 'R', '')
        self.database[self.params_information.PARAM_ALL_DOORS_CLOSED.value] = AhlParam(344, 'PARAM_ALL_DOORS_CLOSED', 'All doors closed', 'R', '')
        self.database[self.params_information.PARAM_ALL_LOCKS_LOCKED.value] = AhlParam(345, 'PARAM_ALL_LOCKS_LOCKED', 'All locks locked', 'R', '')
        self.database[self.params_power.PARAM_BATTERY_POWER_ACTIVE.value] = AhlParam(346, 'PARAM_BATTERY_POWER_ACTIVE', 'Battery power active', 'R', '')
        self.database[self.params_information.PARAM_TEACH_MODE_ACTIVE.value] = AhlParam(347, 'PARAM_TEACH_MODE_ACTIVE', 'Teach mode active', 'R', '')
        self.database[self.params_information.PARAM_EXTENDED_DOOR_DWELL_TIME_ACTIVE.value] = AhlParam(348, 'PARAM_EXTENDED_DOOR_DWELL_TIME_ACTIVE', 'Extended Door Dwell Time active', 'R', '')
        self.database[self.params_information.PARAM_MANUAL_PRIME_OIL_TIME.value] = AhlParam(349, 'PARAM_MANUAL_PRIME_OIL_TIME', 'Manual prime oil time', 'R', '')
        self.database[self.params_information.PARAM_TEACH_MODE_ERROR_CODE.value] = AhlParam(350, 'PARAM_TEACH_MODE_ERROR_CODE', 'Teach mode error code', 'R', '')
        self.database[self.params_information.PARAM_SPM_ACTIVE.value] = AhlParam(351, 'PARAM_SPM_ACTIVE', 'SPM active', 'R', '')
        self.database[self.params_information.PARAM_OIL_LEVEL_PERCENTAGE.value] = AhlParam(352, 'PARAM_OIL_LEVEL_PERCENTAGE', 'Oil level percentage', 'R', '')
        self.database[self.params_settings.PARAM_LATEST_REFILL_LEVEL.value] = AhlParam(353, 'PARAM_LATEST_REFILL_LEVEL', 'Latest refill level', 'RW', '%')
        self.database[self.params_settings.PARAM_CUSTOMER_ID.value] = AhlParam(354, 'PARAM_CUSTOMER_ID', 'Customer id', 'RW', '#')
        self.database[self.params_software.PARAM_RELEASE.value] = AhlParam(356, 'PARAM_RELEASE', 'Release', 'R', '#')
        self.database[self.params_software.PARAM_SAFETY_CHAIN_TRIPPED_SENSOR.value] = AhlParam(357, 'PARAM_SAFETY_CHAIN_TRIPPED_SENSOR', 'Safety Chain Tripped Sensor', 'R', '')
        self.database[self.params_software.PARAM_CAN_BUS_SPEED.value] = AhlParam(358, 'PARAM_CAN_BUS_SPEED', 'CAN bus speed', 'R', '')
        self.database[self.params_configuration.PARAM_OSM_RATED_SPEED.value] = AhlParam(359, 'PARAM_OSM_RATED_SPEED', 'OSM rated speed', 'R', 'mm/s')
        self.database[self.params_settings.PARAM_CHILD_LOCK.value] = AhlParam(360, 'PARAM_CHILD_LOCK', 'Child lock', 'R', '')
        self.database[self.params_settings.PARAM_CHILD_LOCK_EXTERNAL.value] = AhlParam(361, 'PARAM_CHILD_LOCK_EXTERNAL', 'Child lock external', 'RW', '')
        self.database[self.params_settings.PARAM_FLOOR_LOCK.value] = AhlParam(362, 'PARAM_FLOOR_LOCK', 'Floor lock', 'R', '')
        self.database[self.params_settings.PARAM_FLOOR_LOCK_EXTERNAL.value] = AhlParam(363, 'PARAM_FLOOR_LOCK_EXTERNAL', 'Floor lock external', 'RW', '')
        self.database[self.params_lighting.PARAM_SHAFT_DIM_LEVEL.value] = AhlParam(364, 'PARAM_SHAFT_DIM_LEVEL', 'Shaft dim level', 'RW', '')
        self.database[self.params_power.VFD_MOTOR_CURRENT.value] = AhlParam(365, '', 'VFD Motor Current', 'R', '')
        self.database[self.params_power.VFD_MOTOR_POWER.value] = AhlParam(366, '', 'VFD Motor Power', 'R', '')
        self.database[self.params_power.VFD_LINE_MAINS_VOLTAGE.value] = AhlParam(367, '', 'VFD Line Mains Voltage', 'R', '')
        self.database[self.params_power.VFD_DRIVE_THERMAL_STATE.value] = AhlParam(368, '', 'VFD Drive Thermal State', 'R', '')
        self.database[self.params_information.LATEST_DOOR_CLOSING_TIME_1.value] = AhlParam(369, '', 'Latest door closing time 1', 'R', '')
        self.database[self.params_information.LATEST_DOOR_CLOSING_TIME_2.value] = AhlParam(370, '', 'Latest door closing time 2', 'R', '')
        self.database[self.params_information.LATEST_DOOR_CLOSING_TIME_3.value] = AhlParam(371, '', 'Latest door closing time 3', 'R', '')
        self.database[self.params_information.LATEST_DOOR_CLOSING_TIME_4.value] = AhlParam(372, '', 'Latest door closing time 4', 'R', '')
        self.database[self.params_information.LATEST_DOOR_CLOSING_TIME_5.value] = AhlParam(373, '', 'Latest door closing time 5', 'R', '')
        self.database[self.params_information.LATEST_DOOR_CLOSING_TIME_6.value] = AhlParam(374, '', 'Latest door closing time 6', 'R', '')
        self.database[self.params_information.PARAM_AHL_2_LIGHTS.value] = AhlParam(375, 'PARAM_AHL_2_LIGHTS', 'AHL 2 lights', 'R', '#')
        self.database[self.params_lighting.PARAM_DESIGN_WALL_TEMPERATURE.value] = AhlParam(376, 'PARAM_DESIGN_WALL_TEMPERATURE', 'Design wall temperature', 'RW', '#')
        self.database[self.params_lighting.PARAM_DESIGN_WALL_DIM_TEMPERATURE.value] = AhlParam(377, 'PARAM_DESIGN_WALL_DIM_TEMPERATURE', 'Design wall dim temperature', 'RW', '#')
        self.database[self.params_lighting.PARAM_SHAFT_WHITE_TEMPERATURE.value] = AhlParam(378, 'PARAM_SHAFT_WHITE_TEMPERATURE', 'Shaft white temperature', 'RW', '#')
        self.database[self.params_lighting.PARAM_SHAFT_WHITE_DIM_TEMPERATURE.value] = AhlParam(379, 'PARAM_SHAFT_WHITE_DIM_TEMPERATURE', 'Shaft white dim temperature', 'RW', '#')
        self.database[self.params_lighting.PARAM_SHAFT_RGBW_TOGGLE.value] = AhlParam(380, 'PARAM_SHAFT_RGBW_TOGGLE', 'Shaft rgbw toggle', 'RW', '#')
        self.database[self.params_lighting.PARAM_SHAFT_RGBW_DIM_TOGGLE.value] = AhlParam(381, 'PARAM_SHAFT_RGBW_DIM_TOGGLE', 'Shaft rgbw dim toggle', 'RW', '#')


class AhlParam:
    """Stores parameter metadata and current value for one AHL parameter."""

    def __init__(self, param_id: int, register_code: str, name: str, access: str, unit: str):
        self.param_id: int = param_id
        self.register_code: str = register_code
        self.name: str = name
        self.value: int | None = None  # None = not yet read from lift
        self.access: str = access  # "R" or "RW"
        self.unit: str = unit


# --- Parameter category enums ---

class AhlParamSystem(Enum):
    PARAM_LIFT_INTERFACE_USED = 0
    PARAM_LIFT_SUPPORTED_INTERFACE_VERSIONS = 1
    PARAM_POLLING = 2
    PARAM_GATEWAY_STATUS = 3
    PARAM_TIME = 4
    PARAM_RESET_PARAMETERS = 98
    PARAM_REGISTER_HASH_1 = 123
    PARAM_REGISTER_HASH_2 = 124
    PARAM_REGISTER_HASH_3 = 125
    PARAM_REGISTER_HASH_4 = 126
    PARAM_REFERENCE_POSITION = 127
    PARAM_REFERENCE_DELTA = 128


class AhlParamSettings(Enum):
    PARAM_DOOR_DWELL_TIME = 8
    PARAM_EXTENDED_DOOR_DWELL_TIME = 9
    PARAM_FIRE_DRIVE_POLARITY = 10
    PARAM_FIRE_DRIVE_FLOOR = 11
    PARAM_FLOOR1_LEVEL_ADJUST = 12
    PARAM_FLOOR2_LEVEL_ADJUST = 13
    PARAM_FLOOR3_LEVEL_ADJUST = 14
    PARAM_FLOOR4_LEVEL_ADJUST = 15
    PARAM_FLOOR5_LEVEL_ADJUST = 16
    PARAM_FLOOR6_LEVEL_ADJUST = 17
    PARAM_LUBRICATION_TIME = 32
    PARAM_LUBRICATION_INTERVAL = 33
    PARAM_ACCUMULATED_LUBRICATION_TIME_SINCE_REFILL = 34
    PARAM_TOTAL_LUBRICATION_TIME_FOR_FULL_CONTAINER = 35
    PARAM_SERVICE_INTERVAL = 62
    PARAM_SERVICE_INDICATOR_RESET = 63
    PARAM_LIFT_BLOCK = 91
    PARAM_SEND_LIFT_TO_LANDING = 92
    PARAM_REMOTE_CONTROL_ENABLE = 93
    PARAM_LOAD_SENSOR_CAL_LOAD = 95
    PARAM_VFD_TYPE = 106
    PARAM_LATEST_REFILL_LEVEL = 353
    PARAM_CUSTOMER_ID = 354
    PARAM_CHILD_LOCK = 360
    PARAM_CHILD_LOCK_EXTERNAL = 361
    PARAM_FLOOR_LOCK = 362
    PARAM_FLOOR_LOCK_EXTERNAL = 363


class AhlParamInformation(Enum):
    PARAM_TOTAL_RUNTIME = 18
    PARAM_TOTAL_RUN_TRAVEL = 19
    PARAM_SAFETY_CHAIN_STATUS = 20
    PARAM_LOAD_SENSOR = 21
    PARAM_CURRENT_POSITION = 22
    PARAM_LAST_POSITION_SYNC = 23
    PARAM_LAST_SYNC_DIFFERENCE = 24
    PARAM_EMERGENCY_STOP_STATUS = 25
    PARAM_RUN_SIGNAL = 26
    PARAM_PLATFORM_SIZE = 29
    PARAM_TOTAL_NUMBER_DOOR_OPENED_1 = 46
    PARAM_TOTAL_NUMBER_DOOR_OPENED_2 = 47
    PARAM_TOTAL_NUMBER_DOOR_OPENED_3 = 48
    PARAM_TOTAL_NUMBER_DOOR_OPENED_4 = 49
    PARAM_TOTAL_NUMBER_DOOR_OPENED_5 = 50
    PARAM_TOTAL_NUMBER_DOOR_OPENED_6 = 51
    PARAM_TOTAL_NUMBER_DOOR_OPENED_7 = 52
    PARAM_TOTAL_NUMBER_DOOR_OPENED_8 = 53
    PARAM_TOTAL_NUMBER_DOOR_OPENED_9 = 54
    PARAM_TOTAL_NUMBER_DOOR_OPENED_10 = 55
    PARAM_TOTAL_NUMBER_DOOR_OPENED_11 = 56
    PARAM_TOTAL_NUMBER_DOOR_OPENED_12 = 57
    PARAM_LATEST_LCM_BOOT = 64
    PARAM_LATEST_TEACH = 65
    PARAM_LATEST_DC_MOTOR_START = 66
    PARAM_EMERGENCY_MODE_STATUS = 87
    PARAM_NUMBER_OF_STARTS_ON_AC_MOTOR = 88
    PARAM_NUMBER_OF_STARTS_DC_MOTOR = 89
    PARAM_LOAD_SENSOR_CAL_0 = 94
    PARAM_AR_NUMBER = 96
    PARAM_LIGHT_ALWAYS_ON = 97
    PARAM_ELEVATOR_TYPE = 105
    PARAM_TRIPPED_SENSOR = 334
    PARAM_NEED_UPDATE_POSITION = 336
    PARAM_ELEVATOR_RUNNING = 338
    PARAM_CURRENT_FLOOR = 339
    PARAM_LIGHT_STATUS = 340
    PARAM_TEMP_ACCUMULATED_LUBRICATION_TIME_SINCE_REFILL = 341
    PARAM_TEMP_BATTERY_VOLTAGE = 342
    PARAM_TEMP_BATTERY_CURRENT = 343
    PARAM_ALL_DOORS_CLOSED = 344
    PARAM_ALL_LOCKS_LOCKED = 345
    PARAM_TEACH_MODE_ACTIVE = 347
    PARAM_EXTENDED_DOOR_DWELL_TIME_ACTIVE = 348
    PARAM_MANUAL_PRIME_OIL_TIME = 349
    PARAM_TEACH_MODE_ERROR_CODE = 350
    PARAM_SPM_ACTIVE = 351
    PARAM_OIL_LEVEL_PERCENTAGE = 352
    LATEST_DOOR_CLOSING_TIME_1 = 369
    LATEST_DOOR_CLOSING_TIME_2 = 370
    LATEST_DOOR_CLOSING_TIME_3 = 371
    LATEST_DOOR_CLOSING_TIME_4 = 372
    LATEST_DOOR_CLOSING_TIME_5 = 373
    LATEST_DOOR_CLOSING_TIME_6 = 374
    PARAM_AHL_2_LIGHTS = 375


class AhlParamConfiguration(Enum):
    PARAM_RATED_SPEED = 30
    PARAM_AUTOMATIC_RUN = 31
    PARAM_NUM_OF_FLOORS = 43
    PARAM_DCM_1_ADDRESS = 129
    PARAM_DCM_2_ADDRESS = 130
    PARAM_DCM_3_ADDRESS = 131
    PARAM_DCM_4_ADDRESS = 132
    PARAM_DCM_5_ADDRESS = 133
    PARAM_DCM_6_ADDRESS = 134
    PARAM_FLOOR_1_POSITION = 135
    PARAM_FLOOR_2_POSITION = 136
    PARAM_FLOOR_3_POSITION = 137
    PARAM_FLOOR_4_POSITION = 138
    PARAM_FLOOR_5_POSITION = 139
    PARAM_FLOOR_6_POSITION = 140
    PARAM_CALIBRATION_LOAD = 329
    PARAM_LOAD_SENSOR_POTENTIOMETER = 330
    PARAM_LOAD_SENSOR_DAC = 331
    PARAM_LOAD_SENSOR_CALIBRATED = 332
    PARAM_ELEVATOR_CONFIGURED = 333
    PARAM_OSM_RATED_SPEED = 359


class AhlParamLighting(Enum):
    PARAM_PLATFORM_LIGHT_ON_TIME = 5
    PARAM_LIGHT_DIM_TIME = 6
    PARAM_LIGHT_SWITCH = 7
    PARAM_SHAFT_COLOUR = 37
    PARAM_SHAFT_WHITE_LEVEL = 38
    PARAM_SHAFT_LED_TYPE = 39
    PARAM_PLATFORM_WHITE_DIM_LEVEL = 40
    PARAM_DIM_SHAFT_COLOUR_OBSOLETE = 41
    PARAM_SHAFT_WHITE_DIM_LEVEL_OBSOLETE = 42
    PARAM_LIGHT_RAMP_UP_TIME = 44
    PARAM_LIGHT_RAMP_DOWN_TIME = 45
    PARAM_SERVICE_LIGHT = 109
    PARAM_SHAFT_DIM_LEVEL = 364
    PARAM_DESIGN_WALL_TEMPERATURE = 376
    PARAM_DESIGN_WALL_DIM_TEMPERATURE = 377
    PARAM_SHAFT_WHITE_TEMPERATURE = 378
    PARAM_SHAFT_WHITE_DIM_TEMPERATURE = 379
    PARAM_SHAFT_RGBW_TOGGLE = 380
    PARAM_SHAFT_RGBW_DIM_TOGGLE = 381


class AhlParamPower(Enum):
    PARAM_BATTERY_VOLTAGE = 58
    PARAM_BATTERY_CURRENT = 59
    PARAM_BATTERY_CONDITION = 60
    PARAM_BATTERY_CHARGER_STATUS = 61
    PARAM_BATTERY_RUNTIME = 90
    PARAM_DC_DRIVE_ACTIVE = 335
    PARAM_BATTERY_POWER_ACTIVE = 346
    VFD_MOTOR_CURRENT = 365
    VFD_MOTOR_POWER = 366
    VFD_LINE_MAINS_VOLTAGE = 367
    VFD_DRIVE_THERMAL_STATE = 368


class AhlParamAlarms(Enum):
    PARAM_ACTIVE_ALARM_LEVEL_1 = 99
    PARAM_ACTIVE_ALARM_LEVEL_2 = 100
    ACTIVE_ALARM_LEVEL_3 = 101
    PARAM_RESET_ALARM_LEVEL_1 = 102
    PARAM_RESET_ALARM_LEVEL_2 = 103
    PARAM_RESET_ALARM_LEVEL_3 = 104


class AhlParamHardware(Enum):
    PARAM_LCM_HARDWARE_VERSION = 67
    PARAM_SPM_HARDWARE_VERSION = 68
    PARAM_CPM_HARDWARE_VERSION = 69
    PARAM_DCM1_HARDWARE_VERSION = 70
    PARAM_DCM2_HARDWARE_VERSION = 71
    PARAM_DCM3_HARDWARE_VERSION = 72
    PARAM_DCM4_HARDWARE_VERSION = 73
    PARAM_DCM5_HARDWARE_VERSION = 74
    PARAM_DCM6_HARDWARE_VERSION = 75
    PARAM_LMM_HARDWARE_VERSION = 76
    PARAM_LCM_SERIAL_NUMBER = 113
    PARAM_SPM_SERIAL_NUMBER = 114
    PARAM_CPM_SERIAL_NUMBER = 115
    PARAM_DCM1_SERIAL_NUMBER = 116
    PARAM_DCM2_SERIAL_NUMBER = 117
    PARAM_DCM3_SERIAL_NUMBER = 118
    PARAM_DCM4_SERIAL_NUMBER = 119
    PARAM_DCM5_SERIAL_NUMBER = 120
    PARAM_DCM6_SERIAL_NUMBER = 121
    PARAM_LMM_SERIAL_NUMBER = 122


class AhlParamSoftware(Enum):
    PARAM_LCM_SOFTWARE_VERSION = 77
    PARAM_SPM_SOFTWARE_VERSION = 78
    PARAM_CPM_SOFTWARE_VERSION = 79
    PARAM_DCM1_SOFTWARE_VERSION = 80
    PARAM_DCM2_SOFTWARE_VERSION = 81
    PARAM_DCM3_SOFTWARE_VERSION = 82
    PARAM_DCM4_SOFTWARE_VERSION = 83
    PARAM_DCM5_SOFTWARE_VERSION = 84
    PARAM_DCM6_SOFTWARE_VERSION = 85
    PARAM_LMM_SOFTWARE_VERSION = 86
    PARAM_FILE_DOWNLOAD_STATUS = 107
    PARAM_SW_INSTALLATION_CMD = 108
    PARAM_UP_VERSION = 110
    PARAM_SW_UPGRADE_ERROR_CODE = 111
    PARAM_RELEASE = 356
    PARAM_SAFETY_CHAIN_TRIPPED_SENSOR = 357
    PARAM_CAN_BUS_SPEED = 358


class AhlParamNetwork(Enum):
    PARAM_NUM_OF_DCMS = 27
    PARAM_ONLINE_UNITS = 28
    PARAM_REGISTERED_UNITS = 112


class AhlParamAlarmDetails(Enum):
    PARAM_DOOR_STUCK_OPEN = 141
    PARAM_TIME_OCCURRENCE_1 = 142
    PARAM_NUM_OF_OCCURENCES_1 = 143
    PARAM_TIME_ACKNOWLEDGE_1 = 144
    PARAM_DOOR_STUCK_CLOSED = 145
    PARAM_TIME_OCCURRENCE_2 = 146
    PARAM_NUM_OF_OCCURENCES_2 = 147
    PARAM_TIME_ACKNOWLEDGE_2 = 148
    PARAM_LOCK_STUCK_OPEN = 149
    PARAM_TIME_OCCURRENCE_3 = 150
    PARAM_NUM_OF_OCCURENCES_3 = 151
    PARAM_TIME_ACKNOWLEDGE_3 = 152
    PARAM_LOCK_STUCK_CLOSED = 153
    PARAM_TIME_OCCURRENCE_4 = 154
    PARAM_NUM_OF_OCCURENCES_4 = 155
    PARAM_TIME_ACKNOWLEDGE_4 = 156
    PARAM_POWER_FAILURE = 157
    PARAM_TIME_OCCURRENCE_5 = 158
    PARAM_NUM_OF_OCCURENCES_5 = 159
    PARAM_TIME_ACKNOWLEDGE_5 = 160
    PARAM_SC_OPENED = 161
    PARAM_TIME_OCCURRENCE_6 = 162
    PARAM_NUM_OF_OCCURENCES_6 = 163
    PARAM_TIME_ACKNOWLEDGE_6 = 164
    PARAM_NOT_USED_ALARM_1 = 165
    PARAM_TIME_OCCURRENCE_7 = 166
    PARAM_NUM_OF_OCCURENCES_7 = 167
    PARAM_TIME_ACKNOWLEDGE_7 = 168
    PARAM_CHARGE_TERMINATION_FAILURE = 169
    PARAM_TIME_OCCURRENCE_8 = 170
    PARAM_NUM_OF_OCCURENCES_8 = 171
    PARAM_TIME_ACKNOWLEDGE_8 = 172
    PARAM_OVERLOAD = 173
    PARAM_TIME_OCCURRENCE_9 = 174
    PARAM_NUM_OF_OCCURENCES_9 = 175
    PARAM_TIME_ACKNOWLEDGE_9 = 176
    PARAM_EMERGENCY_MODE = 177
    PARAM_TIME_OCCURRENCE_10 = 178
    PARAM_NUM_OF_OCCURENCES_10 = 179
    PARAM_TIME_ACKNOWLEDGE_10 = 180
    PARAM_CONTACTOR_FAILURE_MINOR = 181
    PARAM_TIME_OCCURRENCE_11 = 182
    PARAM_NUM_OF_OCCURENCES_11 = 183
    PARAM_TIME_ACKNOWLEDGE_11 = 184
    PARAM_BRAKE_SENSOR_MINOR = 185
    PARAM_TIME_OCCURRENCE_12 = 186
    PARAM_NUM_OF_OCCURENCES_12 = 187
    PARAM_TIME_ACKNOWLEDGE_12 = 188
    PARAM_LOSS_OF_POSITION = 189
    PARAM_TIME_OCCURRENCE_13 = 190
    PARAM_NUM_OF_OCCURENCES_13 = 191
    PARAM_TIME_ACKNOWLEDGE_13 = 192
    PARAM_REFERENCE_DRIFT = 193
    PARAM_TIME_OCCURRENCE_14 = 194
    PARAM_NUM_OF_OCCURENCES_14 = 195
    PARAM_TIME_ACKNOWLEDGE_14 = 196
    PARAM_REFERENCE_UPDATE_FAILURE = 197
    PARAM_TIME_OCCURRENCE_15 = 198
    PARAM_NUM_OF_OCCURENCES_15 = 199
    PARAM_TIME_ACKNOWLEDGE_15 = 200
    PARAM_FIRE_DETECTED = 201
    PARAM_TIME_OCCURRENCE_16 = 202
    PARAM_NUM_OF_OCCURENCES_16 = 203
    PARAM_TIME_ACKNOWLEDGE_16 = 204
    PARAM_OIL_LEVEL_LOW = 205
    PARAM_TIME_OCCURRENCE_17 = 206
    PARAM_NUM_OF_OCCURENCES_17 = 207
    PARAM_TIME_ACKNOWLEDGE_17 = 208
    PARAM_HIGH_BATTERY_CURRENT = 209
    PARAM_TIME_OCCURRENCE_18 = 210
    PARAM_NUM_OF_OCCURENCES_18 = 211
    PARAM_TIME_ACKNOWLEDGE_18 = 212
    PARAM_LIGHT_FAILURE = 213
    PARAM_TIME_OCCURRENCE_19 = 214
    PARAM_NUM_OF_OCCURENCES_19 = 215
    PARAM_TIME_ACKNOWLEDGE_19 = 216
    PARAM_NOT_USED_ALARM_4 = 217
    PARAM_TIME_OCCURRENCE_20 = 218
    PARAM_NUM_OF_OCCURENCES_20 = 219
    PARAM_TIME_ACKNOWLEDGE_20 = 220
    PARAM_NOT_USED_ALARM_5 = 221
    PARAM_TIME_OCCURRENCE_21 = 222
    PARAM_NUM_OF_OCCURENCES_21 = 223
    PARAM_TIME_ACKNOWLEDGE_21 = 224
    PARAM_OIL_LEVEL_CRITICAL = 225
    PARAM_TIME_OCCURRENCE_22 = 226
    PARAM_NUM_OF_OCCURENCES_22 = 227
    PARAM_TIME_ACKNOWLEDGE_22 = 228
    PARAM_VERSION_ERROR = 229
    PARAM_TIME_OCCURRENCE_23 = 230
    PARAM_NUM_OF_OCCURENCES_23 = 231
    PARAM_TIME_ACKNOWLEDGE_23 = 232
    PARAM_NETWORK_FAILURE = 233
    PARAM_TIME_OCCURRENCE_24 = 234
    PARAM_NUM_OF_OCCURENCES_24 = 235
    PARAM_TIME_ACKNOWLEDGE_24 = 236
    PARAM_OSM_WRONG_TYPE = 237
    PARAM_TIME_OCCURRENCE_25 = 238
    PARAM_NUM_OF_OCCURENCES_25 = 239
    PARAM_TIME_ACKNOWLEDGE_25 = 240
    PARAM_NOT_USED_ALARM_7 = 241
    PARAM_TIME_OCCURRENCE_26 = 242
    PARAM_NUM_OF_OCCURENCES_26 = 243
    PARAM_TIME_ACKNOWLEDGE_26 = 244
    PARAM_SHORT_CIRCUIT_CRITICAL = 245
    PARAM_TIME_OCCURRENCE_27 = 246
    PARAM_NUM_OF_OCCURENCES_27 = 247
    PARAM_TIME_ACKNOWLEDGE_27 = 248
    PARAM_BATTERY_CONDITION_FAILURE = 249
    PARAM_TIME_OCCURRENCE_28 = 250
    PARAM_NUM_OF_OCCURENCES_28 = 251
    PARAM_TIME_ACKNOWLEDGE_28 = 252
    PARAM_LOW_BATTERY_VOLTAGE = 253
    PARAM_TIME_OCCURRENCE_29 = 254
    PARAM_NUM_OF_OCCURENCES_29 = 255
    PARAM_TIME_ACKNOWLEDGE_29 = 256
    PARAM_NOT_USED_ALARM_10 = 257
    PARAM_TIME_OCCURRENCE_30 = 258
    PARAM_NUM_OF_OCCURENCES_30 = 259
    PARAM_TIME_ACKNOWLEDGE_30 = 260
    PARAM_FINAL_LIMIT = 261
    PARAM_TIME_OCCURRENCE_31 = 262
    PARAM_NUM_OF_OCCURENCES_31 = 263
    PARAM_TIME_ACKNOWLEDGE_31 = 264
    PARAM_STARTUP_FAILURE_CRITICAL = 265
    PARAM_TIME_OCCURRENCE_32 = 266
    PARAM_NUM_OF_OCCURENCES_32 = 267
    PARAM_TIME_ACKNOWLEDGE_32 = 268
    PARAM_NOT_USED_ALARM_11 = 269
    PARAM_TIME_OCCURRENCE_33 = 270
    PARAM_NUM_OF_OCCURENCES_33 = 271
    PARAM_TIME_ACKNOWLEDGE_33 = 272
    PARAM_REFERENCE_DRIFT_CRITICAL = 273
    PARAM_TIME_OCCURRENCE_34 = 274
    PARAM_NUM_OF_OCCURENCES_34 = 275
    PARAM_TIME_ACKNOWLEDGE_34 = 276
    PARAM_NOT_USED_ALARM_13 = 277
    PARAM_TIME_OCCURRENCE_35 = 278
    PARAM_NUM_OF_OCCURENCES_35 = 279
    PARAM_TIME_ACKNOWLEDGE_35 = 280
    PARAM_BRAKE_SENSOR_CRITICAL = 281
    PARAM_TIME_OCCURRENCE_36 = 282
    PARAM_NUM_OF_OCCURENCES_36 = 283
    PARAM_TIME_ACKNOWLEDGE_36 = 284
    PARAM_NOT_USED_ALARM_14 = 285
    PARAM_TIME_OCCURRENCE_37 = 286
    PARAM_NUM_OF_OCCURENCES_37 = 287
    PARAM_TIME_ACKNOWLEDGE_37 = 288
    PARAM_OSM_TRIP = 289
    PARAM_TIME_OCCURRENCE_38 = 290
    PARAM_NUM_OF_OCCURENCES_38 = 291
    PARAM_TIME_ACKNOWLEDGE_38 = 292
    PARAM_VFD_COM_FAILURE = 293
    PARAM_TIME_OCCURRENCE_39 = 294
    PARAM_NUM_OF_OCCURENCES_39 = 295
    PARAM_TIME_ACKNOWLEDGE_39 = 296
    PARAM_REVERSE_MOTION_DETECTED = 297
    PARAM_TIME_OCCURRENCE_40 = 298
    PARAM_NUM_OF_OCCURENCES_40 = 299
    PARAM_TIME_ACKNOWLEDGE_40 = 300
    PARAM_VFD_INTERNAL_ERROR = 301
    PARAM_TIME_OCCURRENCE_41 = 302
    PARAM_NUM_OF_OCCURENCES_41 = 303
    PARAM_TIME_ACKNOWLEDGE_41 = 304
    PARAM_BELT_SLIP = 305
    PARAM_TIME_OCCURRENCE_42 = 306
    PARAM_NUM_OF_OCCURENCES_42 = 307
    PARAM_TIME_ACKNOWLEDGE_42 = 308
    PARAM_BRAKE_RESISTOR_TEMP = 309
    PARAM_TIME_OCCURRENCE_43 = 310
    PARAM_NUM_OF_OCCURENCES_43 = 311
    PARAM_TIME_ACKNOWLEDGE_43 = 312
    PARAM_PULSE_SENSOR_POSITION = 313
    PARAM_TIME_OCCURRENCE_44 = 314
    PARAM_NUM_OF_OCCURENCES_44 = 315
    PARAM_TIME_ACKNOWLEDGE_44 = 316
    PARAM_DC_DRIVE_FAIL = 317
    PARAM_TIME_OCCURRENCE_45 = 318
    PARAM_NUM_OF_OCCURENCES_45 = 319
    PARAM_TIME_ACKNOWLEDGE_45 = 320
    PARAM_EXTERNAL_FLASH_FAIL = 321
    PARAM_TIME_OCCURRENCE_46 = 322
    PARAM_NUM_OF_OCCURENCES_46 = 323
    PARAM_TIME_ACKNOWLEDGE_46 = 324
    PARAM_PIM_TRIP = 325
    PARAM_TIME_OCCURRENCE_47 = 326
    PARAM_NUM_OF_OCCURENCES_47 = 327
    PARAM_TIME_ACKNOWLEDGE_47 = 328

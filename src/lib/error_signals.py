from enum import Enum, unique


@unique
class DhCode(Enum):
    SOURCE = 'DiskHandler'
    NO_ERR = 0
    TYPE_ERR = 1
    IN_ARGS_ERR = 2
    DISK_LIMIT_ERR = 3


@unique
class CdCode(Enum):
    SOURCE = 'CleanDisk'
    NO_ERR = 0
    UP_IO_ERR = 1
    UP_UNEXP_ERR = 2
    LA_OS_ERR = 3
    LA_IO_ERR = 4
    LA_UNEXP_ERR = 5
    FLDR_IO_ERR = 6
    FLDR_UNEXP_ERR = 7
    FLDR_ARG_ERR = 8
    LA_SYML_ERR = 9
    INDEX_ERR = 10
    ACTIVE_LA_IO_ERR = 11
    ACTIVE_LA_UNEXP_ERR = 12


@unique
class OsCode(Enum):
    SOURCE = 'OsHandler'
    NO_ERR = 0
    INVALID_ERR = 1
    INVALID_BUILDNUMBER = 2
    IO_ERROR = 3
    UNEXPECTED_ERROR = 4
    UPGRADE_ERROR = 5
    INVALID_PATCHNUMBER = 6


@unique
class MbCode(Enum):
    SOURCE = 'ModBusHandler'
    NO_ERR = 0
    ARG_ERR = 1
    ARG_INT_ERR = 2
    COM_ERR = 3
    REG_ERR = 4
    LCM_ERR = 5
    LOG_TYPE_ERR = 6
    LOG_ERR_CNT = 7
    LOG_SAVE_ERR = 8
    LOG_RUN_ERR = 9
    LOG_NO_LD_ERR = 10
    LOG_REC_LEN_ERR = 11
    LOG_RSP_ERR = 12
    LOG_LD_PARSE_ERR = 13
    LOG_FNAME_ERR = 14
    LOG_ATTR_ERR = 15
    FILE_EMPTY = 16
    FILE_NOT_FOUND = 17
    FILE_TRANSFER_ERR = 18
    LINK_ERR = 19
    DISK_LIMIT_ERR = 20
    FILE_NAME_ERR = 21
    FILE_HEADER_ERR = 22
    CUSTOM_SPEED_ERR = 23
    FLOOR_LOCK_ERR = 24
    PARAM_NOT_IN_DB = 25
    PARAM_NOT_SET = 26

@unique
class MainCode(Enum):
    SOURCE = 'Main'
    NO_ERR = 0
    SIG_LIB_INIT_ERR = 1
    EXCEPTION_ERR = 2
    SOCKET_SRV_CFG_ERR = 3
    SOCKET_SRV_START_ERR = 4


@unique
class ShCode(Enum):
    SOURCE = 'SignalHandler'
    NO_ERR = 0
    SIG_IN_ATTR_ERR = 1
    SIG_IN_NA_ERR = 2
    ARG_IN_ATTR_ERR = 3
    ARG_IN_LEN_ERR = 4
    SIG_IN_CLBK_ERR = 5
    SIG_OUT_ERR = 6
    ARG_OUT_ERR = 7
    CODE_RET_ERR = 8
    TIMEOUT = 9


@unique
class LAuCode(Enum):
    SOURCE = 'LiftAgentUpdater'
    NO_ERR = 0
    ARG_EMPTY_ERR = 1
    ARG_LEN_ERR = 2
    ARG_TYPE_ERR = 3
    ARG_REL_PATH_ERR = 4
    FILE_NOT_FOUND_ERR = 5
    COPY_FILE_ERR = 6
    SYMLINK_ERR = 7
    FILE_NAME_ERR = 8
    FILE_ERR = 9


@unique
class LAvCode(Enum):
    SOURCE = 'LiftAgentVersion'
    NO_ERR = 0
    NO_FILE_ERR = 1
    EMPTY_FILE_ERR = 2
    INVALID_ERR = 3
    FILE_ERR = 4


@unique
class LhCode(Enum):
    SOURCE = 'LogHandler'
    NO_ERR = 0
    COPY_ERR = 1
    DEST_FILES_ERR = 2
    LOG_TYPE_ERR = 3
    ARGS_IN_ATTR_ERR = 4
    ARGS_IN_LEN_ERR = 5
    ARGS_IN_ELEM_ATTR_ERR = 6
    ARGS_IN_ELEM_INT_ERR = 7
    LOG_LEN_ERR = 8
    OS_ERR = 9
    DISK_LIMIT_ERR = 10
    DEST_DIR_ERR = 11
    EMPTY_LOG_ERR = 12


@unique
class RhCode(Enum):
    SOURCE = 'RebootHandler'
    NO_ERR = 0
    TARGET_ERR = 1
    COMMAND_ERR = 2


@unique
class ScHCode(Enum):
    SOURCE = 'ScriptHandler'
    NO_ERR = 0
    ARG_ATTR_ERR = 1
    FNAME_ERR = 2
    CHAR_ERR = 3
    FILE_ERR = 4
    EXIT_ERR = 5
    TIMEOUT_ERR = 6
    KILL_ERR = 7
    FATAL_ERR = 8
    LINE_FEED_ERR = 9


@unique
class ServerCode(Enum):
    SOURCE = 'SocketServer'
    NO_ERR = 0
    IN_QUEUE_FULL_ERR = 1


@unique
class SyncTimeCode(Enum):
    SOURCE = "SyncTimeHandler"
    NO_ERR = 0
    ARG_TYPE_ERR = 1
    ARG_INVALID_ERR = 2
    ARG_MODBUS_ERR = 3
    MODBUS_EXCEPTION_ERR = 4
    MODBUS_ERR = 5
    EPOCH_TIME_ERR = 6

@unique
class Rs232Code(Enum):
    SOURCE = "Rs232Handler"
    NO_ERR = 0
    ARG_TYPE_ERR = 1
    ARGS_IN_ELEM_ATTR_ERR = 2
    ARGS_IN_LEN_ERR = 3
    ARGS_IN_ELEM_INT_ERR = 4
    SERIAL_COM_ERR = 5
    JSON_ERR = 6
    JSON_KEY_ERR = 7
    JSON_VALUE_TYPE_ERR = 8
    STATUS_ERR = 9
    STATUS_FILE_IO_ERR = 10
    STATUS_FILE_EXCEPTION = 11
    CMD_NOT_SUPPORTED = 12
    NO_WAITING_BYTES_ERR = 13
    DATA_TYPE_ERR = 14
    NO_UPDATED_PARAMS = 15
    PARTIAL_ERR = 16
    PARAM_NOT_IN_DB = 17
    PARAM_NOT_SET = 18
    NO_PARAMS_IN_DB = 19
    DATA_LEN_ERR = 20
    LOG_FILE_EXCEPTION = 21
    LOG_FILE_IO_ERR = 22
    LOG_FILE_ALREADY_EXIST = 23
    DATA_ERR = 24
    FILE_NAME_ERR = 25
    LIST_INDEX_ERR = 26
    WRITE_PARAM_NOT_SUPPORTED_BY_1K = 27
    WRITE_PARAM_NOT_IN_FILES = 28
    PACKAGE_NOT_SUPPORTED = 29
    SERIAL_DECODE_ERR = 30
    FLOOR_LOCK_ERR = 31
    VFD_TIMEOUT_ERR = 32
    VFD_NO_PWR_ERR = 33
    VFD_ID_ERR = 34


@unique
class HbCode(Enum):
    SOURCE = 'HeartbeatHandler'
    NO_ERR = 0
    SEND_EVENT_ERR = 1
    REPORT_PROPERTY_ERR = 2
    INTERVAL_READ_ERR = 3


@unique
class LpCode(Enum):
    """LiftProxy error codes."""
    SOURCE = "LiftProxy"
    NO_ERR = 0
    INIT_ERR = 1
    IDENTIFY_ERR = 2
    LINK_ERR = 3
    PARAM_NOT_IN_DB = 4
    PARAM_NOT_SET = 5
    PARAM_READ_ONLY = 6
    COM_ERR = 7
    ARG_ERR = 8
    POLL_ERR = 9
    LOG_ERR = 10
    FILE_ERR = 11
    PARTIAL_ERR = 12
    DATA_ERR = 13


@unique
class MrhCode(Enum):
    SOURCE = 'MethodRequestHandler'
    NO_ERR = 0
    ARG_ERR = 1
    TYPE_ERR = 2
    URL_ERR = 3
    FILE_NAME_ERR = 4
    SIZE_ERR = 5
    DOWNLOAD_ERR = 6

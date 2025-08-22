#!/usr/bin/python
import os
import sys
import json
import shutil
import stat
from enum import Enum, unique

source_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(source_path)
from lib.error_signals import DhCode


@unique
class DiskArea(Enum):
    TOTAL = 'total'
    USED = 'used'
    FREE = 'free'


@unique
class ConfigItems(Enum):
    FILE_STATUS = 'file_status'

    # Add in 'type' order for nicer doc generation
    TRACE_FILES_SRAM = 'trace_files_sram'
    TRACE_FILES = 'trace_files'
    UP_FILES = 'up_files'
    BUILD_INFO = 'build_info'
    SYSTEM_LOG_FILES = 'system_log_files'
    ARK_1000_LOG_FILES = 'ark_1000_log_files'
    LOGGED_PARAMS_FILES = 'logged_params_files'
    DOOR_OPEN_TOTAL_COUNT_FILES = 'door_open_total_count_files'
    DOOR_OPEN_PREVIOUS_COUNT_FILES = 'door_open_previous_counter_files'


@unique
class ConfigNames(Enum):
    COMMENT = "comment__"
    PATH = "path"
    FILENAME = "filename"
    WRITE = "write"
    READ = "read"
    TYPE = "type"


@unique
class FileStatusNames(Enum):
    ERROR = "error"
    NOT_FOUND = "not_found"
    READABLE = "readable"
    WRITEABLE = "writeable"
    READABLE_AND_WRITEABLE = "readable_writeable"


@unique
class GatewayConfigItems(Enum):
    GATEWAY_CONFIG = 'gateway_config'
    COMMENT = ConfigNames.COMMENT.value
    PATH = ConfigNames.PATH.value
    FILENAME = ConfigNames.FILENAME.value


@unique
class GatewayConfigNames(Enum):
    ARITCO_CONFIG = 'aritco_config'
    CERTIFICATE = 'certificate'
    CERTIFICATE_KEY = 'certificate_key'
    WIFI_USER_CREDENTIALS = 'wifi_user_credentials'
    WIFI_AP_CREDENTIALS = 'wifi_ap_credentials'
    CA_CONNECTION_STATUS = 'ca_connection_status'
    CA_DEFAULT_INTERFACE = 'ca_default_interface'


class DiskHandler:

    def __init__(self):
        """
        Class constructor
        """
        self.DhCode = DhCode
        self.name = self.DhCode.SOURCE.value
        self.print = print

        # Limit set as 10%
        limit = 0.1
        self.free_disk_space_limit = limit*self.get_disk_info(DiskArea.TOTAL.value)

        try:
            config_path = os.path.join(source_path, "config", "liftAgent_config.json")
            with open(config_path) as data_file:
                self.sfs_config = json.load(data_file)["shared_file_system"]
            with open(config_path) as data_file:
                self.gateway_config = json.load(data_file)[GatewayConfigItems.GATEWAY_CONFIG.value]

            self.file_status = self.sfs_config[ConfigItems.FILE_STATUS.value]

        except Exception as e:
            self.print("Error: Could not use config file")
            self.print(e)
            # raise SystemExit TODO: Remove comment

    def check_status(self, args):
        """
        Checks the status of a file
        :param args: list, [type, filename], type of file, filename to check status of
        :return: tuple, <status>, <err_source>, <error_code>
        """

        type, filename = self.__validate_status_input_arguments(args)

        if type == -1:
            return self.file_status[FileStatusNames.ERROR.value], self.name, self.DhCode.IN_ARGS_ERR.name

        # Get path for these type of files
        path = self.__get_path_of_type(type)

        if path == -1:
            return self.file_status[FileStatusNames.ERROR.value], self.name, self.DhCode.TYPE_ERR.name

        # Set full path to file
        file_path = os.path.join(path, filename)

        # Determine file status
        if not os.path.isfile(file_path):
            # file not found
            status = self.file_status[FileStatusNames.NOT_FOUND.value]

        elif os.access(file_path, os.R_OK) and os.access(file_path, os.W_OK):
            # file is read- and writeable
            status = self.file_status[FileStatusNames.READABLE_AND_WRITEABLE.value]

        elif os.access(file_path, os.R_OK) and not os.access(file_path, os.W_OK):
            # file is readable but not writeable
            status = self.file_status[FileStatusNames.READABLE.value]

        elif not os.access(file_path, os.R_OK) and os.access(file_path, os.W_OK):
            # file is writeable but not readable
            status = self.file_status[FileStatusNames.WRITEABLE.value]

        else:
            # set status to error since could not determine status
            status = self.file_status[FileStatusNames.ERROR.value]
            self.print("Error: could not determine file status")

        # Check if disk usage is past allowed limit
        if not self.check_enough_free_space():
            self.print("Not enough free space on disk. Free space: {0}, free space limit: {1}".
                       format(self.get_disk_info(DiskArea.FREE.value), self.free_disk_space_limit))
            return status, self.name, self.DhCode.DISK_LIMIT_ERR.name

        return status, self.name, self.DhCode.NO_ERR.name

    def add_file_permissions(self, file_path):
        """
        Function sets read, write and execution flags for file.
        :param file_path: full path to file
        :return: DiskHandler (no) error code
        """
        try:
            # Set the permissions: [owner (0o0700) | group (0o0070) | others (0o0007)]
            os.chmod(file_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            return self.DhCode.NO_ERR
        except FileNotFoundError as e:
            self.print("Error: file permission change failed,  '{}' missing".format(file_path))
            self.print(e)
        except Exception as e:
            self.print("Error: file permission change failed for '{}'".format(file_path))
            self.print(e)
        return self.DhCode.FILE_FLAG_ERR

    def get_disk_info(self, spec):
        """
        Returns total disk size in MB
        The bit shift converts bytes to mb
        :param spec: Specifies disk area
        :return: An int in megabytes
        """
        disk_stat = 0
        disk_info = shutil.disk_usage('/')
        if spec == DiskArea.TOTAL.value:
            disk_stat = disk_info.total
        elif spec == DiskArea.USED.value:
            disk_stat = disk_info.used
        elif spec == DiskArea.FREE.value:
            disk_stat = disk_info.free
        else:
            self.print("Error: Disk info specifier: {0} is not supported".format(spec))
        return int(disk_stat) >> 20

    def check_enough_free_space(self):
        free_space = self.get_disk_info(DiskArea.FREE.value)
        if free_space < self.free_disk_space_limit:
            return False
        return True

    def get_sfs_config(self):
        return self.sfs_config

    def get_partition_config(self):
        return self.partition_config

    def get_upgrade_package_path(self):
        return self.sfs_config[ConfigItems.UP_FILES.value][ConfigNames.PATH.value]

    def get_system_log_path(self):
        return self.sfs_config[ConfigItems.SYSTEM_LOG_FILES.value][ConfigNames.PATH.value]

    def get_1000_log_file_path(self):
        return self.sfs_config[ConfigItems.ARK_1000_LOG_FILES.value][ConfigNames.PATH.value]

    def get_1000_log_file_filename(self):
        return self.sfs_config[ConfigItems.ARK_1000_LOG_FILES.value][ConfigNames.FILENAME.value]

    def get_logged_params_file_path(self):
        return self.sfs_config[ConfigItems.LOGGED_PARAMS_FILES.value][ConfigNames.PATH.value]

    def get_logged_params_file_filename(self):
        return self.sfs_config[ConfigItems.LOGGED_PARAMS_FILES.value][ConfigNames.FILENAME.value]

    def get_open_door_counter_file_path(self):
        return self.sfs_config[ConfigItems.DOOR_OPEN_TOTAL_COUNT_FILES.value][ConfigNames.PATH.value]

    def get_open_door_total_counter_file_filename(self):
        return self.sfs_config[ConfigItems.DOOR_OPEN_TOTAL_COUNT_FILES.value][ConfigNames.FILENAME.value]

    def get_open_door_previous_counter_file_filename(self):
        return self.sfs_config[ConfigItems.DOOR_OPEN_PREVIOUS_COUNT_FILES.value][ConfigNames.FILENAME.value]

    def get_trace_log_path(self):
        return self.sfs_config[ConfigItems.TRACE_FILES.value][ConfigNames.PATH.value]

    def get_buildInfo_path(self):
        path = self.sfs_config[ConfigItems.BUILD_INFO.value][ConfigNames.PATH.value]
        filename = self.sfs_config[ConfigItems.BUILD_INFO.value][ConfigNames.FILENAME.value]
        return os.path.join(path, filename)

    def get_upgrade_package_filename(self):
        return self.sfs_config[ConfigItems.UP_FILES.value][ConfigNames.FILENAME.value]

    def get_wifi_user_credentials_path(self):
        return self.gateway_config[GatewayConfigNames.WIFI_USER_CREDENTIALS.value][GatewayConfigItems.PATH.value]

    def get_wifi_user_credentials_filename(self):
        return self.gateway_config[GatewayConfigNames.WIFI_USER_CREDENTIALS.value][GatewayConfigItems.FILENAME.value]

    def __validate_status_input_arguments(self, args=[]):
        """
        Validate input arguments to check_status function
        :param args: list [type - hex-string, filename - string]
        :return:
        """

        if not isinstance(args, list) or len(args) != 2:
            self.print("Error: expected input argument list with length 2 - got [{}]".format(args))
            return -1, -1

        type = args[0]
        filename = args[1]

        if not isinstance(type, str) or not isinstance(filename, str):
            self.print("Error: inputs must be string")
            return -1, -1

        # Intify the type
        try:
            int(type, 16)

        except ValueError as e:
            self.print("Error: could not convert input to int")
            self.print(e)
            return -1, -1

        return type, filename

    def __get_path_of_type(self, type_in):
        """
        Get the storage path for inputted file type
        :param type_in: str, type of file
        :return: (str) path to file, (int) -1 if error
        """
        for key in self.sfs_config:
            if ConfigNames.TYPE.value in self.sfs_config[key] and \
                    type_in == self.sfs_config[key][ConfigNames.TYPE.value] and \
                    ConfigNames.PATH.value in self.sfs_config[key]:
                return self.sfs_config[key][ConfigNames.PATH.value]

        self.print("Error: could not find path attribute for file type: {}".format(type_in))
        return -1

    def print_config(self):
        """
        Print parsed information from JSON config file.
        :return: void
        """
        print(self.sfs_config[ConfigItems.FILE_STATUS.value][ConfigNames.COMMENT.value])
        for status in FileStatusNames:
            print(status.value + ": " + self.file_status[status.value])
        print()

        for item in ConfigItems:
            if item == ConfigItems.FILE_STATUS:
                continue
            print(self.sfs_config[item.value][ConfigNames.COMMENT.value])
            print("Path: " + self.sfs_config[item.value][ConfigNames.PATH.value])
            print("Filename: " + self.sfs_config[item.value][ConfigNames.FILENAME.value])
            print("Write: " + self.sfs_config[item.value][ConfigNames.WRITE.value])
            print("Read: " + self.sfs_config[item.value][ConfigNames.READ.value])
            print("Type: " + self.sfs_config[item.value][ConfigNames.TYPE.value])
            print()


if __name__ == "__main__":
    dh = DiskHandler()
    dh.print_config()
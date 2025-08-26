#!/usr/bin/env python

import unittest
import sys
import os
import stat
import mock
import collections
from mock import MagicMock

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'src'))
sys.path.append(p)
import filemgmt.disk_handler as DH


class TestDiskHandler(unittest.TestCase):

    def setUp(self):
        print("\nSetup: {}".format(self._testMethodName))

        self.dh = DH.DiskHandler()
        self.dhCodes = self.dh.DhCode
        self.dhArea = DH.DiskArea

        assert self.dh.name == "DiskHandler"

    def tearDown(self):
        print("\nTest done: {}".format(self._testMethodName))

    def test_fileSystemConfigParameters(self):
        """
        Will test the file status list members exist and test their values
        :return:
        """
        assert DH.FileStatusNames.NOT_FOUND.value == "not_found"
        assert DH.FileStatusNames.READABLE.value == "readable"
        assert DH.FileStatusNames.WRITEABLE.value == "writeable"
        assert DH.FileStatusNames.READABLE_AND_WRITEABLE.value == "readable_writeable"
        assert DH.FileStatusNames.ERROR.value == "error"
        assert len(DH.FileStatusNames) == 5

        # Now specifically test our custom statuses
        assert self.dh.file_status[DH.FileStatusNames.NOT_FOUND.value] == '0'
        assert self.dh.file_status[DH.FileStatusNames.READABLE.value] == '1'
        assert self.dh.file_status[DH.FileStatusNames.WRITEABLE.value] == '2'
        assert self.dh.file_status[DH.FileStatusNames.READABLE_AND_WRITEABLE.value] == '3'
        assert self.dh.file_status[DH.FileStatusNames.ERROR.value] == '-1'

    def test_gatewayConfigParameters(self):
        """
        Test parsed gateway_config information from JSON config file and related helper functions.
        """
        assert len(DH.GatewayConfigItems) == 4
        assert DH.GatewayConfigItems.GATEWAY_CONFIG.value == 'gateway_config'
        assert DH.GatewayConfigItems.COMMENT.value == 'comment__'
        assert DH.GatewayConfigItems.PATH.value == 'path'
        assert DH.GatewayConfigItems.FILENAME.value == 'filename'

        assert len(DH.GatewayConfigNames) == 7
        assert DH.GatewayConfigNames.ARITCO_CONFIG.value == 'aritco_config'
        assert DH.GatewayConfigNames.CERTIFICATE.value == 'certificate'
        assert DH.GatewayConfigNames.CERTIFICATE_KEY.value == 'certificate_key'
        assert DH.GatewayConfigNames.WIFI_USER_CREDENTIALS.value == 'wifi_user_credentials'
        assert DH.GatewayConfigNames.WIFI_AP_CREDENTIALS.value == 'wifi_ap_credentials'
        assert DH.GatewayConfigNames.CA_CONNECTION_STATUS.value == 'ca_connection_status'
        assert DH.GatewayConfigNames.CA_DEFAULT_INTERFACE.value == 'ca_default_interface'

        assert self.dh.get_wifi_user_credentials_path() == '/etc/aritco/wlan/'
        assert self.dh.get_wifi_user_credentials_filename() == 'wifi_login'

    def test___validateStatusInputArguments(self):
        """
        Fuzz test the validate_input_arguments functions
        :return:
        """

        # The function requires a list of length 2 and both elements should be strings.

        # -------- Send invalid arguments ---------
        type, filename = self.dh._DiskHandler__validate_status_input_arguments(4)
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments('4')
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments()
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments({0x4})
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments([4, 5, 6])
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments([4, 5])
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments(['4', 5])
        assert type == '-1'
        assert filename == '-1'

        type, filename = self.dh._DiskHandler__validate_status_input_arguments([4, '5'])
        assert type == '-1'
        assert filename == '-1'

        # --------- Send valid arguments, a list with two strings
        type, filename = self.dh._DiskHandler__validate_status_input_arguments(['4', '5'])
        assert type == '4'
        assert filename == '5'

    def test_getPathOfType(self):
        """
        Test that paths exist for tested types. No fuzz-testing, since we trust validate_inputs prepared us for a safe
        trip
        :return:
        """
        # Indicators that we actually hit the specific 'type' rules.
        trace_sram = False
        trace = False
        up = False
        system_log_files = False
        buildnumber = False
        ark_1000_log_file = False
        logged_params_file = False
        open_door_total_counter_file = False
        open_door_previous_counter_file = False
        other = 0
        nr_types_to_check = 256
        valid_types_found = 0
        for k in range(0, nr_types_to_check):

            # Hexlify the integer k for use as input to function below.
            type = hex(k)

            if k < 16:
                # Convert to 2 hex digits - 0xA -> 0x0A, since file types are right now not dependant on their integer
                # value, but rather a specific string match on the hex-string.
                type = '0x0' + type[-1].upper()

            if type == '0x02':
                assert not trace_sram  # Just making sure we were never here before
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/trace/'
                trace_sram = True
                valid_types_found += 1

            elif type == '0x06':
                assert not trace  # Just making sure we were never here before
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/trace/'
                trace = True
                valid_types_found += 1

            elif type == '0x07':
                assert not up
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/up/'
                assert path == self.dh.get_upgrade_package_path()
                up = True
                valid_types_found += 1

            elif type == '0x0C':
                assert not buildnumber
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/buildInfo/'
                buildnumber = True
                valid_types_found += 1

            elif type == '0x0D':
                assert not system_log_files
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/log/system/'
                system_log_files = True
                valid_types_found += 1

            elif type == '0x10':
                assert not ark_1000_log_file
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/log/ARK_1000/'
                ark_1000_log_file = True
                valid_types_found += 1

            elif type == '0x11':
                assert not logged_params_file
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/loggedParams/'
                logged_params_file = True
                valid_types_found += 1

            elif type == '0x12':
                assert not open_door_total_counter_file
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/doorParams/'
                logged_params_file = True
                valid_types_found += 1

            elif type == '0x13':
                assert not open_door_previous_counter_file
                path = self.dh._DiskHandler__get_path_of_type(type)
                print("Found path for {}: {}".format(type, path))
                assert path == '/opt/smartlift/doorParams/'
                logged_params_file = True
                valid_types_found += 1

            else:
                path = self.dh._DiskHandler__get_path_of_type(type)
                assert path == "-1"
                other += 1

        # Test we hit all types
        assert trace_sram
        assert trace
        assert up
        assert buildnumber
        assert system_log_files
        assert ark_1000_log_file
        assert other
        assert other == nr_types_to_check - valid_types_found
        assert len(DH.ConfigItems) == 10
        assert len(DH.ConfigItems) == valid_types_found + 1  # file status has no type

    def test_config_names(self):
        """
        Test config name enums to detect changes in JSON config file.
        :return:
        """
        assert DH.ConfigNames.COMMENT.value == "comment__"
        assert DH.ConfigNames.PATH.value == "path"
        assert DH.ConfigNames.FILENAME.value == "filename"
        assert DH.ConfigNames.WRITE.value == "write"
        assert DH.ConfigNames.READ.value == "read"
        assert DH.ConfigNames.TYPE.value == "type"
        assert len(DH.ConfigNames) == 6

    def test_check_status(self):
        """
        Test return value of check_status, but not on existing files since creating files in /opt/smartlift
        requires root
        :return:
        """

        fname = '3_R_#'  # some filename not supposed to exists in /opt/smartlift/trace

        # ---------------------------------
        # File does not exist -> NO ERROR

        type = '0x06'  # trace - type

        # input should be list
        args = [type, fname]

        # Mock the disk space check
        self.dh.check_enough_free_space = MagicMock(return_value=True)

        ret = list(self.dh.check_status(args))

        assert len(ret) == 3
        assert ret[0] == self.dh.file_status[DH.FileStatusNames.NOT_FOUND.value]
        assert ret[1] == self.dh.name
        assert ret[2] == self.dhCodes.NO_ERR.name

        # ---------------------------------
        # Input type unknown -> TYPE ERROR

        type = '11'  # wrong type

        # input should be list
        args = [type, fname]

        ret = list(self.dh.check_status(args))

        assert len(ret) == 3
        assert ret[0] == self.dh.file_status[DH.FileStatusNames.ERROR.value]
        assert ret[1] == self.dh.name
        assert ret[2] == self.dhCodes.TYPE_ERR.name

        # ---------------------------------
        # Wrong syntax on input arguments -> IN ARGS ERROR

        type = '11'  # wrong type (won't matter, since input arguments syntax should be checked first)

        # input should be list, but here is tuple
        args = (type, fname)

        ret = list(self.dh.check_status(args))

        assert len(ret) == 3
        assert ret[0] == self.dh.file_status[DH.FileStatusNames.ERROR.value]
        assert ret[1] == self.dh.name
        assert ret[2] == self.dhCodes.IN_ARGS_ERR.name

    def test_disk_usage_limit(self):
        """
        Tests that diskHandler respects the free space limit
        :return:
        """

        # Check for no error if limit is not passed

        self.dh.check_enough_free_space = MagicMock(return_value=True)

        fname = '5_gtg_1337'  # some filename
        type = '0x06'  # trace - type

        # input should be list
        args = [type, fname]
        ret = list(self.dh.check_status(args))

        assert len(ret) == 3
        assert ret[0] == self.dh.file_status[DH.FileStatusNames.NOT_FOUND.value]
        assert ret[1] == self.dh.name
        assert ret[2] == self.dhCodes.NO_ERR.name

        # ------------------------------------------------
        # Check for error if limit has been passed

        self.dh.check_enough_free_space = MagicMock(return_value=False)

        ret = list(self.dh.check_status(args))

        assert len(ret) == 3
        assert ret[0] == self.dh.file_status[DH.FileStatusNames.NOT_FOUND.value]
        assert ret[1] == self.dh.name
        assert ret[2] == self.dhCodes.DISK_LIMIT_ERR.name

    def test_get_filename(self):
        """
        Test that filename retrieval functions return a string
        """
        up_package = self.dh.get_upgrade_package_filename()
        assert up_package
        assert isinstance(up_package, str)


    @mock.patch('shutil.disk_usage')
    def test_disk_info_arg(self, mock_disk_usage):
        """
        Test arguments for get_disk_info function. Mocks result from shutil.disk_usage
        :return:
        """
        # Mocking shutil.disk_usage return, returns named tuple
        stat_tuple = collections.namedtuple('usage', 'total used free')
        stat = stat_tuple(total=17 << 20, used=18 << 20, free=19 << 20)
        mock_disk_usage.return_value = stat

        spec = self.dhArea.TOTAL.value
        disk_stat = self.dh.get_disk_info(spec)
        assert disk_stat == 17

        spec = self.dhArea.USED.value
        disk_stat = self.dh.get_disk_info(spec)
        assert disk_stat == 18

        spec = self.dhArea.FREE.value
        disk_stat = self.dh.get_disk_info(spec)
        assert disk_stat == 19

        # Should return 0 if not supported arg
        spec = 'Donny'
        disk_stat = self.dh.get_disk_info(spec)
        assert disk_stat == 0

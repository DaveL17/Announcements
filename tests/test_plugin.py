"""
Unit tests for the Announcements plugin.
"""

from tests.shared import APIBase
from tests.shared.utils import run_host_script
import datetime as dt
import httpx
import re
import sys
import textwrap
from unittest.mock import MagicMock
import dotenv
import os
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

PLUGIN_ID     = os.getenv("PLUGIN_ID")
DEVICE_FOLDER = int(os.getenv("DEVICE_FOLDER", 0))
import tests.shared.classes  # noqa


APIBase.__test__ = (
    False  # prevent pytest from collecting the abstract base class directly
)

_indigo_mock = MagicMock()
_indigo_mock.PluginBase = object
sys.modules.setdefault("indigo", _indigo_mock)
import plugin  # noqa


class TestActions(APIBase):
    """Unit tests for the Announcements plugin."""

    __test__ = True

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures by delegating to the base class."""
        super().setUpClass()

    def test_refresh_all_announcements_action(self):
        """Verify that a basic host script execution returns a result."""
        script = textwrap.dedent(f"""\
            try:
                indigo.actionGroup.execute({os.getenv('ACTION_GROUP_REFRESH_ALL_ANNOUNCEMENTS')})
                return True
            except:
                return False
            """)
        result = run_host_script(script)
        self.assertTrue(result, "The refresh all action group was not executed successfully.")

    def test_refresh_announcement_action(self):
        """Verify that a basic host script execution returns a result."""
        script = textwrap.dedent(f"""\
            try:
                indigo.actionGroup.execute({os.getenv('ACTION_GROUP_REFRESH_ANNOUNCEMENT')})
                return True
            except:
                return False
            """)
        result = run_host_script(script)
        self.assertTrue(result, "The refresh announcement action group was not executed successfully.")

    def test_speak_announcement_action(self):
        """Verify that a basic host script execution returns a result."""
        script = textwrap.dedent(f"""\
            try:
                indigo.actionGroup.execute({os.getenv('ACTION_GROUP_SPEAK_ANNOUNCEMENT')})
                return True
            except:
                return False
            """)
        result = run_host_script(script)
        self.assertTrue(result, "The speak announcement action group was not executed successfully.")

    def test_speak_announcement_trigger(self):
        """Verify that a basic host script execution returns a result."""
        script = textwrap.dedent(f"""\
            try:
                indigo.actionGroup.execute({os.getenv('TRIGGER_SPEAK_ANNOUNCEMENT')})
                return True
            except:
                return False
            """)
        result = run_host_script(script)
        self.assertTrue(result, "The speak announcement trigger was not executed successfully.")


class TestMenuItems(APIBase):

    __test__ = True

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures by delegating to the base class."""
        super().setUpClass()

    @staticmethod
    def _execute_action(action_id: str) -> bool | httpx.Response:
        """Post a plugin.executeAction command to the Indigo Web Server API.

        Args:
            action_id (str): The Indigo action ID to execute.

        Returns:
            bool | httpx.Response: The HTTP response, or False if the request failed.
        """
        try:
            message = {
                "id": "test-plugin-menu-item",
                "message": "plugin.executeAction",
                "pluginId": os.getenv("PLUGIN_ID"),
                "actionId": action_id,
            }
            url = f"{os.getenv('URL_PREFIX')}/v2/api/command/?api-key={os.getenv('GOOD_API_KEY')}"
            return httpx.post(url, json=message, verify=False)
        except Exception as e:
            print(f"API Error {e}")
            return False

    def test_refresh_announcement(self):
        """Verify that a call to `refreshAllAnnouncementsForce` fires the intended action.

        Simulates the user selecting the 'Refresh Announcements' menu item.
        """
        result = self._execute_action("refreshAllAnnouncementsForce")
        self.assertEqual(result.status_code, 200, "The menu item call was not successful.")

    def test_disable_all_plugin_devices(self):
        """Verify that a call to `comms_kill_all` fires the intended action.

        Simulates the user selecting the 'Disable All Plugin Devices' menu item.
        """
        result = self._execute_action("disableAllPluginDevices")
        self.assertEqual(result.status_code, 200, "The menu item call was not successful.")

    def test_enable_all_plugin_devices(self):
        """Verify that a call to `comms_unkill_all` fires the intended action.

        Simulates the user selecting the 'Enable All Plugin Devices' menu item.
        """
        result = self._execute_action("enableAllPluginDevices")
        self.assertEqual(result.status_code, 200, "The menu item call was not successful.")

    def test_log_plugin_information(self):
        """Verify that a call to `log_plugin_environment` fires the intended action.

        Simulates the user selecting the 'Display Plugin Information' menu item.
        """
        result = self._execute_action("displayPluginInformation")
        self.assertEqual(result.status_code, 200, "The menu item call was not successful.")


class TestValidateDeviceConfigUi(APIBase):
    """Unit tests for the validate_device_config_ui method."""

    __test__ = True

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures by delegating to the base class."""
        super().setUpClass()
        cls.mock_self     = MagicMock()
        cls.mock_self.logger = MagicMock()
        cls.mock_self.announcement_update_states = MagicMock()

    def _valid_values(self) -> dict:
        """Return a fully populated valid salutationsDevice values dict."""
        return {
            'morningStart':       '5',
            'morningMessageIn':   'Good morning',
            'morningMessageOut':  'Have a great morning',
            'afternoonStart':     '12',
            'afternoonMessageIn': 'Good afternoon',
            'afternoonMessageOut': 'Have a great afternoon',
            'eveningStart':       '17',
            'eveningMessageIn':   'Good evening',
            'eveningMessageOut':  'Have a great evening',
            'nightStart':         '22',
            'nightMessageIn':     'Good night',
            'nightMessageOut':    'Have a great night',
        }

    def test_valid_salutations_passes(self):
        """Verify that a fully valid salutations config returns True."""
        result = plugin.Plugin.validate_device_config_ui(
            self.mock_self, self._valid_values(), 'salutationsDevice', 0
        )
        self.assertTrue(result[0])

    def test_announcements_device_always_passes(self):
        """Verify that announcementsDevice validation always returns True."""
        result = plugin.Plugin.validate_device_config_ui(
            self.mock_self, {}, 'announcementsDevice', 0
        )
        self.assertTrue(result[0])

    def test_time_order_invalid(self):
        """Verify that out-of-order start times fail validation."""
        values = self._valid_values()
        values['afternoonStart'] = '3'  # less than morningStart=5
        result = plugin.Plugin.validate_device_config_ui(
            self.mock_self, values, 'salutationsDevice', 0
        )
        self.assertFalse(result[0])
        for key in ('morningStart', 'afternoonStart', 'eveningStart', 'nightStart'):
            self.assertIn(key, result[2])

    def test_empty_message_field_fails(self):
        """Verify that an empty message string fails validation."""
        values = self._valid_values()
        values['morningMessageIn'] = ''
        result = plugin.Plugin.validate_device_config_ui(
            self.mock_self, values, 'salutationsDevice', 0
        )
        self.assertFalse(result[0])
        self.assertIn('morningMessageIn', result[2])

    def test_whitespace_only_message_field_fails(self):
        """Verify that a whitespace-only message string fails validation."""
        values = self._valid_values()
        values['eveningMessageOut'] = '   '
        result = plugin.Plugin.validate_device_config_ui(
            self.mock_self, values, 'salutationsDevice', 0
        )
        self.assertFalse(result[0])
        self.assertIn('eveningMessageOut', result[2])

    def test_all_empty_message_fields_fail(self):
        """Verify that all eight message fields are checked for emptiness."""
        message_fields = (
            'morningMessageIn',   'morningMessageOut',
            'afternoonMessageIn', 'afternoonMessageOut',
            'eveningMessageIn',   'eveningMessageOut',
            'nightMessageIn',     'nightMessageOut',
        )
        for field in message_fields:
            with self.subTest(field=field):
                values = self._valid_values()
                values[field] = ''
                result = plugin.Plugin.validate_device_config_ui(
                    self.mock_self, values, 'salutationsDevice', 0
                )
                self.assertFalse(result[0])
                self.assertIn(field, result[2])


class TestAnnouncementCreateId(APIBase):
    """Unit tests for the announcement_create_id method."""

    __test__ = True

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures by delegating to the base class."""
        super().setUpClass()

    def test_announcement_create_id_returns_int(self):
        """Verify that announcement_create_id returns an integer."""
        result = plugin.Plugin.announcement_create_id({})
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0, "Returned an ID that was not greater than zero.")

    def test_announcement_create_id_not_in_dict(self):
        """Verify that the returned ID is not already a key in the dict."""
        temp_dict = {}
        result = plugin.Plugin.announcement_create_id(temp_dict)
        self.assertNotIn(result, temp_dict)

    def test_announcement_create_id_avoids_collision(self):
        """Verify that announcement_create_id produces a unique ID when a collision exists."""
        first_id = plugin.Plugin.announcement_create_id({})
        temp_dict = {first_id: "taken"}
        result = plugin.Plugin.announcement_create_id(temp_dict)
        self.assertNotIn(result, temp_dict)
        self.assertNotEqual(result, first_id, "Returned the same ID as the colliding key.")


class TestFormatDigits(APIBase):
    """Unit tests for the format_digits method."""

    __test__ = True

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures including a mock plugin instance with bound formatter methods."""
        super().setUpClass()
        cls.mock_self = MagicMock()
        cls.mock_self.logger = MagicMock()
        cls.mock_self.format_current_time = (
            lambda m1, m2: plugin.Plugin.format_current_time(cls.mock_self, m1, m2)
        )
        cls.mock_self.format_datetime = lambda m1, m2: plugin.Plugin.format_datetime(
            cls.mock_self, m1, m2
        )
        cls.mock_self.format_number = lambda m1, m2: plugin.Plugin.format_number(
            cls.mock_self, m1, m2
        )

    def _format_digits(self, announcement: str) -> str:
        """Run format_digits via re.sub using the real regex pattern.

        Args:
            announcement (str): The announcement string containing substitution patterns.

        Returns:
            str: The announcement string with all formatting substitutions applied.
        """
        regex_pattern = r"(<<.*?), *(((ct)|(dt)|(n)):.*?>>)"
        return re.sub(
            regex_pattern,
            lambda m: plugin.Plugin.format_digits(self.mock_self, m),
            announcement,
        )

    def test_format_digits_number(self):
        """Verify numeric formatting at various decimal precisions."""
        self.assertEqual(self._format_digits("<<123.45, n:0>>"), "123")
        self.assertEqual(self._format_digits("<<123.45, n:1>>"), "123.5")
        self.assertEqual(self._format_digits("<<123.45, n:2>>"), "123.45")
        self.assertEqual(self._format_digits("<<123.45, n:3>>"), "123.450")

    def test_format_digits_number_negative(self):
        """Verify numeric formatting works correctly for negative numbers."""
        self.assertEqual(self._format_digits("<<-5.0, n:1>>"), "-5.0")
        self.assertEqual(self._format_digits("<<-5.0, n:0>>"), "-5")

    def test_format_digits_number_zero(self):
        """Verify numeric formatting works correctly for zero."""
        self.assertEqual(self._format_digits("<<0, n:2>>"), "0.00")

    def test_format_digits_number_invalid_specifier(self):
        """Verify that an invalid numeric specifier returns the error string."""
        result = self._format_digits("<<123.45, n:z>>")
        self.assertIn("Unallowable", result)

    def test_format_digits_datetime(self):
        """Verify datetime and current-time formatting using dt: and ct: specifiers."""
        self.assertEqual(
            self._format_digits("<<2019-06-21 09:01:14.974913, dt:%A>>"), "Friday"
        )
        self.assertEqual(
            self._format_digits("<<2019-06-21 09:01:14.974913, dt:%m-%d>>"), "06-21"
        )
        self.assertEqual(
            self._format_digits("<<2019-06-21 09:01:14.974913, dt:%H:%M>>"), "09:01"
        )

    def test_format_digits_datetime_invalid_specifier(self):
        """Verify that an invalid datetime specifier returns the error string."""
        result = self._format_digits("<<2019-06-21 09:01:14.974913, dt:!invalid>>")
        self.assertIn("Unallowable", result)

    def test_format_digits_current_time(self):
        """Verify ct: specifier returns the current time, ignoring match1."""
        now = dt.datetime.now()
        result_hm  = self._format_digits(f"<<{now}, ct:%H:%M>>")
        result_year = self._format_digits("<<ignored-value, ct:%Y>>")
        self.assertEqual(result_hm, now.strftime("%H:%M"))
        self.assertEqual(result_year, dt.datetime.now().strftime("%Y"))

    def test_format_digits_current_time_invalid_specifier(self):
        """Verify that an invalid ct: specifier returns the error string."""
        result = self._format_digits("<<now, ct:!invalid>>")
        self.assertIn("Unallowable", result)

    def test_format_digits_fallback(self):
        """Verify that an unrecognized specifier returns the raw value and specifier joined."""
        regex_pattern = r"(<<.*?), *(((ct)|(dt)|(n)|(\w+)):.*?>>)"
        result = re.sub(
            regex_pattern,
            lambda m: plugin.Plugin.format_digits(self.mock_self, m),
            "<<somevalue, xx:something>>",
        )
        self.assertEqual(result, "somevalue xx:something")


# ===================================== Devices =====================================
class TestDevices(APIBase):
    """Tests for plugin devices defined in Devices.xml."""

    @classmethod
    def setUpClass(cls):
        """Skip APIBase setup; tests use module-level env vars."""
        pass

    @staticmethod
    def payload(name: str = "", device_type_id: str = "", props: dict = None) -> str:
        """Generate a host script payload for creating a plugin device.

        Args:
            name (str): The quoted device name string passed to the host script.
            device_type_id (str): The Indigo device type ID from Devices.xml.
            props (dict): The device props dict passed to the host script.

        Returns:
            str: The host script string.
        """
        return textwrap.dedent(f"""\
            try:
                import time
                indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    name={name},
                    description='Announcements plugin unit test device',
                    pluginId='{PLUGIN_ID}',
                    deviceTypeId='{device_type_id}',
                    props={props},
                    folder={DEVICE_FOLDER}
                )
                time.sleep(1)
                return True
            except:
                return False
        """)

    @staticmethod
    def confirm_creation(name: str = "") -> str:
        """Generate a host script that confirms a device was created.

        Args:
            name (str): The quoted device name string to look up.

        Returns:
            str: The host script string.
        """
        return textwrap.dedent(f"""\
            if {name} in [dev.name for dev in indigo.devices.iter('{PLUGIN_ID}')]:
                return True
            else:
                return False
        """)

    @staticmethod
    def delete_device(name: str = "") -> str:
        """Generate a host script that deletes a plugin device.

        Args:
            name (str): The quoted device name string to delete.

        Returns:
            str: The host script string.
        """
        return textwrap.dedent(f"""\
            try:
                indigo.device.delete({name})
                return True
            except:
                return False
        """)

    def create_and_delete_device(self, name: str, device_type_id: str, props: dict) -> None:
        """Create a plugin device, confirm it exists, then delete it.

        Args:
            name (str): The quoted device name string passed to the host script.
            device_type_id (str): The Indigo device type ID from Devices.xml.
            props (dict): The device props dict passed to the host script.
        """
        host_script = self.payload(name, device_type_id, props)
        run_host_script(host_script)
        self.assertTrue(host_script, "Device creation successful.")

        host_script = self.confirm_creation(name)
        self.assertTrue(host_script, "Could not confirm the device was created.")

        host_script = self.delete_device(name)
        run_host_script(host_script)
        self.assertTrue(host_script, "Device deletion failed.")

    # ================================= Announcements Device ==================================
    def test_announcements_device_creation(self):
        """Verify that an Announcements device can be created and deleted via the Indigo API."""
        my_props = {}
        self.create_and_delete_device(
            "'ann_unit_test_announcements_device'",
            'announcementsDevice',
            my_props
        )

    # ================================== Salutations Device ===================================
    def test_salutations_device_creation(self):
        """Verify that a Salutations device can be created and deleted via the Indigo API."""
        my_props  = {'morningStart':       '5',
                     'morningMessageIn':   'Good morning',
                     'morningMessageOut':  'Have a great morning',
                     'afternoonStart':     '12',
                     'afternoonMessageIn':  'Good afternoon',
                     'afternoonMessageOut': 'Have a great afternoon',
                     'eveningStart':       '17',
                     'eveningMessageIn':   'Good evening',
                     'eveningMessageOut':  'Have a great evening',
                     'nightStart':         '22',
                     'nightMessageIn':     'Good night',
                     'nightMessageOut':    'Have a great night'}
        self.create_and_delete_device(
            "'ann_unit_test_salutations_device'",
            'salutationsDevice',
            my_props
        )

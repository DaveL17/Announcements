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

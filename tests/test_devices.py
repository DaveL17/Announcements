"""
Unit tests for the Announcements plugin.
"""
import datetime as dt
import pathlib
import re
import sys
from unittest.mock import MagicMock
from shared import APIBase
import shared.classes  # noqa
from shared.utils import run_host_script

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "Announcements.indigoPlugin/Contents/Server Plugin"))
_indigo_mock              = MagicMock()
_indigo_mock.PluginBase   = object
sys.modules.setdefault('indigo', _indigo_mock)
import plugin  # noqa


class TestPlugin(APIBase):
    """
    Unit tests for the Announcements plugin.
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mock_self                     = MagicMock()
        cls.mock_self.logger              = MagicMock()
        cls.mock_self.format_current_time = lambda m1, m2: plugin.Plugin.format_current_time(cls.mock_self, m1, m2)
        cls.mock_self.format_datetime     = lambda m1, m2: plugin.Plugin.format_datetime(cls.mock_self, m1, m2)
        cls.mock_self.format_number       = lambda m1, m2: plugin.Plugin.format_number(cls.mock_self, m1, m2)

    def test_sample(self):
        result = run_host_script("indigo.server.log('test sample')")
        print(f"test sample: {result}")

    # ===================================== Format Digits =====================================
    def _format_digits(self, announcement: str) -> str:
        """Run format_digits via re.sub using the real regex pattern.

        Args:
            announcement: The announcement string containing substitution patterns.

        Returns:
            The announcement string with all formatting substitutions applied.
        """
        regex_pattern = r'(<<.*?), *(((ct)|(dt)|(n)):.*?>>)'
        return re.sub(regex_pattern, lambda m: plugin.Plugin.format_digits(self.mock_self, m), announcement)

    def test_format_digits_number_zero_decimals(self):
        self.assertEqual(self._format_digits("<<123.45, n:0>>"), "123")

    def test_format_digits_number_one_decimal(self):
        self.assertEqual(self._format_digits("<<123.45, n:1>>"), "123.5")

    def test_format_digits_number_two_decimals(self):
        self.assertEqual(self._format_digits("<<123.45, n:2>>"), "123.45")

    def test_format_digits_number_three_decimals(self):
        self.assertEqual(self._format_digits("<<123.45, n:3>>"), "123.450")

    def test_format_digits_datetime_day_of_week(self):
        self.assertEqual(self._format_digits("<<2019-06-21 09:01:14.974913, dt:%A>>"), "Friday")

    def test_format_digits_datetime_month_day(self):
        self.assertEqual(self._format_digits("<<2019-06-21 09:01:14.974913, dt:%m-%d>>"), "06-21")

    def test_format_digits_datetime_time(self):
        self.assertEqual(self._format_digits("<<2019-06-21 09:01:14.974913, dt:%H:%M>>"), "09:01")

    def test_format_digits_current_time(self):
        now    = dt.datetime.now()
        result = self._format_digits(f"<<{now}, ct:%H:%M>>")
        self.assertEqual(result, now.strftime("%H:%M"))

    # ===================================== Create Announcement ID =====================================
    def test_announcement_create_id_returns_int(self):
        result = plugin.Plugin.announcement_create_id({})
        self.assertIsInstance(result, int)

    def test_announcement_create_id_not_in_dict(self):
        temp_dict = {}
        result    = plugin.Plugin.announcement_create_id(temp_dict)
        self.assertNotIn(result, temp_dict)

    def test_announcement_create_id_avoids_collision(self):
        first_id  = plugin.Plugin.announcement_create_id({})
        temp_dict = {first_id: "taken"}
        result    = plugin.Plugin.announcement_create_id(temp_dict)
        self.assertNotIn(result, temp_dict)

"""
Tests for the Announcements plugin.

The test_plugin module contains all unit tests for the Announcements plugin. If all tests pass, the module will return
True.
"""
from unittest import TestCase
import datetime as dt
import logging
import indigo  # noqa

LOGGER = logging.getLogger('Plugin')

class TestPlugin(TestCase):
    def __init__(self):
        super().__init__()

    @staticmethod
    def my_tests(plugin):
        test_case = TestCase()
        now = dt.datetime.now()
        try:
            test_case.assertIsInstance(plugin.__announcement_file_read__(), dict, "didn't return a dict object.")
            test_case.assertIsInstance(plugin.announcements_export_action(None), str, "didn't return a str object.")
            test_case.assertIsInstance(plugin.generator_announcement_list("", {}, "", 0), list, "didn't return a list object.")
            test_case.assertIsInstance(plugin.generator_device_list("", {}, "", 0), list, "didn't return a list object.")
            test_case.assertIsInstance(plugin.generator_dev_var("", {}, "", 0), list, "didn't return a list object.")
            test_case.assertIsInstance(plugin.generator_state_or_value("", {}, "", 0), list, "didn't return a list object.")
            test_case.assertIsInstance(plugin.generator_time(), list, "didn't return a list object.")

            test_case.assertEqual(plugin.format_datetime("2019-06-21 09:01:14.974913", "%A"), "Friday", "Didn't format the date properly.")
            test_case.assertEqual(plugin.format_current_time(f"{now}", "%H:%M"), f"{now.strftime('%H:%M')}", "didn't format the current time properly.")
            test_case.assertEqual(plugin.format_number('2', '1'), "2.0", "didn't format the number properly.")

            # Substitution format specifiers
            test_case.assertEqual(plugin.substitution_regex("<<123.45, n:0>>"), "123", "Didn't format the number properly.")
            test_case.assertEqual(plugin.substitution_regex("<<123.45, n:1>>"), "123.5", "Didn't format the number properly.")
            test_case.assertEqual(plugin.substitution_regex("<<123.45, n:2>>"), "123.45", "Didn't format the number properly.")
            test_case.assertEqual(plugin.substitution_regex("<<123.45, n:3>>"), "123.450", "Didn't format the number properly.")
            test_case.assertEqual(plugin.substitution_regex("<<2019-06-21 09:01:14.974913, dt:%m-%d>>"), "06-21", "Didn't format the date properly.")
            test_case.assertEqual(plugin.substitution_regex("<<2019-06-21 09:01:14.974913, dt:%A>>"), "Friday", "Didn't format the date properly.")
            test_case.assertEqual(plugin.substitution_regex("<<2019-06-21 09:01:14.974913, dt:%H:%M>>"), "09:01", "Didn't format the time properly.")
            test_case.assertEqual(plugin.substitution_regex(f"<<{now}, ct:%H:%M>>"), f"{now.strftime('%H:%M')}", f"Didn't format the time properly.")
            test_case.assertEqual(plugin.substitution_regex("<<2, n:1>>"), "2.0", "Didn't format the number properly.")

        except AssertionError as error:
            LOGGER.critical(f"{error}")
            return False

        return True

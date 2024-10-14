# noqa pylint: disable=too-many-lines, line-too-long, invalid-name, unused-argument, redefined-builtin, broad-except, fixme

"""
Announcements Indigo Plugin
Author: DaveL17

The Announcements Plugin is used to construct complex announcements for use with text-to-speech tools in Indigo. The
plugin provides a simple call to the indigo.server.speak() hook for simple audio announcements; however, the plugin is
more geared towards creating announcements to be used with more advanced speech tools.
"""

# ================================== IMPORTS ==================================

# Built-in modules
import ast
import datetime as dt
import json
import logging
import os
import re
import shutil
import string

# Third-party modules
try:
    import indigo  # noqa
    from dateutil import parser  # noqa
    import pydevd  # noqa
except ImportError as error:
    pass

# My modules
import DLFramework.DLFramework as Dave
from constants import *  # noqa
from plugin_defaults import kDefaultPluginPrefs  # noqa

# =================================== HEADER ==================================
__author__    = Dave.__author__
__copyright__ = Dave.__copyright__
__license__   = Dave.__license__
__build__     = Dave.__build__
__title__     = 'Announcements Plugin for Indigo Home Control'
__version__   = '2023.1.0'


# ==============================================================================
class Plugin(indigo.PluginBase):
    """
    Standard Indigo Plugin Class

    :param indigo.PluginBase:
    """

    def __init__(self, plugin_id: str = "", plugin_display_name: str = "", plugin_version: str = "",
                 plugin_prefs: indigo.Dict = None):
        """
        Plugin initialization

        :param str plugin_id:
        :param str plugin_display_name:
        :param str plugin_version:
        :param indigo.Dict plugin_prefs:
        """
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        # ============================ Instance Attributes =============================
        self.announcements_file   = ""
        self.debug_level          = int(self.pluginPrefs.get('showDebugLevel', "30"))
        self.pluginIsInitializing = True
        self.pluginIsShuttingDown = False
        self.update_frequency     = int(self.pluginPrefs.get('pluginRefresh', 15))

        # ================================== Logging ===================================
        self.plugin_file_handler.setFormatter(logging.Formatter(fmt=Dave.LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))
        self.indigo_log_handler.setLevel(self.debug_level)

        # =========================== Initialize DLFramework ===========================
        self.Fogbert = Dave.Fogbert(self)

        # ============================= Remote Debugging ==============================
        try:
            pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
        except:
            pass

        self.pluginIsInitializing = False

    def log_plugin_environment(self):
        """
        Log pluginEnvironment information when plugin is first started
        """
        self.Fogbert.pluginEnvironment()

    # ==============================================================================
    def __del__(self):
        """
        Title Placeholder

        :return:
        """
        indigo.PluginBase.__del__(self)

    # =============================================================================
    # ============================== Indigo Methods ===============================
    # =============================================================================
    def closed_device_config_ui(self, values_dict: indigo.Dict=None, user_cancelled: bool=False, type_id: str= "", dev_id: int=0):  # noqa
        """
        Standard Indigo method called when device preferences dialog is closed.

        :param indigo.Dict values_dict:
        :param bool user_cancelled:
        :param str type_id:
        :param int dev_id:
        :return:
        """
        if not user_cancelled:
            self.announcement_update_states(force=True)
            self.logger.debug("closed_device_config_ui()")
        else:
            self.logger.debug("Device configuration cancelled.")

    # =============================================================================
    def closed_prefs_config_ui(self, values_dict: indigo.Dict=None, user_cancelled: bool=False) -> indigo.Dict:  # noqa
        """
        Standard Indigo method called when plugin preferences dialog is closed.

        :param indigo.Dict values_dict:
        :param bool user_cancelled:
        :return indigo.Dict values_dict:
        """
        if not user_cancelled:
            # Ensure that self.pluginPrefs includes any recent changes.
            for k in values_dict:
                self.pluginPrefs[k] = values_dict[k]

            # Debug Logging
            self.debug_level = int(values_dict.get('showDebugLevel', 10))
            self.indigo_log_handler.setLevel(self.debug_level)
            indigo.server.log(f"Debugging on (Level: {DEBUG_LABELS[self.debug_level]} ({self.debug_level})")

            # Plugin-specific actions
            self.update_frequency = int(values_dict.get('pluginRefresh', 15))

            # Update the devices to reflect any changes
            self.announcement_update_states()
            self.logger.debug("Plugin prefs saved.")

        else:
            self.logger.debug("Plugin prefs cancelled.")

        return values_dict

    # =============================================================================
    @staticmethod
    def device_start_comm(dev: indigo.Device):  # noqa
        """
        Standard Indigo method when device comm enabled

        :param indigo.Device dev:
        :return:
        """
        dev.stateListOrDisplayStateIdChanged()
        dev.updateStateOnServer('onOffState', value=True, uiValue=" ")

    # =============================================================================
    @staticmethod
    def device_stop_comm(dev: indigo.Device):  # noqa
        """
        Standard Indigo method when device comm enabled

        :param indigo.Device dev:
        :return:
        """
        dev.updateStateOnServer('onOffState', value=False, uiValue=" ")

    # =============================================================================
    @staticmethod
    def get_device_config_ui_values(values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """
        Standard Indigo method when device config menu opened.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.Dict values_dict:
        """
        # Set the device to disabled while it's being edited.
        indigo.device.enable(dev_id, value=False)

        # Ensure that the dialog opens with fresh fields.
        if type_id == 'announcementsDevice':
            for key in (
                    'announcementName',
                    'announcementList',
                    'announcementRefresh',
                    'announcementText',
                    'subGeneratorResult'
            ):
                values_dict[key] = ''

        return values_dict

    # =============================================================================
    def get_device_state_list(self, dev: indigo.Device=None):  # noqa
        """
        Standard Indigo method to provide dynamic state list definition information.

        :param indigo.Device dev:
        :return list dev_state_list:
        """
        local_vars = {}

        if dev.deviceTypeId not in self.devicesTypeDict:
            return None

        default_states_list = self.devicesTypeDict[dev.deviceTypeId]['States']

        # Open the announcements file and load the contents
        local_vars['announcements'] = self.__announcement_file_read__()

        # Sort the dict and create a list of tuples.
        try:
            announcement_list = [
                (key, local_vars['announcements'][dev.id][key]['Name'])
                for key in local_vars['announcements'][dev.id]
            ]
        except KeyError:
            announcement_list = []

        # Iterate through the list of tuples and save each announcement name as a device key. Keys (state id's) can't
        # contain Unicode.
        for thing in announcement_list:
            thing_name         = thing[1].replace(' ', '_')
            announcement_state = (self.getDeviceStateDictForStringType(thing_name, thing_name, thing_name))
            default_states_list.append(announcement_state)

        return default_states_list

    # =============================================================================
    def run_concurrent_thread(self):  # noqa
        """
        Standard Indigo Concurrent Thread

        :return:
        """
        try:
            while True:
                self.update_frequency = int(self.pluginPrefs.get('pluginRefresh', 15))
                self.announcement_update_states()
                self.sleep(self.update_frequency)
        except self.StopThread:
            pass

    # =============================================================================
    def startup(self):
        """
        Standard Indigo Startup Method

        :return:
        """

        # ============================= Audit Announcements ============================
        path_string             = "/Preferences/Plugins/com.fogbert.indigoplugin.announcements.txt"
        self.announcements_file = f"{indigo.server.getInstallFolderPath()}{path_string}"
        self.initialize_announcements_file()

        # ============= Delete Out of Date Announcements ===============
        # Open the announcements file and load the contents
        infile = self.__announcement_file_read__()

        # Look at each plugin device id and delete any announcements if there is no longer an associated device.
        del_keys = [key for key in infile if key not in indigo.devices]

        if len(del_keys) > 0:
            _ = [infile.pop(key, None) for key in del_keys]

        # Look at each plugin device and construct a placeholder if not already present.
        for dev in indigo.devices.iter('self'):
            if dev.id not in infile:
                infile[dev.id] = {}

        # Open the announcements file and save the new dict.
        self.__announcement_file_write__(infile)

    # =============================================================================
    def validate_device_config_ui(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0):  # noqa
        """
        Standard Indigo method called before device config dialog is closed.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return (bool, indigo.Dict):
        """
        error_msg_dict = indigo.Dict()

        # Announcements device - We do Announcements Device validation elsewhere in the code.
        if type_id == 'announcementsDevice':
            return True, values_dict

        # Salutations device
        if type_id == 'salutationsDevice':
            try:
                if not (
                    int(values_dict['morningStart'])
                    < int(values_dict['afternoonStart'])
                    < int(values_dict['eveningStart'])
                    < int(values_dict['nightStart'])
                ):
                    for key in ('morningStart', 'afternoonStart', 'eveningStart', 'nightStart'):
                        error_msg_dict[key] = "Each start time must be greater than the prior one."

            except ValueError:
                for key in ('morningStart', 'afternoonStart', 'eveningStart', 'nightStart'):
                    error_msg_dict[key] = "You must set *all* the time controls to proceed. Otherwise, select cancel."

        if len(error_msg_dict) > 0:
            return False, values_dict, error_msg_dict

        self.announcement_update_states()
        return True, values_dict

    # =============================================================================
    # ============================== Plugin Methods ===============================
    # =============================================================================
    @staticmethod
    def __announcement_clear__(values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> indigo.Dict:  # noqa
        """
        Clear announcement data from input field

        Clears whatever is in the Announcement textfield.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return indigo.Dict values_dict:
        """
        for key in (
                'announcementIndex',
                'announcementName',
                'announcementRefresh',
                'announcementList',
                'announcementText'
        ):
            values_dict[key] = ''

        values_dict['editFlag'] = False

        return values_dict

    # =============================================================================
    @staticmethod
    def announcement_create_id(temp_dict: dict=None) -> int:  # noqa
        """
        Create a unique ID number for the announcement

        In order to properly track the various announcement strings, we must assign each one a unique ID number. We
        check to see if the number has already been assigned to another announcement and, if not, the new ID is
        assigned.

        :param dict temp_dict:
        :return int:
        """
        local_vars = {}  # noqa

        # Create a new index number.
        local_vars['index'] = id('dummy object')

        # If the new index happens to exist, repeat until unique.
        while local_vars['index'] in temp_dict:
            local_vars['index'] += 1

        return local_vars['index']

    # =============================================================================
    def __announcement_delete__(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """
        Delete the highlighted announcement

        Called when user clicks the Delete Announcement button

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.Dict values_dict:
        """
        # Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()

        index = values_dict['announcementList']
        del announcements[dev_id][index]

        # Open the announcements file and save the new dict.
        self.__announcement_file_write__(announcements)

        for key in (
                'announcementIndex',
                'announcementName',
                'announcementRefresh',
                'announcementList',
                'announcementText'
        ):
            values_dict[key] = ''

        values_dict['editFlag'] = False

        return values_dict

    # =============================================================================
    def __announcement_duplicate__(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """
        Create a duplicate of the selected announcement

        Called when user clicks the Duplicate Announcement button.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.Dict values_dict:
        """
        index = values_dict['announcementList']
        self.logger.info(f"Announcement to be duplicated: {index}")

        # Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()

        # Create a new announcement.
        temp_dict                            = announcements[dev_id]
        new_index                            = self.announcement_create_id(temp_dict)
        temp_dict[new_index]                 = {}
        temp_dict[new_index]['Name']         = announcements[dev_id][index]['Name'] + " copy"
        temp_dict[new_index]['Announcement'] = announcements[dev_id][index]['Announcement']
        temp_dict[new_index]['Refresh']      = announcements[dev_id][index]['Refresh']
        temp_dict[new_index]['nextRefresh']  = announcements[dev_id][index]['nextRefresh']

        # Set the dict element equal to the new list
        announcements[dev_id] = temp_dict

        # Open the announcements file and save the new dict.
        self.__announcement_file_write__(announcements)

        return values_dict

    # =============================================================================
    def __announcement_edit__(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """
        Load the selected announcement for editing

        Called when user clicks the Edit Announcement button.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.Dict values_dict:
        """
        self.logger.debug(f"Editing the {values_dict['announcementName']} announcement")

        # Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()
        temp_dict     = announcements[dev_id]

        # Get the selected announcement index and populate the UI elements.
        index                              = values_dict['announcementList']
        values_dict['announcementIndex']   = index
        values_dict['announcementName']    = temp_dict[index]['Name']
        values_dict['announcementRefresh'] = temp_dict[index]['Refresh']
        values_dict['announcementText']    = temp_dict[index]['Announcement']
        values_dict['editFlag']            = True

        return values_dict

    # =============================================================================
    def __announcement_file_read__(self) -> dict:
        """
        Load the selected announcement file and return its contents

        :return indigo.Dict values_dict:
        """
        with open(self.announcements_file, mode='r', encoding="utf-8") as infile:
            d = infile.read()
            # source is JSON
            try:
                d = json.loads(d)  # yields dict

            # source is not JSON
            except json.decoder.JSONDecodeError:
                self.logger.debug("Converting announcements database to JSON")
                d = ast.literal_eval(node_or_string=d)  # yields dict

                with open(self.announcements_file, 'w', encoding="utf-8") as outfile:
                    json.dump(d, outfile, ensure_ascii=False, indent=4)

        # Convert the string keys to int keys
        return {int(key): value for key, value in d.items()}

    # =============================================================================
    def __announcement_file_write__(self, announcements: dict) -> bool:
        """
        Write the selected announcement file to disk

        :param dict announcements:
        :return bool:
        """
        # Open the announcements file and write the contents
        with open(self.announcements_file, mode='w', encoding="utf-8") as outfile:
            json.dump(announcements, outfile, ensure_ascii=False, indent=4)
        return True

    # =============================================================================
    def announcement_refresh_action(self, plugin_action: indigo.actionGroup):
        """
        Refresh an announcement in response to Indigo Action call

        The announcement_refresh_action() method is used to force an announcement to be refreshed by using an Indigo
        Action Item.

        :param indigo.actionGroup plugin_action:
        """
        announcement_name = plugin_action.props['announcementToRefresh']
        device_id         = int(plugin_action.props['announcementDeviceToRefresh'])
        dev               = indigo.devices[device_id]

        # Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()

        # Iterate through the keys to find the right announcement to update.
        announcement_dict = announcements[int(device_id)]
        for key in announcement_dict:
            if announcement_dict[key]['Name'] == announcement_name.replace('_', ' '):
                announcement = self.substitute(announcements[device_id][key]['Announcement'])
                result       = self.substitution_regex(announcement=announcement)
                dev.updateStateOnServer(announcement_name, value=result)

        self.logger.info(f"Refreshed {announcement_name} announcement.")

    # =============================================================================
    def __announcement_save__(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """
        Save the current announcement

        Called when user clicks the Save Announcement button.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.Dict values_dict:
        """
        error_msg_dict = indigo.Dict()

        # ===================== Validation Methods =====================
        # Strip leading and trailing whitespace if there is any.
        values_dict['announcementName'] = values_dict['announcementName'].strip()

        # Announcement Name
        if values_dict['announcementName'].isspace() \
                or values_dict['announcementName'] in ('', 'REQUIRED',) \
                or values_dict['announcementName'][0].isdigit() \
                or values_dict['announcementName'][0] in set(string.punctuation) \
                or values_dict['announcementName'][0:3].lower() == 'xml':
            values_dict['announcementName']    = 'REQUIRED'
            error_msg_dict['announcementName'] = (
                "A announcement name is required. It cannot start with a number, a form of punctuation or the letters "
                "'xml'."
            )

        # Announcement Text
        if values_dict['announcementText'].isspace() or values_dict['announcementText'] in ('', 'REQUIRED',):
            values_dict['announcementText']    = 'REQUIRED'
            error_msg_dict['announcementText'] = "An announcement is required."

        # Refresh time
        try:
            if float(values_dict['announcementRefresh']) <= 0:
                values_dict['announcementRefresh']    = 1
                error_msg_dict['announcementRefresh'] = "The refresh interval must be a number greater than zero."
        except ValueError:
            values_dict['announcementRefresh']    = 1
            error_msg_dict['announcementRefresh'] = "The refresh interval must be a numeric value greater than zero."

        if len(error_msg_dict) > 0:
            error_msg_dict['showAlertText'] = (
                "Configuration Errors\n\nThere are one or more settings that need to be corrected. Fields requiring "
                "attention will be highlighted."
            )
            return values_dict, error_msg_dict

        # =====================================================================
        # There are no validation errors, so let's continue. Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()

        try:
            temp_dict = announcements[dev_id]
        except KeyError:
            temp_dict = {}

        # Generate a list of announcement names in use for this device.
        announcement_name_list = [temp_dict[key]['Name'] for key in temp_dict]

        # If new announcement, create unique id, then save to dict.
        if not values_dict['editFlag'] and values_dict['announcementName'] not in announcement_name_list:
            index             = self.announcement_create_id(temp_dict=temp_dict)
            temp_dict[index]  = {
                'Name': values_dict['announcementName'],
                'Announcement': values_dict['announcementText'],
                'Refresh': values_dict['announcementRefresh'],
                'nextRefresh': f"{dt.datetime.now()}"
            }

        # If key exists, save to dict.
        elif values_dict['editFlag']:
            index                            = values_dict['announcementIndex']
            temp_dict[index]['Name']         = values_dict['announcementName']
            temp_dict[index]['Announcement'] = values_dict['announcementText']
            temp_dict[index]['Refresh']      = values_dict['announcementRefresh']

        # User has created a new announcement with a name already in use. We add ' X' to the name
        # and write a warning to the log.
        else:
            index            = self.announcement_create_id(temp_dict=temp_dict)
            temp_dict[index] = {
                'Name': f"{values_dict['announcementName']} X",
                'Announcement': values_dict['announcementText'],
                'Refresh': values_dict['announcementRefresh'],
                'nextRefresh': f"{dt.datetime.now()}"
            }
            self.logger.warning("Duplicate announcement name found. Temporary correction applied.")

        # Set the dict element equal to the new list
        announcements[dev_id] = temp_dict

        # Open the announcements file and save the new dict.
        self.__announcement_file_write__(announcements)

        # Clear the fields.
        for key in (
                'announcementIndex',
                'announcementName',
                'announcementRefresh',
                'announcementList',
                'announcementText'
        ):
            values_dict[key] = ''
        values_dict['editFlag'] = False

        return values_dict

    # =============================================================================
    def announcement_speak(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """
        Speak the selected announcement

        Called when user clicks the Speak Announcement button. If an announcement is selected in the list, that is the
        announcement that will be spoken, if there is announcement data in the text fields, that will be what is spoken.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.Dict values_dict:
        """
        default_string = "Please select or enter an item to speak."
        result         = ""

        # The user has entered a value in the announcement field. Speak that.
        if len(values_dict['announcementText']) > 0:
            result = self.substitution_regex(announcement=self.substitute(values_dict['announcementText']))
            indigo.server.speak(result, waitUntilDone=False)
            self.logger.info(f"{result}")

        # If the announcement field is blank, and the user has selected an announcement in the list.
        elif values_dict['announcementList'] != "":
            # Open the announcements file and load the contents
            announcements = self.__announcement_file_read__()
            announcement  = self.substitute(announcements[dev_id][values_dict['announcementList']]['Announcement'])
            result        = self.substitution_regex(announcement=announcement)
            indigo.server.speak(result, waitUntilDone=False)

            self.logger.info(f"{result}")

        # Otherwise, let the user know that there is nothing to speak.
        else:
            self.logger.error(default_string)
            indigo.server.speak(default_string, waitUntilDone=False)

        # If enabled in plugin prefs, save copy of the current announcement to variable called
        # 'spoken_announcement_raw'. This is done to allow the Speak Announcement button to trigger speech in another
        # application.
        try:
            if self.pluginPrefs.get('saveToVariable', False):
                indigo.variable.updateValue('spoken_announcement_raw', result)
                self.logger.debug("Announcement saved to variable: `spoken_announcement_raw`")
        # Variable does not exist.
        except ValueError:
            self.logger.warning(
                "Please create an Indigo variable named 'spoken_announcement_raw' or disable the 'Save to Variable' "
                "feature in plugin preferences if it's no longer needed."
            )
        return values_dict

    # =============================================================================
    def announcements_export_action(self, plugin_action: indigo.actionGroup) -> str:  # noqa
        """
        Return a copy of the announcements database in JSON format

        The call to announcements_export() is a request to receive a copy of the announcements database in JSON format.
        It will be provided agnostically; the complete database will be provided.

        :param indigo.actionGroup plugin_action:
        :return str:
        """
        # Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()
        return json.dumps(announcements)

    # =============================================================================
    def announcement_speak_action(self, plugin_action: indigo.actionGroup):
        """
        Speak an announcement in response to an Indigo action item

        Indigo action for speaking any device state or variable value.

        :param indigo.actionGroup plugin_action:
        """
        item_source   = int(plugin_action.props['announcementDeviceToRefresh'])
        item_to_speak = plugin_action.props['announcementToSpeak']

        try:
            if indigo.devices[item_source] in indigo.devices:
                announcement = f"{indigo.devices[item_source].states[item_to_speak]}"
                indigo.server.speak(announcement, waitUntilDone=False)
            else:
                announcement = indigo.variables[item_source].value
                indigo.server.speak(announcement, waitUntilDone=False)

        except ValueError:
            self.logger.warning(f"Unable to speak {item_to_speak} value.")
            self.logger.debug("Error: ", exc_info=True)

        except KeyError:
            self.logger.warning(f"No announcements to speak for this device {item_to_speak}")
            self.logger.debug("Error: ", exc_info=True)

    # =============================================================================
    def __update_salutations_device__(self, dev: indigo.Device):
        """
        Updates salutations device

        :param indigo.Device dev:
        """
        states_list = []
        now         = dt.datetime.now()
        today       = dt.datetime.today().date()

        morning_start   = int(dev.pluginProps.get('morningStart', '5'))
        afternoon_start = int(dev.pluginProps.get('afternoonStart', '12'))
        evening_start   = int(dev.pluginProps.get('eveningStart', '17'))
        night_start     = int(dev.pluginProps.get('nightStart', '21'))
        morning         = dt.datetime.combine(today, dt.time(morning_start, 0))
        afternoon       = dt.datetime.combine(today, dt.time(afternoon_start, 0))
        evening         = dt.datetime.combine(today, dt.time(evening_start, 0))
        night           = dt.datetime.combine(today, dt.time(night_start, 0))

        # Determine proper salutation based on the current time.
        if morning <= now < afternoon:
            intro_value = dev.pluginProps.get('morningMessageIn', 'Good morning.')
            outro_value = dev.pluginProps.get('morningMessageOut', 'Have a great morning.')

        elif afternoon <= now < evening:
            intro_value = dev.pluginProps.get('afternoonMessageIn', 'Good afternoon.')
            outro_value = dev.pluginProps.get('afternoonMessageOut', 'Have a great afternoon.')

        elif evening <= now < night:
            intro_value = dev.pluginProps.get('eveningMessageIn', 'Good evening.')
            outro_value = dev.pluginProps.get('eveningMessageOut', 'Have a great evening.')

        else:
            intro_value = dev.pluginProps.get('nightMessageIn', 'Good night.')
            outro_value = dev.pluginProps.get('nightMessageOut', 'Have a great night.')

        # Don't update the device state unless the value has changed.
        if intro_value != dev.states['intro']:
            self.logger.debug(f"Updating intro to: {intro_value}")
            states_list.append({'key': 'intro', 'value': intro_value})

        if outro_value != dev.states['outro']:
            self.logger.debug(f"Updating outro to: {outro_value}")
            states_list.append({'key': 'outro', 'value': outro_value})

        states_list.append({'key': 'onOffState', 'value': True, 'uiValue': " "})
        dev.updateStatesOnServer(states_list)

    # =============================================================================
    def __update_announcements_device__(self, dev: indigo.Device, announcements: dict, force: bool = False) -> dict:
        """
        Updates salutations device

        :param indigo.Device dev:
        :param dict announcements:
        :param bool force:
        :return dict announcements:
        """
        now         = dt.datetime.now()
        states_list = []

        # Look at each plugin device and construct a placeholder if not already present. This is a placeholder and
        # doesn't actually write the key back to the file.
        try:
            if dev.id not in announcements:
                announcements[dev.id] = {}

            for key in announcements[dev.id]:
                state_name = announcements[dev.id][key]['Name'].replace(' ', '_')
                state_name = f"{state_name}"
                try:
                    refresh_time = announcements[dev.id][key].get('nextRefresh', '1970-01-01 00:00:00')
                    update_time  = parser.parse(refresh_time)

                except ValueError:
                    self.logger.warning("Error coercing announcement update time.")
                    self.logger.debug("Error: ", exc_info=True)
                    update_time = now - dt.timedelta(minutes=1)

                # If it's time for an announcement to be refreshed.
                if now >= update_time:
                    # Update the announcement text.
                    announcement = self.substitute(announcements[dev.id][key]['Announcement'])
                    result       = self.substitution_regex(announcement)
                    states_list.append({'key': state_name, 'value': result})

                    # Set the next refresh time
                    next_update = now + dt.timedelta(minutes=float(announcements[dev.id][key]['Refresh']))
                    announcements[dev.id][key]['nextRefresh'] = next_update.strftime('%Y-%m-%d %H:%M:%S')
                    self.logger.debug(f"{announcements[dev.id][key]['Name']} updated.")
                    states_list.append({'key': 'onOffState', 'value': True, 'uiValue': " "})
                    dev.updateStatesOnServer(states_list)

                elif force:
                    # Force an update the announcement text.
                    announcement = self.substitute(announcements[dev.id][key]['Announcement'])
                    result       = self.substitution_regex(announcement)
                    states_list.append({'key': state_name, 'value': result})
                    states_list.append({'key': 'onOffState', 'value': True, 'uiValue': " "})
                    dev.updateStatesOnServer(states_list)

            return announcements

        except KeyError:
            self.logger.debug("Error: ", exc_info=True)
            return announcements

    # =============================================================================
    def announcement_update_states(self, force: bool = False):
        """
        Update the state values of each announcement

        Refresh the custom state values of select announcements. The user sets a preference for how often the plugin
        will cycle, and a per-announcement refresh cycle. For example, the plugin will check every X seconds to see if
        any announcements require a refresh. The determination is based on the setting for each announcement and the
        amount of time that has transpired since it was last refreshed.

        :param: bool force:
        """
        self.logger.debug("Updating announcement states")

        # Load the announcements file and convert to a dict
        announcements = self.__announcement_file_read__()

        for dev in indigo.devices.iter('self'):

            if dev.enabled:

                # Salutations device
                if dev.deviceTypeId == 'salutationsDevice':
                    self.__update_salutations_device__(dev)

                # Announcements device
                elif dev.deviceTypeId == 'announcementsDevice':
                    announcements = self.__update_announcements_device__(dev, announcements, force)

        # Open the announcements file and save the updated dict.
        self.__announcement_file_write__(announcements)

    # =============================================================================
    def announcement_update_states_now(self):
        """
        Force announcements updates based on menu item call

        The call to announcement_update_states() includes the attribute `force=True` which causes announcements to be
        updated regardless of their update time.

        :return:
        """
        self.announcement_update_states(force=True)

    # =============================================================================
    def announcement_update_states_now_action(self, action: indigo.actionGroup=None):  # noqa
        """
        Force announcements updates based on menu item call

        The call to announcement_update_states() includes the attribute `force=True` which causes announcements to be
        updated regardless of their update time.

        :return:
        """
        self.announcement_update_states(force=True)

    # =============================================================================
    def comms_kill_all(self):
        """
        Disable communication for all plugin-defined devices

        comms_kill_all() sets the enabled status of all plugin devices to false.
        """
        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=False)

            except ValueError:
                self.logger.critical("Exception when trying to kill all comms.")
                self.logger.debug("Error: ", exc_info=True)

    # =============================================================================
    def comms_unkill_all(self):
        """
        Enable communication for all plugin-defined devices

        comms_unkill_all() sets the enabled status of all plugin devices to true.
        """
        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=True)

            except ValueError:
                self.logger.critical("Exception when trying to unkill all comms.")
                self.logger.debug("Error: ", exc_info=True)

    # =============================================================================
    def format_digits(self, match: re.match) -> re.match:
        """
        Format announcement digits based on announcement criteria

        The format_digits function determines the proper formatting routine to use when converting target values to the
        specified format. It sends the target value to the proper function for formatting.

        :param re.match match:
        :return re.match result:
        """
        match1 = match.group(1)  # the string to be formatted
        match2 = match.group(2)  # the format specification
        match1 = match1.replace('<<', '')
        match2 = match2.replace('>>', '')

        # Current time conversions specified with ct: ...
        if match2.startswith('ct:'):
            result = self.format_current_time(match1, match2)

        # Datetime conversions specified with dt: ...
        elif match2.startswith('dt:'):
            result = self.format_datetime(match1, match2)

        # Number conversions specified with n: ...
        elif match2.startswith('n:'):
            result = self.format_number(match1, match2)

        else:
            result = f"{match1} {match2}"

        return result

    # =============================================================================
    def format_current_time(self, match1: str, match2: str) -> str:  # noqa
        """
        Format announcement times based on announcement criteria

        The format_current_time function is used to create a formatted version of the current time. It's called when
        the format specifier is "ct:". It receives two regex match objects.

        :param str match1:
        :param str match2:
        :return str result:
        """
        match2 = match2.replace('ct:', '')

        try:
            for char in match2:
                if char not in '.,%:-aAwdbBmyYHIpMSfzZjUWcxX ':  # allowable datetime specifiers
                    raise ValueError
            match1 = dt.datetime.now()
            return f"{match1:{match2}}"

        except ValueError:
            self.logger.debug("Error: ", exc_info=True)
            return f"Unallowable datetime specifiers: {match1} {match2}"

    # =============================================================================
    def format_datetime(self, match1: str, match2: str):  # noqa
        """
        Format announcement datetime based on announcement criteria

        The format_datetime function is used to format the string based on common Python datetimeformat specifiers.
        It's called when the format specifier is "dt:".

        :param str match1:
        :param str match2:
        :return str result:
        """
        match2 = match2.replace('dt:', '')

        try:
            for char in match2:
                if char not in '.,%:-aAwdbBmyYHIpMSfzZjUWcxX ':  # allowable datetime specifiers
                    raise ValueError
            if match1 == 'now':
                match1 = dt.datetime.now()
            else:
                match1 = parser.parse(match1)
            return f"{match1:{match2}}"

        except ValueError:
            self.logger.debug("Error: ", exc_info=True)
            return f"Unallowable datetime specifiers: {match1} {match2}"

    # =============================================================================
    def format_number(self, match1: str, match2: str) -> str:  # noqa
        """
        Format announcement number based on announcement criteria

        The format_number function is used to format the string based on common Python numeric format specifiers. It's
        called when the format specifier is "n:".

        :param str match1:
        :param str match2:
        :return str result:
        """
        match2 = match2.replace('n:', '')

        try:
            for char in match2:
                if char not in '%+-0123456789eEfFgGn':  # allowable numeric specifiers
                    raise ValueError
            return f"{float(match1):0.{int(match2)}f}"

        except ValueError:
            self.logger.debug("Error: ", exc_info=True)
            return f"Unallowable datetime specifiers: {match1} {match2}"

    # =============================================================================
    @staticmethod
    def generator_announcement_list(fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """
        Generate a list of states for Indigo controls

        Returns a list of states for selected plugin device.

        :param str fltr:
        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """
        try:
            announcement_id = int(values_dict['announcementDeviceToRefresh'])
            if announcement_id in indigo.devices:
                result = [
                    (state, state.replace("_", " "))
                    for state in indigo.devices[announcement_id].states
                    if 'onOffState' not in state
                ]
            else:
                result = [('value', 'Value')]

        except KeyError:
            result = [('None', 'None')]

        return result

    # =============================================================================
    def generator_device_list(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """
        Generate a list of plugin-owned devices.

        Returns a list of plugin devices. Returns a list of tuples in the form: [(ID, "Name"), (ID, "Name")].

        :param str fltr:
        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """
        return self.Fogbert.deviceList(dev_filter='self')

    # =============================================================================
    def generator_dev_var(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """
        Generate a list of Indigo devices and variables.

        This method collects IDs and names for all Indigo devices and variables. It creates a list of the form:
        [(dev.id, dev.name), (var.id, var.name)].

        :param str fltr:
        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """
        return self.Fogbert.deviceAndVariableList()

    # =============================================================================
    def generator_list(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """
        Generate a list of configured announcements

        Populates the list of announcements based on the device's states. Returns a list based on a dict (infile) of
        the form:

        {'announcement ID':
          {'Announcement': "announcement string",
           'nextRefresh': "YYYY-MM-DD HH:MM:SS",
           'Name': "announcement name",
           'Refresh': "minutes",
          }
        }

        The returned list is of the form: [(announcement ID, announcement name),]

        :param str fltr:
        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list announcements:
        """
        # Open the announcements file and load the contents
        infile = self.__announcement_file_read__()

        # Sort the dict and create a list of tuples for the device config list control.
        try:
            announcements = [(key, infile[target_id][key]['Name']) for key in infile[target_id]]
        except KeyError:
            announcements = []

        if len(announcements) > 0:
            announcements = sorted(announcements, key=lambda y: y[1])

        return announcements

    # =============================================================================
    def generator_state_or_value(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """
        Return a list of device states or variable value for selected device

        The generator_state_or_value() method returns a list to populate the relevant device states or variable value
        to populate a menu control.

        :param str fltr:
        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list:
        """
        id_number = values_dict.get('devVarMenu', 'None')
        return self.Fogbert.generatorStateOrValue(dev_id=id_number)

    # =============================================================================
    def generator_substitutions(self, values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> indigo.Dict:  # noqa
        """
        Generate an Indigo substitution string

        The generator_substitutions function is used with the Substitution Generator. It is the callback that's used to
        create the Indigo substitution construct.

        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return indigo.Dict values_dict:
        """
        dev_var_id    = values_dict['devVarMenu']
        dev_var_value = values_dict['generator_state_or_value']

        try:
            if int(values_dict['devVarMenu']) in indigo.devices:
                values_dict['subGeneratorResult'] = f"%%d:{dev_var_id}:{dev_var_value}%%"

            else:
                values_dict['subGeneratorResult'] = f"%%v:{dev_var_id}%%"

            values_dict['devVarMenu'] = ''
            values_dict['generator_state_or_value'] = ''

            return values_dict

        except ValueError:
            announcement = self.substitute(values_dict['textfield1'])
            result       = self.substitution_regex(announcement=announcement)
            self.logger.info(f'Substitution Generator announcement: "{result}"')
            return values_dict

    # =============================================================================
    def generator_time(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """
        Generate a list of hours for plugin control menus

        Creates a list of times for use in setting salutation settings of the form:[(0, "00:00"), (1, "01:00"), ...]

        :param str fltr:
        :param indigo.Dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list:
        """
        # return [(hour, f"{hour:02.0f}:00") for hour in range(0, 24)]
        return self.Fogbert.time_list()

    # ==============================================================================
    def initialize_announcements_file(self):
        """
        Audit the default announcements file.

        Determine whether the announcement file exists and is in the proper location.

        :return:
        """
        working_directory = f"{os.path.expanduser('~')}/Announcements Plugin/"
        old_file          = f"{working_directory}announcements.txt"

        # If it exists under the old location, move it over.
        if os.path.isfile(old_file):
            os.rename(old_file, self.announcements_file)
            self.sleep(1)
            shutil.rmtree(path=working_directory, ignore_errors=True)

        # If there's no file at all, lets establish a new empty Announcements dict.
        if not os.path.isfile(self.announcements_file):
            self.logger.warning(
                "Announcements file not found. Creating a placeholder file. If a configured announcements device "
                "should be present, reach out for assistance or consult server back-up files."
            )
            self.__announcement_file_write__({})
            self.sleep(1)

    # =============================================================================
    def refresh_fields(self, fltr: str="", type_id: str="", target_id: str=0):  # noqa
        """
        Dummy callback to force dynamic control refreshes

        The refresh_fields() method is a dummy callback used solely to fire other actions that require a callback be
        run. It performs no other function.

        :param str fltr:
        :param str type_id:
        :param int target_id:
        """
        self.logger.debug("refresh_fields()")

    # =============================================================================
    def substitution_regex(self, announcement: str) -> re.match:
        """
        Regex method for formatting substitutions.

        This is the main regex used for formatting substitutions. The only possible matches are expressly listed in the
        pattern. Currently, supported matches are --> ct:, dt:, n:

        :param str announcement: The announcement string to be parsed.
        :return re.match: (announcement), (format specifier).
        """
        return re.sub(r'(<<.*?), *(((ct)|(dt)|(n)):.*?>>)', self.format_digits, announcement)

    def my_tests(self, action=None):
        """
        The main unit test method

        The my_tests method is called from a plugin action item and, when called, imports all unit tests and runs them.
        If the unit test module returns True, then all tests have passed.
        """
        from Tests import test_plugin
        tests = test_plugin.TestPlugin()
        if tests.my_tests(self):
            self.logger.warning("All tests passed.")

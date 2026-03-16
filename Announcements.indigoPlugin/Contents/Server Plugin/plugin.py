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
except ImportError:
    pass

# My modules
import DLFramework.DLFramework as Dave
from constants import DEBUG_LABELS  # noqa
from plugin_defaults import kDefaultPluginPrefs  # noqa

# =================================== HEADER ==================================
__author__    = Dave.__author__
__copyright__ = Dave.__copyright__
__license__   = Dave.__license__
__build__     = Dave.__build__
__title__     = 'Announcements Plugin for Indigo Home Control'
__version__   = '2025.2.1'


# =============================================================================
class Plugin(indigo.PluginBase):
    """Standard Indigo Plugin Class."""

    def __init__(self, plugin_id: str = "", plugin_display_name: str = "", plugin_version: str = "",
                 plugin_prefs: indigo.Dict = None):
        """Plugin initialization.

        Args:
            plugin_id (str): The plugin's unique identifier.
            plugin_display_name (str): The plugin's display name.
            plugin_version (str): The plugin's version string.
            plugin_prefs (indigo.Dict): The plugin's stored preferences.
        """
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        # ============================ Instance Attributes ============================
        self.announcements_file   = ""
        self.debug_level          = int(self.pluginPrefs.get('showDebugLevel', "30"))
        self.pluginIsInitializing = True
        self.pluginIsShuttingDown = False
        self.update_frequency     = int(self.pluginPrefs.get('pluginRefresh', 15))

        # ================================== Logging ==================================
        self.plugin_file_handler.setFormatter(logging.Formatter(fmt=Dave.LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))
        self.indigo_log_handler.setLevel(self.debug_level)

        # ========================== Initialize DLFramework ===========================
        self.Fogbert = Dave.Fogbert(self)

        self.pluginIsInitializing = False

    # =============================================================================
    def __del__(self) -> None:
        """Destructor for the class.

        Calls the superclass method to ensure things are destroyed gracefully.
        """
        indigo.PluginBase.__del__(self)

    # =============================================================================
    # ============================== Indigo Methods ===============================
    # =============================================================================
    def closed_device_config_ui(self, values_dict: indigo.Dict=None, user_cancelled: bool=False, type_id: str= "", dev_id: int=0) -> None:  # noqa
        """Standard Indigo method called when device preferences dialog is closed.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            user_cancelled (bool): True if the user cancelled the dialog.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.
        """
        if not user_cancelled:
            self.announcement_update_states(force=True)
            self.logger.debug("closed_device_config_ui()")
        else:
            self.logger.debug("Device configuration cancelled.")

    # =============================================================================
    def closed_prefs_config_ui(self, values_dict: indigo.Dict=None, user_cancelled: bool=False) -> indigo.Dict:  # noqa
        """Standard Indigo method called when plugin preferences dialog is closed.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            user_cancelled (bool): True if the user cancelled the dialog.

        Returns:
            indigo.Dict: The updated values dict.
        """
        if not user_cancelled:
            # Ensure that self.pluginPrefs includes any recent changes.
            for k in values_dict:
                self.pluginPrefs[k] = values_dict[k]

            # Debug Logging
            self.debug_level = int(values_dict.get('showDebugLevel', 10))
            self.indigo_log_handler.setLevel(self.debug_level)
            indigo.server.log(f"Logging level: {DEBUG_LABELS[self.debug_level]} ({self.debug_level})")

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
    def device_start_comm(dev: indigo.Device) -> None:  # noqa
        """Standard Indigo method called when device comm is enabled.

        Args:
            dev (indigo.Device): The Indigo device object.
        """
        dev.stateListOrDisplayStateIdChanged()
        dev.updateStateOnServer('onOffState', value=True, uiValue=" ")

    # =============================================================================
    @staticmethod
    def device_stop_comm(dev: indigo.Device) -> None:  # noqa
        """Standard Indigo method called when device comm is disabled.

        Args:
            dev (indigo.Device): The Indigo device object.
        """
        dev.updateStateOnServer('onOffState', value=False, uiValue=" ")

    # =============================================================================
    @staticmethod
    def get_device_config_ui_values(values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """Standard Indigo method called when device config menu is opened.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            indigo.Dict: The updated values dict.
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
    def get_device_state_list(self, dev: indigo.Device=None) -> list:  # noqa
        """Standard Indigo method to provide dynamic state list definition information.

        Args:
            dev (indigo.Device): The Indigo device object.

        Returns:
            list: The updated device state list.
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
            announcement_state = self.getDeviceStateDictForStringType(thing_name, thing_name, thing_name)
            default_states_list.append(announcement_state)

        return default_states_list

    # =============================================================================
    def run_concurrent_thread(self) -> None:  # noqa
        """Standard Indigo concurrent thread."""
        try:
            while True:
                self.update_frequency = int(self.pluginPrefs.get('pluginRefresh', 15))
                self.announcement_update_states()
                self.sleep(self.update_frequency)
        except self.StopThread:
            pass

    # =============================================================================
    def startup(self) -> None:
        """Standard Indigo startup method."""

        # ============================ Audit Announcements ============================
        path_string             = "/Preferences/Plugins/com.fogbert.indigoplugin.announcements.txt"
        self.announcements_file = f"{indigo.server.getInstallFolderPath()}{path_string}"
        self.initialize_announcements_file()

        # ===================== Delete Out of Date Announcements =====================
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
    def validate_device_config_ui(self, values_dict: indigo.Dict=None, type_id: str="salutationsDevice", dev_id: int=0) -> tuple:  # noqa
        """Standard Indigo method called before device config dialog is closed.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            tuple[bool, indigo.Dict]: Validation result and the values dict.
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
        """Clear announcement data from input fields.

        Clears whatever is in the Announcement textfield.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            indigo.Dict: The updated values dict with cleared fields.
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
        """Create a unique ID number for the announcement.

        In order to properly track the various announcement strings, we must assign each one a unique ID number. We
        check to see if the number has already been assigned to another announcement and, if not, the new ID is
        assigned.

        Args:
            temp_dict (dict): The current announcements dict to check for ID collisions.

        Returns:
            int: A unique announcement ID.
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
        """Delete the highlighted announcement.

        Called when user clicks the Delete Announcement button.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            indigo.Dict: The updated values dict.
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
        """Create a duplicate of the selected announcement.

        Called when user clicks the Duplicate Announcement button.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            indigo.Dict: The updated values dict.
        """
        index = values_dict['announcementList']
        self.logger.info("Announcement to be duplicated: %s", index)

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
        """Load the selected announcement for editing.

        Called when user clicks the Edit Announcement button.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            indigo.Dict: The updated values dict with the selected announcement loaded.
        """
        self.logger.debug("Editing the %s announcement", values_dict['announcementName'])

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
        """Load the announcements file and return its contents.

        Returns:
            dict: The announcements data keyed by device ID.
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
        """Write the announcements dict to disk.

        Args:
            announcements (dict): The announcements data to persist.

        Returns:
            bool: True if write succeeded.
        """
        # Open the announcements file and write the contents
        with open(self.announcements_file, mode='w', encoding="utf-8") as outfile:
            json.dump(announcements, outfile, ensure_ascii=False, indent=4)
        return True

    # =============================================================================
    def announcement_refresh_action(self, plugin_action: indigo.actionGroup) -> None:
        """Refresh an announcement in response to an Indigo action call.

        Forces an announcement to be refreshed via an Indigo Action Item.

        Args:
            plugin_action (indigo.actionGroup): The Indigo action group object.
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

        self.logger.info("Refreshed %s announcement.", announcement_name)

    # =============================================================================
    def __announcement_save__(self, values_dict: indigo.Dict=None, type_id: str="", dev_id: int=0) -> indigo.Dict:  # noqa
        """Save the current announcement.

        Called when user clicks the Save Announcement button.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            indigo.Dict: The updated values dict.
        """
        error_msg_dict = indigo.Dict()

        # ============================ Validation Methods =============================
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

        # =============================================================================
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

        # User has created a new announcement with a name already in use. We add " X" to the name and write a warning
        # to the log.
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
        """Speak the selected announcement.

        Called when user clicks the Speak Announcement button. If an announcement is selected in the list, that is the
        announcement that will be spoken; if there is announcement data in the text fields, that will be what is spoken.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            dev_id (int): The device ID.

        Returns:
            indigo.Dict: The updated values dict.
        """
        default_string = "Please select or enter an item to speak."
        result         = ""

        # The user has entered a value in the announcement field. Speak that.
        if len(values_dict['announcementText']) > 0:
            result = self.substitution_regex(announcement=self.substitute(values_dict['announcementText']))
            indigo.server.speak(result, waitUntilDone=False)
            self.logger.info("%s", result)

        # If the announcement field is blank, and the user has selected an announcement in the list.
        elif values_dict['announcementList'] != "":
            # Open the announcements file and load the contents
            announcements = self.__announcement_file_read__()
            announcement  = self.substitute(announcements[dev_id][values_dict['announcementList']]['Announcement'])
            result        = self.substitution_regex(announcement=announcement)
            indigo.server.speak(result, waitUntilDone=False)

            self.logger.info("%s", result)

        # Otherwise, let the user know that there is nothing to speak.
        else:
            self.logger.error("%s", default_string)
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
        """Return a copy of the announcements database in JSON format.

        The complete database will be returned agnostically.

        Args:
            plugin_action (indigo.actionGroup): The Indigo action group object.

        Returns:
            str: The announcements database serialized as JSON.
        """
        # Open the announcements file and load the contents
        announcements = self.__announcement_file_read__()
        return json.dumps(announcements)

    # =============================================================================
    def announcement_speak_action(self, plugin_action: indigo.actionGroup) -> None:
        """Speak an announcement in response to an Indigo action item.

        Indigo action for speaking any device state or variable value.

        Args:
            plugin_action (indigo.actionGroup): The Indigo action group object.
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
            self.logger.warning("Unable to speak %s value.", item_to_speak)
            self.logger.debug("Error: ", exc_info=True)

        except KeyError:
            self.logger.warning("No announcements to speak for this device %s", item_to_speak)
            self.logger.debug("Error: ", exc_info=True)

    # =============================================================================
    def __update_salutations_device__(self, dev: indigo.Device) -> None:
        """Update the salutations device states based on the current time of day.

        Args:
            dev (indigo.Device): The salutations device to update.
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
            self.logger.debug("Updating intro to: %s", intro_value)
            dev.states['intro'] = dev.states['intro']
            states_list.append({'key': 'intro', 'value': intro_value})

        if outro_value != dev.states['outro']:
            self.logger.debug("Updating outro to: %s", outro_value)
            states_list.append({'key': 'outro', 'value': outro_value})

        states_list.append({'key': 'onOffState', 'value': True, 'uiValue': " "})
        dev.updateStatesOnServer(states_list)

    # =============================================================================
    def __update_announcements_device__(self, dev: indigo.Device, announcements: dict, force: bool = False) -> dict:
        """Update the announcements device states.

        Args:
            dev (indigo.Device): The announcements device to update.
            announcements (dict): The full announcements data dict.
            force (bool): If True, update regardless of scheduled refresh time.

        Returns:
            dict: The updated announcements data dict.
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
                    self.logger.debug("%s updated.", announcements[dev.id][key]['Name'])
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
    def announcement_update_states(self, force: bool = False) -> None:
        """Update the state values of each announcement.

        Refreshes the custom state values of select announcements. The plugin checks every X seconds to see if any
        announcements require a refresh, based on each announcement's individual refresh interval and the time elapsed
        since it was last refreshed.

        Args:
            force (bool): If True, update all announcements regardless of their scheduled refresh time.
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
    def announcement_update_states_now(self) -> None:
        """Force all announcement updates via menu item call.

        Calls announcement_update_states() with force=True, causing all announcements to be updated regardless of their
        scheduled refresh time.
        """
        self.announcement_update_states(force=True)

    # =============================================================================
    def announcement_update_states_now_action(self, action: indigo.actionGroup=None):  # noqa
        """Force all announcement updates via action item call.

        Calls announcement_update_states() with force=True, causing all announcements to be updated regardless of their
        scheduled refresh time.

        Args:
            action (indigo.actionGroup): The Indigo action group object.
        """
        self.announcement_update_states(force=True)

    # =============================================================================
    def comms_kill_all(self, action: indigo.actionGroup=None) -> None:
        """Disable communication for all plugin-defined devices.

        Sets the enabled status of all plugin devices to False.
        """
        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=False)

            except ValueError:
                self.logger.critical("Exception when trying to kill all comms.")
                self.logger.debug("Error: ", exc_info=True)

    # =============================================================================
    def comms_unkill_all(self, action: indigo.actionGroup=None) -> None:
        """Enable communication for all plugin-defined devices.

        Sets the enabled status of all plugin devices to True.
        """
        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=True)

            except ValueError:
                self.logger.critical("Exception when trying to unkill all comms.")
                self.logger.debug("Error: ", exc_info=True)

    # =============================================================================
    def format_digits(self, match: re.Match) -> str:
        """Format announcement digits based on announcement criteria.

        Determines the proper formatting routine to use when converting target values to the specified format, then
        delegates to the appropriate formatter.

        Args:
            match (re.Match): The regex match object containing the value and format spec groups.

        Returns:
            str: The formatted result string.
        """
        match1: str = match.group(1)  # the string to be formatted
        match2: str = match.group(2)  # the format specification
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
        """Format the current time based on announcement criteria.

        Creates a formatted version of the current time. Called when the format specifier is "ct:".

        Args:
            match1 (str): The original value string (unused for current time).
            match2 (str): The format specification string (e.g., "ct:%H:%M").

        Returns:
            str: The formatted current time string.
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
    def format_datetime(self, match1: str, match2: str) -> str:  # noqa
        """Format a datetime string based on announcement criteria.

        Formats a string using common Python datetime format specifiers. Called when the format specifier is "dt:".

        Args:
            match1 (str): The datetime value string to parse (or "now" for the current time).
            match2 (str): The format specification string (e.g., "dt:%A").

        Returns:
            str: The formatted datetime string.
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
        """Format a number based on announcement criteria.

        Formats a string using common Python numeric format specifiers. Called when the format specifier is "n:".

        Args:
            match1 (str): The numeric value string to format.
            match2 (str): The format specification string (e.g., "n:2" for 2 decimal places).

        Returns:
            str: The formatted number string.
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
        """Generate a list of states for Indigo controls.

        Returns a list of states for the selected plugin device.

        Args:
            fltr (str): Optional filter string.
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            list: List of (state_id, display_name) tuples.
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
        """Generate a list of plugin-owned devices.

        Returns a list of tuples in the form: [(ID, "Name"), ...].

        Args:
            fltr (str): Optional filter string.
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            list: List of (device_id, device_name) tuples.
        """
        return self.Fogbert.deviceList(dev_filter='self')

    # =============================================================================
    def generator_dev_var(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """Generate a list of Indigo devices and variables.

        Collects IDs and names for all Indigo devices and variables in the form: [(id, name), ...].

        Args:
            fltr (str): Optional filter string.
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            list: List of (id, name) tuples for all devices and variables.
        """
        return self.Fogbert.deviceAndVariableList()

    # =============================================================================
    def generator_list(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """Generate a list of configured announcements.

        Populates the announcement list based on the device's stored data. The source dict has the form::

            {'announcement ID': {'Announcement': "...", 'nextRefresh': "YYYY-MM-DD HH:MM:SS",
                                 'Name': "...", 'Refresh': "minutes"}}

        Args:
            fltr (str): Optional filter string.
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            list: List of (announcement_id, announcement_name) tuples, sorted by name.
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
        """Return a list of device states or variable values for the selected device.

        Populates the relevant device states or variable value for a menu control.

        Args:
            fltr (str): Optional filter string.
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            list: List of state or value options for the selected device/variable.
        """
        id_number = values_dict.get('devVarMenu', 'None')
        return self.Fogbert.generatorStateOrValue(dev_id=id_number)

    # =============================================================================
    def generator_substitutions(self, values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> indigo.Dict:  # noqa
        """Generate an Indigo substitution string.

        Callback for the Substitution Generator that creates the Indigo substitution construct.

        Args:
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            indigo.Dict: The updated values dict with the generated substitution string.
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
            self.logger.info('Substitution Generator announcement: "%s"', result)
            return values_dict

    # =============================================================================
    def generator_time(self, fltr: str="", values_dict: indigo.Dict=None, type_id: str="", target_id: int=0) -> list:  # noqa
        """Generate a list of hours for plugin control menus.

        Creates a list of times for use in salutation settings: [(0, "00:00"), (1, "01:00"), ...].

        Args:
            fltr (str): Optional filter string.
            values_dict (indigo.Dict): The dialog's current values.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.

        Returns:
            list: List of (hour_int, "HH:00") tuples for each hour of the day.
        """
        # return [(hour, f"{hour:02.0f}:00") for hour in range(0, 24)]
        return self.Fogbert.time_list()

    # =============================================================================
    def initialize_announcements_file(self) -> None:
        """Audit the default announcements file.

        Determines whether the announcement file exists and is in the proper location, migrating it from the old
        location if necessary, or creating a new empty file if it doesn't exist.
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
    def log_plugin_environment(self, action: indigo.actionGroup=None) -> None:  # noqa
        """Log plugin environment information when "Display Plugin Information" is selected from the plugin menu."""
        self.Fogbert.pluginEnvironment()

    # =============================================================================
    def refresh_fields(self, fltr: str="", type_id: str="", target_id: str=0):  # noqa
        """Dummy callback to force dynamic control refreshes.

        Used solely to fire other actions that require a callback. Performs no other function.

        Args:
            fltr (str): Optional filter string.
            type_id (str): The device type identifier.
            target_id (int): The target device ID.
        """
        self.logger.debug("refresh_fields()")

    # =============================================================================
    def substitution_regex(self, announcement: str) -> str:
        """Apply regex formatting substitutions to an announcement string.

        The only possible matches are expressly listed in the pattern. Currently supported specifiers: ct:, dt:, n:.

        Args:
            announcement (str): The announcement string to be parsed.

        Returns:
            str: The announcement string with all formatting substitutions applied.
        """
        return re.sub(r'(<<.*?), *(((ct)|(dt)|(n)):.*?>>)', self.format_digits, announcement)

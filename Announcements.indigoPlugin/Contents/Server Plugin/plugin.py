#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-

""" Announcements Plugin for Indigo Home Control Server

The Announcements Plugin is used to construct complex announcements for use
with text-to-speech tools in Indigo. The plugin provides a simple call to the
indigo.server.speak() hook for simple audio announcements; however, the plugin
is more geared towards creating announcements to be used with more advanced
speech tools.

"""

# =================================== TO DO ===================================

# TODO: how will the plugin handle localization like comma separators?
# TODO: on dev, the substitution generator is only showing announcements
#       devices.

# ================================== IMPORTS ==================================

# Built-in modules
import ast
import datetime as dt
from dateutil import parser
import logging
import os
import re
import shutil
import string
import sys

# Third-party modules
try:
    import indigo
except ImportError, error:
    indigo.server.log(unicode(error), isError=True)

try:
    import pydevd
except ImportError:
    pass

# My modules
import DLFramework.DLFramework as Dave

# =================================== HEADER ==================================

__author__    = Dave.__author__
__copyright__ = Dave.__copyright__
__license__   = Dave.__license__
__build__     = Dave.__build__
__title__     = 'Announcements Plugin for Indigo Home Control'
__version__   = '1.0.11'

# =============================================================================

kDefaultPluginPrefs = {
    u'pluginRefresh': "15",
    u'showDebugLevel': "30",
}


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.pluginIsInitializing = True
        self.pluginIsShuttingDown = False

        self.plugin_file_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)-10s\t%(name)s.%(funcName)-28s %(msg)s', datefmt='%Y-%m-%d %H:%M:%S'))
        self.debug      = True
        self.debugLevel = int(self.pluginPrefs.get('showDebugLevel', "30"))
        self.indigo_log_handler.setLevel(self.debugLevel)

        self.update_frequency = int(self.pluginPrefs.get('pluginRefresh', 15))
        self.logger.debug(u"Plugin refresh interval: {0}".format(self.update_frequency))

        # ====================== Initialize DLFramework =======================

        self.Fogbert = Dave.Fogbert(self)

        # Log pluginEnvironment information when plugin is first started
        self.Fogbert.pluginEnvironment()

        # =====================================================================

        # Establish the default announcements file.
        working_directory       = u"{0}/Announcements Plugin/".format(os.path.expanduser('~'))
        old_file                = u"{0}announcements.txt".format(working_directory)
        self.announcements_file = u"{0}/Preferences/Plugins/com.fogbert.indigoplugin.announcements.txt".format(indigo.server.getInstallFolderPath())

        # If it exists under the old location, let's move it over.
        if os.path.isfile(old_file):
            os.rename(old_file, self.announcements_file)
            self.sleep(1)
            shutil.rmtree(working_directory, ignore_errors=True)

        # If a new install, lets establish a new empty dict.
        if not os.path.isfile(self.announcements_file):
            with open(self.announcements_file, 'w+') as outfile:
                outfile.write(u"{}")
            self.sleep(1)  # Wait a moment to let the system catch up.

        # try:
        #     pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
        # except:
        #     pass

        self.pluginIsInitializing = False

    def __del__(self):
        indigo.PluginBase.__del__(self)

    # =============================================================================
    # ============================== Indigo Methods ===============================
    # =============================================================================
    def closedDeviceConfigUi(self, values_dict, user_cancelled, type_id, dev_id):

        pass

    # =============================================================================
    def closedPrefsConfigUi(self, values_dict, user_cancelled):

        if not user_cancelled:
            debug_label = {10: u"Debugging Messages", 20: u"Informational Messages", 30: u"Warning Messages", 40: u"Error Messages", 50: u"Critical Errors Only"}
            self.debugLevel       = int(values_dict['showDebugLevel'])
            self.update_frequency = int(values_dict['pluginRefresh'])
            self.indigo_log_handler.setLevel(self.debugLevel)
            indigo.server.log(u"Debugging set to: {0}".format(debug_label[self.debugLevel]))

            # Update the devices to reflect any changes
            self.announcement_update_states()

            # Ensure that self.pluginPrefs includes any recent changes.
            for k in values_dict:
                self.pluginPrefs[k] = values_dict[k]

    # =============================================================================
    def deviceStartComm(self, dev):

        dev.stateListOrDisplayStateIdChanged()
        dev.updateStateOnServer('onOffState', value=False, uiValue=u" ")

    # =============================================================================
    def deviceStopComm(self, dev):

        dev.updateStateOnServer('onOffState', value=False, uiValue=u" ")

    # =============================================================================
    def getDeviceConfigUiValues(self, values_dict, type_id, dev_id):

        # Set the device to disabled while it's being edited.
        indigo.device.enable(dev_id, value=False)

        # Ensure that the dialog opens with fresh fields.
        if type_id == 'announcementsDevice':
            for key in ('announcementName', 'announcementList', 'announcementRefresh', 'announcementText', 'subGeneratorResult'):
                values_dict[key] = ''

        return values_dict

    # =============================================================================
    def getDeviceStateList(self, dev):

        dev_id  = dev.id
        type_id = dev.deviceTypeId

        if type_id not in self.devicesTypeDict:
            return None

        default_states_list = self.devicesTypeDict[type_id][u'States']

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
        infile = ast.literal_eval(infile)

        # Sort the dict and create a list of tuples.
        try:
            announcement_list = [(key, infile[dev_id][key]['Name']) for key in infile[dev_id].keys()]
        except KeyError:
            announcement_list = []

        # Iterate through the list of tuples and save each announcement name as a device key. Keys (state id's) can't contain Unicode.
        for thing in announcement_list:
            thing_name         = thing[1].replace(' ', '_')
            announcement_state = self.getDeviceStateDictForStringType(thing_name, thing_name, thing_name)
            default_states_list.append(announcement_state)

        return default_states_list

    # =============================================================================
    def runConcurrentThread(self):

        try:
            while True:
                self.sleep(1)

                self.update_frequency = int(self.pluginPrefs.get('pluginRefresh', 15))
                self.announcement_update_states()
                self.sleep(self.update_frequency)

        except self.StopThread:
            pass

    # =============================================================================
    def sendDevicePing(self, dev_id=0, suppress_logging=False):

        indigo.server.log(u"Announcements Plugin devices do not support the ping function.")
        return {'result': 'Failure'}

    # =============================================================================
    def startup(self):

        # =========================== Audit Indigo Version ============================
        self.Fogbert.audit_server_version(min_ver=7)

        # ============= Delete Out of Date Announcements ===============

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict.
        infile = ast.literal_eval(infile)

        # Look at each plugin device id and delete any announcements if there is no longer an associated device.
        for key in infile.keys():
            if key not in indigo.devices.keys('self'):
                del infile[key]

        # Look at each plugin device and construct a placeholder if not already present.
        for dev in indigo.devices.iter('self'):
            if dev.id not in infile.keys():
                infile[dev.id] = {}

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

    # =============================================================================
    # def validatePrefsConfigUi(self, values_dict):
    #
    #     return True, values_dict

    # =============================================================================
    def validateDeviceConfigUi(self, values_dict, type_id, dev_id):

        error_msg_dict = indigo.Dict()

        # try:
        # Announcements device
        if type_id == 'announcementsDevice':
            return True, values_dict

        # Salutations device
        if type_id == 'salutationsDevice':
            morning   = int(values_dict['morningStart'])
            afternoon = int(values_dict['afternoonStart'])
            evening   = int(values_dict['eveningStart'])
            night     = int(values_dict['nightStart'])

            if not (morning < afternoon < evening < night):
                for key in ('morningStart', 'afternoonStart', 'eveningStart', 'nightStart'):
                    error_msg_dict[key] = u"Each start time must be greater than the prior one."

        if len(error_msg_dict) > 0:
            return False, values_dict, error_msg_dict

        self.announcement_update_states()
        return True, values_dict

    # =============================================================================
    # ============================== Plugin Methods ===============================
    # =============================================================================
    def announcement_clear(self, values_dict, type_id="", target_id=0):
        """
        Clear announcement data from input field

        Clears whatever is in the Announcement textfield.

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return indigo.dict values_dict:
        """

        for key in ('announcementIndex', 'announcementName', 'announcementRefresh', 'announcementList', 'announcementText'):
            values_dict[key] = ''

        values_dict['editFlag'] = False

        return values_dict

    # =============================================================================
    def announcement_create_id(self, temp_dict):
        """
        Create a unique ID number for the announcement

        In order to properly track the various announcement strings, we must assign
        each one a unique ID number. We check to see if the number has already been
        assigned to another announcement and, if not, the new ID is assigned.

        -----

        :param dict temp_dict:
        """

        # Create a new index number.
        index = id('dummy object')

        # If the new index happens to exist, repeat until unique.
        while index in temp_dict.keys():
            index += 1

        return index

    # =============================================================================
    def announcement_delete(self, values_dict, type_id, dev_id):
        """
        Delete the highlighted announcement

        Called when user clicks the Delete Announcement button

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.dict values_dict:
        """

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and delete the key.
        infile = ast.literal_eval(infile)
        index  = int(values_dict['announcementList'])
        del infile[dev_id][index]

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

        for key in ('announcementIndex', 'announcementName', 'announcementRefresh', 'announcementList', 'announcementText'):
            values_dict[key] = ''

        values_dict['editFlag'] = False

        return values_dict

    # =============================================================================
    def announcement_duplicate(self, values_dict, type_id, dev_id):
        """
        Create a duplicate of the selected announcement

        Called when user clicks the Duplicate Announcement button.

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.dict values_dict:
        """

        index = int(values_dict['announcementList'])
        self.logger.info(u"Announcement to be duplicated: {0}".format(index))

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and delete the key.
        infile = ast.literal_eval(infile)

        # Create a new announcement.
        temp_dict = infile[dev_id]
        new_index = self.announcement_create_id(temp_dict)
        temp_dict[new_index]                 = {}
        temp_dict[new_index]['Name']         = infile[dev_id][index]['Name'] + u" copy"
        temp_dict[new_index]['Announcement'] = infile[dev_id][index]['Announcement']
        temp_dict[new_index]['Refresh']      = infile[dev_id][index]['Refresh']
        temp_dict[new_index]['nextRefresh']  = infile[dev_id][index]['nextRefresh']

        # Set the dict element equal to the new list
        infile[dev_id] = temp_dict

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

        return values_dict

    # =============================================================================
    def announcement_edit(self, values_dict, type_id, dev_id):
        """
        Load the selected announcement for editing

        Called when user clicks the Edit Announcement button.

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.dict values_dict:
        """

        self.logger.debug(u"Editing the {0} announcement".format(values_dict['announcementName']))

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and get the data for this device.
        infile    = ast.literal_eval(infile)
        temp_dict = infile[dev_id]

        # Get the selected announcement index and populate the UI elements.
        index = int(values_dict['announcementList'])
        values_dict['announcementIndex']   = index
        values_dict['announcementName']    = temp_dict[index]['Name']
        values_dict['announcementRefresh'] = temp_dict[index]['Refresh']
        values_dict['announcementText']    = temp_dict[index]['Announcement']
        values_dict['editFlag']            = True

        return values_dict

    # =============================================================================
    def announcementRefreshAction(self, plugin_action):
        """
        Refresh an announcement in response to Indigo Action call

        The announcementRefreshAction() method is used to force an
        announcement to be refreshed by using an Indigo Action Item.

        -----

        :param indigo.action plugin_action:
        """

        announcement_name = plugin_action.props['announcementToRefresh']
        device_id         = int(plugin_action.props['announcementDeviceToRefresh'])
        dev               = indigo.devices[device_id]

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
        infile = ast.literal_eval(infile)

        # Iterate through the keys to find the right announcement to update.
        announcement_dict = infile[int(device_id)]
        for key in announcement_dict.keys():
            if announcement_dict[key]['Name'] == announcement_name.replace('_', ' '):
                announcement = self.substitute(infile[device_id][key]['Announcement'])
                result = self.substitution_regex(announcement)
                dev.updateStateOnServer(announcement_name, value=result)

    # =============================================================================
    def announcement_save(self, values_dict, type_id, dev_id):
        """
        Save the current announcement

        Called when user clicks the Save Announcement button.

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.dict values_dict:
        """

        # ===================== Validation Methods =====================

        values_dict['announcementName'] = values_dict['announcementName'].strip()  # Strip leading and trailing whitespace if there is any.

        # Announcement Name empty or 'REQUIRED'
        if values_dict['announcementName'].isspace() or values_dict['announcementName'] in ('', 'REQUIRED',):
            self.logger.error(u"A announcement name is required.")
            values_dict['announcementName'] = 'REQUIRED'
            return values_dict

        # Announcement Name starts with digit'
        if values_dict['announcementName'][0].isdigit():
            self.logger.error(u"A announcement name can not start with a number.")
            return values_dict

        # Announcement Name starts with punctuation
        exclude = set(string.punctuation)
        if values_dict['announcementName'][0] in exclude:
            self.logger.error(u"A announcement name can not start with punctuation.")
            return values_dict

        # Announcement Name starts with XML.
        if values_dict['announcementName'][0:3].lower() == 'xml':
            self.logger.error(u"A announcement name can not start with the letters 'xml'.")
            return values_dict

        if not all(ord(char) < 128 for char in values_dict['announcementName']):
            self.logger.error(u"A announcement name can not contain Unicode characters.")
            return values_dict

        # Announcement Text is empty or 'REQUIRED'
        if values_dict['announcementText'].isspace() or values_dict['announcementText'] in ('', 'REQUIRED',):
            self.logger.error(u"An announcement is required.")
            values_dict['announcementText'] = 'REQUIRED'
            return values_dict

        # Announcement Text not digit or less than 1
        if not values_dict['announcementRefresh'].isdigit() or int(values_dict['announcementRefresh']) < 1:
            self.logger.error(u"A positive integer greater than zero is required.")
            return values_dict

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict.
        infile = ast.literal_eval(infile)

        try:
            temp_dict = infile[dev_id]

        except KeyError:
            temp_dict = {}

        # Generate a list of announcement names in use for this device.
        announcement_name_list = [temp_dict[key]['Name'] for key in temp_dict.keys()]

        # If new announcement, create unique id, then save to dict.
        if not values_dict['editFlag'] and values_dict['announcementName'] not in announcement_name_list:
            index = self.announcement_create_id(temp_dict)
            temp_dict[index]                 = {}
            temp_dict[index]['Name']         = values_dict['announcementName']
            temp_dict[index]['Announcement'] = values_dict['announcementText']
            temp_dict[index]['Refresh']      = values_dict['announcementRefresh']
            temp_dict[index]['nextRefresh']  = unicode(dt.datetime.now())

        # If key exists, save to dict.
        elif values_dict['editFlag']:
            index                            = int(values_dict['announcementIndex'])
            temp_dict[index]['Name']         = values_dict['announcementName']
            temp_dict[index]['Announcement'] = values_dict['announcementText']
            temp_dict[index]['Refresh']      = values_dict['announcementRefresh']

        # User has created a new announcement with a name already in use
        else:
            index = self.announcement_create_id(temp_dict)
            temp_dict[index]                 = {}
            temp_dict[index]['Name']         = values_dict['announcementName'] + u'*'
            temp_dict[index]['Announcement'] = values_dict['announcementText']
            temp_dict[index]['Refresh']      = values_dict['announcementRefresh']
            temp_dict[index]['nextRefresh']  = unicode(dt.datetime.now())
            self.logger.error(u"Duplicate announcement name found.")

        # Set the dict element equal to the new list
        infile[dev_id] = temp_dict

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

        # Clear the fields.
        for key in ('announcementIndex', 'announcementName', 'announcementRefresh', 'announcementList', 'announcementText'):
            values_dict[key] = ''

        values_dict['editFlag'] = False

        return values_dict

    # =============================================================================
    def announcementSpeak(self, values_dict, type_id, dev_id):
        """
        Speak the selected announcement

        Called when user clicks the Speak Announcement button. If an announcement is
        selected in the list, that is the announcement that will be spoken, if there is
        announcement data in the text fields, that will be what is spoken.

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int dev_id:
        :return indigo.dict values_dict:
        """

        default_string = u"Please select or enter an item to speak."

        # The user has entered a value in the announcement field. Speak that.
        if len(values_dict['announcementText']) > 0:
            result = self.substitution_regex(self.substitute(values_dict['announcementText']))
            indigo.server.speak(result, waitUntilDone=False)

            self.logger.info(u"{0}".format(result))

        # If the announcement field is blank, and the user has selected an announcement in the list.
        elif values_dict['announcementList'] != "":
            # Open the announcements file and load the contents
            with open(self.announcements_file) as outfile:
                infile = outfile.read()

            # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
            infile = ast.literal_eval(infile)

            announcement = self.substitute(infile[dev_id][int(values_dict['announcementList'])]['Announcement'])
            result       = self.substitution_regex(announcement)
            indigo.server.speak(result, waitUntilDone=False)

            self.logger.info(u"{0}".format(result))

        # Otherwise, let the user know that there is nothing to speak.
        else:
            self.logger.error(default_string)
            indigo.server.speak(default_string, waitUntilDone=False)

        return values_dict

    # =============================================================================
    def announcementSpeakAction(self, plugin_action):
        """
        Speak an announcement in response to an Indigo action item

        Indigo action for speaking any device state or variable value.

        -----

        :param indigo.action plugin_action:
        """

        item_source   = int(plugin_action.props['announcementDeviceToRefresh'])
        item_to_speak = plugin_action.props['announcementToSpeak']

        try:
            if item_source in indigo.devices.keys():
                announcement = unicode(indigo.devices[item_source].states[item_to_speak])
                indigo.server.speak(announcement, waitUntilDone=False)
            else:
                announcement = indigo.variables[item_source].value
                indigo.server.speak(announcement, waitUntilDone=False)
        except ValueError:
            self.logger.warning(u"Unable to speak {0} value.".format(item_to_speak))

        except KeyError:
            self.logger.warning(u"No announcements to speak for this device.".format(item_to_speak))

    # =============================================================================
    def announcement_update_states(self, force=False):
        """
        Update the state values of each announcement

        Refresh the custom state values of select announcements. The user sets a
        preference for how often the plugin will cycle, and a per-announcement refresh
        cycle.  For example, the plugin will check every X seconds to see if any
        announcements require a refresh. The determination is based on the setting for
        each announcement and the amount of time that has transpired since it was last
        refreshed.

        -----

        """

        now = indigo.server.getTime()

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
        infile = ast.literal_eval(infile)

        for dev in indigo.devices.iter('self'):

            states_list = []
            if dev.enabled:

                if dev.deviceTypeId == 'salutationsDevice':
                    now   = dt.datetime.now()
                    today = dt.datetime.today().date()

                    morning_start   = int(dev.pluginProps.get('morningStart', '5'))
                    afternoon_start = int(dev.pluginProps.get('afternoonStart', '12'))
                    evening_start   = int(dev.pluginProps.get('eveningStart', '17'))
                    night_start     = int(dev.pluginProps.get('nightStart', '21'))

                    morning   = dt.datetime.combine(today, dt.time(morning_start, 0))
                    afternoon = dt.datetime.combine(today, dt.time(afternoon_start, 0))
                    evening   = dt.datetime.combine(today, dt.time(evening_start, 0))
                    night     = dt.datetime.combine(today, dt.time(night_start, 0))

                    # Determine proper salutation based on the current time.
                    if morning <= now < afternoon:
                        intro_value = (dev.pluginProps.get('morningMessageIn', 'Good morning.'))
                        outro_value = (dev.pluginProps.get('morningMessageOut', 'Have a great morning.'))

                    elif afternoon <= now < evening:
                        intro_value = (dev.pluginProps.get('afternoonMessageIn', 'Good afternoon.'))
                        outro_value = (dev.pluginProps.get('afternoonMessageOut', 'Have a great afternoon.'))

                    elif evening <= now < night:
                        intro_value = (dev.pluginProps.get('eveningMessageIn', 'Good evening.'))
                        outro_value = (dev.pluginProps.get('eveningMessageOut', 'Have a great evening.'))

                    else:
                        intro_value = (dev.pluginProps.get('nightMessageIn', 'Good night.'))
                        outro_value = (dev.pluginProps.get('nightMessageOut', 'Have a great night.'))

                    # Don't update the device state unless the value has changed.
                    if intro_value != dev.states['intro']:
                        self.logger.debug(u"Updating intro to: {0}".format(intro_value))
                        states_list.append({'key': 'intro', 'value': intro_value})

                    if outro_value != dev.states['outro']:
                        self.logger.debug(u"Updating outro to: {0}".format(outro_value))
                        states_list.append({'key': 'outro', 'value': outro_value})

                    states_list.append({'key': 'onOffState', 'value': True, 'uiValue': u" "})
                    dev.updateStatesOnServer(states_list)

                elif dev.deviceTypeId == 'announcementsDevice':

                    # Cycle through the announcements and update as needed
                    try:

                        # Look at each plugin device and construct a placeholder if not already present. This is a placeholder
                        # and doesn't actually write the key back to the file.
                        if dev.id not in infile.keys():
                            infile[dev.id] = {}

                        for key in infile[dev.id].keys():

                            state_name = u"{0}".format(infile[dev.id][key]['Name'].replace(' ', '_'))
                            try:
                                refresh_time = infile[dev.id][key].get('nextRefresh', '1970-01-01 00:00:00')
                                update_time = parser.parse(refresh_time)

                            except ValueError as sub_error:
                                self.logger.warning(u"Error coercing announcement update time. Error: {0}".format(sub_error))
                                update_time = now - dt.timedelta(minutes=1)

                            # If it's time for an announcement to be refreshed.
                            if now >= update_time:
                                # Update the announcement text.
                                announcement = self.substitute(infile[dev.id][key]['Announcement'])
                                result = self.substitution_regex(announcement)
                                states_list.append({'key': state_name, 'value': result})

                                # Set the next refresh time
                                next_update = now + dt.timedelta(minutes=int(infile[dev.id][key]['Refresh']))
                                infile[dev.id][key]['nextRefresh'] = next_update.strftime('%Y-%m-%d %H:%M:%S')
                                self.logger.debug(u"{0} updated.".format(infile[dev.id][key]['Name']))

                            elif force:
                                # Force update the announcement text.
                                announcement = self.substitute(infile[dev.id][key]['Announcement'])
                                result = self.substitution_regex(announcement)
                                states_list.append({'key': state_name, 'value': result})

                        states_list.append({'key': 'onOffState', 'value': True, 'uiValue': u" "})
                        dev.updateStatesOnServer(states_list)

                    except KeyError as sub_error:
                        self.logger.error(u"error: {0}".format(sub_error))
                        pass

        # Open the announcements file and save the updated dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

    # =============================================================================
    def announcement_update_states_now(self):
        self.announcement_update_states(force=True)

    # =============================================================================
    def commsKillAll(self):
        """
        Disable communication for all plugin-defined devices

        commsKillAll() sets the enabled status of all plugin devices to
        false.

        -----

        """

        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=False)

            except Exception as sub_error:
                self.logger.critical(u"Exception when trying to kill all comms. Error: (Line {0}  {1})".format(sys.exc_traceback.tb_lineno, sub_error))

    # =============================================================================
    def commsUnkillAll(self):
        """
        Enable communication for all plugin-defined devices

        commsUnkillAll() sets the enabled status of all plugin devices to
        true.

        -----

        """

        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=True)

            except Exception as sub_error:
                self.logger.critical(u"Exception when trying to unkill all comms. Error: (Line {0}  {1})".format(sys.exc_traceback.tb_lineno, sub_error))

    # =============================================================================
    def format_digits(self, match):
        """
        Format announcement digits based on announcement criteria

        The format_digits function determines the proper formatting routine to
        use when converting target values to the specified format. It sends the
        target value to the proper function for formatting.

        -----

        :param str match:
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
            result = u"{0} {1}".format(match1, match2)

        return result

    # =============================================================================
    def format_current_time(self, match1, match2):
        """
        Format announcement times based on announcement criteria

        The format_current_time function is used to create a formatted version
        of the current time.

        -----

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
            return "{0:{1}}".format(match1, match2)

        except ValueError:
            return "{0} {1}".format(match1, match2)

    # =============================================================================
    def format_datetime(self, match1, match2):
        """
        Format announcement datetime based on announcement criteria

        The format_datetime function is used to format the string based on common
        Python datetime format specifiers.

        -----

        :param str match1:
        :param str match2:
        :return str result:
        """

        match2 = match2.replace('dt:', '')

        try:
            for char in match2:
                if char not in '.,%:-aAwdbBmyYHIpMSfzZjUWcxX ':  # allowable datetime specifiers
                    raise ValueError
            match1 = parser.parse(match1)
            return "{0:{1}}".format(match1, match2)

        except ValueError:
            return "{0} {1}".format(match1, match2)

    # =============================================================================
    def format_number(self, match1, match2):
        """
        Format announcement number based on announcement criteria

        The format_number function is used to format the string based on common
        Python numeric format specifiers

        -----

        :param str match1:
        :param str match2:
        :return str result:
        """

        match2 = match2.replace('n:', '')

        try:
            for char in match2:
                if char not in '%+-0123456789eEfFgGn':  # allowable numeric specifiers
                    raise ValueError
            return u"{0:0.{1}f}".format(float(match1), int(match2))

        except ValueError:
            return "{0} {1}".format(match1, match2)

    # =============================================================================
    def generatorAnnouncementList(self, filter="", values_dict=None, type_id="", target_id=0):
        """
        Generate a list of states for Indigo controls

        Returns a list of states for selected plugin device.

        -----

        :param str filter:
        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """

        try:
            announcement_id = int(values_dict['announcementDeviceToRefresh'])
            if announcement_id in indigo.devices.keys():
                return [(state, state) for state in indigo.devices[announcement_id].states if 'onOffState' not in state]
            else:
                return [('value', 'Value')]

        except KeyError:
            return [('None', 'None')]

    # =============================================================================
    def generatorDeviceList(self, filter="", values_dict=None, type_id="", target_id=0):
        """
        Generate a list of plugin-owned devices.

        Returns a list of plugin devices. Returns a list of tuples in the form:
        [(ID, "Name"), (ID, "Name")].

        -----

        :param str filter:
        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """

        return self.Fogbert.deviceList(filter='self')

    # =============================================================================
    def generatorDevVar(self, filter="", values_dict=None, type_id="", target_id=0):
        """
        Generate a list of Indigo devices and variables.

        This method collects IDs and names for all Indigo devices and
        variables. It creates a list of the form:
        [(dev.id, dev.name), (var.id, var.name)].

        -----

        :param str filter:
        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """

        return [(dev.id, dev.name) for dev in indigo.devices.iter()]

    # =============================================================================
    def generatorList(self, filter="", values_dict=None, type_id="", target_id=0):
        """
        Generate a list of configured announcements

        Populates the list of announcements based on the device's states. Returns a
        list based on a dict (infile) of the form:

        {announcement ID:
          {'Announcement': u"announcement string",
           'nextRefresh': 'YYYY-MM-DD HH:MM:SS',
           'Name': u'announcement name',
           'Refresh': u'minutes'
          }
        }

        The returned list is of the form:
        [(announcement ID, announcement name),]

        -----

        :param str filter:
        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """

        # Open the announcements file and load the contents
        with open(self.announcements_file) as input_file:
            infile = input_file.read()

        # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
        infile = ast.literal_eval(infile)

        # Sort the dict and create a list of tuples for the device config list control.
        try:
            announcement_list = [(key, infile[target_id][key]['Name']) for key in infile[target_id].keys()]

        except KeyError:
            announcement_list = []

        return sorted(announcement_list, key=lambda (k, val): unicode.lower(val))

    # =============================================================================
    def generatorStateOrValue(self, filter="", values_dict=None, type_id="", target_id=0):
        """
        Return a list of device states or variable value for selected device

        The generatorStateOrValue() method returns a list to populate the relevant
        device states or variable value to populate a menu control.

        -----

        :param str filter:
        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """

        try:
            id_number = int(values_dict['devVarMenu'])

            if id_number in indigo.devices.keys():
                state_list = [(state, state) for state in indigo.devices[id_number].states if not state.endswith('.ui')]
                state_list.remove(('onOffState', 'onOffState'))
                return state_list

            elif id_number in indigo.variables.keys():
                return [('value', 'Value')]

        except (KeyError, ValueError):
            return [(0, 'Pick a Device or Variable')]

    # =============================================================================
    def generator_substitutions(self, values_dict, type_id="", target_id=0):
        """
        Generate an Indigo substitution string

        The generator_substitutions function is used with the Substitution Generator.
        It is the callback that's used to create the Indigo substitution
        construct.

        -----

        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return indigo.dict values_dict:
        """

        dev_var_id    = values_dict['devVarMenu']
        dev_var_value = values_dict['generatorStateOrValue']

        try:
            if int(values_dict['devVarMenu']) in indigo.devices.keys():
                values_dict['subGeneratorResult'] = u"%%d:{0}:{1}%%".format(dev_var_id, dev_var_value)

            else:
                values_dict['subGeneratorResult'] = u"%%v:{0}%%".format(dev_var_id)

            values_dict['devVarMenu'] = ''
            values_dict['generatorStateOrValue'] = ''

            return values_dict

        except ValueError:
            announcement = self.substitute(values_dict['textfield1'])
            result       = self.substitution_regex(announcement)
            self.logger.info(u"Substitution Generator announcement: \"{0}\"".format(result))
            return values_dict

    # =============================================================================
    def generator_time(self, filter="", values_dict=None, type_id="", target_id=0):
        """
        Generate a list of times for plugin control menus

        Creates a list of times for use in setting salutation settings of the form:
        [(0, "00:00"), (1, "01:00"), ...]

        -----

        :param str filter:
        :param indigo.dict values_dict:
        :param str type_id:
        :param int target_id:
        :return list result:
        """

        return [(hour, u"{0:02.0f}:00".format(hour)) for hour in range(0, 24)]

    # =============================================================================
    def refreshFields(self, filter="", type_id="", target_id=0):
        """
        Dummy callback to force dynamic control refreshes

        The refreshFields() method is a dummy callback used solely to fire
        other actions that require a callback be run. It performs no other
        function.

        -----

        :param str filter:
        :param str type_id:
        :param int target_id:
        """

        pass

    # =============================================================================
    def substitution_regex(self, announcement):
        """
        Regex method for formatting substitutions

        This is the main regex used for formatting substitutions.

        -----

        :param str announcement:
        :return str result:
        """

        return re.sub(r'(<<.*?), *([ct|dt|n:].*?>>)', self.format_digits, announcement)
    # =============================================================================


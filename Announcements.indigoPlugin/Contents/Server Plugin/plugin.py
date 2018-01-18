#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-

""" docstring placeholder """

# =================================== TO DO ===================================

# TODO: Datetime modifier appears to be broken when there's an embedded space.

# ================================== IMPORTS ==================================

# Built-in modules
import ast
import datetime as dt
from dateutil import parser
import logging
import os
import re
import string
import sys

# Third-party modules
from DLFramework import indigoPluginUpdateChecker
try:
    import indigo
except ImportError, error:
    indigo.server.log(str(error), isError=True)

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
__version__   = '0.4.0'

# =============================================================================

kDefaultPluginPrefs = {
    u'pluginRefresh': "15",
    u'updaterEmailsEnabled': False,
    u'updaterEmail': "",
    u'showDebugLevel': "30",
}


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        updater_url = "https://davel17.github.io/Announcements/Announcements_version.html"
        self.updater = indigoPluginUpdateChecker.updateChecker(self, updater_url)

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

        # Establish data folder if it doesn't exist.
        working_directory = u"{0}/Announcements Plugin/".format(os.path.expanduser('~'))
        if not os.path.exists(working_directory):
            os.makedirs(working_directory)

        # Establish announcements file if it doesn't exist.
        self.announcements_file = u"{0}announcements.txt".format(working_directory)
        if not os.path.isfile(self.announcements_file):
            with open(self.announcements_file, 'w+') as outfile:
                outfile.write(u'{}')
            self.sleep(1)  # Wait a moment to let the system catch up.

        # try:
        #     pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
        # except:
        #     pass

    # ==============================================================
    # ======================= Indigo Methods =======================
    # ==============================================================

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
        """"""
        self.logger.debug(u"closedDeviceConfigUi() called.")

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        """ User closes config menu. The validatePrefsConfigUI() method will
        also be called."""
        self.logger.debug(u"closedPrefsConfigUi() called.")

        debug_label = {10: u"Debugging Messages", 20: u"Informational Messages", 30: u"Warning Messages", 40: u"Error Messages", 50: u"Critical Errors Only"}
        self.debugLevel = int(valuesDict['showDebugLevel'])
        self.update_frequency = int(valuesDict['pluginRefresh'])
        self.indigo_log_handler.setLevel(self.debugLevel)
        indigo.server.log(u"Debugging set to: {0}".format(debug_label[self.debugLevel]))

        # Update the devices to reflect any changes
        self.updateAnnouncementStates()

    def deviceStartComm(self, dev):
        """"""
        self.logger.debug(u"deviceStartComm() called.")
        dev.stateListOrDisplayStateIdChanged()
        dev.updateStateOnServer('onOffState', value=False, uiValue=u" ")

    def deviceStopComm(self, dev):
        """"""
        self.logger.debug(u"deviceStopComm() called.")
        dev.updateStateOnServer('onOffState', value=False, uiValue=u" ")

    def getDeviceConfigUiValues(self, valuesDict, typeId, devId):
        """Called when a device configuration dialog is opened. """
        self.logger.debug(u"getDeviceConfigUiValues() called.")

        # Set the device to disabled while it's being edited.
        indigo.device.enable(devId, value=False)

        # Ensure that the dialog opens with fresh fields.
        if typeId == 'announcementsDevice':
            for key in ['announcementName', 'announcementList', 'announcementRefresh', 'announcementText', 'subGeneratorResult']:
                valuesDict[key] = ''

        return valuesDict

    def getDeviceStateList(self, dev):
        """Called when an edit dialog is opened for a device.
           Called when user clicks Save Announcement
           Note: if this method is present, existing device states will need to 
           be established here or they 'won't exist.'"""
        self.logger.debug(u"getDeviceStateList() called.")

        dev_id = dev.id
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
            thing_name = thing[1].replace(' ', '_')
            announcement_state = self.getDeviceStateDictForStringType(thing_name, thing_name, thing_name)
            default_states_list.append(announcement_state)

        return default_states_list

    def runConcurrentThread(self):
        """ Main plugin thread. """
        self.logger.debug(u"runConcurrentThread initiated.")

        try:
            while True:
                self.updater.checkVersionPoll()
                self.sleep(1)

                self.update_frequency = int(self.pluginPrefs.get('pluginRefresh', 15))
                self.updateAnnouncementStates()
                self.sleep(self.update_frequency)

        except self.StopThread:
            pass

    def startup(self):
        """"""
        self.logger.debug(u"startup() called.")

        self.updater.checkVersionPoll()

        # ==============================================================
        # ============= Delete Out of Date Announcements ===============
        # ==============================================================

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

    def validatePrefsConfigUi(self, valuesDict):
        """ Validate select plugin config menu settings."""
        self.logger.debug(u"validatePrefsConfigUi() called.")

        return True, valuesDict

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """"""
        self.logger.debug(u"validateDeviceConfigUi() called.")
        error_msg_dict = indigo.Dict()

        # Announcements device
        if 'speakAnnouncement' in valuesDict.keys():
            pass

        # Salutations device
        if 'salutationsTitle' in valuesDict.keys():
            morning = int(valuesDict['morningStart'])
            afternoon = int(valuesDict['afternoonStart'])
            evening = int(valuesDict['eveningStart'])
            night = int(valuesDict['nightStart'])

            if not (morning < afternoon < evening < night):
                for _ in ['morningStart', 'afternoonStart', 'eveningStart', 'nightStart']:
                    error_msg_dict[_] = u"Each start time must be greater than the prior one."
                error_msg_dict['showAlertText'] = u"Message Start Time Error\n\nEach start time must be greater than the preceding one (morning < afternoon < evening < night)."
                return False, valuesDict, error_msg_dict

        self.updateAnnouncementStates()
        return True, valuesDict

    # ==============================================================
    # ================ Announcement Plugin Methods =================
    # ==============================================================

    def checkVersionNow(self):
        """ The checkVersionNow() method will call the Indigo Plugin Update
        Checker based on a user request. """

        self.updater.checkVersionNow()

    def createAnnouncementId(self, temp_dict):
        """Create a unique ID number for the announcement."""
        # Create a new index number.
        index = id('dummy object')

        # If the new index happens to exist, repeat until unique.
        while index in temp_dict.keys():
            index += 1

        return index

    def killAllComms(self):
        """ killAllComms() sets the enabled status of all plugin devices to
        false. """
        self.logger.debug(u"killAllComms method() called.")

        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=False)

            except Exception as sub_error:
                self.logger.critical(u"Exception when trying to kill all comms. Error: (Line {0}  {1})".format(sys.exc_traceback.tb_lineno, sub_error))

    def unkillAllComms(self):
        """ unkillAllComms() sets the enabled status of all plugin devices to
        true. """
        self.logger.debug(u"unkillAllComms method() called.")

        for dev in indigo.devices.itervalues("self"):
            try:
                indigo.device.enable(dev, value=True)

            except Exception as sub_error:
                self.logger.critical(u"Exception when trying to unkill all comms. Error: (Line {0}  {1})".format(sys.exc_traceback.tb_lineno, sub_error))

    # ==============================================================
    # ================ Announcement Format Methods =================
    # ==============================================================

    def formatDigits(self, match):
        """The formatDigits function determines the proper formatting routine to
        use when converting target values to the specified format. It sends the
        target value to the proper function for formatting."""

        match1 = match.group(1)  # the string to be formatted
        match2 = match.group(2)  # the format specification
        match1 = match1.replace('<<', '')
        match2 = match2.replace('>>', '')

        # Current time conversions specified with ct: ...
        if match2.startswith('ct:'):
            result = self.formatCurrentTime(match1, match2)

        # Datetime conversions specified with dt: ...
        elif match2.startswith('dt:'):
            result = self.formatDatetime(match1, match2)

        # Number conversions specified with n: ...
        elif match2.startswith('n:'):
            result = self.formatNumber(match1, match2)

        else:
            result = u"{0} {1}".format(match1, match2)

        return result

    def formatCurrentTime(self, match1, match2):
        """The formatCurrentTime function is used to create a formatted version
        of the current time."""

        match2 = match2.replace('ct:', '')

        try:
            for char in match2:
                if char not in '%:-aAwdbBmyYHIpMSfzZjUWcxX':  # allowable datetime specifiers
                    raise ValueError
            match1 = dt.datetime.now()
            return "{0:{1}}".format(match1, match2)

        except ValueError:
            return "{0} {1}".format(match1, match2)

    def formatDatetime(self, match1, match2):
        """The formatDatetime function is used to format the string based on common
        Python datetime format specifiers."""

        match2 = match2.replace('dt:', '')

        try:
            for char in match2:
                if char not in '%:-aAwdbBmyYHIpMSfzZjUWcxX':  # allowable datetime specifiers
                    raise ValueError
            match1 = parser.parse(match1)
            return "{0:{1}}".format(match1, match2)

        except ValueError:
            return "{0} {1}".format(match1, match2)

    def formatNumber(self, match1, match2):
        """The formatNumber function is used to format the string based on common
        Python numeric format specifiers"""

        match2 = match2.replace('n:', '')

        try:
            for char in match2:
                if char not in '%+-0123456789eEfFgGn':  # allowable numeric specifiers
                    raise ValueError
            return u"{0:0.{1}f}".format(float(match1), int(match2))

        except ValueError:
            return "{0} {1}".format(match1, match2)

    # ==============================================================
    # ======================== Generators ==========================
    # ==============================================================

    def generatorAnnouncementList(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Returns a list of states for selected plugin device."""
        self.logger.debug(u"generatorAnnouncementList() called.")

        try:
            announcement_id = int(valuesDict['announcementDeviceToRefresh'])
            if announcement_id in indigo.devices.keys():
                return [(state, state) for state in indigo.devices[announcement_id].states if 'onOffState' not in state]
            else:
                return [('value', 'Value')]

        except KeyError:
            return [('None', 'None')]

    def generatorDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Returns a list of plugin devices."""
        self.logger.debug(u"generatorDeviceList() called.")

        return self.Fogbert.deviceList(filter='self')

    def generatorDevVar(self, filter="", valuesDict=None, typeId="", targetId=0):
        """This method collects IDs and names for all Indigo devices and
        variables. It creates a list of the form:
        [(dev.id, dev.name), (var.id, var.name)].
        """
        self.logger.debug(u"generatorDevVar() called.")

        return self.Fogbert.deviceAndVariableList()

    def generatorList(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Populates the list of announcements based on the device's states."""
        self.logger.debug(u"generatorList() called.")

        # Open the announcements file and load the contents
        with open(self.announcements_file) as input_file:
            infile = input_file.read()

        # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
        infile = ast.literal_eval(infile)

        # Sort the dict and create a list of tuples for the device config list control.
        try:
            announcement_list = [(key, infile[targetId][key]['Name']) for key in infile[targetId].keys()]

        except KeyError:
            announcement_list = []

        return sorted(announcement_list, key=lambda (k, val): unicode.lower(val))

    def generatorStateOrValue(self, filter="", valuesDict=None, typeId="", targetId=0):
        """The generatorStateOrValue() method returns a list to populate the relevant
        device states or variable value to populate a menu control."""
        self.logger.debug(u"generatorStateOrValue() called.")

        try:
            id_number = int(valuesDict['devVarMenu'])

            if id_number in indigo.devices.keys():
                state_list = [(state, state) for state in indigo.devices[id_number].states if not state.endswith('.ui')]
                state_list.remove(('onOffState', 'onOffState'))
                return state_list

            elif id_number in indigo.variables.keys():
                return [('value', 'Value')]

        except (KeyError, ValueError):
            return [(0, 'Pick a Device or Variable')]

    def generatorSubstitutions(self, valuesDict, typeId="", targetId=0):
        """The generatorSubstitutions function is used with the Substitution Generator.
        It is the callback that's used to create the Indigo substitution
        construct."""
        self.logger.debug(u"generatorSubstitutions() called.")

        dev_var_id    = valuesDict['devVarMenu']
        dev_var_value = valuesDict['generatorStateOrValue']

        try:
            if int(valuesDict['devVarMenu']) in indigo.devices.keys():
                valuesDict['subGeneratorResult'] = u"%%d:{0}:{1}%%".format(dev_var_id, dev_var_value)

            else:
                valuesDict['subGeneratorResult'] = u"%%v:{0}%%".format(dev_var_id)

            valuesDict['devVarMenu'] = ''
            valuesDict['generatorStateOrValue'] = ''

            return valuesDict

        except ValueError:
            announcement = self.substitute(valuesDict['textfield1'])
            result = self.substitutionRegex(announcement)
            self.logger.info(u"Substitution Generator announcement: \"{0}\"".format(result))
            return valuesDict

    def generatorTime(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Creates a list of times for use in setting salutation settings."""
        self.logger.debug(u"generatorTime() called.")

        return [(hour, u"{0:02.0f}:00".format(hour)) for hour in range(0, 24)]

    def updateAnnouncementStates(self):
        """"""
        # self.logger.debug(u"updateAnnouncementStates() called. Note: if called from the Indigo Menu, it will only cause announcements waiting for an update to refresh.")
        now = indigo.server.getTime()

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
        infile = ast.literal_eval(infile)

        for dev in indigo.devices.iter('self'):

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
                        dev.updateStateOnServer('intro', value=intro_value)

                    if outro_value != dev.states['outro']:
                        self.logger.debug(u"Updating outro to: {0}".format(outro_value))
                        dev.updateStateOnServer('outro', value=outro_value)

                    dev.updateStateOnServer('onOffState', value=True, uiValue=u" ")

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
                                update_time = dt.datetime.strptime(infile[dev.id][key]['nextRefresh'], '%Y-%m-%d %H:%M:%S')

                            except ValueError:
                                self.logger.warning(u"Error coercing announcement update time.")
                                update_time = now - dt.timedelta(minutes=1)  # If the refresh time hasn't been established yet.

                            # If it's time for an announcement to be refreshed.
                            if now >= update_time:
                                # Update the announcement text.
                                announcement = self.substitute(infile[dev.id][key]['Announcement'])
                                result = self.substitutionRegex(announcement)
                                dev.updateStateOnServer(state_name, value=result)

                                # Set the next refresh time
                                next_update = now + dt.timedelta(minutes=int(infile[dev.id][key]['Refresh']))
                                infile[dev.id][key]['nextRefresh'] = next_update.strftime('%Y-%m-%d %H:%M:%S')
                                self.logger.debug(u"{0} updated.".format(infile[dev.id][key]['Name']))

                        dev.updateStateOnServer('onOffState', value=True, uiValue=u" ")

                    except KeyError as sub_error:
                        self.logger.error(u"error: {0}".format(sub_error))
                        pass

        # Open the announcements file and save the updated dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

    # ==============================================================
    # ============= Announcement Device Button Methods =============
    # ==============================================================

    def clearAnnouncement(self, valuesDict, typeId="", targetId=0):
        """Clears whatever is in the Announcement textfield."""
        self.logger.debug(u"clearAnnouncement() called.")

        for key in ['announcementIndex', 'announcementName', 'announcementRefresh', 'announcementList', 'announcementText']:
            valuesDict[key] = ''

        valuesDict['editFlag'] = False
        return valuesDict

    def deleteAnnouncement(self, valuesDict, typeId, devId):
        """Called when user clicks the Delete Announcement button"""
        self.logger.debug(u"deleteAnnouncement() called.")

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and delete the key.
        infile = ast.literal_eval(infile)
        index = int(valuesDict['announcementList'])
        del infile[devId][index]

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

        for key in ['announcementIndex', 'announcementName', 'announcementRefresh', 'announcementList', 'announcementText']:
            valuesDict[key] = ''

        valuesDict['editFlag'] = False

        return valuesDict

    def duplicateAnnouncement(self, valuesDict, typeId, devId):
        """Called when user clicks the Duplicate Announcement button"""
        self.logger.debug(u"duplicateAnnouncement() called.")

        index = int(valuesDict['announcementList'])
        self.logger.info(u"Announcement to be duplicated: {0}".format(index))

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and delete the key.
        infile = ast.literal_eval(infile)

        # Create a new announcement.
        temp_dict = infile[devId]
        new_index = self.createAnnouncementId(temp_dict)
        temp_dict[new_index] = {}
        temp_dict[new_index]['Name'] = infile[devId][index]['Name'] + u" copy"
        temp_dict[new_index]['Announcement'] = infile[devId][index]['Announcement']
        temp_dict[new_index]['Refresh'] = infile[devId][index]['Refresh']
        temp_dict[new_index]['nextRefresh'] = infile[devId][index]['nextRefresh']

        # Set the dict element equal to the new list
        infile[devId] = temp_dict

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

        return valuesDict

    def editAnnouncement(self, valuesDict, typeId, devId):
        """Called when user clicks the Edit Announcement button"""
        self.logger.debug(u"editAnnouncement() called.")
        self.logger.debug(u"Editing the {0} announcement".format(valuesDict['announcementName']))

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict, and get the data for this device.
        infile = ast.literal_eval(infile)
        temp_dict = infile[devId]

        # Get the selected announcement index and populate the UI elements.
        index = int(valuesDict['announcementList'])
        valuesDict['announcementIndex'] = index
        valuesDict['announcementName'] = temp_dict[index]['Name']
        valuesDict['announcementRefresh'] = temp_dict[index]['Refresh']
        valuesDict['announcementText'] = temp_dict[index]['Announcement']
        valuesDict['editFlag'] = True

        return valuesDict

    def saveAnnouncement(self, valuesDict, typeId, devId):
        """Called when user clicks the Save Announcement button."""
        self.logger.debug(u"saveAnnouncement() called.")

        # ==============================================================
        # ===================== Validation Methods =====================
        # ==============================================================

        valuesDict['announcementName'] = valuesDict['announcementName'].strip()  # Strip leading and trailing whitespace if there is any.

        # Announcement Name empty or 'REQUIRED'
        if valuesDict['announcementName'].isspace() or valuesDict['announcementName'] in ['', 'REQUIRED', ]:
            self.logger.error(u"A announcement name is required.")
            valuesDict['announcementName'] = 'REQUIRED'
            return valuesDict

        # Announcement Name starts with digit'
        if valuesDict['announcementName'][0].isdigit():
            self.logger.error(u"A announcement name can not start with a number.")
            return valuesDict

        # Announcement Name starts with punctuation
        exclude = set(string.punctuation)
        if valuesDict['announcementName'][0] in exclude:
            self.logger.error(u"A announcement name can not start with punctuation.")
            return valuesDict

        # Announcement Name starts with XML.
        if valuesDict['announcementName'][0:3].lower() == 'xml':
            self.logger.error(u"A announcement name can not start with the letters 'xml'.")
            return valuesDict

        if not all(ord(char) < 128 for char in valuesDict['announcementName']):
            self.logger.error(u"A announcement name can not contain Unicode characters.")
            return valuesDict

        # Announcement Text is empty or 'REQUIRED'
        if valuesDict['announcementText'].isspace() or valuesDict['announcementText'] in ['', 'REQUIRED', ]:
            self.logger.error(u"An announcement is required.")
            valuesDict['announcementText'] = 'REQUIRED'
            return valuesDict

        # Announcement Text not digit or less than 1
        if not valuesDict['announcementRefresh'].isdigit() or int(valuesDict['announcementRefresh']) < 1:
            self.logger.error(u"A positive integer greater than zero is required.")
            return valuesDict

        # Open the announcements file and load the contents
        with open(self.announcements_file) as outfile:
            infile = outfile.read()

        # Convert the string implementation of the dict to an actual dict.
        infile = ast.literal_eval(infile)

        try:
            temp_dict = infile[devId]

        except KeyError:
            temp_dict = {}

        # Generate a list of announcement names in use for this device.
        announcement_name_list = [temp_dict[key]['Name'] for key in temp_dict.keys()]

        # If new announcement, create unique id, then save to dict.
        if not valuesDict['editFlag'] and valuesDict['announcementName'] not in announcement_name_list:
            index = self.createAnnouncementId(temp_dict)
            temp_dict[index] = {}
            temp_dict[index]['Name'] = valuesDict['announcementName']
            temp_dict[index]['Announcement'] = valuesDict['announcementText']
            temp_dict[index]['Refresh'] = valuesDict['announcementRefresh']
            temp_dict[index]['nextRefresh'] = str(dt.datetime.now())

        # If key exists, save to dict.
        elif valuesDict['editFlag']:
            index = int(valuesDict['announcementIndex'])
            temp_dict[index]['Name'] = valuesDict['announcementName']
            temp_dict[index]['Announcement'] = valuesDict['announcementText']
            temp_dict[index]['Refresh'] = valuesDict['announcementRefresh']

        # User has created a new announcement with a name already in use
        else:
            index = self.createAnnouncementId(temp_dict)
            temp_dict[index] = {}
            temp_dict[index]['Name'] = valuesDict['announcementName'] + u'*'
            temp_dict[index]['Announcement'] = valuesDict['announcementText']
            temp_dict[index]['Refresh'] = valuesDict['announcementRefresh']
            temp_dict[index]['nextRefresh'] = str(dt.datetime.now())
            self.logger.error(u"Duplicate announcement name found.")

        # Set the dict element equal to the new list
        infile[devId] = temp_dict

        # Open the announcements file and save the new dict.
        with open(self.announcements_file, 'w') as outfile:
            outfile.write(u"{0}".format(infile))

        # Clear the fields.
        for key in ['announcementIndex', 'announcementName', 'announcementRefresh', 'announcementList', 'announcementText']:
            valuesDict[key] = ''

        valuesDict['editFlag'] = False

        return valuesDict

    # ==============================================================
    # ====================== Plugin Callbacks ======================
    # ==============================================================

    def speakAnnouncement(self, valuesDict, typeId, devId):
        """Called when user clicks the Speak Announcement button"""
        self.logger.debug(u"speakAnnouncement() called.")
        default_string = u"Please select or enter an item to speak."

        # The user has entered a value in the announcement field. Speak that.
        if len(valuesDict['announcementText']) > 0:
            result = self.substitutionRegex(self.substitute(valuesDict['announcementText']))
            indigo.server.speak(result, waitUntilDone=False)

            self.logger.info(u"{0}".format(result))

        # If the announcement field is blank, and the user has selected an announcement in the list.
        elif valuesDict['announcementList'] != "":
            # Open the announcements file and load the contents
            with open(self.announcements_file) as outfile:
                infile = outfile.read()

            # Convert the string implementation of the dict to an actual dict, and get the sub dict for the device.
            infile = ast.literal_eval(infile)

            announcement = self.substitute(infile[devId][int(valuesDict['announcementList'])]['Announcement'])
            result = self.substitutionRegex(announcement)
            indigo.server.speak(result, waitUntilDone=False)

            self.logger.info(u"{0}".format(result))

        # Otherwise, let the user know that there is nothing to speak.
        else:
            self.logger.error(default_string)
            indigo.server.speak(default_string, waitUntilDone=False)

        return valuesDict

    def speakAnnouncementAction(self, pluginAction):
        """
        Indigo action for speaking any device state or variable value.
        """
        indigo.server.log('speakAnnouncementAction() called.')

        item_source   = int(pluginAction.props['announcementDeviceToRefresh'])
        item_to_speak = pluginAction.props['announcementToSpeak']

        try:
            if item_source in indigo.devices.keys():
                announcement = str(indigo.devices[item_source].states[item_to_speak])
                indigo.server.speak(announcement, waitUntilDone=False)
            else:
                announcement = indigo.variables[item_source].value
                indigo.server.speak(announcement, waitUntilDone=False)
        except ValueError:
            self.logger.warning(u"Unable to speak {0} value.".format(item_to_speak))

    def refreshFields(self, filter="", typeId="", targetId=0):
        """The refreshFields() method is a dummy callback used solely to fire
        other actions that require a callback be run. It performs no other
        function."""
        self.logger.debug(u"refreshFields() called.")
        pass

    # ==============================================================
    # ======== Plugin Action to Refresh Single Announcement ========
    # ==============================================================

    def refreshAnnouncementAction(self, pluginAction):
        """The refreshAnnouncementAction() method is used to force an
        announcement to be refreshed by using an Indigo Action Item."""
        self.logger.debug(u"refreshAnnouncementAction() called.")
        announcement_name = pluginAction.props['announcementToRefresh']
        device_id         = int(pluginAction.props['announcementDeviceToRefresh'])
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
                result = self.substitutionRegex(announcement)
                dev.updateStateOnServer(announcement_name, value=result)

    def substitutionRegex(self, announcement):
        """This is the main regex used for formatting substitutions."""
        return re.sub(r'(<<.*?), *([ct|dt|n:].*?>>)', self.formatDigits, announcement)

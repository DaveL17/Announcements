
### v2022.0.6
- Adds function to mirror Speak Text value to a designated variable.
- Adds scripting action to request a copy of the announcements database.

### v2022.0.5
- Fixes bug where announcements were not being automatically updated.

### v2022.0.4
- Adds foundation for API `3.1`.
 
### v2022.0.3
- Adds `_to_do_list.md` and changes changelog to markdown.
- Moves plugin environment logging to plugin menu item (log only on request).

### v2022.0.2
- Fixes bug in `Speak Announcement` action item where executing action doesn't result in spoken announcement.

### v2022.0.1
- Updates plugin for Indigo 2022.1 and Python 3.
- Adds new Action Item to force refresh of all announcements.
- Allows fractional refresh intervals (i.e., 0.5 = 30 seconds, 0.25 = 15 seconds).
- Fixes bug in announcement save validation where duplicate names would cause an illegal XML error.
- Tightens code surrounding errors at plugin startup when announcements file is corrupted or incompatible.
- Adds logging for instances where announcements file is not present at startup.
- Standardizes Indigo method implementation.

### v1.0.21
- Implements Constants.py
- Code refinements

### v1.0.20
- Fixes bug in Announcements to Speak Action configuration where dropdown did not filter to show plugin devices only.

### v1.0.19
- Fixes bug in Announcements device configuration upon first creation.
- Fixes bug in Salutations device where time values not initially validated properly.

### v1.0.18
- Fixes bug in plugin initialization for new plugin installations.

### v1.0.17
- Fixes broken link to logo image in README.md

### v1.0.16
- Fixes bug in generator_state_or_value.
- Fixes bug in substitution generator where only plugin devices may display.

### v1.0.15
- Code refinements.

### v1.0.14
- Fixes bug in device substitution generator where control was only listing devices and not variables.
- Further integration with DLFramework.

### v1.0.13
- Better integration of DLFramework.
- Improved device settings validation.
- Code refinements.

### v1.0.12
- Removes blue text for all displays (views poorly in dark mode).

### v1.0.11
- Improvements to device configuration validation.
- Code refinements.

### v1.0.10
- Removes all references to legacy version checking.

### v1.0.09
- Ensures that the plugin is compatible with the Indigo server version.
- Standardizes SupportURL behavior across all plugin functions.

### v1.0.08
- Fixes bug in substitution generator where generator was returning only plugin devices.

### v1.0.07
- Synchronize self.pluginPrefs in closedPrefsConfigUi().

### v1.0.06
- Changes "En/Disable all Announcements Devices" to "En/Disable all Plugin Devices".

### v1.0.05
- Changes Python lists to tuples where possible to improve performance.

### v1.0.04
- Fixes critical bug where restarting the plugin deletes saved announcements.

### v1.0.03
- Fixes bug when a "Speak Announcement Action" was called when there was no announcement to speak.
- Refines logging.

### v1.0.02
- Removes plugin update notifications.
- Moves announcement settings file to Indigo plugin preferences directory.
- Code refinements.

### v1.0.01
- Takes plugin out of beta.
- Fixes bug where speak action returned all indigo devices and variables instead of only plugin devices.
- Code refinements.

### v0.5.02
- Fixes bug in naming of PluginConfig.xml (which caused problems on systems set up as case-sensitive).
- Code refinements.

### v0.5.01
- Now requires Indigo 7.
- Updates devices states using Indigo API 2.0
- Updates docstrings to Sphinx standard.
- Fixes minor bug in setting of announcement refresh time when new announcements are first created.
- Code refinements.

### v0.4.01
- Updates plugin update checker to use curl to overcome outdated security of Apple's Python install.

### v0.4.0
- Moves plugin to Beta.
- Creates Speak Announcement Action item.
- Adds period, space and comma to allowable datetime and current time modifiers.
- Increments to Indigo API 2.0.

### v0.3.7
- Prepared for Indigo Plugin Store
- Establishes kDefaultPluginPrefs
- Implements indigoPluginUpdateChecker

### v0.3.6
- Code consolidation using DLFramework.
- Code consolidation using pluginConfig templates.
- Implements plugin version update checker.

### v0.3.5
- Fixes bug in substitution generator.

### v0.3.4
- Fixes pydevd import error.

### v0.3.3
- Moves the Refresh Announcements Action item to the devices actions list. (Select Action Group --> Device Actions --> Announcements Controls)
- Improves time banding for salutation selection.
- Adds remote debugging.

### v0.3.2
- Adds Action to update single announcement on demand.
- Fixed bug in announcement refresh interval.
- Consolidates regex substitutions to single function call.

### v0.3.1
- Initial release.

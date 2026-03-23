"""
Repository of application constants

The constants.py file contains all application constants and is imported as a library. References are denoted as
constants by the use of all caps.
"""


def __init__():
    pass


ANNOUNCEMENT_DIALOG_FIELDS = (
    'announcementIndex',
    'announcementName',
    'announcementRefresh',
    'announcementList',
    'announcementText',
)

ANNOUNCEMENT_DIALOG_OPEN_FIELDS = (
    'announcementName',
    'announcementList',
    'announcementRefresh',
    'announcementText',
    'subGeneratorResult',
)

DEBUG_LABELS = {
    10: "Debugging Messages",
    20: "Informational Messages",
    30: "Warning Messages",
    40: "Error Messages",
    50: "Critical Errors Only"
}

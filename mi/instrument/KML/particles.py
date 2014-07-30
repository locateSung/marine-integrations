"""
@package mi.instrument.KML.particles
@file marine-integrations/mi/instrument/KML/driver.py
@author SUng Ahn
@brief Driver particle code for the KML particles
Release notes:
"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import re
from struct import unpack
import time as time
import datetime as dt

from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.instrument.teledyne.driver import NEWLINE

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

#
# Particle Regex's'
#
CAMDS_RESPONSE = r'.*\n<::>'

# ##############################################################################
# Data Particles
# ##############################################################################
class DataParticleType(BaseEnum):
    """
    Stream types of data particles
    """
    RAW = CommonDataParticleType.RAW
    CAMDS_RESPONSE = "camds_response"
    CAMDS_VIDEO_BINARY = "camds_video_binary"

# keys for video stream
class CAMDS_VIDEO_KEY(BaseEnum):
    CAMDS_VIDEO = "camds video"

# Data particle for PT4 command
class CAMDS_VIDEO(DataParticle):
    _data_particle_type = DataParticleType.CAMDS_VIDEO_BINARY

    RE01 = re.compile(r'.*')

    def _build_parsed_values(self):
        # Initialize
        matches = {}
        for key, regex, formatter in [
            (CAMDS_VIDEO_KEY.CAMDS_VIDEO, self.RE01, float)
        ]:
            match = regex.search(self.raw_data)
            matches[key] = formatter(match.group(1))

        result = []
        for key, value in matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result





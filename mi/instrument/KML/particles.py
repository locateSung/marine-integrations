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
CAMDS_RESPONSE_MATCHER = re.compile(CAMDS_RESPONSE,re.DOTALL)

# CAMDS_VIDEO = r'.{500}'
# CAMDS_VIDEO_MATCH = re.compile(CAMDS_VIDEO, re.DOTALL)

# ADCP_PD0_PARSED_REGEX = r'\x7f\x7f(..)'  # .*
# ADCP_PD0_PARSED_REGEX_MATCHER = re.compile(ADCP_PD0_PARSED_REGEX, re.DOTALL)
# ADCP_SYSTEM_CONFIGURATION_REGEX = r'(Instrument S/N.*?)\>'
# ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER = re.compile(ADCP_SYSTEM_CONFIGURATION_REGEX, re.DOTALL)
# ADCP_COMPASS_CALIBRATION_REGEX = r'(ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM.*?)\>'
# ADCP_COMPASS_CALIBRATION_REGEX_MATCHER = re.compile(ADCP_COMPASS_CALIBRATION_REGEX, re.DOTALL)
# ADCP_ANCILLARY_SYSTEM_DATA_REGEX = r'(Ambient  Temperature.*\n.*\n.*)\n>'
# ADCP_ANCILLARY_SYSTEM_DATA_REGEX_MATCHER = re.compile(ADCP_ANCILLARY_SYSTEM_DATA_REGEX)
# ADCP_TRANSMIT_PATH_REGEX = r'(IXMT.*\n.*\n.*\n.*)\n>'
# ADCP_TRANSMIT_PATH_REGEX_MATCHER = re.compile(ADCP_TRANSMIT_PATH_REGEX)


# ##############################################################################
# Data Particles
# ##############################################################################
class DataParticleType(BaseEnum):
    """
    Stream types of data particles
    """
    RAW = CommonDataParticleType.RAW
    CAMDS_RESPONSE = "camds_response"
    CAMDS_VIDEO = "camds_video"
    CAMDS_HEALTH_STATUS = "camds_health_status"
    CAMDS_DISK_STATUS = "camds_disc_status"

# keys for video stream
class CAMDS_VIDEO_KEY(BaseEnum):
    CAMDS_VIDEO_BINARY = "raw"

# Data particle for PT4 command
class CAMDS_VIDEO(DataParticle):
    _data_particle_type = DataParticleType.CAMDS_VIDEO

    def _build_parsed_values(self):

        result = []
        result.append({DataParticleKey.VALUE_ID: CAMDS_VIDEO_KEY.CAMDS_VIDEO_BINARY,
                       DataParticleKey.VALUE: self.raw_data})
        return result


# HS command
class CAMDS_HEALTH_STATUS_KEY(BaseEnum):
    temp = "camds_temp"
    humidity = "camds_humidity"
    error = "camds_error"

# Data particle for HS command
class CAMDS_HEALTH_STATUS(DataParticle):
    _data_particle_type = DataParticleType.CAMDS_HEALTH_STATUS

    RE01 = re.compile(r'.*')

    def _build_parsed_values(self):
        # Initialize
        matches = {}
        for key, regex, formatter in [
            (CAMDS_HEALTH_STATUS_KEY.temp, self.RE01, float)
        ]:
            match = regex.search(self.raw_data)
            matches[key] = formatter(match.group(1))

        result = []
        for key, value in matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result


# GC command
class CAMDS_DISK_STATUS_KEY(BaseEnum):
    size = "camds_disc_size"
    disk_remaining = "camds_disc_remaining"
    image_remaining = "camds_images_remaining"
    image_on_disk = "camds_images_on_disc"

# Data particle for GC command
class CAMDS_DISK_STATUS(DataParticle):
    _data_particle_type = DataParticleType.CAMDS_HEALTH_STATUS

    RE01 = re.compile(r'.*')

    def _build_parsed_values(self):
        # Initialize
        matches = {}
        for key, regex, formatter in [
            (CAMDS_DISK_STATUS_KEY.image_on_disk, self.RE01, float)
        ]:
            match = regex.search(self.raw_data)
            matches[key] = formatter(match.group(1))

        result = []
        for key, value in matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result




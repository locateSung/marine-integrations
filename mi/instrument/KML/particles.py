"""
@package mi.instrument.KML.particles
@file marine-integrations/mi/instrument/KML/driver.py
@author SUng Ahn
@brief Driver particle code for the KML particles
Release notes:
"""
import struct
from mi.instrument.KML.driver import KMLParameter

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

#
# Particle Regex's'
#
CAMDS_DISK_STATUS_MATCHER = r'<\x0B:\x06:GC[\0-\xFF]+>'
CAMDS_HEALTH_STATUS_MATCHER = r'<\x07:\x06:HS[\0-\xFF]+>'
CAMDS_SNAPSHOT_MATCHER = r'<\x04:\x06:CI>'
CAMDS_START_CAPTURING = r'<\x04:\x06:SP>'
CAMDS_STOP_CAPTURING = r'<\x04:\x06:SR>'


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
    CAMDS_IMAGE_METADATA = "camds_image_metadata"

# keys for video stream
class CAMDS_VIDEO_KEY(BaseEnum):
    """
    Video stream data key
    """
    CAMDS_VIDEO_BINARY = "raw"

# Data particle for PT4 command
class CAMDS_VIDEO(DataParticle):
    """
    CAMDS video stream data particle
    """
    _data_particle_type = DataParticleType.CAMDS_VIDEO

    def _build_parsed_values(self):
        result = []
        result.append({DataParticleKey.VALUE_ID: CAMDS_VIDEO_KEY.CAMDS_VIDEO_BINARY,
                       DataParticleKey.VALUE: self.raw_data})
        return result


# HS command
class CAMDS_HEALTH_STATUS_KEY(BaseEnum):
    """
    CAMDS health status keys
    """
    temp = "camds_temp"
    humidity = "camds_humidity"
    error = "camds_error"

# Data particle for HS command
class CAMDS_HEALTH_STATUS(DataParticle):
    """
    CAMDS health status data particle
    """
    _data_particle_type = DataParticleType.CAMDS_HEALTH_STATUS

    def build_data_particle(self, temp = None, humidity = None,
                            error = None):
        result = []
        for key in [CAMDS_HEALTH_STATUS_KEY.temp,
                    CAMDS_HEALTH_STATUS_KEY.humidity,
                    CAMDS_HEALTH_STATUS_KEY.error ]:

            if key == CAMDS_HEALTH_STATUS_KEY.temp:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : temp
                })

            if key == CAMDS_HEALTH_STATUS_KEY.humidity:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : humidity
                })

            if key == CAMDS_HEALTH_STATUS_KEY.error:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : error
                })
        return result

    def _build_parsed_values(self):

        resopnse_striped = '%r' % self.raw_data.strip()
        #check the size of the response
        if len(resopnse_striped) != 7:
            log.error("Disk status size should be 12 %r" +  resopnse_striped)
            return
        if resopnse_striped[0] != '<':
            log.error("Disk status is not correctly formated %r" +  resopnse_striped)
            return
        if resopnse_striped[len(resopnse_striped) -1] != '>':
            log.error("Disk status is not correctly formated %r" +  resopnse_striped)
            return

        int_bytes = bytearray(resopnse_striped)
        _temp = int_bytes[7]
        _humidity = int_bytes[8]
        _error = int_bytes[9]



        sample = CAMDS_HEALTH_STATUS(resopnse_striped)
        parsed_sample = sample.build_data_particle(temp = _temp, humidity = _humidity,
                                                   error = _error)
        return parsed_sample


# GC command
class CAMDS_DISK_STATUS_KEY(BaseEnum):
    """
    CAMDS disk status keys
    """
    size = "camds_disc_size"
    disk_remaining = "camds_disc_remaining"
    image_remaining = "camds_images_remaining"
    image_on_disk = "camds_images_on_disc"

# Data particle for GC command
class CAMDS_DISK_STATUS(DataParticle):
    "CAMDS disk status data particle"
    _data_particle_type = DataParticleType.CAMDS_DISK_STATUS

    def build_data_particle(self, size = None, disk_remaining = None,
                            image_remaining = None, image_on_disk = None):
        result = []
        for key in [CAMDS_DISK_STATUS_KEY.size,
                    CAMDS_DISK_STATUS_KEY.disk_remaining,
                    CAMDS_DISK_STATUS_KEY.image_remaining,
                    CAMDS_DISK_STATUS_KEY.image_on_disk ]:

            if key == CAMDS_DISK_STATUS_KEY.size:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : disk_remaining
                })

            if key == CAMDS_DISK_STATUS_KEY.disk_remaining:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : disk_remaining
                })

            if key == CAMDS_DISK_STATUS_KEY.image_remaining:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : image_remaining
                })

            if key == CAMDS_DISK_STATUS_KEY.image_on_disk:
                result.append( {
                DataParticleKey.VALUE_ID: key,
                DataParticleKey.VALUE : image_on_disk
                })
        return result


    def _build_parsed_values(self):
        resopnse_striped = '%r' % self.raw_data.strip()
        #check the size of the response
        if len(resopnse_striped) != 12:
            log.error("Disk status size should be 12 %r" +  resopnse_striped)
            return
        if resopnse_striped[0] != '<':
            log.error("Disk status is not correctly formated %r" +  resopnse_striped)
            return
        if resopnse_striped[len(resopnse_striped) -1] != '>':
            log.error("Disk status is not correctly formated %r" +  resopnse_striped)
            return

        int_bytes = bytearray(resopnse_striped)
        byte1 = int_bytes[7]
        byte2 = int_bytes[8]
        byte3 = int_bytes[9]

        available_disk = byte1 * pow(10, byte2)
        available_disk_percent = byte3
        temp = struct.pack('!h', resopnse_striped[9] + resopnse_striped[10])
        images_remaining = temp[0]
        temp = struct.pack('!h', resopnse_striped[11] + resopnse_striped[12])
        images_on_disk = temp[0]

        sample = CAMDS_DISK_STATUS(resopnse_striped)
        parsed_sample = sample.build_data_particle(size = available_disk, disk_remaining = available_disk_percent,
                            image_remaining = images_remaining,
                            image_on_disk = images_on_disk)
        # if self._driver_event:
        #         self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)
        #########################

        return parsed_sample


#CAMDS meta data data particle
class CAMDS_IMAGE_METADATA_KEY(BaseEnum):
    """
    CAMDS image meta data keys
    """

    PAN_POSITION = "camds_pan_position"
    TILT_POSITION = "camds_tilt_position"
    FOCUS_POSITION = "camds_focus_position"
    ZOOM_POSITION = "camds_zoom_position"
    IRIS_POSITION = "camds_iris_position"
    GAIN = "camds_gain"
    RESOLUTION = "camds_resolution"
    BRIGHTNESS = "camds_brightness"

# Data particle for GC command
class CAMDS_IMAGE_METADATA(DataParticle):
    """
    CAMDS image data particle
    """
    _data_particle_type = DataParticleType.CAMDS_IMAGE_METADATA

    def _build_parsed_values(self):
        # Initialize
        pd = self._param_dict.get_all()

        result = []
        for key, value in self.raw_data.items():
            if key == KMLParameter.PAN_POSITION:
                result.append({DataParticleKey.VALUE_ID: "camds_pan_position",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.TILT_POSITION:
                result.append({DataParticleKey.VALUE_ID: "camds_tilt_position",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.FOCUS_POSITION:
                result.append({DataParticleKey.VALUE_ID: "camds_focus_position",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.ZOOM_POSITION:
                result.append({DataParticleKey.VALUE_ID: "camds_zoom_position",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.IRIS_POSITION:
                result.append({DataParticleKey.VALUE_ID: "camds_iris_position",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.CAMERA_GAIN:
                result.append({DataParticleKey.VALUE_ID: "camds_gain",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.IMAGE_RESOLUTION:
                result.append({DataParticleKey.VALUE_ID: "camds_resolution",
                           DataParticleKey.VALUE: value})
            elif key == KMLParameter.LAMP_BRIGHTNESS:
                result.append({DataParticleKey.VALUE_ID: "camds_brightness",
                           DataParticleKey.VALUE: value})

        return result
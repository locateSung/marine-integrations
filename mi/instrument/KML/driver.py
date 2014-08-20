"""
@package mi.instrument.KML.driver
@file marine-integrations/mi/instrument/KML/driver.py
@author Sung Ahn
@brief Driver for the KML family
Release notes:
"""
import struct
from mi.instrument.KML.particles import CAMDS_DISK_STATUS

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import re
import base64
import time
import functools

import sys
from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed

from mi.core.exceptions import InstrumentParameterException, NotImplementedException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException

from mi.core.log import get_logger
log = get_logger()
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver, DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.util import dict_equal


# default timeout.
TIMEOUT = 20

# newline.
NEWLINE = '\r\n'

DEFAULT_CMD_TIMEOUT = 20
DEFAULT_WRITE_DELAY = 0

ZERO_TIME_INTERVAL = '00:00:00'


class KMLPrompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '\r\n<::>'
    ACK = '\x06'
    NAK = '\x15'

class parameterIndex(BaseEnum):
    SET = 0
    GET = 1
    Start = 2
    LENGTH = 3
    DEFAULT_DATA = 4
    DISPLAY_NAME = 5
    DESCRIPTION = 6

class KMLParameter(DriverParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #
    """
    set <\x16:NT:\x05\x00\x00157.237.237.104\x00>
    Byte1 = Interval in second (5 seconds)
    Byte2 & 3 = 16 bit Integer Port Nr (if 0 use default port 123)
    Byte 4 to end = Server name in ASCII with \ 0 end of string
    Default is 5 seconds, 0 for port #123, server name = 157.237.237.104,
    ReadOnly

    get <\x03:GN:>
    GN + Variable number of bytes.
    Byte1 = Interval in seconds
    Byte2 & 3 = 16 bit Integer Port Nr
    Byte 4 to end = Server name in ASCII with \0 end of string

    """
    NTP_SETTING =('NT', '<\x03:GN:>', 1, 19, '\x05\x00\x00157.237.237.104\x00', 'NTP Setting',
                  'interval(in second), NTP port, NTP Server name' )

    """
    set <\x04:CL:\x00>
    variable number of bytes representing \0 terminated ASCII string.
    (\0 only) indicates files are saved in the default location on the camera

    get <\x03:FL:>
    Byte1 to end = Network location as an ASCII string with \0 end of string. Send only \0 character to set default
    """
    NETWORK_DRIVE_LOCATION = ('CL','<\x04:CL:\x00>', 1, None, '\x00',
                              'Network Drive Location','\x00 for local default location' )


    """
    set <\x04:RM:\x01>
    1 byte with value \x01 or \x02
    0x1 = Replace oldest image on the disk
    0x2 = return NAK (or stop capture) when disk is full.
    Default is 0x1 and it is ReadOnly :set <0x04:RM:0x01>

    get <0x03:GM:>
    GM + 1 byte with value 0x1 or 0x2 0x1 = Replace oldest image on the disk
    0x2 = return NAK (or stop capture) when disk is full.
    """
    WHEN_DISK_IS_FULL = ('RM', '<\x03:GM:>', 1, 1, '\x01', 'When Disk Is Full',
                         '0x1 = Replace oldest image on the disk, 0x2 = return ERROR when disk is full')

    """
    Camera Mode

    set <\x04:SV:\x09>
    1 byte:
    0x00 = None (off)
    0x09 = Stream
    0x0A = Framing
    0x0B = Focus
    Default is 0x09 <0x04:SV:0x09>

    get <0x03:GV:>
    GV + 1 byte:
    0x00 = None
    0x09 = Stream
    0x0A = Framing
    0x0B = Area of Interest
    """

    CAMERA_MODE = ('SV', '<\x03:GV:>', 1, 1, '\x09', 'Camera Mode',
                   '0x00 = None (off) 0x09 = Stream 0x0A = Framing 0x0B = Focus')

    """
    set <\x04:FR:\x1E>
    1 Byte with value between 1 and 30. If the requested frame rate cannot be achieved, the maximum rate will be used
    Default is 0x1E : set <0x04:FR:0x1E>

    get <0x03:GR:>
    GR + 1 Byte with value between 1 and 30.
    If the requested frame rate cannot be achieved, the maximum rate will be used.
    """
    FRAME_RATE = ('FR' '<\x03:GR:>', 1, 1, '\x1E', 'Frame Rate', 'From 1 to 30 frames/second')

    """
    set <\x04:SD:\x01>
    1 Byte with a dividing value of 0x1, 0x2, 0x4 and 0x8.
    0x1 = Full resolution
    0x2 = ½ Full resolution etc
    Default is 0x1 : set <0x04:SD:0x01>,

    get <0x03:GD:>
    GD + 1 Byte with a dividing value of 0x1, 0x2, 0x4 and 0x8.
    """
    IMAGE_RESOLUTION = ('SD', '<\x03:GD:>', 1, 1, '\x01',
                        'Image Resolution','0x1 = Full resolution, 0x2 = half Full resolution')

    """
    set <\x04:CD:\x64>
    1 Byte with value between 0x01 and 0x64. (decimal 1 - 100)
    0x64 = Minimum data loss
    0x01 = Maximum data loss
    Default is 0x64 : set <0x04:CD:0x64>

    get <0x03:GI:>
    GI + 1 Byte with value between 0x01 and 0x64. (decimal 1 - 100) 0x64 = Minimum data loss 0x01 = Maximum data loss
    """
    COMPRESSION_RATIO = ('CD', '<\x03:GI:>',1, 1, '\x64', 'Compression Ratio',
                         '0x64 = Minimum data loss, 0x01 = Maximum data loss')

    """
    set <\x05:ET:\xFF\xFF>
    2 bytes.
    Byte1 = Value (starting value)
    Byte2 = Exponent (Number of zeros to add)
    Default is 0xFF 0xFF (auto shutter mode) : set <0x05:ET:0xFF0xFF>

    get <0x03:EG:>
    EG + 2 bytes
    Byte1 = Value (starting value)
    Byte2 = Multiplier (Number of zeros to add)
    e.g.. If Byte1 = 25 and byte2 = 3 then exposure time will be 25000 Max value allowed is 60000000 microseconds
    (if both bytes are set to 0xFF, the camera is in auto shutter mode)
    """
    SHUTTER_SPEED = ('ET', '<\x03:EG:>', 1, 2, '\xFF\xFF', 'Shutter Speed',
                     'Byte1 = Value (starting value), Byte2 = Exponent (Number of zeros to add)')

    """
    get <\x04:GS:\xFF>
    byte Value 0x01 to 0x20 sets a static value and 0xFF sets auto gain.
    In automatic gain control, the camera will attempt to adjust the gain to give the optimal exposure.
    Default is 0xFF : set <\x04:GS:\xFF>

    get <0x03:GG:>
    GG + 1 byte
    Value 0x01 to 0x20 for a static value and 0xFF for auto GAIN
    """
    CAMERA_GAIN = ('GS', '<\x03:GG:>',1,1, '\xFF', 'Camera Gain','From 0x01 to 0x20 and 0xFF sets auto gain')

    """
    set <\x05:BF:\x03\x32>
    Byte 1 is lamp to control: 0x01 = Lamp1 0x02 = Lamp2 0x03 = Both Lamps
    Byte 2 is brightness between 0x00 and 0x64
    Default is 0x03 0x32

    set <0x03:PF:>
    PF + 2 bytes
    1st byte for lamp 1
    2nd byte for lamp 2. For each lamp, MSB indicates On/Off
    """
    LAMP_BRIGHTNESS = ('BF', '<0x03:PF:>', 1, 2, '\x03\x32','Lamp Brightness',
                       'Byte 1 is lamp to control: 0x01 = Lamp1 0x02 = Lamp2 0x03 = Both Lamps, Byte 2 is brightness between 0x00 and 0x64')

    """
    Set <\x04:FX:\x00>
    Set focus speed
    1 byte between 0x00 and 0x0F
    Default is 0x00 : set <\x04:FX:\x00>

    No get focus speed
    ???set <0x03:FP:>
    ???FP + 1 byte between \x00 and \xC8
    """
    FOCUS_SPEED = ('FX', None, 1, 1, '\x00', 'Focus Speed','between 0x00 and 0x0F')

    """
    set <\x04:ZX:\x00>
    Set zoom speed.
    1 byte between 0x00 and 0x0F
    Default is 0x00 : set <\x04:ZX:\x00>

    ???get <0x03:ZP:>
    ???ZP + 1 byte between 0x00 and 0xC8
    """
    ZOOM_SPEED = ('ZX', None, 1, 1, '\x00', 'Zoom Speed', 'between 0x00 and 0x0F')

    """
    Set <\x04:IG:\x08>
    Iris_Position
    1 byte between 0x00 and 0x0F
    default is 0x08 <0x04:IG:0x08>

    IP + 1 byte between 0x00
    get <0x03:IP>
    """
    IRIS_POSITION = ('IG', '<0x03:IP>', 1,1, '\x08', 'Iris Position', 'between 0x00 and 0x0F')

    """
    Zoom Position
    set <\x04:ZG:\x64>

    1 byte between 0x00 and 0xC8 (200 Zoom positions)
    Default value is <0x04:ZG:0x64>
    ZP + 1 byte between 0x00 and 0xC8
    get <0x03:ZP:>
    """
    ZOOM_POSITION = ('ZG', '<0x03:ZP:>', 1, 1, '\x64', 'Zoom Position', 'between 0x00 and 0xC8')

    """
    Pan Speed
    1 byte between 0x00 and 0x64
    Default is 0x32 : set <0x04:DS:0x32>

    ???? No get pan speed
    """
    PAN_SPEED = ('DS', None, None, None, '\x32', 'Pan Speed', 'between 0x00 and 0x64')

    """
    Set tilt speed
    1 byte between 0x00 and 0x64
    Default is 0x32 : <0x04:TA:0x32>
    """
    TILT_SPEED = ('TA', None, None, None, '\x32', 'TILT Speed','between 0x00 and 0x64')

    """
    Enable or disable the soft end stops of the pan and tilt device
    1 byte:0x00 = Disable 0x01 = Enable
    Default is 0x01 : <0x04:ES:0x01>

    get <0x03:AS:>
    AS + 7 bytes
    Byte1 = Tilt Position hundreds
    Byte2 = Tilt Position tens
    Byte3 = Tilt Position units
    Byte4 = Pan Position hundreds
    Byte5 = Pan Position tens Byte6 = Pan Position units
    Byte7 = End stops enable (0x1 = enabled, 0x0 = disabled)
    Bytes 1 to 6 are ASCII characters between 0x30 and 0x39
    """
    SOFT_END_STOPS = ('ES', '<0x03:AS:>', 7, 1, '\x01', 'Soft End Stops','0x00 = Disable 0x01 = Enable')

    """
    3 Bytes representing a three letter string containing the required pan location.
    Byte1 = Hundreds of degrees
    Byte2 = Tens of degrees
    Byte 3 = Units of degrees
    (e.g.. 90 = 0x30, 0x37, 0x35 or 360 = 0x33, 0x36, 0x30)
    Default is 90 degree : <0x06:PP:0x30 0x37 0x35>

    get <0x03:AS:>
    AS + 7 bytes
    Byte1 = Tilt Position hundreds
    Byte2 = Tilt Position tens
    Byte3 = Tilt Position units
    Byte4 = Pan Position hundreds
    Byte5 = Pan Position tens Byte6 = Pan Position units
    Byte7 = End stops enable (0x1 = enabled, 0x0 = disabled)
    Bytes 1 to 6 are ASCII characters between 0x30 and 0x39
    """
    PAN_POSITION = ('PP', '<0x03:AS:>', 4, 3,'\x30\x37\x35','Pan Position',
                    'Byte1 = Hundreds of degrees, Byte2 = Tens of degrees, Byte 3 = Units of degrees')

    """
    3 Bytes representing a three letter string containing the required tilt location.
    Byte1 = Hundreds of degrees
    Byte2 = Tens of degrees
    Byte 3 = Units of degrees
    (e.g.. 90 = 0x30, 0x37, 0x35 or 360 = 0x33, 0x36, 0x30)

    get <0x03:AS:>
    AS + 7 bytes
    Byte1 = Tilt Position hundreds
    Byte2 = Tilt Position tens
    Byte3 = Tilt Position units
    Byte4 = Pan Position hundreds
    Byte5 = Pan Position tens Byte6 = Pan Position units
    Byte6 = Pan Position Pan Position units
    Byte7 = End stops enable (0x1 = enabled, 0x0 = disabled)
    Bytes 1 to 6 are ASCII characters between 0x30 and 0x39
    """
    TILT_POSITION = ('TP', '<0x03:AS:>',1, 3, '\x30\x37\x35', 'Tilt Position',
                    'Byte1 = Hundreds of degrees, Byte2 = Tens of degrees, Byte 3 = Units of degrees')

    """
    set <\x04:FG:\x64>
    1 byte between 0x00 and 0xC8

    get <\x03:FP:>
    """
    FOCUS_POSITION = ('FG', '<\x03:FP:>', 1, 1, '\x64', 'Focus Position', 'between \x00 and \xC8')

    # Engineering parameters for the scheduled commands
    SAMPLE_INTERVAL = (None, None, None, None, '00:00:00', 'Sample Interval', 'hh:mm:ss, 00:00:00 will turn off the schedule')
    ACQUIRE_STATUS_INTERVAL = (None, None, None, None, '00:00:00', 'Acquire Status Interval', 'hh:mm:ss, 00:00:00 will turn off the schedule')
    VIDEO_FORWARDING = (None, None, None, None, False, 'Video Forwarding Flag',
                        'True - Turn on Video, False - Turn off video')
    VIDEO_FORWARDING_TIMEOUT = (None, None, None, None, '00:00:00', 'video forwarding timeout',
                                'hh:mm:ss, 00:00:00 means No timeout')
    PRESET_NUMBER = (None, None, None, None, 1,'Preset number', 'preset number (1- 15)' )
    AUTO_CAPTURE_DURATION = (None, None, None, None, '3', 'Auto Capture Duration','1 to 5 Seconds')



class KMLInstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """

    START_CAPTURE = 'SP'
    STOP_CAPTURE = 'SR'

    TAKE_SNAPSHOT = 'CI'

    START_FOCUS_NEAR = 'FN'
    START_FOCUS_FAR = 'FF'
    STOP_FOCUS = 'FS'

    START_ZOOM_OUT = 'ZW'
    START_ZOOM_IN = 'ZT'
    STOP_ZOOM ='ZS'

    INCREASE_IRIS = 'II'
    DECREASE_IRIS = 'ID'

    START_PAN_LEFT = 'PL'
    START_PAN_RIGHT = 'PR'
    STOP_PAN = 'PS'

    START_TILT_UP = 'TU'
    START_TILT_DOWN = 'TD'
    STOP_TILT = 'TS'

    GO_TO_PRESET = 'XG'

    TILE_UP_SOFT = 'UT'
    TILE_DOWN_SOFT = 'DT'
    PAN_LEFT_SOFT = 'AW'
    PAN_RIGHT_SOFT = 'CW'
    SET_PRESET = 'XS'

    LAMP_ON = 'OF'
    LAMP_OFF = 'NF'

    LASER_ON = 'OL'
    LASER_OFF = 'NL'

    GET_DISK_USAGE = 'GC'
    HEALTH_REQUEST  = 'HS'

    GET = 'get'
    SET = 'set'

class CAMDSProtocolState(DriverProtocolState):
    """
    Base states for driver protocols. Subclassed for specific driver
    protocols.
    """

    #CAPTURE = 'DRIVER_STATE_CAPTURE'


class KMLProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = CAMDSProtocolState.UNKNOWN
    COMMAND = CAMDSProtocolState.COMMAND
    AUTOSAMPLE = CAMDSProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = CAMDSProtocolState.DIRECT_ACCESS


class KMLProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    INIT_PARAMS = DriverEvent.INIT_PARAMS
    DISCOVER = DriverEvent.DISCOVER

    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT

    GET = DriverEvent.GET
    SET = DriverEvent.SET

    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT

    PING_DRIVER = DriverEvent.PING_DRIVER

    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE

    LASER_1_ON = "DRIVER_EVENT_LASER_1_ON"
    LASER_2_ON = "DRIVER_EVENT_LASER_2_ON"
    LASER_BOTH_ON = "DRIVER_EVENT_LASER_BOTH_ON"
    LASER_1_OFF = "DRIVER_EVENT_LASER_1_OFF"
    LASER_2_OFF = "DRIVER_EVENT_LASER_2_OFF"
    LASER_BOTH_OFF = "DRIVER_EVENT_LASER_BOTH_OFF"

    LAMP_ON = "DRIVER_EVENT_LAMP_ON"
    LAMP_OFF = "DRIVER_EVENT_LAMP_OFF"
    SET_PRESET =  "DRIVER_EVENT_SET_PRESET"
    GOTO_PRESET = "DRIVER_EVENT_GOTO_PRESET"

    START_CAPTURING = 'DRIVER_EVENT_STARP_CAPTURE'
    STOP_CAPTURING = 'DRIVER_EVENT_STOP_CAPTURE'


class KMLCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

    ACQUIRE_STATUS = KMLProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_SAMPLE = KMLProtocolEvent.ACQUIRE_SAMPLE

    STOP_CAPTURE = KMLProtocolEvent.STOP_CAPTURING
    START_CAPTURE = KMLProtocolEvent.START_CAPTURING

    LASER_1_ON = KMLProtocolEvent.LASER_1_ON
    LASER_2_ON = KMLProtocolEvent.LASER_2_ON
    LASER_BOTH_ON = KMLProtocolEvent.LASER_BOTH_ON
    LASER_1_OFF = KMLProtocolEvent.LASER_1_OFF
    LASER_2_OFF = KMLProtocolEvent.LASER_2_OFF
    LASER_BOTH_OFF = KMLProtocolEvent.LASER_BOTH_OFF

    LAMP_ON = KMLProtocolEvent.LAMP_ON
    LAMP_OFF = KMLProtocolEvent.LAMP_OFF

    SET_PRESET = KMLProtocolEvent.SET_PRESET
    GOTO_PRESET = KMLProtocolEvent.GOTO_PRESET


class KMLScheduledJob(BaseEnum):
    SAMPLE = 'sample'
    VIDEO_FORWARDING = "video forwarding"
    STATUS = "status"
    STOP_CAPTURE = "stop capturing"


class KMLInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver Family SubClass
    """

    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        # Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
                                         DriverEvent.DISCOVER,
                                         self._handler_connected_discover)

    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params
        # when we discover. Gotta get into command mode first though.
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        self.apply_startup_params()
        return result


# noinspection PyMethodMayBeStatic
class KMLProtocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol Family SubClass
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        self.last_wakeup = 0
        self.video_fowarding_flag = False

        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        self.last_wakeup = 0

        # Build ADCPT protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(KMLProtocolState, KMLProtocolEvent,
                                           KMLProtocolEvent.ENTER, KMLProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(KMLProtocolState.UNKNOWN, KMLProtocolEvent.ENTER,
                                       self._handler_unknown_enter)
        self._protocol_fsm.add_handler(KMLProtocolState.UNKNOWN, KMLProtocolEvent.EXIT,
                                       self._handler_unknown_exit)
        self._protocol_fsm.add_handler(KMLProtocolState.UNKNOWN, KMLProtocolEvent.DISCOVER,
                                       self._handler_unknown_discover)

        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.ENTER,
                                       self._handler_command_enter)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.EXIT,
                                       self._handler_command_exit)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.INIT_PARAMS,
                                       self._handler_command_init_params)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.GET,
                                       self._handler_get)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.SET,
                                       self._handler_command_set)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)

        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LAMP_ON,
                                       self._handler_command_lamp_on)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LAMP_OFF,
                                       self._handler_command_lamp_off)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LASER_1_ON,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_ON, '\x01'))
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LASER_2_ON,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_ON, '\x02'))
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LASER_BOTH_ON,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_ON, '\x03'))
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LASER_1_OFF,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_OFF, '\x01'))
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LASER_2_OFF,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_OFF, '\x02'))
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.LASER_BOTH_OFF,
                                      self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_OFF, '\x03'))
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.SET_PRESET,
                                       self._handler_command_set_preset)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.GOTO_PRESET,
                                       self._handler_command_goto_preset)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.START_CAPTURING,
                                       self._handler_command_start_capture)
        self._protocol_fsm.add_handler(KMLProtocolState.COMMAND, KMLProtocolEvent.STOP_CAPTURING,
                                       self._handler_command_stop_capture)

        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.ENTER,
                                       self._handler_autosample_enter)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.EXIT,
                                       self._handler_autosample_exit)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.INIT_PARAMS,
                                       self._handler_autosample_init_params)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.GET,
                                       self._handler_get)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.SET,
                                       self._handler_command_set)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LAMP_ON,
                                       self._handler_command_lamp_on)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LAMP_OFF,
                                       self._handler_command_lamp_off)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LASER_1_ON,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_ON, '\x01'))
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LASER_2_ON,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_ON, '\x02'))
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LASER_BOTH_ON,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_ON, '\x03'))
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LASER_1_OFF,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_OFF, '\x01'))
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LASER_2_OFF,
                                       self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_OFF, '\x02'))
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.LASER_BOTH_OFF,
                                      self._handler_command_laser_wrapper(KMLInstrumentCmds.LASER_OFF, '\x03'))
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.SET_PRESET,
                                       self._handler_command_set_preset)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.GOTO_PRESET,
                                       self._handler_command_goto_preset)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.START_CAPTURING,
                                       self._handler_command_start_capture)
        self._protocol_fsm.add_handler(KMLProtocolState.AUTOSAMPLE, KMLProtocolEvent.STOP_CAPTURING,
                                       self._handler_command_stop_capture)

        self._protocol_fsm.add_handler(KMLProtocolState.DIRECT_ACCESS, KMLProtocolEvent.ENTER,
                                       self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(KMLProtocolState.DIRECT_ACCESS, KMLProtocolEvent.EXIT,
                                       self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(KMLProtocolState.DIRECT_ACCESS, KMLProtocolEvent.EXECUTE_DIRECT,
                                       self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(KMLProtocolState.DIRECT_ACCESS, KMLProtocolEvent.STOP_DIRECT,
                                       self._handler_direct_access_stop_direct)

        # Build dictionaries for driver schema
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        ##################

        ##########
        # Add build handlers for device commands.

        self._add_build_handler(KMLInstrumentCmds.SET, self._build_set_command)
        self._add_build_handler(KMLInstrumentCmds.GET, self._build_get_command)

        self._add_build_handler(KMLInstrumentCmds.START_CAPTURE, self.build_start_capture_command)
        self._add_build_handler(KMLInstrumentCmds.STOP_CAPTURE, self.build_stop_capture_command)

        self._add_build_handler(KMLInstrumentCmds.TAKE_SNAPSHOT, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.START_FOCUS_NEAR, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.START_FOCUS_FAR, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.STOP_FOCUS, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.START_ZOOM_OUT, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.START_ZOOM_IN, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.STOP_ZOOM, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.INCREASE_IRIS, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.DECREASE_IRIS, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.GO_TO_PRESET, self.build_preset_command)
        self._add_build_handler(KMLInstrumentCmds.SET_PRESET, self.build_preset_command)

        self._add_build_handler(KMLInstrumentCmds.START_PAN_LEFT, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.START_PAN_RIGHT, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.STOP_PAN, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.START_TILT_UP, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.START_TILT_DOWN, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.STOP_TILT, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.TILE_UP_SOFT, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.TILE_DOWN_SOFT, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.PAN_LEFT_SOFT, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.PAN_RIGHT_SOFT, self.build_simple_command)

        self._add_build_handler(KMLInstrumentCmds.LAMP_ON, self.build_lamp_command)
        self._add_build_handler(KMLInstrumentCmds.LAMP_OFF, self.build_lamp_command)

        self._add_build_handler(KMLInstrumentCmds.LASER_ON, self.build_lamp_command)
        self._add_build_handler(KMLInstrumentCmds.LASER_OFF, self.build_lamp_command)

        self._add_build_handler(KMLInstrumentCmds.GET_DISK_USAGE, self.build_simple_command)
        self._add_build_handler(KMLInstrumentCmds.HEALTH_REQUEST, self.build_simple_command)

        # add response_handlers
        self._add_response_handler(KMLInstrumentCmds.SET, self._parse_set_response)
        self._add_response_handler(KMLInstrumentCmds.GET, self._parse_get_response)

        self._add_response_handler(KMLInstrumentCmds.SET_PRESET, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.GO_TO_PRESET, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.LAMP_OFF, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.LAMP_ON, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.LASER_OFF, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.LASER_ON, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.PAN_LEFT_SOFT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.PAN_RIGHT_SOFT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.DECREASE_IRIS, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_CAPTURE, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_FOCUS_FAR, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_FOCUS_NEAR, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_PAN_RIGHT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_PAN_LEFT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_TILT_DOWN, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_TILT_UP, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.TILE_UP_SOFT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.TILE_DOWN_SOFT, self._parse_simple_response)

        #Generate data particle
        self._add_response_handler(KMLInstrumentCmds.GET_DISK_USAGE, self._parse_simple_response)

        #Generate data particle
        self._add_response_handler(KMLInstrumentCmds.HEALTH_REQUEST, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_ZOOM_IN, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.START_ZOOM_OUT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.INCREASE_IRIS, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.TAKE_SNAPSHOT, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.STOP_ZOOM, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.STOP_CAPTURE, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.STOP_FOCUS, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.STOP_PAN, self._parse_simple_response)
        self._add_response_handler(KMLInstrumentCmds.STOP_TILT, self._parse_simple_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(KMLProtocolState.UNKNOWN)

        # commands sent sent to device to be
        # filtered in responses for telnet DA
        self._sent_cmds = []

        self.disable_autosample_recover = False

    def build_simple_command(self, cmd, *args):
        self.build_camds_3byte_command(self, cmd, *args)

    def build_camds_3byte_command(self, cmd, *args):
        """
        Builder for 3-byte CAMDS commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument
        """

        return "<\x03:%s:>" % cmd


    def build_camds_4byte_command(self, cmd, *args):
        """
        Builder for 4-byte CAMDS commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument
        """
        data = struct.pack('!b', args[0])
        return "<\x04:%s:%s>" % (cmd, data)

    def build_camds_5byte_command(self, cmd, *args):
        """
        Builder for 5-byte CAMDS commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument
        """
        data1 = struct.pack('!b', args[0])
        data2 = struct.pack('!b', args[1])
        return "<\x05:%s:%s%s>" % (cmd, data1, data2)

    def stop_scheduled_job(self, schedule_job):
        """
        Remove the scheduled job
        @param schedule_job scheduling job.
        """
        log.debug("Attempting to remove the scheduler")
        if self._scheduler is not None:
            try:
                self._remove_scheduler(schedule_job)
                log.debug("successfully removed scheduler")
            except KeyError:
                log.debug("_remove_scheduler could not find %s", schedule_job)

    def start_scheduled_job(self, param, schedule_job, protocol_event):
        """
        Add a scheduled job
        """
        self.stop_scheduled_job(schedule_job)

        interval = self._param_dict.get(param).split(':')
        hours = interval[0]
        minutes = interval[1]
        seconds = interval[2]
        log.debug("Setting scheduled interval to: %s %s %s", hours, minutes, seconds)

        if hours == '00' and minutes == '00' and seconds == '00':
            # if interval is all zeroed, then stop scheduling jobs
            self.stop_scheduled_job(schedule_job)
        else:
            config = {DriverConfigKey.SCHEDULER: {
                schedule_job: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.HOURS: int(hours),
                        DriverSchedulerConfigKey.MINUTES: int(minutes),
                        DriverSchedulerConfigKey.SECONDS: int(seconds)
                    }
                }
            }
            }
            self.set_init_params(config)
            self._add_scheduler_event(schedule_job, protocol_event)

    def _build_param_dict(self):
        """
        It will be implemented in its child
        @throw NotImplementedException
        """
        raise NotImplementedException('Not implemented.')

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if KMLCapability.has(x)]

    # #######################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @throws: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        if (self.get_current_state() != KMLProtocolState.COMMAND and
                    self.get_current_state() != KMLProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.

        if not self._instrument_config_dirty():
            return True

        error = None

        try:
            self._apply_params()

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION WAS " + str(e))
            error = e

        if error:
            raise error

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @throws: InstrumentProtocolException if in wrong mode.
        """
        log.debug("IN _apply_params")
        config = self.get_startup_config()
        # Pass true to _set_params so we know these are startup values
        self._set_params(config, True)

    def _get_params(self):
        return dir(KMLParameter)

    def _getattr_key(self, attr):
        return getattr(KMLParameter, attr)

    def _has_parameter(self, param):
        return KMLParameter.has(param)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """
        log.debug("in _update_params")
        error = None
        results = None

        try:
            # Get old param dict config.
            old_config = self._param_dict.get_config()
            kwargs['expected_prompt'] = KMLPrompt.COMMAND
            cmds = self._get_params()
            results = ""
            for attr in sorted(cmds):
                if attr not in [ KMLParameter.SAMPLE_INTERVAL, KMLParameter.VIDEO_FORWARDING_TIMEOUT,
                                 KMLParameter.ACQUIRE_STATUS_INTERVAL, KMLParameter.AUTO_CAPTURE_DURATION,
                                 KMLParameter.VIDEO_FORWARDING, KMLParameter.PRESET_NUMBER]:
                    key = self._getattr_key(attr)
                    result = self._do_cmd_resp(KMLInstrumentCmds.GET, key, **kwargs)
                    results += result + NEWLINE

            new_config = self._param_dict.get_config()

            if not dict_equal(new_config, old_config):
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION in _update_params WAS " + str(e))
            error = e

        if error:
            raise error

        return results

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        log.trace("in _set_params")
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        result = None
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        log.trace("_set_params calling _verify_not_readonly ARGS = " + repr(args))
        self._verify_not_readonly(*args, **kwargs)
        for key, val in params.iteritems():
            if key not in [ KMLParameter.SAMPLE_INTERVAL,KMLParameter.VIDEO_FORWARDING_TIMEOUT,
                                 KMLParameter.ACQUIRE_STATUS_INTERVAL, KMLParameter.AUTO_CAPTURE_DURATION,
                                 KMLParameter.VIDEO_FORWARDING, KMLParameter.PRESET_NUMBER]:
                result = self._do_cmd_resp(KMLInstrumentCmds.SET, key, val, **kwargs)
        log.trace("_set_params calling _update_params")
        self._update_params()
        return result

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @throws: InstrumentParameterException
        """
        log.trace("in _instrument_config_dirty")
        # Refresh the param dict cache
        #self._update_params()

        startup_params = self._param_dict.get_startup_list()
        log.trace("Startup Parameters: %s" % startup_params)

        for param in startup_params:
            if not self._has_parameter(param):
                raise InstrumentParameterException("A param is unknown")

            if self._param_dict.get(param) != self._param_dict.get_config_value(param):
                log.trace("DIRTY: %s %s != %s" % (
                    param, self._param_dict.get(param), self._param_dict.get_config_value(param)))
                return True

        log.trace("Clean instrument config")
        return False

    def _sanitize(self, s):
        s = s.replace('\xb3', '_')
        s = s.replace('\xbf', '_')
        s = s.replace('\xc0', '_')
        s = s.replace('\xd9', '_')
        s = s.replace('\xda', '_')
        s = s.replace('\xf8', '_')

        return s

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to initialize parameters and send a config change event.
        self._protocol_fsm.on_event(KMLProtocolEvent.INIT_PARAMS)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self.stop_scheduled_job(KMLScheduledJob.SAMPLE)

        status_interval = self._param_dict.get(KMLParameter.ACQUIRE_STATUS_INTERVAL)
        if status_interval != ZERO_TIME_INTERVAL:
            self.start_scheduled_job(KMLParameter.ACQUIRE_STATUS_INTERVAL, KMLScheduledJob.STATUS,
                                     KMLProtocolEvent.ACQUIRE_STATUS)

        # start scheduled event for get_status only if the interval is not "00:00:00
        self.video_fowarding_flag = self._param_dict.get(KMLParameter.VIDEO_FORWARDING)
        #if(self.video_fowarding_flag):
        #    # todo : Start video forwarding

        self.forwarding_time = self._param_dict.get(KMLParameter.VIDEO_FORWARDING_TIMEOUT)


    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        self.stop_scheduled_job(KMLScheduledJob.STOP_CAPTURE)
        self.stop_scheduled_job(KMLScheduledJob.STATUS)
        self.stop_scheduled_job(KMLScheduledJob.STOP_CAPTURE)

        pass

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """

    ######################################################
    #                                                    #
    ######################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @return protocol_state, agent_state if successful
        """
        protocol_state, agent_state = self._discover()
        if protocol_state == KMLProtocolState.COMMAND:
            agent_state = ResourceAgentState.IDLE

        return protocol_state, agent_state

    ######################################################
    #                                                    #
    ######################################################
    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        next_state = None
        result = None

        self._init_params()
        return next_state, result

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        self._protocol_fsm.on_event(KMLProtocolEvent.INIT_PARAMS)
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # start scheduled event for Sampling only if the interval is not "00:00:00
        sample_interval = self._param_dict.get(KMLParameter.SAMPLE_INTERVAL)
        if sample_interval != ZERO_TIME_INTERVAL:
            self.start_scheduled_job(KMLParameter.SAMPLE_INTERVAL, KMLScheduledJob.SAMPLE,
                                     KMLProtocolEvent.ACQUIRE_SAMPLE)


    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """

    def _handler_autosample_init_params(self, *args, **kwargs):
        """
        initialize parameters.  For this instrument we need to
        put the instrument into command mode, apply the changes
        then put it back.
        """
        log.debug("in _handler_autosample_init_params")
        next_state = None
        result = None
        error = None

        try:
            log.debug("stopping logging without checking")
            self._init_params()

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        if error:
            log.error("Error in apply_startup_params: %s", error)
            raise error

        return next_state, result

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @return next_state, (next_agent_state, result) if successful.
        """
        result = None
        kwargs['expected_prompt'] = KMLPrompt.COMMAND
        kwargs['timeout'] = 30

        # start scheduled event for Sampling only if the interval is not "00:00:00
        sample_interval = self._param_dict.get(KMLParameter.SAMPLE_INTERVAL)
        if sample_interval != ZERO_TIME_INTERVAL:
            self.start_scheduled_job(KMLParameter.SAMPLE_INTERVAL, KMLScheduledJob.SAMPLE,
                                     KMLProtocolEvent.ACQUIRE_STATUS)

        next_state = KMLProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return next_state, (next_agent_state, result)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @return  next_state, (next_agent_state, result) if successful.
        incorrect prompt received.
        """
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = KMLProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self.stop_scheduled_job(KMLScheduledJob.SAMPLE)

        return next_state, (next_agent_state, result)

    def _handler_autosample_get_calibration(self, *args, **kwargs):
        """
        execute a get calibration from autosample mode.  
        For this command we have to move the instrument
        into command mode, get calibration, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @return (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        output = ""
        error = None

        try:
            # Switch to command mode,
            kwargs['timeout'] = 120
            output = self._do_cmd_resp(KMLInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        if error:
            raise error

        result = self._sanitize(base64.b64decode(output))
        return next_state, (next_agent_state, result)

    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        execute a get configuration from autosample mode.  
        For this command we have to move the instrument
        into command mode, get configuration, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @return (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        output = ""
        error = None

        try:
            # Sync the clock
            output = self._do_cmd_resp(KMLInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        if error:
            raise error

        result = self._sanitize(base64.b64decode(output))

        return next_state, (next_agent_state, result)

    def _handler_recover_autosample(self, *args, **kwargs):
        """
        Reenter autosample mode.  Used when our data handler detects
        as data sample.
        @return next_state, next_agent_state
        """
        next_state = KMLProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        self._async_agent_state_change(ResourceAgentState.STREAMING)

        return next_state, next_agent_state

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @return (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if parameter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        log.trace("IN _handler_command_set")
        next_state = None
        startup = False
        changed = False

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.

        # Handle engineering parameters
        if KMLParameter.SAMPLE_INTERVAL in params:
            if (params[KMLParameter.SAMPLE_INTERVAL] != self._param_dict.get(
                    KMLParameter.SAMPLE_INTERVAL)):
                self._param_dict.set_value(KMLParameter.SAMPLE_INTERVAL,
                                           params[KMLParameter.SAMPLE_INTERVAL])
                changed = True

        if KMLParameter.ACQUIRE_STATUS_INTERVAL in params:
            if (params[KMLParameter.ACQUIRE_STATUS_INTERVAL] != self._param_dict.get(
                    KMLParameter.ACQUIRE_STATUS_INTERVAL)):
                self._param_dict.set_value(KMLParameter.ACQUIRE_STATUS_INTERVAL,
                                           params[KMLParameter.ACQUIRE_STATUS_INTERVAL])
                changed = True

        if KMLParameter.VIDEO_FORWARDING_TIMEOUT in params:
            if (params[KMLParameter.VIDEO_FORWARDING_TIMEOUT] != self._param_dict.get(
                    KMLParameter.VIDEO_FORWARDING_TIMEOUT)):
                self._param_dict.set_value(KMLParameter.VIDEO_FORWARDING_TIMEOUT,
                                           params[KMLParameter.VIDEO_FORWARDING_TIMEOUT])
                changed = True

        if KMLParameter.VIDEO_FORWARDING in params:
            if (params[KMLParameter.VIDEO_FORWARDING] != self._param_dict.get(
                    KMLParameter.VIDEO_FORWARDING)):
                self._param_dict.set_value(KMLParameter.VIDEO_FORWARDING,
                                           params[KMLParameter.VIDEO_FORWARDING])
                changed = True

        if KMLParameter.AUTO_CAPTURE_DURATION in params:
            if (params[KMLParameter.AUTO_CAPTURE_DURATION] != self._param_dict.get(
                    KMLParameter.AUTO_CAPTURE_DURATION)):
                self._param_dict.set_value(KMLParameter.AUTO_CAPTURE_DURATION,
                                           params[KMLParameter.AUTO_CAPTURE_DURATION])
                changed = True

        if KMLParameter.PRESET_NUMBER in params:
            if (params[KMLParameter.PRESET_NUMBER] != self._param_dict.get(
                    KMLParameter.PRESET_NUMBER)):
                self._param_dict.set_value(KMLParameter.PRESET_NUMBER,
                                           params[KMLParameter.PRESET_NUMBER])
                changed = True

        if changed:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        result = self._set_params(params, startup)

        return next_state, result

    def _handler_command_start_direct(self, *args, **kwargs):
        result = None

        next_state = KMLProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        return next_state, (next_agent_state, result)

    def _handler_capture_start(self, *args, **kwargs):
        result = None

        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = KMLPrompt.COMMAND
        result = self._do_cmd_resp(KMLInstrumentCmds.START_CAPTURE, *args, **kwargs)

        next_state = KMLProtocolState.CAPTURE
        next_agent_state = ResourceAgentState.STREAMING
        return next_state, (next_agent_state, result)

    def _handler_capture_stop(self, *args, **kwargs):
        """
        @reval next_state, (next_agent_state, result)
        """

        result = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = KMLPrompt.COMMAND
        result = self._do_cmd_resp(KMLInstrumentCmds.STOP_CAPTURE, *args, **kwargs)

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)

        (next_state, next_agent_state) = self._discover()

        return next_state, (next_agent_state, result)

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """

    def _handler_capture_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_capture_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """

    def _handler_direct_access_execute_direct(self, data):
        next_state = None
        result = None
        next_agent_state = None
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return next_state, (next_agent_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        try:
            self._do_cmd_resp(KMLInstrumentCmds.TAKE_SNAPSHOT, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        # After taking snapshot, the driver need to generate metadata
        time.sleep(.5)


        return next_state, (None, None)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        # Execute the following commands
        #  GET_DISK_USAGE = 'GC'
        #  HEALTH_REQUEST  = 'HS'
        try:
            self._do_cmd_resp(KMLInstrumentCmds.GET_DISK_USAGE, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        time.sleep(.5)
        try:
            self._do_cmd_resp(KMLInstrumentCmds.HEALTH_REQUEST, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))


        return next_state, (None, None)

    def _handler_command_lamp_on(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        try:
            self._do_cmd_resp(KMLInstrumentCmds.LAMP_ON, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        return next_state, (None, None)

    def _handler_command_lamp_off(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        try:
            self._do_cmd_resp(KMLInstrumentCmds.LAMP_OFF, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        return next_state, (None, None)

    def _handler_command_laser_wrapper(self, command, light):

        def _handler_command_laser(self, *args, **kwargs):
            """
            Take a snapshot
            """
            log.debug("IN _handler_command_acquire_status")
            next_state = None

            kwargs['timeout'] = 2
            kwargs['expected_prompt'] = KMLPrompt.COMMAND

            try:
                self._do_cmd_resp(command, light, *args, **kwargs)

            except Exception as e:
                raise InstrumentParameterException(
                    'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

            return next_state, (None, None)

        return _handler_command_laser

    def _handler_command_set_preset(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        # Execute the following commands
        #  GET_DISK_USAGE = 'GC'
        #  HEALTH_REQUEST  = 'HS'
        pd = self._param_dict.get_all()

        result = []
        presetNumber = 1
        for key, value in self.raw_data.items():
            if key == KMLParameter.PRESET_NUMBER:
                presetNumber = value

        try:
            self._do_cmd_resp(KMLInstrumentCmds.SET_PRESET, presetNumber, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        return next_state, (None, None)

    def _handler_command_start_capture (self, *args, **kwargs):

        log.debug("IN _handler_command_start_capture")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        capturing_duration = self._param_dict.get(KMLParameter.AUTO_CAPTURE_DURATION)

        if capturing_duration != ZERO_TIME_INTERVAL:
            self.start_scheduled_job(KMLParameter.AUTO_CAPTURE_DURATION, KMLScheduledJob.STOP_CAPTURE,
                                     KMLProtocolEvent.STOP_CAPTURING)

        try:
            self._do_cmd_resp(KMLInstrumentCmds.START_CAPTURE, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        # update VIDEO_FORWARDING flag and update the change to the upstream
        self._param_dict.set_value(KMLParameter.VIDEO_FORWARDING, True)
        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        self.video_fowarding_flag = True

    def _handler_command_stop_capture (self, *args, **kwargs):

        log.debug("IN _handler_command_stop_capture")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        self.stop_scheduled_job(KMLScheduledJob.STOP_CAPTURE)

        try:
            self._do_cmd_resp(KMLInstrumentCmds.STOP_CAPTURE, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        # update VIDEO_FORWARDING flag and update the change to the upstream
        self._param_dict.set_value(KMLParameter.VIDEO_FORWARDING, False)
        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        self.video_fowarding_flag = False


    def _handler_command_goto_preset(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        # Execute the following commands
        #  GET_DISK_USAGE = 'GC'
        #  HEALTH_REQUEST  = 'HS'
        pd = self._param_dict.get_all()

        result = []
        presetNumber = 1
        for key, value in self.raw_data.items():
            if key == KMLParameter.PRESET_NUMBER:
                presetNumber = value

        try:
            self._do_cmd_resp(KMLInstrumentCmds.GO_TO_PRESET, presetNumber, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        return next_state, (None, None)

    def _handler_command_acquire_statusXXXX(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        # Execute the following commands
        #  GET_DISK_USAGE = 'GC'
        #  HEALTH_REQUEST  = 'HS'
        try:
            self._do_cmd_resp(KMLInstrumentCmds.GET_DISK_USAGE, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        time.sleep(.5)
        try:
            self._do_cmd_resp(KMLInstrumentCmds.HEALTH_REQUEST, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))


        return next_state, (None, None)

    def _handler_command_acquire_statusXXXX(self, *args, **kwargs):
        """
        Take a snapshot
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 2
        kwargs['expected_prompt'] = KMLPrompt.COMMAND

        # Execute the following commands
        #  GET_DISK_USAGE = 'GC'
        #  HEALTH_REQUEST  = 'HS'
        try:
            self._do_cmd_resp(KMLInstrumentCmds.GET_DISK_USAGE, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        time.sleep(.5)
        try:
            self._do_cmd_resp(KMLInstrumentCmds.HEALTH_REQUEST, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))


        return next_state, (None, None)

    def _discover(self):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE or UNKNOWN.
        @return (next_protocol_state, next_agent_state)
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        if self._scheduler is not None:
            return KMLProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING
        return KMLProtocolState.COMMAND, ResourceAgentState.COMMAND

    def _handler_direct_access_stop_direct(self):
        """
        @reval next_state, (next_agent_state, result)
        """
        result = None
        (next_state, next_agent_state) = self._discover()

        return next_state, (next_agent_state, result)

    def _handler_command_restore_factory_params(self):
        """
        """

    def _get_response(self, response):
        #<size:command:data>
        #throw InstrumentProtocolException

        # make sure that the response is right format
        if '<' in response:
            if response[0] == '<':
                if response[len(response)-1] == '>':
                    if ':' in response:
                        response.replace('<','')
                        response.replace('>','')
                        return response.split(':')
        # Not valid response
        raise InstrumentProtocolException('Not valid instrument response %s' % response)

    def _parse_get_disk_usage_response(self, response, prompt):
        #TODO generate data particle

        resopnse_striped = '%r' % response.strip()
        #check the size of the response
        if len(resopnse_striped) != 12:
            raise InstrumentParameterException('Size of the get_disk_usage is not 12 ' + self.get_param
                                               + '  ' + resopnse_striped + ' ' + self.get_cmd)
        if resopnse_striped[0] != '<':
            raise InstrumentParameterException('Failed to cmd a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped + ' ' + self.get_cmd)
        if resopnse_striped[len(resopnse_striped) -1] != '>':
            raise InstrumentParameterException('Failed to cmd a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped + ' ' + self.get_cmd)
        if resopnse_striped[3] == KMLPrompt.NAK:
            raise InstrumentProtocolException(
                'Protocol._parse_set_response : Set command not recognized: %s' + resopnse_striped,
                + ' : ' + self.get_param + ' :' +  self.CAMDS_failure_message(resopnse_striped[5]))

    def _build_get_command(self, cmd, param, **kwargs):
        """
        param=val followed by newline.
        @param cmd get command
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The get command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        kwargs['expected_prompt'] = KMLPrompt.COMMAND
        # try:
        self.get_param = param
        self.get_cmd = cmd
        #     get_cmd = param + '?' + NEWLINE
        # except KeyError:
        #     raise InstrumentParameterException('Unknown driver parameter.. %s' % param)

        return param[parameterIndex.GET]

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        self.get_param = param
        self.get_cmd = cmd

        try:
            # str_val = self._param_dict.format(param, val)
            # # TODO replace the value set in the set command

            data_size = len(val) + 3
            set_cmd = '<%s:%s:%s>' % (data_size, param[parameterIndex.SET], val)
            log.trace("IN _build_set_command CMD = '%s'", set_cmd)
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter. %s' % param)

        return set_cmd

    def build_start_capture_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        #self.get_param = param
        self.get_cmd = cmd

        command = '<\x03:%s:>' % cmd
        return command

    def build_stop_capture_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        #self.get_param = param
        self.get_cmd = cmd

        command = '<\x03:%s:>' % cmd
        return command

    def build_simple_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        #self.get_param = param
        self.get_cmd = cmd

        command = '<\x03:%s:>' % cmd
        return command

    def build_lamp_command(self, cmd, data, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        #self.get_param = param
        self.get_cmd = cmd

        command = '<\x03:%s:%s>' % (cmd, data)
        return command

    def build_preset_command(self, cmd, data, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        #self.get_param = param
        self.get_cmd = cmd

        command = '<\x03:%s:%s>' % (cmd, data)
        return command


    def _parse_set_response(self, response, prompt):

        log.trace("SET RESPONSE = " + repr(response))

        #Make sure the response is the right format
        resopnse_striped = '%r' % response.strip()
        if resopnse_striped[0] != '<':
            raise InstrumentParameterException('Failed to set a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped)
        if resopnse_striped[len(resopnse_striped) -1] != '>':
            raise InstrumentParameterException('Failed to set a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped)
        if resopnse_striped[3] == KMLPrompt.NAK:
            raise InstrumentProtocolException(
                'Protocol._parse_set_response : Set command not recognized: %s' + resopnse_striped,
                + ' : ' + self.get_param + ' :' +  self.CAMDS_failure_message(resopnse_striped[5]))

        #self.get_count = 0
        return response

    def _parse_get_response(self, response, prompt):
        log.trace("GET RESPONSE = " + repr(response))

        #Make sure the response is the right format
        resopnse_striped = '%r' % response.strip()
        if resopnse_striped[0] != '<':
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped)
        if resopnse_striped[len(resopnse_striped) -1] != '>':
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped)
        if resopnse_striped[3] == KMLPrompt.NAK:
            raise InstrumentProtocolException(
                'Protocol._parse_set_response : get command not recognized: %s' + resopnse_striped,
                + ' : ' + self.get_param + ' :' +  self.CAMDS_failure_message(resopnse_striped[5]))

        if resopnse_striped[3] == KMLPrompt.ACK:

            #parse out parameter value first

            if self.get_param[parameterIndex.GET] !=  None:
                # No response data to process
                return
            if self.get_param[parameterIndex.LENGTH] == None:
                # Not fixed size of the response data
                # get the size of the responding data
                raw_value = resopnse_striped[self.get_param[parameterIndex.Start]+ 6 :
                                             len(resopnse_striped) - 2]
            else:
                raw_value = resopnse_striped[self.get_param[parameterIndex.Start]+ 6 :
                                             self.get_param[parameterIndex.Start]+
                                             self.get_param[parameterIndex.LENGTH]+6]

            self._param_dict.update(response, target_params = self.get_param)

        self.get_count = 0
        return response

    def _parse_simple_response(self, response, prompt):
        log.trace("GET RESPONSE = " + repr(response))

        #Make sure the response is the right format
        resopnse_striped = '%r' % response.strip()
        if resopnse_striped[0] != '<':
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped)
        if resopnse_striped[len(resopnse_striped) -1] != '>':
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param
                                               + '  ' + resopnse_striped)
        if resopnse_striped[3] == KMLPrompt.NAK:
            raise InstrumentProtocolException(
                'Protocol._parse_set_response : get command not recognized: %s' + resopnse_striped,
                + ' : ' + self.get_param + ' :' +  self.CAMDS_failure_message(resopnse_striped[5]))

        self.get_count = 0
        return response

    def CAMDS_failure_message(self, error_code):
        """
        Struct a error message based on error code
            0x00 - Undefined
            0x01 - Command not recognised
            0x02 - Invalid Command Structure
            0x03 - Command Timed out
            0x04 - Command cannot be processed because the camera is in an incorrect state.
            0x05 - Invalid data values
            0x06 - Camera Busy Processing
        """
        if error_code == '\x00':
            return "Undefined"
        if error_code == '\x01':
            return "Command not recognized"
        if error_code == '\x02':
            return "Invalid Command Structure"
        if error_code == '\x03':
            return "Command Timed out"
        if error_code == '\x04':
            return "Command cannot be processed because the camera is in an incorrect state"
        if error_code == '\x05':
            return "Invalid data values"
        if error_code == '\x05':
            return "Camera Busy Processing"
        return "Unknown"

    def _get_params(self):
        #return dir(KMLParameter)
        return KMLParameter.list()

    def _getattr_key(self, attr):
        return getattr(KMLParameter, attr)

    def _has_parameter(self, param):
        return KMLParameter.has(param)

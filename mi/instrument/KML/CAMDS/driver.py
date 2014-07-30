"""
@package mi.instrument.KML.CAMDS.driver
@file marine-integrations/mi/instrument/KLM/CAMDS/driver.py
@author Sung Ahn
@brief Driver for the CAMDS

"""
from mi.core.common import Units, Prefixes
from mi.core.common import BaseEnum
from mi.instrument.KML.driver import KMLScheduledJob
from mi.instrument.KML.driver import KMLCapability
from mi.instrument.KML.driver import KMLInstrumentCmds
from mi.instrument.KML.driver import KMLProtocolState
from mi.instrument.KML.driver import KMLPrompt
from mi.instrument.KML.driver import KMLProtocol
from mi.instrument.KML.driver import KMLInstrumentDriver
from mi.instrument.KML.driver import KMLParameter

from mi.core.log import get_logger

log = get_logger()

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.instrument.KML.driver import KMLProtocolEvent
from mi.core.instrument.chunker import StringChunker

# default timeout.
TIMEOUT = 20

# newline.
NEWLINE = '\r\n'

DEFAULT_CMD_TIMEOUT = 20
DEFAULT_WRITE_DELAY = 0

ZERO_TIME_INTERVAL = '00:00:00'
# newline.
NEWLINE = '\r\n'


# ##############################################################################
# Driver
# ##############################################################################

class CAMDSInstrumentDriver(KMLInstrumentDriver):
    """
    InstrumentDriver subclass for CAMDS driver.
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """

    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        # Construct superclass.
        KMLInstrumentDriver.__init__(self, evt_callback)

    # #######################################################################
    # Protocol builder.
    # #######################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = CAMDSProtocol(KMLPrompt, NEWLINE, self._driver_event)


# ##########################################################################
# Protocol
# ##########################################################################

class CAMDSProtocol(KMLProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    @staticmethod
    def sieve_function(raw_data):
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.
        The chunks are all the same type.
        """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        # Construct protocol superclass.
        KMLProtocol.__init__(self, prompts, newline, driver_event)

        self._chunker = StringChunker(CAMDSProtocol.sieve_function)

    def _build_command_dict(self):
        """
        Build command dictionary
        """
        self._cmd_dict.add(KMLCapability.START_AUTOSAMPLE,
                           timeout=300,
                           display_name="Start Autosample",
                           description="Place the instrument into autosample mode")
        self._cmd_dict.add(KMLCapability.STOP_AUTOSAMPLE,
                           display_name="Stop Autosample",
                           description="Exit autosample mode and return to command mode")

    # #######################################################################
    # Private helpers.
    # #######################################################################
    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        # if (self._extract_sample(KML_COMPASS_CALIBRATION_DataParticle,
        #                          KML_COMPASS_CALIBRATION_REGEX_MATCHER,
        #                          chunk,
        #                          timestamp)):
        #     log.debug("_got_chunk - successful match for KML_COMPASS_CALIBRATION_DataParticle")
        #
        # elif (self._extract_sample(KML_PD0_PARSED_DataParticle,
        #                            KML_PD0_PARSED_REGEX_MATCHER,
        #                            chunk,
        #                            timestamp)):
        #     log.debug("_got_chunk - successful match for KML_PD0_PARSED_DataParticle")
        #
        # elif (self._extract_sample(KML_SYSTEM_CONFIGURATION_DataParticle,
        #                            KML_SYSTEM_CONFIGURATION_REGEX_MATCHER,
        #                            chunk,
        #                            timestamp)):
        #     log.debug("_got_chunk - successful match for KML_SYSTEM_CONFIGURATION_DataParticle")
        #
        # elif (self._extract_sample(KML_ANCILLARY_SYSTEM_DATA_PARTICLE,
        #                            KML_ANCILLARY_SYSTEM_DATA_REGEX_MATCHER,
        #                            chunk,
        #                            timestamp)):
        #     log.trace("_got_chunk - successful match for KML_ANCILLARY_SYSTEM_DATA_PARTICLE")
        #
        # elif (self._extract_sample(KML_TRANSMIT_PATH_PARTICLE,
        #                            KML_TRANSMIT_PATH_REGEX_MATCHER,
        #                            chunk,
        #                            timestamp)):
        #     log.trace("_got_chunk - successful match for KML_TRANSMIT_PATH_PARTICLE")

    def _get_params(self):
        return dir(KMLParameter)

    def _getattr_key(self, attr):
        return getattr(KMLParameter, attr)

    def _has_parameter(self, param):
        return KMLParameter.has(param)

    def _send_break_cmd(self, delay):
        """
        Send a BREAK to attempt to wake the device.
        """
        self._connection.send_break(delay)

class Prompt(KMLPrompt):
    """
    Device i/o prompts..
    """


class Parameter(KMLParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #


class ProtocolEvent(KMLProtocolEvent):
    """
    Protocol events
    """


class Capability(KMLCapability):
    """
    Protocol events that should be exposed to users (subset of above).
    """


class ScheduledJob(KMLScheduledJob):
    """
    Create ScheduledJob from KMLScheduledJob
    """


class InstrumentCmds(KMLInstrumentCmds):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """


class ProtocolState(KMLProtocolState):
    """
    Instrument protocol states
    """


class InstrumentDriver(CAMDSInstrumentDriver):
    """
    Specialization for this version of the CAMDS driver
    """

    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        # Construct superclass.
        CAMDSInstrumentDriver.__init__(self, evt_callback)

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)
        log.debug("self._protocol = " + repr(self._protocol))


class Protocol(CAMDSProtocol):
    """
    Specialization for this version of the CAMDS driver
    """

    def __init__(self, prompts, newline, driver_event):
        log.debug("IN Protocol.__init__")
        CAMDSProtocol.__init__(self, prompts, newline, driver_event)
        self.initialize_scheduler()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with KML parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.NTP_SETTING,
                             r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.NTP_SETTING[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.NTP_SETTING[KMLParameter.DESCRIPTION],
                             startup_param=False,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             default_value=Parameter.NTP_SETTING[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.WHEN_DISK_IS_FULL,
                             r'CF = (\d+) \-+ Flow Ctrl ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.WHEN_DISK_IS_FULL[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.WHEN_DISK_IS_FULL[KMLParameter.DESCRIPTION],
                             startup_param=False,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             default_value=Parameter.WHEN_DISK_IS_FULL[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.CAMERA_MODE,
                             r'CH = (\d) \-+ Suppress Banner',
                             lambda match: bool(int(match.group(1))),
                             int,
                             type=ParameterDictType.BOOL,
                             display_name=Parameter.CAMERA_MODE[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.CAMERA_MODE[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.CAMERA_MODE[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.FRAME_RATE,
                             r'CH = (\d) \-+ Suppress Banner',
                             lambda match: bool(int(match.group(1))),
                             int,
                             type=ParameterDictType.BOOL,
                             display_name=Parameter.FRAME_RATE[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.FRAME_RATE[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.FRAME_RATE[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.IMAGE_RESOLUTION,
                             r'CI = (\d+) \-+ Instrument ID ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.IMAGE_RESOLUTION[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.IMAGE_RESOLUTION[KMLParameter.DESCRIPTION],
                             direct_access=True,
                             startup_param=True,
                             default_value=Parameter.IMAGE_RESOLUTION[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.COMPRESSION_RATIO,
                             r'CL = (\d) \-+ Sleep Enable',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.COMPRESSION_RATIO[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.COMPRESSION_RATIO[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.COMPRESSION_RATIO[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.SHUTTER_SPEED,
                             r'CN = (\d) \-+ Save NVRAM to recorder',
                             lambda match: bool(int(match.group(1))),
                             int,
                             type=ParameterDictType.BOOL,
                             display_name=Parameter.SHUTTER_SPEED[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.SHUTTER_SPEED[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.SHUTTER_SPEED[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.CAMERA_GAIN,
                             r'CP = (\d) \-+ PolledMode ',
                             lambda match: bool(int(match.group(1))),
                             int,
                             type=ParameterDictType.BOOL,
                             display_name=Parameter.CAMERA_GAIN[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.CAMERA_GAIN[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.CAMERA_GAIN[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.LAMP_BRIGHTNESS,
                             r'CQ = (\d+) \-+ Xmt Power ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.LAMP_BRIGHTNESS[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.LAMP_BRIGHTNESS[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.LAMP_BRIGHTNESS[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.FOCUS_SPEED,
                             r'CX = (\d) \-+ Trigger Enable ',
                             lambda match: bool(int(match.group(1))),
                             int,
                             type=ParameterDictType.BOOL,
                             display_name=Parameter.FOCUS_SPEED[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.FOCUS_SPEED[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.FOCUS_SPEED[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.ZOOM_SPEED,
                             r'EA = ([+-]\d+) \-+ Heading Alignment',
                             lambda match: int(match.group(1)),
                             lambda value: '%+06d' % value,
                             type=ParameterDictType.INT,
                             display_name=Parameter.ZOOM_SPEED[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.ZOOM_SPEED[KMLParameter.DESCRIPTION],
                             direct_access=True,
                             startup_param=True,
                             default_value=Parameter.ZOOM_SPEED[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.IRIS,
                             r'EB = ([+-]\d+) \-+ Heading Bias',
                             lambda match: int(match.group(1)),
                             lambda value: '%+06d' % value,
                             type=ParameterDictType.INT,
                             display_name=Parameter.IRIS[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.IRIS[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.IRIS[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.ZOOM_TO_GO,
                             r'EB = ([+-]\d+) \-+ Heading Bias',
                             lambda match: int(match.group(1)),
                             lambda value: '%+06d' % value,
                             type=ParameterDictType.INT,
                             display_name=Parameter.ZOOM_TO_GO[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.ZOOM_TO_GO[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.ZOOM_TO_GO[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.PAN_SPEED,
                             r'EB = ([+-]\d+) \-+ Heading Bias',
                             lambda match: int(match.group(1)),
                             lambda value: '%+06d' % value,
                             type=ParameterDictType.INT,
                             display_name=Parameter.PAN_SPEED[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.PAN_SPEED[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.PAN_SPEED[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.TILT_SPEED,
                             r'EC = (\d+) \-+ Speed Of Sound',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.TILT_SPEED[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.TILT_SPEED[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.TILT_SPEED[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.ENABLE_SOFT_END,
                             r'ED = (\d+) \-+ Transducer Depth ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.ENABLE_SOFT_END[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.ENABLE_SOFT_END[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.ENABLE_SOFT_END[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.PAN_LOCATION,
                             r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.PAN_LOCATION[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.PAN_LOCATION[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.PAN_LOCATION[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.TILT_LOCATION,
                             r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.TILT_LOCATION[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.TILT_LOCATION[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.TILT_LOCATION[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.SAMPLE_INTERVAL,
                             r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.SAMPLE_INTERVAL[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.SAMPLE_INTERVAL[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.SAMPLE_INTERVAL[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.VIDEO_FORWARDING,
                             r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.VIDEO_FORWARDING[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.VIDEO_FORWARDING[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.VIDEO_FORWARDING[KMLParameter.DEFAULT_DATA])

        self._param_dict.add(Parameter.VIDEO_FORWARDING_TIMEOUT,
                             r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name=Parameter.VIDEO_FORWARDING_TIMEOUT[KMLParameter.DISPLAY_NAME],
                             value_description=Parameter.VIDEO_FORWARDING_TIMEOUT[KMLParameter.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.VIDEO_FORWARDING_TIMEOUT[KMLParameter.DEFAULT_DATA])

        self._param_dict.set_default(Parameter.SAMPLE_INTERVAL)
        self._param_dict.set_default(Parameter.VIDEO_FORWARDING)
        self._param_dict.set_default(Parameter.VIDEO_FORWARDING_TIMEOUT)
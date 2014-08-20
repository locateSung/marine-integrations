"""
@package mi.instrument.KML.CAMDS.driver
@file marine-integrations/mi/instrument/KLM/CAMDS/driver.py
@author Sung Ahn
@brief Driver for the CAMDS

"""
from mi.core.common import BaseEnum
import time
from mi.instrument.KML.driver import KMLScheduledJob, parameterIndex
from mi.instrument.KML.driver import KMLCapability
from mi.instrument.KML.driver import KMLInstrumentCmds
from mi.instrument.KML.driver import KMLProtocolState
from mi.instrument.KML.driver import KMLPrompt
from mi.instrument.KML.driver import KMLProtocol
from mi.instrument.KML.driver import KMLInstrumentDriver
from mi.instrument.KML.driver import KMLParameter
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.exceptions import InstrumentConnectionException
from mi.core.exceptions import InstrumentParameterException

from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.instrument.port_agent_client import PortAgentClient
from mi.instrument.KML.particles import DataParticleType, CAMDS_SNAPSHOT_MATCHER, CAMDS_IMAGE_METADATA, \
    CAMDS_STOP_CAPTURING, CAMDS_START_CAPTURING
from mi.core.instrument.data_particle import RawDataParticle

from mi.core.log import get_logger

log = get_logger()

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.instrument.KML.driver import KMLProtocolEvent
from mi.core.instrument.chunker import StringChunker
from mi.instrument.KML.particles import CAMDS_HEALTH_STATUS, CAMDS_DISK_STATUS,\
                                        CAMDS_HEALTH_STATUS_MATCHER, CAMDS_DISK_STATUS_MATCHER

# default timeout.
TIMEOUT = 20

# newline.
NEWLINE = '\r\n'

DEFAULT_CMD_TIMEOUT = 20
DEFAULT_WRITE_DELAY = 0

ZERO_TIME_INTERVAL = '00:00:00'


# ##############################################################################
# Driver
# ##############################################################################

class CAMDSConnections(BaseEnum):
    """
    The protocol needs to have 2 connections
    """
    DRIVER = 'Driver'
    STREAM = 'Stream'

class StreamPortAgentClient(PortAgentClient):
    """
    Wrap PortAgentClient for Video stream
    """
    def __init__(self, host, port, cmd_port, delim=None):
        PortAgentClient.__init__(self, host, port, cmd_port, delim=None)
        self.info = "This is portAgentClient for Video Stream"

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

        # multiple portAgentClient
        self._connections = {}

    # #######################################################################
    # Protocol builder.
    # #######################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = CAMDSProtocol(KMLPrompt, NEWLINE, self._driver_event)

    def _handler_unconfigured_configure(self, *args, **kwargs):
        """
        Configure driver for device comms.
        @param args[0] Communications config dictionary.
        @return (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None) if successful, (None, None) otherwise.
        @raises InstrumentParameterException if missing or invalid param dict.
        """
        result = None
        log.trace('_handler_unconfigured_configure args: %r kwargs: %r', args, kwargs)
        # Get the required param dict.
        config = kwargs.get('config', None)  # via kwargs

        if config is None:
            try:
                config = args[0]  # via first argument
            except IndexError:
                pass

        if config is None:
            raise InstrumentParameterException('Missing comms config parameter.')

        # multiple portAgentClients
        self._connections = self._build_connections(config)
        next_state = DriverConnectionState.DISCONNECTED

        return next_state, result

    # for Master and Slave
    def _handler_disconnected_initialize(self, *args, **kwargs):
        """
        Initialize device communications. Causes the connection parameters to
        be reset.
        @return (next_state, result) tuple, (DriverConnectionState.UNCONFIGURED,
        None).
        """
        result = None
        self._connections = None
        next_state = DriverConnectionState.UNCONFIGURED

        return next_state, result

    # for master and slave
    def _handler_disconnected_configure(self, *args, **kwargs):
        """
        Configure driver for device comms.
        @param args[0] Communications config dictionary.
        @return (next_state, result) tuple, (None, None).
        @raises InstrumentParameterException if missing or invalid param dict.
        """
        next_state = None
        result = None

        # Get required config param dict.
        config = kwargs.get('config', None)  # via kwargs

        if config is None:
            try:
                config = args[0]  # via first argument
            except IndexError:
                pass

        if config is None:
            raise InstrumentParameterException('Missing comms config parameter.')

        # Verify configuration dict, and update connections if possible.
        self._connections = self._build_connections(config)

        return next_state, result

    # for Master and Slave
    def _handler_disconnected_connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger and
        construct and initialize a protocol FSM for device interaction.
        @return (next_state, result) tuple, (DriverConnectionState.CONNECTED,
        None) if successful.
        @raises InstrumentConnectionException if the attempt to connect failed.
        """
        next_state = DriverConnectionState.CONNECTED
        result = None

        self._build_protocol()

        # for Master first
        try:
            self._connections[CAMDSConnections.DRIVER].init_comms(self._protocol.got_data,
                                                                 self._protocol.got_raw,
                                                                 self._got_exception,
                                                                 self._lost_connection_callback)
            self._protocol._connection = self._connections[CAMDSConnections.DRIVER]
        except InstrumentConnectionException as e:
            log.error("CAMDS Driver Connection init Exception: %s", e)
            # Re-raise the exception
            raise e

        # for Slave
        try:
            self._connections[CAMDSConnections.STREAM].init_comms(self._protocol.got_data_stream,
                                                                  self._protocol.got_raw_stream,
                                                                  self._got_exception,
                                                                  self._lost_connection_callback)
            self._protocol._connection_stream = self._connections[CAMDSConnections.STREAM]

        except InstrumentConnectionException as e:
            log.error("Video Stream Connection init Exception: %s", e)
            # we don't need to roll back the connection on 4 beam
            # Just don't change the state to 'CONNECTED'
            # Re-raise the exception
            raise e
        return next_state, result

    # for master and slave
    def _handler_connected_disconnect(self, *args, **kwargs):
        """
        Disconnect to the device via port agent / logger and destroy the
        protocol FSM.
        @return (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None) if successful.
        """
        result = None

        for connection in self._connections.values():
            connection.stop_comms()
        self._protocol = None
        next_state = DriverConnectionState.DISCONNECTED

        return next_state, result

    # for master and slave
    def _handler_connected_connection_lost(self, *args, **kwargs):
        """
        The device connection was lost. Stop comms, destroy protocol FSM and
        revert to disconnected state.
        @return (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None).
        """
        result = None

        for connection in self._connections.values():
            connection.stop_comms()
        self._protocol = None

        # Send async agent state change event.
        log.info("_handler_connected_connection_lost: sending LOST_CONNECTION "
                 "event, moving to DISCONNECTED state.")
        self._driver_event(DriverAsyncEvent.AGENT_EVENT,
                           ResourceAgentEvent.LOST_CONNECTION)

        next_state = DriverConnectionState.DISCONNECTED

        return next_state, result

    # for Master and Slave
    def _build_connections(self, all_configs):
        """
        Constructs and returns a Connection object according to the given
        configuration. The connection object is a LoggerClient instance in
        this base class. Subclasses can overwrite this operation as needed.
        The value returned by this operation is assigned to self._connections
        and also to self._protocol._connection upon entering in the
        DriverConnectionState.CONNECTED state.

        @param all_configs configuration dict

        @return a Connection instance, which will be assigned to
                  self._connections

        @throws InstrumentParameterException Invalid configuration.
        """
        connections = {}
        for name, config in all_configs.items():
            if not isinstance(config, dict):
                continue
            if 'mock_port_agent' in config:
                mock_port_agent = config['mock_port_agent']
                # check for validity here...
                if mock_port_agent is not None:
                    connections[name] = mock_port_agent
            else:
                try:
                    addr = config['addr']
                    port = config['port']
                    cmd_port = config.get('cmd_port')

                    if isinstance(addr, str) and isinstance(port, int) and len(addr) > 0:
                        connections[name] = StreamPortAgentClient(addr, port, cmd_port)
                    else:
                        raise InstrumentParameterException('Invalid comms config dict in build_connections.')

                except (TypeError, KeyError):
                    raise InstrumentParameterException('Invalid comms config dict..')
        return connections

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
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.
        The chunks are all the same type.
        """

        sieve_matchers = [CAMDS_SNAPSHOT_MATCHER,
                          CAMDS_DISK_STATUS_MATCHER,
                          CAMDS_HEALTH_STATUS_MATCHER,
                          CAMDS_START_CAPTURING,
                          CAMDS_STOP_CAPTURING]

        return_list = []

        for matcher in sieve_matchers:

            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list


    @staticmethod
    def sieve_function_stream(raw_data):
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.
        The chunks are all the same type.
        """

        # It only generate raw stream type.
        return_list = []
        return return_list

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        # Construct protocol superclass.
        KMLProtocol.__init__(self, prompts, newline, driver_event)

        self._connection = None
        self._connection_stream = None

        # Line buffer for input from device.
        self._linebuf_stream = ''

        # Short buffer to look for prompts from device in command-response
        # mode.
        self._promptbuf_stream = ''

        self._chunker = StringChunker(self.sieve_function)
        self._chunker_stream = StringChunker(self.sieve_function_stream)


    def _build_command_dict(self):
        """
        Build command dictionary
        """
        self._cmd_dict.add(KMLCapability.START_AUTOSAMPLE,
                           timeout=300,
                           display_name="Start Autosample",
                           description="Place the instrument into autosample mode")
        self._cmd_dict.add(KMLCapability.STOP_AUTOSAMPLE,
                           timeout=300,
                           display_name="Stop Autosample",
                           description="Exit autosample mode and return to command mode")
        self._cmd_dict.add(KMLCapability.START_CAPTURE,
                           timeout=300,
                           display_name="Start Capturing",
                           description="Start capturing images")
        self._cmd_dict.add(KMLCapability.STOP_CAPTURE,
                           timeout=300,
                           display_name="Stop Capturing",
                           description="Stop capturing images")
        self._cmd_dict.add(KMLCapability.ACQUIRE_STATUS,
                           timeout=300,
                           display_name="Acquire Status",
                           description="Get disk usage and check health")
        self._cmd_dict.add(KMLCapability.ACQUIRE_SAMPLE,
                           timeout=300,
                           display_name="Acquire Sample",
                           description="Take a snapshot")
        self._cmd_dict.add(KMLCapability.GOTO_PRESET,
                           timeout=300,
                           display_name="Goto Preset",
                           description="Go to the preset number")
        self._cmd_dict.add(KMLCapability.SET_PRESET,
                           timeout=300,
                           display_name="Set Preset",
                           description="Set the preset number")
        self._cmd_dict.add(KMLCapability.LAMP_OFF,
                           timeout=300,
                           display_name="lamp off",
                           description="Turn off the lamp")
        self._cmd_dict.add(KMLCapability.LAMP_ON,
                           timeout=300,
                           display_name="lamp on",
                           description="Turn on the lamp")
        self._cmd_dict.add(KMLCapability.LASER_1_OFF,
                           timeout=300,
                           display_name="Laser 1  off",
                           description="Turn off the laser #1")
        self._cmd_dict.add(KMLCapability.LASER_2_OFF,
                           timeout=300,
                           display_name="Laser 2 off",
                           description="Turn off the laser #2")
        self._cmd_dict.add(KMLCapability.LASER_BOTH_OFF,
                           timeout=300,
                           display_name="Laser off",
                           description="Turn off the all laser")
        self._cmd_dict.add(KMLCapability.LASER_1_ON,
                           timeout=300,
                           display_name="Laser 1  on",
                           description="Turn on the laser #1")
        self._cmd_dict.add(KMLCapability.LASER_2_ON,
                           timeout=300,
                           display_name="Laser 2 on",
                           description="Turn on the laser #2")
        self._cmd_dict.add(KMLCapability.LASER_BOTH_ON,
                           timeout=300,
                           display_name="Laser on",
                           description="Turn on the all laser")

    # #######################################################################
    # Private helpers.
    # #######################################################################

    def got_data_stream(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers.

        @param port_agent_packet is port agent stream.

        Also add data to the chunker and when received call got_chunk
        to publish results.
        """

        data_length = port_agent_packet.get_data_length()
        data = port_agent_packet.get_data()
        timestamp = port_agent_packet.get_timestamp()

        if data_length > 0:
            if self.get_current_state() == DriverProtocolState.DIRECT_ACCESS:
                self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)

            self.add_to_buffer_stream(data)

            self._chunker_stream.add_chunk(data, timestamp)
            (timestamp, chunk) = self._chunker_stream.get_next_data()
            while chunk:
                self._got_chunk_stream(chunk, timestamp)
                (timestamp, chunk) = self._chunker_stream.get_next_data()

    def add_to_buffer_stream(self, data):
        """
        Add a chunk of data to the internal data buffers
        @param data: bytes to add to the buffer
        """
        # Update the line and prompt buffers.
        self._linebuf_stream += data
        self._promptbuf_stream += data
        self._last_data_timestamp_stream = time.time()

    def got_raw(self, port_agent_packet):
        """
        Called by the port agent client when raw data is available, such as data
        sent by the driver to the instrument, the instrument responses,etc.
        """
        self.publish_raw(port_agent_packet)

    def got_raw_stream(self, port_agent_packet):
        """
        Called by the port agent client when raw data is available, such as data
        sent by the driver to the instrument, the instrument responses,etc.
        """
        self.publish_raw_stream(port_agent_packet)

    def publish_raw_stream(self, port_agent_packet):
        """
        Publish raw data
        @param: port_agent_packet port agent packet containing raw
        """
        particle = RawDataParticle(port_agent_packet.get_as_dict(),
                                           port_timestamp=port_agent_packet.get_timestamp())

        parsed_sample = particle.generate()
        parsed_sample._data_particle_type = DataParticleType.CAMDS_VIDEO
        if self._driver_event:
            if(self.video_fowarding_flag):
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

    def _got_chunk_stream(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """
        pass
        # The video stream will be sent through publish raw

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        if (self._extract_sample(CAMDS_DISK_STATUS,
                                 CAMDS_DISK_STATUS_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for CAMDS_DISK_STATUS")

        elif (self._extract_sample(CAMDS_HEALTH_STATUS,
                                   CAMDS_HEALTH_STATUS_MATCHER,
                                   chunk,
                                   timestamp)):
            log.debug("_got_chunk - successful match for CAMDS_HEALTH_STATUS")

        elif (self._extract_sample(CAMDS_IMAGE_METADATA,
                                   CAMDS_SNAPSHOT_MATCHER,
                                   chunk,
                                   timestamp)):
            log.debug("_got_chunk - successful match for CAMDS_IMAGE_METADATA(Snapshot)")

        elif (self._extract_sample(CAMDS_IMAGE_METADATA,
                                   CAMDS_START_CAPTURING,
                                   chunk,
                                   timestamp)):
            log.debug("_got_chunk - successful match for CAMDS_IMAGE_METADATA(Start Capturing)")

        elif (self._extract_sample(CAMDS_IMAGE_METADATA,
                                   CAMDS_STOP_CAPTURING,
                                   chunk,
                                   timestamp)):
            log.debug("_got_chunk - successful match for CAMDS_IMAGE_METADATA(Stop Capturing")

    def _get_params(self):
        return dir(KMLParameter)

    def _getattr_key(self, attr):
        return getattr(KMLParameter, attr)

    def _has_parameter(self, param):
        return KMLParameter.has(param)


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
                             r'NOT USED',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.NTP_SETTING[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.NTP_SETTING[parameterIndex.DESCRIPTION],
                             startup_param=False,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             default_value=Parameter.NTP_SETTING[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.NETWORK_DRIVE_LOCATION,
                             r'NOT USED',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.NETWORK_DRIVE_LOCATION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.NETWORK_DRIVE_LOCATION[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.NETWORK_DRIVE_LOCATION[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.WHEN_DISK_IS_FULL,
                             r'NOT USED',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.WHEN_DISK_IS_FULL[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.WHEN_DISK_IS_FULL[parameterIndex.DESCRIPTION],
                             startup_param=False,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             default_value=Parameter.WHEN_DISK_IS_FULL[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.CAMERA_MODE,
                             r'NOT USED',
                             lambda match: bool(int(match.group(1))),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.CAMERA_MODE[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.CAMERA_MODE[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.CAMERA_MODE[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.FRAME_RATE,
                             r'NOT USED',
                             lambda match: bool(int(match.group(1))),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.FRAME_RATE[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.FRAME_RATE[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.FRAME_RATE[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.IMAGE_RESOLUTION,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.IMAGE_RESOLUTION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.IMAGE_RESOLUTION[parameterIndex.DESCRIPTION],
                             direct_access=True,
                             startup_param=True,
                             default_value=Parameter.IMAGE_RESOLUTION[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.COMPRESSION_RATIO,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.COMPRESSION_RATIO[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.COMPRESSION_RATIO[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.COMPRESSION_RATIO[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.SHUTTER_SPEED,
                             r'NOT USED',
                             lambda match: bool(int(match.group(1))),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.SHUTTER_SPEED[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.SHUTTER_SPEED[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.SHUTTER_SPEED[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.CAMERA_GAIN,
                             r'NOT USED',
                             lambda match: bool(int(match.group(1))),
                             int,
                             type=ParameterDictType.BOOL,
                             display_name=Parameter.CAMERA_GAIN[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.CAMERA_GAIN[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.CAMERA_GAIN[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.LAMP_BRIGHTNESS,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.LAMP_BRIGHTNESS[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.LAMP_BRIGHTNESS[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.LAMP_BRIGHTNESS[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.FOCUS_SPEED,
                             r'NOT USED',
                             lambda match: bool(int(match.group(1))),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.FOCUS_SPEED[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.FOCUS_SPEED[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.FOCUS_SPEED[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.ZOOM_SPEED,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             lambda value: '%+06d' % value,
                             type=ParameterDictType.INT,
                             display_name=Parameter.ZOOM_SPEED[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.ZOOM_SPEED[parameterIndex.DESCRIPTION],
                             direct_access=True,
                             startup_param=True,
                             default_value=Parameter.ZOOM_SPEED[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.IRIS_POSITION,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.IRIS_POSITION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.IRIS_POSITION[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.IRIS_POSITION[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.ZOOM_POSITION,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.ZOOM_POSITION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.ZOOM_POSITION[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.ZOOM_POSITION[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.PAN_SPEED,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.PAN_SPEED[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.PAN_SPEED[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.PAN_SPEED[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.TILT_SPEED,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.TILT_SPEED[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.TILT_SPEED[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.TILT_SPEED[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.SOFT_END_STOPS,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.SOFT_END_STOPS[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.SOFT_END_STOPS[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.SOFT_END_STOPS[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.PAN_POSITION,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.PAN_POSITION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.PAN_POSITION[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.PAN_POSITION[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.TILT_POSITION,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.TILT_POSITION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.TILT_POSITION[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=True,
                             default_value=Parameter.TILT_POSITION[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.SAMPLE_INTERVAL,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.SAMPLE_INTERVAL[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.SAMPLE_INTERVAL[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.SAMPLE_INTERVAL[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.ACQUIRE_STATUS_INTERVAL,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.ACQUIRE_STATUS_INTERVAL[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.ACQUIRE_STATUS_INTERVAL[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.ACQUIRE_STATUS_INTERVAL[parameterIndex.DEFAULT_DATA])


        self._param_dict.add(Parameter.VIDEO_FORWARDING,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.VIDEO_FORWARDING[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.VIDEO_FORWARDING[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.VIDEO_FORWARDING[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.VIDEO_FORWARDING_TIMEOUT,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.VIDEO_FORWARDING_TIMEOUT[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.VIDEO_FORWARDING_TIMEOUT[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.VIDEO_FORWARDING_TIMEOUT[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.PRESET_NUMBER,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.PRESET_NUMBER[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.PRESET_NUMBER[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.PRESET_NUMBER[parameterIndex.DEFAULT_DATA])

        self._param_dict.add(Parameter.AUTO_CAPTURE_DURATION,
                             r'NOT USED',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name=Parameter.AUTO_CAPTURE_DURATION[parameterIndex.DISPLAY_NAME],
                             value_description=Parameter.AUTO_CAPTURE_DURATION[parameterIndex.DESCRIPTION],
                             startup_param=True,
                             direct_access=False,
                             default_value=Parameter.AUTO_CAPTURE_DURATION[parameterIndex.DEFAULT_DATA])

        self._param_dict.set_default(Parameter.SAMPLE_INTERVAL)
        self._param_dict.set_default(Parameter.ACQUIRE_STATUS_INTERVAL)
        self._param_dict.set_default(Parameter.VIDEO_FORWARDING)
        self._param_dict.set_default(Parameter.VIDEO_FORWARDING_TIMEOUT)
        self._param_dict.set_default(Parameter.PRESET_NUMBER)
        self._param_dict.set_default(Parameter.AUTO_CAPTURE_DURATION)
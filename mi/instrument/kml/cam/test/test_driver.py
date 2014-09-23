"""
@package mi.instrument.KML.CAMDS.test.test_driver
@file marine-integrations/mi/instrument/KML/CAMDS/test/test_driver.py
@author Sung Ahn
@brief Test Driver for CAMDS
Release notes:

"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import time as time
import unittest
from nose.plugins.attrib import attr
from mi.core.log import get_logger

log = get_logger()

# MI imports.
from mi.idk.unit_test import AgentCapabilityType

from mi.instrument.kml.test.test_driver import KMLUnitTest
from mi.instrument.kml.test.test_driver import KMLIntegrationTest
from mi.instrument.kml.test.test_driver import KMLQualificationTest
from mi.instrument.kml.test.test_driver import KMLPublicationTest

from mi.instrument.kml.particles import DataParticleType
from mi.instrument.kml.driver import KMLProtocolState
from mi.instrument.kml.driver import KMLProtocolEvent
from mi.instrument.kml.driver import KMLParameter
from mi.instrument.kml.driver import ParameterIndex

from mi.core.exceptions import InstrumentCommandException

from mi.core.instrument.instrument_driver import ResourceAgentState


# ################################### RULES ####################################
# #
# Common capabilities in the base class                                       #
# #
# Instrument specific stuff in the derived class                              #
# #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
# #
# Qualification tests are driven through the instrument_agent                 #
# #
# ##############################################################################

class CAMParameterAltValue():
    # Values that are valid, but not the ones we want to use,
    # used for testing to verify that we are setting good values.
    #

    # Probably best NOT to tweek this one.
    SERIAL_FLOW_CONTROL = '11110'
    BANNER = 1
    SAVE_NVRAM_TO_RECORDER = True  # Immutable.
    SLEEP_ENABLE = 1
    POLLED_MODE = True
    PITCH = 1
    ROLL = 1


# ##############################################################################
# UNIT TESTS                                   #
# ##############################################################################
@attr('UNIT', group='mi')
class CAMDriverUnitTest(KMLUnitTest):
    def setUp(self):
        KMLUnitTest.setUp(self)


# ##############################################################################
# INTEGRATION TESTS                                #
# ##############################################################################
@attr('INT', group='mi')
class CAMDriverIntegrationTest(KMLIntegrationTest):
    def setUp(self):
        KMLIntegrationTest.setUp(self)

    # ##
    # Add instrument specific integration tests
    ###
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', KMLParameter.ALL)
        log.error("Sung get_resource %s", repr(reply))

        self.assert_driver_parameters(reply, True)

    def test_break(self):
        self.assert_initialize_driver()
        self.assert_driver_command(KMLProtocolEvent.START_AUTOSAMPLE, state=KMLProtocolState.AUTOSAMPLE,
                                   delay=1)
        self.assert_driver_command(KMLProtocolEvent.STOP_AUTOSAMPLE, state=KMLProtocolState.COMMAND, delay=10)

    #@unittest.skip('It takes many hours for this test')
    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()
        ####
        # First test in command mode
        ####

        self.assert_driver_command(KMLProtocolEvent.START_AUTOSAMPLE, state=KMLProtocolState.AUTOSAMPLE,
                                   delay=1)
        self.assert_driver_command(KMLProtocolEvent.STOP_AUTOSAMPLE, state=KMLProtocolState.COMMAND, delay=1)
        self.assert_driver_command(KMLProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_driver_command(KMLProtocolEvent.LAMP_ON)
        self.assert_driver_command(KMLProtocolEvent.LAMP_OFF)
        self.assert_driver_command(KMLProtocolEvent.LASER_1_ON)
        self.assert_driver_command(KMLProtocolEvent.LASER_1_OFF)
        self.assert_driver_command(KMLProtocolEvent.LASER_BOTH_ON)
        self.assert_driver_command(KMLProtocolEvent.LASER_BOTH_OFF)
        self.assert_driver_command(KMLProtocolEvent.ACQUIRE_STATUS)
        self.assert_driver_command(KMLProtocolEvent.LASER_2_ON)
        self.assert_driver_command(KMLProtocolEvent.LASER_2_OFF)
        self.assert_driver_command(KMLProtocolEvent.LASER_BOTH_ON)
        self.assert_driver_command(KMLProtocolEvent.LASER_BOTH_OFF)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    #@unittest.skip('It takes many hours for this test')
    # def test_startup_params(self):
    #     """
    #     Verify that startup parameters are applied correctly. Generally this
    #     happens in the driver discovery method.
    #
    #     since nose orders the tests by ascii value this should run first.
    #     """
    #     self.assert_initialize_driver()
    #
    #     get_values = {
    #         KMLParameter.FRAME_RATE[ParameterIndex.KEY]: 30,
    #         KMLParameter.ZOOM_SPEED[ParameterIndex.KEY]: 0,
    #         KMLParameter.ACQUIRE_STATUS_INTERVAL[ParameterIndex.KEY]: '00:00:00',
    #         KMLParameter.AUTO_CAPTURE_DURATION[ParameterIndex.KEY]: 3,
    #         KMLParameter.CAMERA_GAIN[ParameterIndex.KEY]: 255,
    #         KMLParameter.CAMERA_MODE[ParameterIndex.KEY]: 9,
    #         KMLParameter.COMPRESSION_RATIO[ParameterIndex.KEY]: 100,
    #         KMLParameter.FOCUS_POSITION[ParameterIndex.KEY]: 100,
    #         KMLParameter.FOCUS_SPEED[ParameterIndex.KEY]: 0,
    #         KMLParameter.IMAGE_RESOLUTION[ParameterIndex.KEY]: 1,
    #         KMLParameter.IRIS_POSITION[ParameterIndex.KEY]: 8,
    #         KMLParameter.LAMP_BRIGHTNESS[ParameterIndex.KEY]: '3:50',
    #         KMLParameter.PAN_POSITION[ParameterIndex.KEY]: 90,
    #         KMLParameter.PAN_SPEED[ParameterIndex.KEY]: 50,
    #
    #     }
    #     new_set = {
    #         'SERIAL_FLOW_CONTROL': '11110',
    #         'BANNER': 1,
    #         'SAVE_NVRAM_TO_RECORDER': True,  # Immutable.
    #         'PITCH': 1,
    #         'ROLL': 1
    #     }
    #     # Change the values of these parameters to something before the
    #     # driver is reinitialized.  They should be blown away on reinit.
    #     new_values = {}
    #
    #     p = KMLParameter.dict()
    #     for k, v in new_set.items():
    #         if k not in ('BANNER', 'SERIAL_FLOW_CONTROL', 'SAVE_NVRAM_TO_RECORDER', 'TIME'):
    #             new_values[(p[k])[ParameterIndex.KEY]] = v
    #     self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)

    def assert_clock_sync(self):
        """
        Verify the clock is set to at least the current date
        """
        dt = self.assert_get(KMLParameter.TIME)
        lt = time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:10].upper() in dt.upper())


# ##############################################################################
# QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class CAMDriverQualificationTest(KMLQualificationTest):
    def setUp(self):
        KMLQualificationTest.setUp(self)

    def assert_configuration(self, data_particle, verify_values=False):
        """
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        """
        # self.assert_data_particle_keys(ADCP_SYSTEM_CONFIGURATION_KEY, self._system_configuration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._system_configuration_data_parameters, verify_values)

    def assert_compass_calibration(self, data_particle, verify_values=False):
        """
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        """
        # self.assert_data_particle_keys(ADCP_COMPASS_CALIBRATION_KEY, self._calibration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    # need to override this because we are slow and dont feel like modifying the base class lightly
    def assert_set_parameter(self, name, value, verify=True):
        """
        verify that parameters are set correctly.  Assumes we are in command mode.
        """
        setParams = {name: value}
        getParams = [name]

        self.instrument_agent_client.set_resource(setParams, timeout=300)

        if verify:
            result = self.instrument_agent_client.get_resource(getParams, timeout=300)
            self.assertEqual(result[name], value)

    @unittest.skip('It takes time for this test')
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports
         direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()
        self.assert_set_parameter(KMLParameter.SPEED_OF_SOUND, 1487)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)

        # self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))

        # self.tcp_client.expect(KMLPrompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        # Direct access is true, it should be set before
        self.assert_get_parameter(KMLParameter.SPEED_OF_SOUND, 1487)

    # Only test when time is sync in startup
    @unittest.skip('It takes time for this test')
    def _test_execute_clock_sync(self):
        """
        Verify we can synchronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(KMLProtocolEvent.CLOCK_SYNC)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([KMLParameter.TIME], timeout=45)

        instrument_time = time.mktime(
            time.strptime(check_new_params.get(KMLParameter.TIME).lower(), "%Y/%m/%d,%H:%M:%S %Z"))

        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 45)

    @unittest.skip('It takes time for this test')
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                KMLProtocolEvent.CLOCK_SYNC,
                KMLProtocolEvent.START_AUTOSAMPLE,
                KMLProtocolEvent.GET_CALIBRATION,
                KMLProtocolEvent.RUN_TEST_200,
                KMLProtocolEvent.ACQUIRE_STATUS,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
            KMLProtocolEvent.STOP_AUTOSAMPLE,
            KMLProtocolEvent.GET_CALIBRATION,
        ]
        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
        ]

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

    @unittest.skip('It takes many hours for this test')
    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if not self._driver_parameters[k][self.READONLY]:
                    self.assert_get_parameter(k, self._driver_parameters[k][self.VALUE])
                    log.debug("VERIFYING %s is set to %s appropriately ", k,
                              str(self._driver_parameters[k][self.VALUE]))

        # self.assert_set_parameter(WorkhorseParameter.XMIT_POWER, 250)
        # self.assert_set_parameter(WorkhorseParameter.SPEED_OF_SOUND, 1480)
        # self.assert_set_parameter(WorkhorseParameter.PITCH, 1)
        # self.assert_set_parameter(WorkhorseParameter.ROLL, 1)
        # self.assert_set_parameter(WorkhorseParameter.SALINITY, 36)
        # self.assert_set_parameter(WorkhorseParameter.TRANSDUCER_DEPTH, 6000, False)
        # self.assert_set_parameter(WorkhorseParameter.TRANSDUCER_DEPTH, 0)
        #
        # self.assert_set_parameter(WorkhorseParameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        # self.assert_set_parameter(WorkhorseParameter.TIME_PER_ENSEMBLE, '01:00:00.00')
        #
        # self.assert_set_parameter(WorkhorseParameter.FALSE_TARGET_THRESHOLD, '049,002')
        # self.assert_set_parameter(WorkhorseParameter.BANDWIDTH_CONTROL, 1)
        # self.assert_set_parameter(WorkhorseParameter.CORRELATION_THRESHOLD, 63)
        #
        # self.assert_set_parameter(WorkhorseParameter.ERROR_VELOCITY_THRESHOLD, 1999)
        # self.assert_set_parameter(WorkhorseParameter.BLANK_AFTER_TRANSMIT, 714)
        #
        # self.assert_set_parameter(WorkhorseParameter.CLIP_DATA_PAST_BOTTOM, 1)
        # self.assert_set_parameter(WorkhorseParameter.RECEIVER_GAIN_SELECT, 0)
        # self.assert_set_parameter(WorkhorseParameter.NUMBER_OF_DEPTH_CELLS, 99)
        # self.assert_set_parameter(WorkhorseParameter.PINGS_PER_ENSEMBLE, 0)
        # self.assert_set_parameter(WorkhorseParameter.DEPTH_CELL_SIZE, 790)
        #
        # self.assert_set_parameter(WorkhorseParameter.TRANSMIT_LENGTH, 1)
        # self.assert_set_parameter(WorkhorseParameter.PING_WEIGHT, 1)
        # self.assert_set_parameter(WorkhorseParameter.AMBIGUITY_VELOCITY, 176)


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific publication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class CAMDriverPublicationTest(KMLPublicationTest):
    def setUp(self):
        KMLPublicationTest.setUp(self)



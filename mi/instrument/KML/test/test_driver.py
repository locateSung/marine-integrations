"""
@package mi.instrument.KML.test.test_driver
@file marine-integrations/mi/instrument/KML/test/test_driver.py
@author Sung Ahn
@brief Driver for the KML family
Release notes:
"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import time
import unittest
from mi.core.log import get_logger

log = get_logger()

from nose.plugins.attrib import attr
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase
from mi.core.exceptions import NotImplementedException
from mi.instrument.kml.particles import DataParticleType

from mi.instrument.kml.driver import KMLProtocolState
from mi.instrument.kml.driver import KMLProtocolEvent
from mi.instrument.kml.driver import KMLParameter

DEFAULT_CLOCK_DIFF = 5


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
# 1. Pick a single method within the class.                                   #
# 2. Create an instance of the class                                          #
# 3. If the method to be tested tries to call out, over-ride the offending    #
#    method with a mock                                                       #
# 4. Using above, try to cover all paths through the functions                #
# 5. Negative testing if at all possible.                                     #
###############################################################################
@attr('UNIT', group='mi')
class KMLUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class KMLIntegrationTest(InstrumentDriverIntegrationTestCase):

    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def _is_time_set(self, time_param, expected_time, time_format="%d %b %Y %H:%M:%S", tolerance=DEFAULT_CLOCK_DIFF):
        """
        Verify is what we expect it to be within a given tolerance
        @param time_param: driver parameter
        @param expected_time: what the time should be in seconds since unix epoch or formatted time string
        @param time_format: date time format
        @param tolerance: how close to the set time should the get be?
        """
        log.debug("Expected time un-formatted: %s", expected_time)

        result_time = self.assert_get(time_param)

        log.debug("RESULT TIME = " + str(result_time))
        log.debug("TIME FORMAT = " + time_format)
        result_time_struct = time.strptime(result_time, time_format)
        converted_time = time.mktime(result_time_struct)

        if isinstance(expected_time, float):
            expected_time_struct = time.localtime(expected_time)
        else:
            expected_time_struct = time.strptime(expected_time, time_format)

        log.debug("Current Time: %s, Expected Time: %s", time.strftime("%d %b %y %H:%M:%S", result_time_struct),
                  time.strftime("%d %b %y %H:%M:%S", expected_time_struct))

        log.debug("Current Time: %s, Expected Time: %s, Tolerance: %s",
                  converted_time, time.mktime(expected_time_struct), tolerance)

        # Verify the clock is set within the tolerance
        return abs(converted_time - time.mktime(expected_time_struct)) <= tolerance

    ###
    #   Test scheduled events
    ###
    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        raise NotImplementedException()

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        raise NotImplementedException()

    def assert_clock_sync(self):
        """
        Verify the clock is set to at least the current date
        """
        dt = self.assert_get(KMLParameter.TIME)
        lt = time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:13].upper() in dt.upper())

    def assert_acquire_status(self):
        """
        Assert that Acquire_status return the following ASYNC particles
        """
        self.assert_async_particle_generation(DataParticleType.ADCP_COMPASS_CALIBRATION, self.assert_calibration,
                                              timeout=60)
        self.assert_async_particle_generation(DataParticleType.ADCP_ANCILLARY_SYSTEM_DATA, self.assert_ancillary_data,
                                              timeout=60)
        self.assert_async_particle_generation(DataParticleType.ADCP_TRANSMIT_PATH, self.assert_transmit_data,
                                              timeout=60)

    def assert_transmit_data(self, data_particle, verify_values=True):
        """
        Verify an adcpt ps0 data particle
        @param data_particle: ADCP_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_TRANSMIT_PATH)

    def assert_ancillary_data(self, data_particle, verify_values=True):
        """
        Verify an adcp ps0 data particle
        @param data_particle: ADCP_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_ANCILLARY_SYSTEM_DATA)

    def assert_calibration(self, data_particle, verify_values=True):
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)

    def test_scheduled_interval_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_initialize_driver()
        self.assert_set(KMLParameter.CLOCK_SYNCH_INTERVAL, '00:00:04')
        time.sleep(10)

        self.assert_set(KMLParameter.CLOCK_SYNCH_INTERVAL, '00:00:00')
        self.assert_current_state(KMLProtocolState.COMMAND)

    def test_scheduled_interval_acquire_status_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_initialize_driver()
        self.assert_set(KMLParameter.GET_STATUS_INTERVAL, '00:00:04')
        time.sleep(10)
        self.assert_acquire_status()

        self.assert_set(KMLParameter.GET_STATUS_INTERVAL, '00:00:00')
        self.assert_current_state(KMLProtocolState.COMMAND)

        failed = False
        try:
            self.assert_acquire_status()
            failed = True
        except AssertionError:
            pass
        self.assertFalse(failed)

    @unittest.skip('It takes many hours for this test')
    def test_scheduled_acquire_status_autosample(self):
        """
        Verify the scheduled acquire status is triggered and functions as expected
        """

        self.assert_initialize_driver()
        self.assert_current_state(KMLProtocolState.COMMAND)
        self.assert_set(KMLParameter.GET_STATUS_INTERVAL, '00:00:04')
        self.assert_driver_command(KMLProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(KMLProtocolState.AUTOSAMPLE)
        time.sleep(10)
        self.assert_acquire_status()
        self.assert_driver_command(KMLProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_current_state(KMLProtocolState.COMMAND)
        self.assert_set(KMLParameter.GET_STATUS_INTERVAL, '00:00:00')
        self.assert_current_state(KMLProtocolState.COMMAND)

    @unittest.skip('It takes many hours for this test')
    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """

        self.assert_initialize_driver()
        self.assert_current_state(KMLProtocolState.COMMAND)
        self.assert_set(KMLParameter.CLOCK_SYNCH_INTERVAL, '00:00:04')
        self.assert_driver_command(KMLProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(KMLProtocolState.AUTOSAMPLE)
        time.sleep(10)
        self.assert_driver_command(KMLProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_current_state(KMLProtocolState.COMMAND)
        self.assert_set(KMLParameter.CLOCK_SYNCH_INTERVAL, '00:00:00')
        self.assert_current_state(KMLProtocolState.COMMAND)

    @unittest.skip('It takes time')
    def test_acquire_status(self):
        """
        Verify the acquire_status command is functional
        """

        self.assert_initialize_driver()
        self.assert_driver_command(KMLProtocolEvent.ACQUIRE_STATUS)
        self.assert_acquire_status()

    # This will be called by test_set_range()
    def _tst_set_xmit_power(self):
        ###
        #   test get set of a variety of parameter ranges
        ###

        # XMIT_POWER:  -- Int 0-255
        self.assert_set(KMLParameter.XMIT_POWER, 0)
        self.assert_set(KMLParameter.XMIT_POWER, 128)
        self.assert_set(KMLParameter.XMIT_POWER, 254)

        self.assert_set_exception(KMLParameter.XMIT_POWER, "LEROY JENKINS")
        self.assert_set_exception(KMLParameter.XMIT_POWER, 256)
        self.assert_set_exception(KMLParameter.XMIT_POWER, -1)
        self.assert_set_exception(KMLParameter.XMIT_POWER, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(KMLParameter.XMIT_POWER, self._driver_parameters[KMLParameter.XMIT_POWER][self.VALUE])

    # This will be called by test_set_range()
    def _tst_set_speed_of_sound(self):
        ###
        #   test get set of a variety of parameter ranges
        ###

        # SPEED_OF_SOUND:  -- Int 1485 (1400 - 1600)
        self.assert_set(KMLParameter.SPEED_OF_SOUND, 1400)
        self.assert_set(KMLParameter.SPEED_OF_SOUND, 1450)
        self.assert_set(KMLParameter.SPEED_OF_SOUND, 1500)
        self.assert_set(KMLParameter.SPEED_OF_SOUND, 1550)
        self.assert_set(KMLParameter.SPEED_OF_SOUND, 1600)

        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, 0)
        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, 1399)

        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, 1601)
        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, "LEROY JENKINS")
        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, -256)
        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, -1)
        self.assert_set_exception(KMLParameter.SPEED_OF_SOUND, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(KMLParameter.SPEED_OF_SOUND,
                        self._driver_parameters[KMLParameter.SPEED_OF_SOUND][self.VALUE])

    # This will be called by test_set_range()
    def _tst_set_salinity(self):
        ###
        #   test get set of a variety of parameter ranges
        ###

        # SALINITY:  -- Int (0 - 40)
        self.assert_set(KMLParameter.SALINITY, 1)
        self.assert_set(KMLParameter.SALINITY, 10)
        self.assert_set(KMLParameter.SALINITY, 20)
        self.assert_set(KMLParameter.SALINITY, 30)
        self.assert_set(KMLParameter.SALINITY, 40)

        self.assert_set_exception(KMLParameter.SALINITY, "LEROY JENKINS")

        # AssertionError: Unexpected exception: ES no value match (40 != -1)
        self.assert_set_exception(KMLParameter.SALINITY, -1)

        # AssertionError: Unexpected exception: ES no value match (35 != 41)
        self.assert_set_exception(KMLParameter.SALINITY, 41)

        self.assert_set_exception(KMLParameter.SALINITY, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(KMLParameter.SALINITY, self._driver_parameters[KMLParameter.SALINITY][self.VALUE])


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class KMLQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)


###############################################################################
#                             PUBLICATION  TESTS                              #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class KMLPublicationTest(InstrumentDriverPublicationTestCase):
    def setUp(self):
        InstrumentDriverPublicationTestCase.setUp(self)

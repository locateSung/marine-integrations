#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdmo
@file marine-integrations/mi/dataset/parser/test/test_ctdmo.py
@author Emily Hahn, Steve Myerson (recovered)
@brief Test code for a Ctdmo data parser
Files used for Recovered CO:
  CTD2000.DAT
    1 CT block
    0 CO blocks
  CTD2001.DAT
    1 CT
    1 CO w/6 records, 5 valid IDs
  CTD2002.DAT
    1 CO w/4 records, 3 valid IDs
    1 CT
    1 CO w/5 records, 3 valid IDs
  CTD2004.DAT
    1 CT
    1 CO w/2 records, 0 valid IDs
    1 CO w/2 records, 1 valid ID
    1 CO w/5 records, 4 valid IDs
    1 CT
    1 CO w/3 records, 3 valid IDs
"""

import gevent
import unittest
import os
from nose.plugins.attrib import attr
from StringIO import StringIO

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey

from mi.dataset.parser.ctdmo import \
    CtdmoRecoveredCoParser, \
    CtdmoRecoveredCtParser, \
    CtdmoRecoveredInstrumentDataParticle, \
    CtdmoRecoveredOffsetDataParticle, \
    CtdmoTelemeteredParser, \
    CtdmoTelemeteredInstrumentDataParticle, \
    CtdmoTelemeteredOffsetDataParticle, \
    CtdmoStateKey

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import DatasetParserException

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
                 'dataset', 'driver', 'mflm',
                 'ctd', 'resource')

@attr('UNIT', group='mi')
class CtdmoParserUnitTestCase(ParserUnitTestCase):

    def create_rec_co_parser(self, file_handle, new_state=None):
        """
        This function creates a Ctdmo parser for recovered CO data.
        """
        if new_state is None:
            new_state = self.state
        parser = CtdmoRecoveredCoParser(self.config_rec_co, new_state, file_handle,
            self.rec_state_callback, self.pub_callback, self.exception_callback)
        return parser

    def create_rec_ct_parser(self, file_handle, new_state=None):
        """
        This function creates a Ctdmo parser for recovered CT data.
        """
        if new_state is None:
            new_state = self.state
        parser = CtdmoRecoveredCtParser(self.config_rec_ct, new_state, file_handle,
            self.rec_state_callback, self.pub_callback, self.exception_callback)
        return parser

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                ['CtdmoTelemeteredInstrumentDataParticle',
                 'CtdmoTelemeteredOffsetDataParticle'],
            CtdmoStateKey.INDUCTIVE_ID: 55
        }

        self.config_rec_co = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredOffsetDataParticle',
            CtdmoStateKey.INDUCTIVE_ID: 55
        }

        self.config_rec_ct = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredInstrumentDataParticle',
            CtdmoStateKey.INDUCTIVE_ID: 55,
            CtdmoStateKey.SERIAL_NUMBER: '03710261'
        }

        # all indices give in the comments are in actual file position, not escape sequence replace indices
        # packets have the same timestamp, the first has 3 data samples [394-467]
        self.particle_a = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF36D6',
             b'\x37',
             b'\x39\x4c\xe0\xc3\x54\xe6\x0a',
             b'\x81\xd5\x81\x19'))

        # this is the start of packet 2 [855:1045]
        self.particle_b = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF52F6',
             b'7',
             b'7\xf0\x00\xc3T\xe5\n',
             b'\xa1\xf1\x81\x19'))
        
        # this is the start of packet 3 [1433:1623]
        self.particle_c = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF6F16',
             b'7',
             b'6$p\xc3T\xe4\n',
             b'\xc1\r\x82\x19'))
        
        # this is the start of packet 4 [5354:5544]
        self.particle_d = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF8B36',
             b'\x37',
             b'\x35\x8b\xe0\xc3T\xe5\n',
             b'\xe1)\x82\x19'))
        
        # this is the start of packet 5 [6321:6511]
        self.particle_e = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFC376',
             b'7',
             b'7\x17\xd6\x8eI;\x10',
             b'!b\x82\x19'))
        
        # start of packet 6 [6970-7160]
        self.particle_f = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFDF96',
             b'\x37',
             b'\x36\xe7\xe6\x89W9\x10',
             b'A~\x82\x19'))
        
        # packet 7 [7547-7737]
        self.particle_g = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFFBB6',
             b'\x37',
             b'\x32\t6F\x0c\xd5\x0f',
             b'a\x9a\x82\x19'))

        # first offset at 9543
        self.particle_a_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F05016', b'7', b'\x00\x00\x00\x00'))

        # in long file, starts at 13453
        self.particle_z = CtdmoTelemeteredInstrumentDataParticle(
            (b'51F0A476',
             b'7',
             b'3\xb9\xa6]\x93\xf2\x0f',
             b'!C\x83\x19'))

        # in longest file second offset at 19047
        self.particle_b_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F1A196', b'7', b'\x00\x00\x00\x00'))
        
        # third offset at 30596
        self.particle_c_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F2F316', b'7', b'\x00\x00\x00\x00'))

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def assert_result(self, result, in_process_data, unprocessed_data, particle):
        self.assertEqual(result, [particle])
        self.assert_state(in_process_data, unprocessed_data)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def assert_state(self, in_process_data, unprocessed_data):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)

    def test_simple(self):
        """
        Read test data from the file and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                  'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, None,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        log.debug('===== TEST SIMPLE GET RECORD 1 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
             [[853,1043,1,0], [1429,1619,1,0], [5349,5539,1,0],
                 [6313,6503,1,0], [6958,7148,1,0], [7534,7724,1,0]],
             [[0, 12], [336, 394], [853,1043], [1429,1619], [5349,5539],
                 [5924,5927], [6313,6503], [6889,7148], [7534,7985]],
             self.particle_a)

        log.debug('===== TEST SIMPLE GET RECORD 2 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[1429,1619,1,0], [5349,5539,1,0], [6313,6503,1,0],
                [6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [1429,1619], [5349,5539], [5924,5927],
                [6313,6503], [6889,7148], [7534,7985]],
            self.particle_b)

        log.debug('===== TEST SIMPLE GET RECORD 3 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0],
                [7534,7724,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7148], [7534,7985]],
            self.particle_c)

        log.debug('===== TEST SIMPLE GET RECORD 4 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[6313,6503,1,0], [6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5924,5927], [6313,6503], [6889,7148],
                [7534,7985]],
            self.particle_d)

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_missing_inductive_id_config(self):
        """
        Make sure that the driver complains about a missing inductive ID in the config
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 8000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        bad_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoTelemeteredInstrumentDataParticle',
            }
        with self.assertRaises(DatasetParserException):
            self.parser = CtdmoTelemeteredParser(bad_config, self.state,
                self.stream_handle, self.state_callback,
                self.pub_callback, self.exception_callback)

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 7500]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.state,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(5)
        self.stream_handle.close()
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_d, self.particle_e])
        self.assert_state([[6958,7148,1,0]],
                           [[0, 12], [336, 394], [5924,5927], [6889,7500]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 14000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_longer.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.state,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(13)
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[9], self.particle_a_offset)
        self.assertEqual(result[-1], self.particle_z)
        self.assert_state([],
            [[0, 12], [336, 394], [5924,5927],  [6889, 6958], [8687,8756], 
               [8946,9522], [13615, 14000]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_longest_for_co(self):
        """
        Test an even longer file which contains more of the CO samples
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_longest.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, None,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(36)
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[9], self.particle_a_offset)
        self.assertEqual(result[12], self.particle_z)
        self.assertEqual(result[22], self.particle_b_offset)
        self.assertEqual(result[-1], self.particle_c_offset)

        self.assert_state([],
            [[0, 12], [336, 394], [5924,5927],  [6889, 6958], [8687,8756], 
             [8946,9522], [14576,14647], [16375,16444], [18173,18240],
             [20130,20199], [21927,21996], [29707,29776], [30648,30746]])

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [1429,7500]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, new_state,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7500]],
            self.particle_c)
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {
            StateKey.IN_PROCESS_DATA:
                [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0],
                    [7534,7724,1,0]],
            StateKey.UNPROCESSED_DATA:
                [[0, 12], [336, 394], [5349,5539], [5924,5927],
                    [6313,6503], [6889,7148], [7534,7985]]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, new_state,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_d)
        self.assertEqual(result[-1], self.particle_e)
        self.assert_state([[6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5924,5927], [6889,7148], [7534,7985]])

        self.assertEqual(self.publish_callback_value[-1], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 500]],
                      StateKey.IN_PROCESS_DATA:[]}

        new_state = {
            StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [1429,7500]],
            StateKey.IN_PROCESS_DATA:[]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.state,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        # there should only be 1 records, make sure we stop there
        result = self.parser.get_records(1)
        self.assertEqual(result[0], self.particle_a)
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7500]],
            self.particle_c)

        self.assertEqual(self.exception_callback_value, None)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        # this file has a block of CT data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replace.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, None,
             self.stream_handle, self.state_callback,
             self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)

        # particle d has been replaced in this file with zeros
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_e])
        self.assert_state([[6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927], [6889,7148],
                [7534,7985]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_e)

        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of CT data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, next_state,
            self.stream_handle, self.state_callback,
            self.pub_callback, self.exception_callback)

        # first get the old 'in process' records from [6970-7160]
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_f, self.particle_g])
        self.assert_state([],
            [[0, 12], [336, 394], [5349,5539], [5924,5927], [6889,6958],
                [7724,7985]])

        self.assertEqual(self.publish_callback_value[0], self.particle_f)
        self.assertEqual(self.publish_callback_value[1], self.particle_g)

        # this should be the first of the newly filled in particles from [5354-5544]
        result = self.parser.get_records(1)
        self.assert_result(result,
            [],
            [[0, 12], [336, 394], [5924,5927], [6889,6958], [7724,7985]],
            self.particle_d)

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)


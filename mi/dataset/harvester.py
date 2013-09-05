#!/usr/bin/env python

"""
@package mi.dataset.harvester A collection of polling routines that pull
data out of some source (an external file?) and put them into the ION system
via data set agents.
@file mi/dataset/harvester.py
@author Steve Foley
@brief Base classes for data set agent pollers
"""

__author__ = 'Christopher Mueller, Jonathan Newbrough, Steve Foley'
__license__ = 'Apache 2.0'

import os

from mi.core.log import get_logger ; log = get_logger()
from ooi.poller import DirectoryPoller, ConditionPoller

class Harvester(object):
    """ abstract class to show API needed for plugin poller objects """
    def __init__(self, config, memento, data_callback, exception_callback):  
        pass

    def start(self): 
        pass

    def shutdown(self): 
        pass
    
    def connect_to_source(self):
        """
        Trigger a connection to the data source using the configuration
        information for this stream. 
        """
        pass

## other pollers that check HTTP, FTP or other methods of finding data may be
## added here down the road

class AdditiveSequentialFileHarvester(DirectoryPoller, Harvester):
    """
    Poll a single directory looking for new files with the directory poller.
    """
    def __init__(self, config, memento, file_callback, exception_callback):
        if not isinstance(config, dict):
            raise TypeError("Config object must be a dict")

        self.callback = file_callback
        self.last_file_completed = memento
        DirectoryPoller.__init__(self,
                                 config['directory'],
                                 config['pattern'],
                                 self.on_new_files,
                                 exception_callback,
                                 config.get('frequency', 1))

    def on_new_files(self, files):
        """
        New files have been found, open each file and process it in the callback
        """
        for file in files:
            if file>self.last_file_completed:
                with open(file,'rb') as f:
                    self.callback(f, file)
                    
            
class FilePoller(ConditionPoller):
    """
    poll a single file to determine if that file has had additional data appended to it
    """
    
    def __init__(self, fullfile, last_read_offset, callback, exception_callback=None, interval=1):
        """
        @param fullfile full file path to the file to monitor
        @param last_read_offset offset of the last byte read in this file (can be None)
        @param callback the callback to call when new data has been found in the file
        @param exception_callback the callback to call when an exception has occurred
        @param interval the interval between checking on the file in seconds
        """
        try:
            if not os.path.isfile(fullfile):
                raise ValueError('%s is not an existing file'%fullfile)
            self._file = fullfile
            self._last_offset = last_read_offset
            super(FilePoller,self).__init__(self._check_for_data, callback, exception_callback, interval)
        except:
            log.error('failed init?', exc_info=True)
            
    def _check_for_data(self):
        """
        find out how the last file offset relates to the current file size.  If it is less than the current file size, return the 
        """
        filesize = os.path.getsize(self._file)
        # files, but no change since last time
        log.debug("Checking file size, size is %d, last offset is %s", filesize, str(self._last_offset))
        if filesize == 0:
            # file is empty
            return None
        if self._last_offset and filesize and filesize==self._last_offset:
            # no change since last filesize
            return None
        self._last_offset = filesize
        return self._file
    
    
class SingleFileHarvester(FilePoller, Harvester):
    """
    Poll a single file to determine if data has been appended to the file
    """
    def __init__(self, config, last_read_offset, data_callback, exception_callback):
        """
        @param config a configuration dictionary containing harvester config
        @param last_read_offset offset of the last byte read in this file (can be None)
        @param data_callback the callback to call when new data has been found in the file
        @param exception_callback the callback to call when an exception has occurred
        """
        if not isinstance(config, dict):
            raise TypeError("Config object must be a dict")
        
        self.fullfile = config['directory'] + '/' + config['filename']
        self.callback = data_callback
        self.last_offset = last_read_offset
        
        FilePoller.__init__(self, self.fullfile,
                            self.last_offset,
                            self.on_new_data,
                            exception_callback,
                            config.get('frequency', 1))
        
    def on_new_data(self, fullfile):
        """
        When new data has been found, open the file and seek to the last
        offset if there is one
        """
        if fullfile:
            filesize = os.path.getsize(fullfile)
            with open(fullfile, 'rb') as f:
                self.callback(f, filesize)


class SortingDirectoryPoller(ConditionPoller):
    """
    poll for new files added to a directory that match a wildcard pattern.
    expects files to be added which can have several separate IDs separated with underscores
    these will be sorted from left to right as integers (not ascii)
    """
    def __init__(self, directory, wildcard, callback, exception_callback=None, interval=1):
        try:
            if not os.path.isdir(directory):
                raise ValueError('%s is not a directory'%directory)
            self._path = directory + '/' + wildcard
            self._last_filename = None
            super(DirectoryPoller,self).__init__(self._check_for_files, callback, exception_callback, interval)
        except:
            log.error('failed init?', exc_info=True)
            
    def _check_for_files(self):
        unsorted_filenames = glob.glob(self._path)
        filenames = self._sort_files(unsorted_filenames)
        # files, but no change since last time
        if self._last_filename and filenames and filenames[-1]==self._last_filename:
            return None
        # no files yet, just like last time
        if not self._last_filename and not filenames:
            return None
        if self._last_filename:
            position = filenames.index(self._last_filename) # raises ValueError if file was removed
            out = filenames[position+1:]
        else:
            out = filenames
        self._last_filename = filenames[-1]
        log.trace('found files: %r', out)
        return out
    
    def _sort_files(self, filenames):
        """
        Sorts files which have multiple indices separated by underscores in a file name.
        Ascii sorting will sort '16' less than '6', so separate by underscores, turn into
        integers, then sort
        """
        # this assumes all files have the same extension
        file_extension = filenames[0].split('.')
        
        split_names = ()
        for fn in filenames:
            # remove file extension and split by underscores
            split_name = fn.replace('.' + file_extension, '').split('_')
            for i in range(0, len(split_name)):
                # if this part of the filename can be turned into an int, do it
                try:
                    int_val = int(split_name[i])
                    split_name[i] = int_val
                except ValueError:
                    # ignore error
            
            # append this split up name as a tuple
            split_names = split_names + (split_name, )
        # now sort all the int formatted names
        split_names.sort()
        # put the filenames back to string format
        sorted_filenames = []
        i = 0
        for fn in split_names:
            # recombine files with underscores
            this_file = ''
            for item in fn:
                this_file = this_file + str(item) + '_'
            # remove the last underscore, and add the file extension back in
            sorted_filenames[i] = this_file[:-1] + '.' + file_extension
            i++
            
        return sorted_filenames
        
        
    

__author__ = 'Bill French'

import argparse

from mi.idk.platform.which_driver import WhichDriver

def run():
    app = WhichDriver()
    app.run()
   

if __name__ == '__main__':
    run()

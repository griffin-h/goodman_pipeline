from __future__ import print_function
import os
from ccdproc import ImageFileCollection
import matplotlib.pyplot as plt
import time
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
import re
import glob
import logging
import argparse
from data_classifier import DataClassifier
from night_organizer import NightOrganizer
from image_processor import ImageProcessor

FORMAT = '%(levelname)s: %(asctime)s: %(module)s: %(message)s'
DATE_FORMAT = '%m/%d/%Y %I:%M:%S%p'
logging.basicConfig(level=logging.DEBUG, format=FORMAT, datefmt=DATE_FORMAT)
log = logging.getLogger('goodmanccd')


class MainApp(object):
    def __init__(self):
        self.args = self.get_args()
        self.data_container = None
        self.full_path = None
        self.instrument = None
        self.technique = None
    
    def __call__(self, *args, **kwargs):
        folders = glob.glob(re.sub('//', '/', '/'.join(self.args.raw_path.split('/') + ['*'])))
        # print(re.sub('//', '/', '/'.join(self.args.raw_path.split('/') + ['*'])))
        if any('.fits' in item for item in folders):
            folders = [self.args.raw_path]
        for data_folder in folders:
            # check start
            self.args.raw_path = data_folder
            if self.args.red_path == './RED' or len(folders) > 1:
                log.info('No special reduced data path defined. Proceeding with defaults.')
                if self.args.raw_path not in self.args.red_path:
                    self.args.red_path = re.sub('//', '/', '/'.join(self.args.raw_path.split('/') + ['RED']))
                    print(self.args.red_path)
            if os.path.isdir(self.args.red_path):
                # TODO (simon): warn if folder is not empty
                self.args.red_path = os.path.abspath(self.args.red_path)
                log.debug(os.path.abspath(self.args.red_path))
            else:
                try:
                    log.warning("Reduction folder doesn't exist.")
                    os.mkdir(os.path.abspath(self.args.red_path))
                    log.info('Created reduced data directory!')
                    log.info(os.path.abspath(self.args.red_path))
                except OSError as error:
                    log.error(error)
            # check ends
            night_sorter = DataClassifier(self.args)
            night_sorter()
            self.instrument = night_sorter.instrument
            self.technique = night_sorter.technique
            # print(night_sorter.nights_dict)
            for night in night_sorter.nights_dict:
                # print(night_sorter.nights_dict[night])
                night_organizer = NightOrganizer(args=self.args, night_dict=night_sorter.nights_dict[night])
                self.data_container = night_organizer()
                if self.data_container is False or self.data_container is None:
                    log.error('Discarding night ' + str(night))
                    break
                process_images = ImageProcessor(self.args, self.data_container)
                process_images()

                # for group in self.data_container.data_groups:
                #     print('\nNew group ')
                #     print(group.file)

            # # this is intended for letting a global app wether to continue with the spectroscopic part.
            # if night_sorter.technique == 'Spectroscopy':
            #     return True
            # else:
            #     return False

    @staticmethod
    def get_args():
        # Parsing Arguments ---
        parser = argparse.ArgumentParser(description="PyGoodman CCD Reduction - CCD reductions for "
                                                     "Goodman spectroscopic data")

        # parser.add_argument('-c', '--clean',
        #                     action='store_true',
        #                     help="Clean cosmic rays from science data.")

        # # removed because is not working properly
        # parser.add_argument('-s', '--slit', action='store_true',
        #                     help="Find slit edge to make an additional trimming (Maintainer: Not recommended for now).")

        # remove saturated data
        parser.add_argument('--remove-saturated',
                            action='store_true',
                            dest='remove_saturated',
                            help="Remove images above saturation level")

        parser.add_argument('--ignore-bias',
                            action='store_true',
                            dest='ignore_bias',
                            help="Ignore bias correction")

        parser.add_argument('--saturation',
                            action='store',
                            default=55000.,
                            dest='saturation_limit',
                            metavar='<Value>',
                            help="Saturation limit. Default to 55.000 ADU (counts)")

        parser.add_argument('--raw-path',
                            action='store',
                            metavar='raw_path',
                            default='./',
                            type=str,
                            help="Path to raw data (e.g. /home/jamesbond/soardata/).")

        parser.add_argument('--red-path',
                            action='store',
                            metavar='red_path',
                            type=str,
                            default='./RED',
                            help="Full path to reduced data (e.g /home/jamesbond/soardata/RED/).")

        # parser.add_argument('--red-camera', action='store_true', default=False, dest='red_camera',
        #                    help='Enables Goodman Red Camera')

        args = parser.parse_args()
        if os.path.isdir(args.raw_path):
            args.raw_path = os.path.abspath(args.raw_path)
            log.debug(os.path.abspath(args.raw_path))
        else:
            parser.print_help()
            parser.exit("Raw data folder doesn't exist")

        return args




if __name__ == '__main__':
    # path = '/data/simon/data/soar/work/20170208_eng/2017-02-08_clean'
    # path = '/user/simon/data/soar/raw/spectroscopy_engineering_night/'
    # path = '/data/simon/data/soar/raw/2017-02-08'
    # path = '/user/simon/data/soar/work2'
    # path = '/user/simon/data/soar/work/20161114_eng_2'
    # path = '/user/simon/data/soar/work/imaging/2017-01-11'
    main_app = MainApp()
    main_app()
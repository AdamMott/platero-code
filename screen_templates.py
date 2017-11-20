#!/usr/bin/env python

"""
Generate the screening templates for the specified batches
"""

import os
import logging
import argparse

from sqlalchemy import func
from platero.commands import CliCommand, arg_is_valid_directory
from platero.model.queries import get_batch_proteins, get_plates

from platero.wellplate import *
from platero.model.models import BatchProtein, Plate
from platero.model.naming import *
from platero.platero import db, config
from platero.templates import export_storage_plate, export_screen_plate
from storage_templates import arg_batch_ids

def create_screen_plates(bait_batch_id, prey_batch_id, outfolder):
    metadata = OrderedDict()
    metadata['Plate name'] = ''
    metadata['Plate type'] = 'Screen'
    metadata['Timeshift'] = ''
    metadata['Bait plate'] = ''
    metadata['Prey plate'] = storage_prey_plate_name(prey_batch_id)

    # Same prey plate for all screen plates
    prey_prots = get_batch_proteins(prey_batch_id)
    prey_plate = PreyStoragePlate(prey_prots)
    prey_plate.name = storage_prey_plate_name(prey_batch_id)

    # 2 bait proteins per plate

    bait_prots = get_batch_proteins(bait_batch_id)
    for i in range(0, len(bait_prots), ScreenPlate.capacity()):
        plate = Plate(bait_batch_id=bait_batch_id, prey_batch_id=prey_batch_id)
        db.add(plate)
        db.flush()
        baits = bait_prots[i:i + ScreenPlate.capacity()]

        bait_plate_name = storage_bait_plate_name(bait_batch_id, BaitStoragePlate.bait_plate_index(i))
        screen_plate = ScreenPlate(baits, bait_plate_name, BaitStoragePlate.bait_plate_offset(i), prey_plate)
        screen_plate.name = screen_plate_name(plate.id)

        metadata['Plate name'] = screen_plate.name
        metadata['Bait plate'] = bait_plate_name
        metadata['Prey plate'] = screen_plate.prey_plate_name
        template_file = os.path.join(outfolder, '{}_b{:02d}_p{:02d}_template.xlsx'.format(
            screen_plate.name, bait_batch_id, prey_batch_id))
        export_screen_plate(template_file, screen_plate, metadata)
        logging.info("Saved screen template to {}".format(template_file))

        # Save to database
        db.commit()
        # TODO: save template?


class ScreenTemplates(CliCommand):
    short_description = "Generate the screen templates for the specified batches"

    @classmethod
    def _arg_parser(cls):
        parser = argparse.ArgumentParser(description='Generate the screen templates for the specified batches')
        parser.add_argument('bait_ids', type=lambda x: arg_batch_ids(parser, x),
                            help='Id(s) of the batch(es) to use as BAIT. Multiple ids can be specified as a comma separated list')
        parser.add_argument('prey_ids', type=lambda x: arg_batch_ids(parser, x),
                            help='Id(s) of the batch(es) to use as PREY. Multiple ids can be specified as a comma separated list')
        parser.add_argument('outfolder', type=lambda x: arg_is_valid_directory(parser, x),
                            help='Path to directory where the templates will be saved')

        return parser

    @classmethod
    def _main(cls, args):
        for bait_batch_id in args.bait_ids:
            for prey_batch_id in args.prey_ids:
                if get_plates(bait_batch_id, prey_batch_id).count():
                    logging.info("Skipped screen templates for batches {} vs {}, already generated".format(
                                 bait_batch_id, prey_batch_id))
                else:
                    logging.info("Generating screen templates for batches {} vs {}".format(
                                 bait_batch_id, prey_batch_id))
                    create_screen_plates(bait_batch_id, prey_batch_id, args.outfolder)


if __name__ == '__main__':
    ScreenTemplates.run()

#!/usr/bin/env python

"""
Generate the storage templates for the specified batches
"""

import os
import argparse
import logging
from collections import OrderedDict

from platero.commands import CliCommand, arg_is_valid_directory

from platero.wellplate import PreyStoragePlate, BaitStoragePlate
from platero.model.queries import get_batch_proteins
from platero.model.naming import batch_name, storage_prey_plate_name, storage_bait_plate_name
from platero.templates import export_storage_plate

def create_storage_templates(batch_id, outfolder):
    proteins = get_batch_proteins(batch_id)

    # Prey storage plate
    prey_plate = PreyStoragePlate(proteins)
    prey_plate.name = storage_prey_plate_name(batch_id)

    metadata = OrderedDict()
    metadata['Plate name'] = prey_plate.name
    metadata['Plate type'] = 'Prey storage'
    metadata['Batch name'] = batch_name(batch_id)
    template_file = os.path.join(outfolder, '{}.xlsx'.format(prey_plate.name))
    logging.info("Saved storage template to {}".format(template_file))
    export_storage_plate(template_file, prey_plate, metadata)

    # Bait storage plates
    metadata = OrderedDict({
        'Plate name': '',
        'Plate type': 'Bait storage',
        'Batch name': batch_name(batch_id)
    })

    bait_plates = []
    for i in range(0, len(proteins), BaitStoragePlate.capacity()):
        baits = proteins[i:i + BaitStoragePlate.capacity()]

        bait_plate = BaitStoragePlate(baits)
        bait_plate.name = storage_bait_plate_name(batch_id, BaitStoragePlate.bait_plate_index(i))
        bait_plates.append(bait_plate)

        # print(bait_plate)
        metadata['Plate name'] = bait_plate.name
        template_file = os.path.join(outfolder, '{}.xlsx'.format(bait_plate.name))
        export_storage_plate(template_file, bait_plate, metadata)
        logging.info("Saved storage template to {}".format(template_file))

    return prey_plate, bait_plates



class BatchStorageTemplates(CliCommand):
    short_description = "Generate the storage templates"

    @classmethod
    def _arg_parser(cls):
        parser = argparse.ArgumentParser(description='Generate the storage templates for the specified batch')
        parser.add_argument('batch_ids', type=lambda x: arg_batch_ids(parser, x),
                            help=('Id(s) of the batch for which to generate the storage plates. '
                                  'Multiple ids can be specified as a comma separated list'))
        parser.add_argument('outfolder', type=lambda x: arg_is_valid_directory(parser, x),
                            help='Path to directory where the templates will be saved')
        return parser

    @classmethod
    def _main(cls, args):
        for batch_id in args.batch_ids:
            logging.info("Generating storage templates for batch {}".format(batch_id))
            create_storage_templates(batch_id, args.outfolder)

def arg_batch_ids(parser, arg):
    try:
        return [int(x) for x in arg.split(',')]
    except ValueError as exc:
        parser.error('Value {} is not a valid list of numeric ids'.format(arg))


if __name__ == '__main__':
    BatchStorageTemplates.run()

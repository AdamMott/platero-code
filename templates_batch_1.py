#!/usr/bin/env python

"""
Create templates for the plates in the first batch
"""
import argparse
from collections import OrderedDict
import os
import pandas as pd

from platero.commands import CliCommand, arg_is_valid_directory
from platero.platero import db
from platero.model.queries import get_batch_proteins, save_template
from platero.model.naming import screen_plate_name
from platero.model.models import Plate, PlateCell
from platero.parsing.parsing import iterate96WP, reverse
from platero.templates import TemplateWorkbook, NEG_CONTROL, POS_CONTROL, DELIMITER
from platero.assets import SCREEN_PLATE_TEMPLATE


def parse_1st_batch_list(filepath):
    """ Parse the reference XLS file for the first batch of plates """
    book = pd.ExcelFile(filepath)

    # Parse list of plates, returning as list of dictionaries
    df = book.parse(0, parse_cols=4)
    df.columns = ['filename', 'Bait_1', 'Bait_2', 'timepoint']
    df['filename'] = df['filename'].str.strip()
    df['Bait_1'] = df['Bait_1'].str.strip()
    df['Bait_2'] = df['Bait_2'].str.strip()
    df.fillna('', inplace=True)
    plates = df.to_dict('records')

    # Parse template into dictionary
    df = book.parse(1)
    df.fillna('', inplace=True)
    df.replace('^p2$', NEG_CONTROL, regex=True, inplace=True)
    df.replace('^pos contr$', POS_CONTROL, regex=True, inplace=True)
    template = {}
    for index, row in df.iterrows():
        for col, value in row.iteritems():
            cell = "{}{}".format(index, col)
            template[cell] = {'bait': '', 'prey': value.strip()}

    return plates, template


def replace_prey_symbols(template, prots_by_symbol):
    for (cell, row, col) in iterate96WP():
        if template[cell]['prey'] not in [POS_CONTROL, NEG_CONTROL,'']:
            template[cell]['prey'] = prots_by_symbol[template[cell]['prey']]


def add_baits(base_template, bait_1, bait_2=None):
    """ Prepare a template from the first batch of plates """
    template = {}
    for cell in base_template:
        template[cell] = {'bait': '', 'prey': ''}
        bait = bait_1 if int(cell[1:]) <= 6 else bait_2
        if bait:
            template[cell]['prey'] = base_template[cell]['prey']
            if base_template[cell]['prey'] == POS_CONTROL:
                template[cell]['bait'] = POS_CONTROL
            elif base_template[cell]['prey']:
                template[cell]['bait'] = bait
            else:
                template[cell]['bait'] = ''

    return template

def export_1st_batch_plate(plate_name, cells, metadata, outfolder):
    ws_template = 'Template'
    rng_template_proteins = 'rng_template_proteins'
    rng_template_nicknames = 'rng_template_nicknames'
    rng_template_labels = 'rng_template_labels'

    ws_pipetting = 'Pipetting'

    wb = TemplateWorkbook(SCREEN_PLATE_TEMPLATE)

    # Template sheet
    plate_label = 'Plate: {}'.format(plate_name)
    wb.set_cell_range(ws_template, rng_template_labels, [plate_label])

    nicknames = []
    proteins = []

    for (id, row, col) in iterate96WP():
        cell = cells[id]
        if cell['prey'] == POS_CONTROL:
            nickname = protein = POS_CONTROL
        elif cell['prey'] == NEG_CONTROL:
            nickname = protein = NEG_CONTROL
        elif cell['prey']:
            protein = "{}{}{}".format(cell['bait'].id, DELIMITER, cell['prey'].id)
            nickname = "{}{}{}".format(cell['bait'].nickname, DELIMITER, cell['prey'].nickname)
        else:
            nickname = protein = ''

        nicknames.append(nickname)
        proteins.append(protein)

    wb.set_cell_range(ws_template, rng_template_proteins, proteins)
    wb.set_cell_range(ws_template, rng_template_nicknames, nicknames)

    # Pipetting sheet (remove)
    wb.remove_sheet_by_name(ws_pipetting)

    wb.set_info(metadata)
    wb.save(os.path.join(outfolder, '{}_b01_p01_template.xlsx'.format(plate_name)))


def plates_first_batch(first_batch_list, outfolder):
    batch_id = 1

    metadata = OrderedDict()
    metadata['Notes'] = 'Generated from the original batch 1 template'
    metadata['Batch 1 file'] = ''

    plates, base_template = parse_1st_batch_list(first_batch_list)
    # Index ids for batch, by sybmol
    proteins = get_batch_proteins(batch_id)
    prots_by_symbol = {protein.symbol:protein for protein in proteins}

    replace_prey_symbols(base_template, prots_by_symbol)

    # Remove plates from db
    db.query(Plate).filter(Plate.bait_batch_id==batch_id,
                           Plate.prey_batch_id==batch_id
                           ).delete()

    for id, plate in enumerate(plates):
        bait_1 = prots_by_symbol.get(plate['Bait_1'], None)
        bait_2 = prots_by_symbol.get(plate['Bait_2'], None)

        template = add_baits(base_template, bait_1, bait_2)

        # Plate 4 of the first batch was put turned 180 in the reader
        if plate['filename'] == 'batch 4 SERK1 BAK1':
            template = reverse(template)

        plate_id = id + 1
        plate_name = screen_plate_name(plate_id)
        metadata['Batch 1 file'] = plate['filename']
        metadata['Timeshift'] = plate['timepoint']

        # Save plate to database
        plate = Plate(id=plate_id, bait_batch_id=batch_id, prey_batch_id=batch_id)
        db.add(plate)
        db.commit()
        save_template(plate_id, template)

        # TODO: export plate from database?
        export_1st_batch_plate(plate_name, template, metadata, outfolder)



class PlatesFirstBatch(CliCommand):
    short_description = "Generate the templates for the screening plates in the first batch"

    @classmethod
    def _arg_parser(cls):
        parser = argparse.ArgumentParser(description='Generate the templates for the screening plates in the first batch')
        parser.add_argument('first_batch_list', type=argparse.FileType('rb'),
                            help='An excel file containing the information for the plates in the first batch')
        parser.add_argument('outfolder', type=lambda x: arg_is_valid_directory(parser, x),
                            help='Path to directory where the templates will be saved')

        return parser

    @classmethod
    def _main(cls, args):
        plates_first_batch(args.first_batch_list.name, args.outfolder)


if __name__ == '__main__':
    PlatesFirstBatch.run()

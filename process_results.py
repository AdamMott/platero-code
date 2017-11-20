#!/usr/bin/env python

"""
Reads the screening plates and generates the screen data to be used
for heatmaps and protein interaction graphs
"""
import argparse
import logging
import re

from collections import OrderedDict
import os
import pandas as pd

from platero.commands import CliCommand, arg_is_valid_directory
from platero.utils import find_files
from platero.parsing.parsing import parse_plate_results

from platero.platero import db
from platero.model.models import Plate, PlateCell, BatchProtein
from platero.parsing.parsing import iterate96WP
from platero.templates import NEG_CONTROL, POS_CONTROL, DELIMITER, DELIMITER_RE


PROTEIN_LABELS = {}
PROTEIN_FAMILIES = {}
PROTEIN_SUBFAMILIES = {}

for bp in db.query(BatchProtein):
    PROTEIN_LABELS[bp.protein.id] = bp.protein.label
    PROTEIN_FAMILIES[bp.protein.id] = bp.protein.family
    PROTEIN_SUBFAMILIES[bp.protein.id] = bp.protein.subfamily


from platero.utils import filter_digits
def control_index(cell_id):
    # TODO: what a hack!
    return (filter_digits(cell_id) - 1) // 6

def get_interaction_values(reads, timepoint, template):
    '''
    Map the reads of a certain timepoint to a given template and normalize
    values to controls
    '''

    # Get reads for specified timepoint
    timepoint_reads = reads.loc[reads['Time'] == timepoint]
    if timepoint_reads.empty:
        raise ValueError('Invalid timepoint ({}) for provided plate reads'.format(timepoint))
    cell_values = timepoint_reads.ix[:, template.keys()].squeeze().to_dict()

    # Merge protein information from template with read values
    data = []
    controls = {}
    for cell_id, interaction in template.items():
        if interaction == NEG_CONTROL:
            controls.setdefault(control_index(cell_id), []).append(cell_values[cell_id])
            logging.debug("Added control {} ({}, {})".format(cell_values[cell_id],
                                                     cell_id,
                                                     control_index(cell_id)))
        elif type(interaction) == dict:
            row = {
                'Value': cell_values[cell_id],
                'PlateCell': cell_id,
                'BaitId': interaction['bait'],
                'PreyId': interaction['prey'],
                'ControlId': control_index(cell_id),
            }
            data.append(row)
            logging.debug("Added values {} ({})".format(cell_values[cell_id], cell_id))

    # Create data frame
    df = pd.DataFrame(data)

    if len(df[df.Value <= 0]) > 0:
        print(df[df.Value <= 0])
        logging.warning("Some reads in the plate contain invalid values (<=0)!")

    # Add protein symbols
    protein_labels = {bp.protein.id:bp.protein.label for bp in db.query(BatchProtein)}
    df['Bait'] = df.BaitId.map(PROTEIN_LABELS)
    df['Prey'] = df.PreyId.map(PROTEIN_LABELS)
    df['BaitFamily'] = df.BaitId.map(PROTEIN_FAMILIES)
    df['BaitSubfamily'] = df.BaitId.map(PROTEIN_SUBFAMILIES)
    df['PreyFamily'] = df.PreyId.map(PROTEIN_FAMILIES)
    df['PreySubfamily'] = df.PreyId.map(PROTEIN_SUBFAMILIES)

    # Calculate and add normalized values
    controls = {i:(sum(controls[i])/len(controls[i])) for i in controls}
    df['NC'] = df.ControlId.map(controls)
    df['Normalized'] = df.Value/df.NC

    return df


from platero.parsing.parsing import read_excel_list
from platero.templates import DELIMITER
from openpyxl import load_workbook

def parse_interaction(text):
    if text in [POS_CONTROL, NEG_CONTROL, '', None]:
        return text

    proteins = DELIMITER_RE.split(text)
    if len(proteins) != 2:
       logging.warning("Couldn't extract bait and prey from a plate template cell ({})".format(text))
    return dict( zip(['bait', 'prey'], [x.strip().upper() for x in proteins]) )


def parse_plate_template(filepath):
    """ Process a template file, returning a ?? TODO: ?? and the metadata (timepoint) """
    logging.debug("Parsing plate template has: {}".format(filepath))
    df = read_excel_list(filepath, 'Info', {'A':'Field', 'B':'Value'})
    info = pd.Series(df.Value.values,index=df.Field).to_dict()

    wb = load_workbook(filepath, read_only=True)
    ws = wb.get_sheet_by_name('Template')
    cells = ws.get_named_range('rng_template_proteins')

    # TODO: support multiple plate sizes via metadata or guessing?
    template = OrderedDict()
    for position, cell in zip(iterate96WP(), cells):
        cell_id = position[0]
        template[cell_id] = parse_interaction(cell.value)

    return template, info


def process_results_plate(results_path, template_path):
    """
    Process a single results plate and return the interaction data
    """
    reads, plate_info = parse_plate_results(results_path)

    template, template_info = parse_plate_template(template_path)
    timeshift = template_info['Timeshift']
    if not timeshift:
        logging.error("Plate template has no valid 'Timeshift' value in the 'Info' sheet ({})".format(filepath))
        return None
    logging.debug("Timeshift found: {}".format(timeshift))

    df = get_interaction_values(reads, timeshift, template)
    # TODO: very hackish!!! use template info instead (currently not available in templates for batch 1)
    df['Plate'] = filter_digits(results_path.split('/plate_')[1].split('_')[0])

    return df

def export_results(df, outfolder, basename):
    columns = ['Bait', 'Prey', 'Normalized', 'Value', 'NC', 'Plate', 'PlateCell',
               'BaitId', 'BaitFamily', 'BaitSubfamily', 'PreyId', 'PreyFamily', 'PreySubfamily']

    # TODO: just one excel file with multiple sheets (fix openpyxl dependency)
    outfile = os.path.join(outfolder, '{}.xls'.format(basename))
    df.to_excel(outfile, index=False, columns=columns, sheet_name='Data')

    ctdf = df.fillna(0).sort(['PreyFamily', 'PreySubfamily']).pivot_table(index=['PreyFamily', 'PreySubfamily', 'Prey'], columns=['BaitFamily', 'BaitSubfamily', 'Bait'], values='Normalized')


    ctdf.reset_index(inplace=True)
    ctdf.rename(columns={'Prey':'Prey vs Bait'}, inplace=True)

    # Check if missing values
    n_blanks = ctdf.isnull().sum().sum()
    if n_blanks > 0:
        logging.warning("Some interaction comparison values are missing (a total of {})".format(n_blanks))

    outfile = os.path.join(outfolder, '{}_crosstab.csv'.format(basename))
    ctdf.to_csv(outfile, index=False, sheet_name='Data')

    # TODO: failing with missing values/NaN
    # from bokeh.charts import HeatMap, output_file, show
    # from bokeh.palettes import RdBu9 as palette
    # import numpy as np
    # hm = HeatMap(ctdf.fillna(0), title="Interaction level", xlabel="Bait", ylabel="Prey", width=1200, height=1200, palette=palette)
    # output_file(os.path.join(outfolder, '{}.html'.format(basename)))
    # show(hm)


def process_results(datafolder, outfolder):
    """
    Reads the screening plates and genereates the screen data to be used
    for heatmaps and protein interaction graphs
    """

    # Generate screen summary table
    df = pd.DataFrame()

    for results_path in find_files(datafolder, '^plate_.*_results\.xlsx?$'):
        logging.info("Processing results file: {}".format(results_path))

        template_path = re.sub('_results\.xlsx?$', '_template.xlsx', results_path)
        if not os.path.isfile(template_path):
           logging.warning("Couldn't find matching template file ({}), results won't be processed".format(template_path))
           continue

        results = process_results_plate(results_path, template_path)
        df = df.append(results, ignore_index=True)

    # TODO: Deal with repeated compared values? (averages?)
    # Export summary table
    logging.info("Exporting screen interaction results to: {}".format(outfolder))
    export_results(df, outfolder, 'interactions')

    # Export table with cutoffs by STD multiples
    filtered = df.copy()
    stdev = df.Normalized.std()

    # TODO: use 0 or something else?
    filtered.Normalized = [value if value >= 4*stdev else 0 for value in filtered.Normalized]
    export_results(filtered, outfolder, 'interactions_4xSTD')

    filtered.Normalized = [value if value >= 6*stdev else 0 for value in filtered.Normalized]
    export_results(filtered, outfolder, 'interactions_6xSTD')

    return df


class ProcessResults(CliCommand):
    short_description = "Process screen results and export to table files"

    @classmethod
    def _arg_parser(cls):
        parser = argparse.ArgumentParser(description='Generate the templates for the screening plates in the first batch')
        parser.add_argument('datafolder', type=lambda x: arg_is_valid_directory(parser, x),
                            help='Path to directory where the plate templates and results are stored')
        parser.add_argument('outfolder', type=lambda x: arg_is_valid_directory(parser, x),
                            help='Path to directory where the results of the processed files will be saved')

        return parser

    @classmethod
    def _main(cls, args):
        process_results(args.datafolder, args.outfolder)


if __name__ == '__main__':
    ProcessResults.run()

"""
Generates the results for the CSI screen
"""
import logging
from pandas.io.excel import ExcelWriter

logger = logging.getLogger()

from collections import OrderedDict
import pandas as pd

from init_db import *
from platero.parsing.parsing import parse_plate_results
from platero.platero import db, db_reset
from platero.model.models import BatchProtein
from platero.parsing.parsing import iterate96WP
from platero.templates import NEG_CONTROL, POS_CONTROL, TEMPLATE_CELL_RE, DELIMITER
from platero.utils import find_files, filter_digits, get_batch_ids

from platero.parsing.parsing import read_excel_list

RESULTS_FILENAME = 'interactions.xls'

PROTEIN_LABELS = {}
PROTEIN_FAMILIES = {}
PROTEIN_SUBFAMILIES = {}

def process_plates(plates_folder, proteins_list, output_folder):
    '''
    Generate the CSI screen results with the given input
    '''
    logger.info("Start plates processing")

    # Basic valdiation
    if not os.path.isdir(plates_folder):
        raise NotADirectoryError("Plates folder location doesn't exist or is not a folder")
    if not os.path.isdir(plates_folder):
        raise FileNotFoundError("Proteins list file can't be found")
    if not os.path.isdir(output_folder):
        raise NotADirectoryError("Output folder location doesn't exist or is not a folder")


    load_proteins_list(proteins_list)
    df = process_results(plates_folder)
    export_results(df, output_folder)

    logger.info("Finished plates processing")

def load_proteins_list(filepath):
    '''
    Reads in the CSI screen list and creates the reference proteins DB
    '''
    logger.info("Loading proteins list from {}".format(filepath))

    with open(filepath, 'rb') as file:
        db_reset()
        init_db(file)

    # Init global variables
    for bp in db.query(BatchProtein):
        PROTEIN_LABELS[bp.protein.id] = bp.protein.label
        PROTEIN_FAMILIES[bp.protein.id] = bp.protein.family
        PROTEIN_SUBFAMILIES[bp.protein.id] = bp.protein.subfamily


def export_results(df, outfolder):
    # Export summary table
    logger.info("Exporting screen interaction results to: {}".format(outfolder))
    basename = os.path.splitext(RESULTS_FILENAME)[0]

    save_results_file(df, outfolder, basename)

    # TODO: remove this
    # Export table with cutoffs by old Z-Score
    filtered = df.copy()
    stdev = df.Normalized.std()

    # TODO: use 0 or something else?
    filtered.Normalized = [value if value >= 4*stdev else 0 for value in filtered.Normalized]
    save_results_file(filtered, outfolder, 'interactions_4xSTD')

    filtered.Normalized = [value if value >= 6*stdev else 0 for value in filtered.Normalized]
    save_results_file(filtered, outfolder, 'interactions_6xSTD')

    # TODO: remove this
    # Export table with cutoffs by old Z-Score
    filtered = df.copy()

    # TODO: use 0 or something else?
    filtered.ix[df.Z_Score_Old_Plate < 4, 'Normalized'] = 0
    save_results_file(filtered, outfolder, 'interactions_4xSTD_plate')

    filtered.ix[df.Z_Score_Old_Plate < 6, 'Normalized'] = 0
    save_results_file(filtered, outfolder, 'interactions_6xSTD_plate')



    # Export table with cutoffs by Z-Score by plate
    filtered = df.copy()

    filtered.ix[df.Z_Score_Plate < 4, 'Normalized'] = 0
    save_results_file(filtered, outfolder, '{}_Z4_plate'.format(basename))

    filtered.ix[df.Z_Score_Plate < 6, 'Normalized'] = 0
    save_results_file(filtered, outfolder, '{}_Z6_plate'.format(basename))

    # Export table with cutoffs by Z-Score
    filtered = df.copy()

    filtered.ix[df.Z_Score < 4, 'Normalized'] = 0
    save_results_file(filtered, outfolder, '{}_Z4'.format(basename))

    filtered.ix[df.Z_Score < 6, 'Normalized'] = 0
    save_results_file(filtered, outfolder, '{}_Z6'.format(basename))



def save_results_file(df, outfolder, basename):
    # TODO: remove Z_Score_Old
    columns = ['Bait', 'Prey', 'Normalized', 'Value', 'NC', 'Z_Score', 'Z_Score_Plate', 'Z_Score_Old', 'Z_Score_Old_Plate', 'Plate', 'PlateCell',
               'BaitId', '                                                  BaitFamily', 'BaitSubfamily', 'PreyId', 'PreyFamily', 'PreySubfamily', 'InteractionId']

    # Generate crosstab data frame for export
    ctdf = df.sort_values(by=['PreyFamily', 'PreySubfamily']).pivot_table(index=['PreyFamily', 'PreySubfamily', 'Prey'],
                                                                          columns=['BaitFamily', 'BaitSubfamily',
                                                                                   'Bait'], values='Normalized')
    ctdf.reset_index(inplace=True)
    ctdf.rename(columns={'Prey': 'Prey vs Bait'}, inplace=True)

    # Check if missing values
    n_blanks = ctdf.isnull().sum().sum()
    if n_blanks > 0:
        logger.debug("Some interaction comparisons are missing (a total of {}). It means you haven't tested all " \
                        "combinations for the proteins both as bait and prey. These missing values will " \
                        "show up as 0s in the crosstab file format (i.e. gaps in a heatmap). ".format(n_blanks))

    # Fill the blanks with 0s
    ctdf.fillna(0, inplace=True)

    # NOTE: mini hack to nicefy columns
    tmpfile = os.path.join(outfolder, '{}_crosstab.csv'.format(basename))
    ctdf.to_csv(tmpfile, index=False)
    ctdf = pd.read_csv(tmpfile, header=None, skiprows=[3])
    ctdf.loc[2, 0:2] = ctdf.loc[0, 0:3]
    ctdf.loc[0:1, 0:1] = None
    ctdf.loc[0, 2] = 'BaitFamily'
    ctdf.loc[1, 2] = 'BaitSubfamily'
    os.remove(tmpfile)

    outfile = os.path.join(outfolder, '{}.xls'.format(basename))
    with ExcelWriter(outfile) as writer:
        df.to_excel(writer, index=False, columns=columns, sheet_name='Table')
        ctdf.to_excel(writer, index=False, header=None, sheet_name='Crosstab')


def process_results(datafolder):
    """
    Reads the screening plates and generates the screen summary dataframe
    """

    # Check available files
    df_files = pd.DataFrame(find_files(datafolder, '^plate_.*_results\.xlsx?$'), columns=['results'])
    df_files['template'] = df_files.results.replace(to_replace='_results\.xlsx?$', value='_template.xlsx', regex=True)
    df_files['filename'] = [os.path.basename(x) for x in df_files.template]
    df_files['found'] = [os.path.isfile(x) for x in df_files.template]
    assert_empty_df(df_files[df_files.found==False],
                    "Some template files for available plate reader results are missing. "\
                    "Check the console/logfile for more details", ['results', 'filename'],
                    n_lines=0)

    # Generate screen summary table
    df = pd.DataFrame()

    n_plates = len(df_files)
    for i, plate in enumerate(df_files.to_dict(orient='records')):
        logger.info("Processing results plate ({}/{}): {}".format(i + 1, n_plates, plate['results']))
        results = process_results_plate(plate['results'], plate['template'])
        df = df.append(results, ignore_index=True)

    #  Add global Z-Score
    add_z_score(df, 'Normalized', 'Z_Score')
    # TODO: remove this
    df['Z_Score_Old'] = df.Normalized/df.Normalized.std()


    # Add unique interaction ID
    df['InteractionId'] = df['BaitId'] + DELIMITER + df['PreyId']
    if any(df.InteractionId.duplicated()):
        # TODO: Deal with repeated compared values? (averages?)
        logger.warning("Some of the interaction values are duplicated (i.e. you screened the same twice)! The script is not ready for this yet!")

    return df


def control_index(cell_id):
    # TODO: what a hack!
    return (filter_digits(cell_id) - 1) // 6

def validate_half_plate(df, half):
    if len(df.BaitId.unique()) > 1:
        raise ValueError("More than 1 bait id used in the {} half of a "\
                         "screening plate ({})".format(half, ', '.join(list(df.BaitId.unique()))))

    if any(df.PreyId.duplicated()):
        raise ValueError("Duplicated prey ids in the the {} half of a "\
                         "screening plate ({})".format(half, ', '.join(df.PreyId[df.PreyId.duplicated()])))


def validate_simmetry(df):
    df_left = df[df.ControlId==0]
    df_right = df[df.ControlId==1]

    validate_half_plate(df_left, 'left')
    validate_half_plate(df_right, 'right')

    df_error = pd.DataFrame(list(zip(df_left.PlateCell.values, df_left.PreyId.values, df_right.PreyId.values, df_right.PlateCell.values)), columns=['Cell_L', 'PreyId_L', 'PreyId_R', 'Cell_R'])
    df_error = df_error[df_error.PreyId_L != df_error.PreyId_R]
    assert_empty_df(df_error, "Left and right halves of the plate don't have the same prey protein ids")


def get_interaction_values(timepoint_reads, template):
    '''
    Map the reads of a certain timepoint to a given template and normalize
    values to controls
    '''

    cell_values = timepoint_reads.ix[:, template.keys()].squeeze().to_dict()

    # Merge protein information from template with read values
    data = []
    controls = {}
    for cell_id, interaction in template.items():
        if interaction == NEG_CONTROL:
            controls.setdefault(control_index(cell_id), []).append(cell_values[cell_id])
            logger.debug("Added control {} ({}, {})".format(cell_values[cell_id],
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
            logger.debug("Added values {} ({})".format(cell_values[cell_id], cell_id))

        # TODO: activate? might cause problems
        # NOTE: we should ignore this errors, as it is expected to happen when using
        # a multipippette
        # elif cell_values[cell_id] > 0:
        #     raise ValueError("Value ({}) found in unexpected plate position ({})".format(cell_values[cell_id], cell_id))


    # Create data frame
    df = pd.DataFrame(data)

    # Cross validation
    validate_simmetry(df)

    # Add protein symbols
    protein_labels = {bp.protein.id: bp.protein.label for bp in db.query(BatchProtein)}
    df['Bait'] = df.BaitId.map(PROTEIN_LABELS)
    df['Prey'] = df.PreyId.map(PROTEIN_LABELS)
    df['BaitFamily'] = df.BaitId.map(PROTEIN_FAMILIES)
    df['BaitSubfamily'] = df.BaitId.map(PROTEIN_SUBFAMILIES)
    df['PreyFamily'] = df.PreyId.map(PROTEIN_FAMILIES)
    df['PreySubfamily'] = df.PreyId.map(PROTEIN_SUBFAMILIES)

    # Calculate and add normalized values
    controls = {i: (sum(controls[i]) / len(controls[i])) for i in controls}
    df['NC'] = df.ControlId.map(controls)
    if any(df.NC.isnull()):
        raise ValueError("No negative control found on the template. Make sure there is a [NC] value for each part of the plate")

    df['Normalized'] = df.Value / df.NC

    #  Add Z-Score per plate
    add_z_score(df, 'Normalized', 'Z_Score_Plate')

    # TODO: remove this
    df['Z_Score_Old_Plate'] = df.Normalized/df.Normalized.std()

    return df


def add_z_score(df, value, z_score):
    '''
    Add a Z score column to a data frame
    '''
    df[z_score] = (df[value] - df[value].mean())/df[value].std()


def parse_interaction(text):
    if text in [POS_CONTROL, NEG_CONTROL, '', None]:
        return text

    m = TEMPLATE_CELL_RE.match(text.upper())
    if not m:
        raise ValueError("Couldn't extract valid bait and prey protein ids from a template cell value ({})".format(text))

    return dict(zip(['bait', 'prey'], m.groups()))


def parse_plate_template(filepath):
    """
    Process a template file, returning an ordered dictionary
    TODO:
    with information of each cell's contents, plus the metadata (timepoint)
    """
    logger.debug("Parsing plate template: {}".format(filepath))

    try:
        df = read_excel_list(filepath, 'Info', {'A': 'Field', 'B': 'Value'})
        info = pd.Series(df.Value.values, index=df.Field).to_dict()

        wb = load_workbook(filepath, read_only=True)
        ws = wb.get_sheet_by_name('Template')
        cells = ws.get_named_range('rng_template_proteins')

        # TODO: support multiple plate sizes via metadata or guessing?
        template = OrderedDict()
        for position, cell in zip(iterate96WP(), cells):
            cell_id = position[0]
            template[cell_id] = parse_interaction(cell.value)

    except Exception as exc:
        raise ValueError("Error parsing template: {}. In {}.".format(str(exc), filepath)) from exc

    # Check if bait/prey are in the selected batch
    # NOTE: we are searching for bait id. A bait id is determined by extracting the digits from
    # the sheet name in the proteins list
    bait_batch_id, prey_batch_id = get_batch_ids(os.path.basename(filepath))
    baits = set()
    preys = set()
    for k in template:
        if isinstance(template[k], dict):
            baits.add(template[k]['bait'])
            preys.add(template[k]['prey'])

    for bait in baits:
        if db.query(BatchProtein.protein_id).filter(BatchProtein.protein_id == bait, BatchProtein.batch_id == bait_batch_id).count() == 0:
            raise ValueError("Protein '{}' was used as a BAIT on the template, but it can't be found on batch #{}".format(bait, bait_batch_id))

    for prey in preys:
        if db.query(BatchProtein.protein_id).filter(BatchProtein.protein_id == prey, BatchProtein.batch_id == prey_batch_id).count() == 0:
            raise ValueError("Protein '{}' was used as a PREY on the template, but it can't be found on batch #{}".format(prey, prey_batch_id))

    return template, info


def process_results_plate(results_path, template_path):
    """
    Process a single results plate and return the interaction data
    """
    reads, plate_info = parse_plate_results(results_path)

    template, template_info = parse_plate_template(template_path)

    # Get reads for specified timepoint
    timeshift = template_info['Timeshift']
    if pd.isnull(timeshift):
        raise ValueError("Plate template has no valid 'Timeshift' value in the 'Info' sheet ({})".format(template_path))
    timepoint_reads = reads.loc[reads['Time'] == timeshift]
    if timepoint_reads.empty:
        raise ValueError("Specified timeshift ({}) not found in the plate reads ({})".format(timeshift, template_path))

    try:
        df = get_interaction_values(timepoint_reads, template)
    except Exception as exc:
        raise ValueError("Error parsing plate results: {}. In {}.".format(str(exc), results_path)) from exc

    assert_empty_df(df[df.Value <= 0],
                    "Some reads in the plate contain invalid values (<=0), in {}".format(results_path),
                    columns=['PlateCell', 'BaitId', 'PreyId', 'Value'])


    # TODO: very hackish!!! use template info instead (currently not available in templates for batch 1)
    df['Plate'] = filter_digits(results_path.split('/plate_')[1].split('_')[0])

    return df

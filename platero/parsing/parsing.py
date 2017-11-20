
import pandas as pd

def strip(text):
    try:
        return text.strip()
    except AttributeError:
        return text

def read_excel_list(file, sheet, column_map):
    columns = sorted(column_map.keys())
    strip_all = {i:strip for i in range(len(columns))}
    df = pd.read_excel(file, sheet, parse_cols=','.join(columns), converters=strip_all)
    df.columns = [column_map[key] for key in columns]
    df.dropna(how='all', inplace=True)

    return df


def iterate96WP():
    for row in 'ABCDEFGH':
        for col in range(1, 13):
            yield "{}{}".format(row,col), row, col


def reverse(template):
    """ Reverse a template, in case the plate was put in the wrong direction """
    reversed = {}
    rows = 'ABCDEFGH'
    cols = range(1,13)
    for i, row in enumerate(rows):
      for col in cols:
          cell = "{}{}".format(row, col)
          reverse_cell = "{}{}".format(rows[-(i+1)], len(cols) - (col - 1))
          reversed[reverse_cell] = template[cell]

    return reversed


# TODO: maybe do with openpyxl?
import xlrd
from collections import OrderedDict
import datetime
def parse_plate_results(filepath):
    ''' Parse the raw file coming from the plate reader'''
    book = xlrd.open_workbook(filepath)
    sheet = book.sheet_by_index(0)

    # Parse some metadata at the beginning of the file, until we find the reads
    # TODO: date values, hierarchies, empty values, ...
    metadata = OrderedDict()
    tag = None
    for row_index in range(sheet.nrows):
        col_0 = sheet.cell(row_index, 0).value
        col_1 = sheet.cell(row_index, 1).value
        if col_1 == 'Time':
            break
        if col_0 and col_1:
            tag = col_0
            metadata[tag] = col_1
        elif col_1 and tag:
            metadata[tag] += '\n' + col_1
        else:
            tag = None

    # Parse reads, grouped by timepoint
    # TODO: maybe strip columns?
    data_cols = sheet.row_values(row_index, 1)
    data_rows = []
    while sheet.cell(row_index + 1, 2).value:
        row_index += 1
        row_data = sheet.row_values(row_index, 1, len(data_cols) + 1)
        # Fix timepoint format
        timepoint = xlrd.xldate_as_tuple(row_data[0], book.datemode)
        row_data[0] = datetime.time(*timepoint[3:])
        data_rows.append(row_data)

    reads = pd.DataFrame(data_rows, columns=data_cols)

    return reads, metadata


def dump_template(template):
    for row in 'ABCDEFGH':
        line = ""
        for col in range(1, 13):
            cell = "{}{}".format(row, col)
            line += "{Bait}x{Prey}\t".format(**template[cell])
        print(line)


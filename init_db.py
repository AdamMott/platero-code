#!/usr/bin/env python

import os
import logging
import argparse

from openpyxl import load_workbook

from platero.platero import config, db_init, db, db_reset
from platero.commands import CliCommand
from platero.model.models import Protein, BatchProtein, PROTEIN_ID_REGEX
from platero.model.utils import update_or_create
from platero.parsing.parsing import read_excel_list
from platero.utils import filter_digits, assert_empty_df


def import_batch_sheet(filename, sheet, mapping, expected_ids):
    '''
    Import a batch sheet validating the data and checking that the
    included ids are part of the reference protein list
    '''
    logging.info("Importing batch sheet '%s' from %s" % (sheet, filename))
    batch_id = filter_digits(sheet)
    batch_name = sheet[len('batch'):].strip()


    # Import batch proteins
    df_batch = read_excel_list(filename, sheet, mapping)
    df_batch['id'] = df_batch['id'].str.upper()
    df_batch['symbol'].fillna(df_batch.id, inplace=True)
    # TODO: remove those not cloned?
    logging.debug("Batch contains %d successfully cloned proteins" % len(df_batch))

    # Validate data
    required = ['subfamily', 'id', 'symbol', 'nickname']
    df_incomplete =  df_batch[df_batch[required].isnull().any(axis=1)]
    assert_empty_df(df_incomplete, "Some of the proteins in sheet '{}' have incomplete information".format(sheet))

    df_invalid_id = df_batch[~df_batch.id.str.contains("^{}$".format(PROTEIN_ID_REGEX), regex=True, na=False)]
    assert_empty_df(df_invalid_id, "Some of the provided ids in sheet '{}' are invalid".format(sheet), ['#', 'id'])

    df_duplicate_id = df_batch[df_batch.duplicated(subset='id', keep=False)]
    assert_empty_df(df_duplicate_id, "Some of the provided ids in sheet '{}' are duplicated".format(sheet), ['#', 'id'])

    df_unexpected_id = df_batch[~df_batch.id.isin(expected_ids)]
    assert_empty_df(df_unexpected_id, "Some of the provided ids in sheet '{}' are not in the reference protein list".format(sheet), ['#', 'id'])

    # Update the protein info with id, nickname, subfamily and symbol
    proteins = df_batch.to_dict(orient='records')
    for protein in proteins:
        db.query(Protein).\
        filter(Protein.id == protein['id']).\
        update({k: protein[k] for k in ('subfamily', 'symbol', 'nickname')})
    db.commit()

    # Import the batch info
    # TODO: order number? reindex?
    df_batch_proteins = df_batch.copy()[['id', 'nickname', 'cloned']]
    df_batch_proteins.rename(columns={'id':'protein_id'}, inplace=True)
    df_batch_proteins['batch_name'] = batch_name
    df_batch_proteins['batch_id'] = batch_id
    df_batch_proteins['order'] = df_batch_proteins.index
    batch_proteins = df_batch_proteins.to_dict(orient='records')
    db.execute(BatchProtein.__table__.insert(), batch_proteins)


def get_batch_sheets(filename):
    return [sheet for sheet in load_workbook(filename).get_sheet_names() if sheet.strip().lower().startswith("batch") ]


def init_db(proteins_list):
    db_reset()

    # Import proteins list
    mapping = {'A':'family', 'C': 'id', 'I':'symbol',
               'J': 'long_symbol', 'K': 'description'}
    df_proteins = read_excel_list(proteins_list, 'Proteins List', mapping)
    df_proteins['id'] = df_proteins['id'].str.upper()
    df_proteins['symbol'].fillna(df_proteins.id, inplace=True)

    # Validate data
    df_invalid_id = df_proteins[~df_proteins.id.str.contains("^{}$".format(PROTEIN_ID_REGEX), regex=True, na=False)]
    assert_empty_df(df_invalid_id, "Some of the provided ids in the protein list are invalid")

    df_duplicate_id = df_proteins[df_proteins.duplicated(subset='id', keep=False)]
    assert_empty_df(df_duplicate_id, "Some of the provided ids in the protein list are duplicated")

    df_no_family = df_proteins[df_proteins.family.isnull()]
    assert_empty_df(df_no_family, "Some of the proteins in the reference list don't have an assigned family")

    # Insert proteins into DB
    proteins = df_proteins.to_dict(orient='records')
    db.execute(Protein.__table__.insert(), proteins)

    # Import batch sheets
    mapping = {'A': '#', 'B':'subfamily', 'C': 'id', 'D':'symbol',
               'E': 'nickname', 'J': 'cloned'}

    for sheet in get_batch_sheets(proteins_list.name):
        import_batch_sheet(proteins_list.name, sheet, mapping, df_proteins.id)

    db.commit()


class InitDatabase(CliCommand):
    short_description = "Initialize platero database"

    @classmethod
    def _arg_parser(cls):
        parser = argparse.ArgumentParser(description='Initialize platero database')
        parser.add_argument('proteins_list', type=argparse.FileType('rb'),
                            help='An excel file containing the proteins list')

        return parser

    @classmethod
    def _main(cls, args):
        init_db(args.proteins_list)


if __name__ == '__main__':
    InitDatabase.run()

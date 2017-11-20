from .models import Plate, PlateCell, BatchProtein
from platero.parsing.parsing import iterate96WP
from platero.platero import db
from platero.wellplate import POS_CONTROL, NEG_CONTROL


def get_batch_proteins(batch_id):
    return [ bp.protein for bp in
             db.query(BatchProtein).filter(
                 BatchProtein.batch_id==batch_id, BatchProtein.cloned=='yes'
             ).order_by(BatchProtein.order)]

def get_plates(bait_batch_id, prey_batch_id):
    return db.query(Plate).filter(Plate.bait_batch_id==bait_batch_id,
                                  Plate.prey_batch_id==prey_batch_id).order_by(Plate.id)

def save_template(plate_id, template):
    for (cell, row, col) in iterate96WP():
        if not template[cell]['prey']:
            continue

        bait = prey = None
        is_NC = is_PC = False

        if template[cell]['prey']==POS_CONTROL:
            is_PC = True
        elif template[cell]['prey']==NEG_CONTROL:
            is_NC = True
        else:
            bait=template[cell]['bait']
            prey=template[cell]['prey']

        plate_cell = PlateCell(
            row=row,
            column=col,
            bait=bait,
            prey=prey,
            is_NC=is_NC,
            is_PC=is_PC,
            plate_id=plate_id
        )
        db.add(plate_cell)

    db.commit()



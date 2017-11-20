
from collections import OrderedDict

NEG_CONTROL = '[NC]'
POS_CONTROL = '[PC]'

class WellPlate(object):
    def __init__(self, rows, columns, default=None, values={}, name=''):
        self.name = name
        self.rows = rows
        self.columns = columns
        self.init(default)
        self.update(values)

    def init(self, default):
        """ Set default values for the plate cells """
        self.values = OrderedDict()
        for i, row in enumerate(self.rows):
            for j, column in enumerate(self.columns):
                self.values[self.cell_id(i, j)] = default

    def update(self, values):
        """ Update plate cells values """
        self.values.update(values)

    def cell_id(self, i, j):
        """ Get the id of a cell, based on 0-indexed row and column numbers """
        # TODO: check that they are valid indexes?
        return self.cell_name(self.rows[i], self.columns[j])

    def cell_name(self, row, column):
        """ Get the id of a cell, based on row and column """
        # TODO: check that they are valid indexes? Merge with cell_id
        return "{}{}".format(row, column)

    def size(self):
        """ Number of wells available """
        return len(self.rows) * len(self.columns)

    def __str__(self):
        """ String representation for a WellPlate object """
        as_str = '\t' + '\t'.join(self.columns) + '\n'
        if self.name:
            as_str = 'Plate: ' + self.name + '\n' + as_str

        for i, row in enumerate(self.rows):
            line = row
            for j, column in enumerate(self.columns):
                line += '\t' + str(self.values[self.cell_name(row, column)])
            as_str += line + '\n'

        return as_str

    def to_dict(self):
        """ Convery WellPlate object to dict """
        return self.values


class WellPlate96(WellPlate):
    rows = list('ABCDEFGH')
    columns = [str(i) for i in range(1,13)]

    def __init__(self, default='', values={}):
        super().__init__(WellPlate96.rows, WellPlate96.columns, default, values)

    @classmethod
    def size(cls):
        """ Number of wells available """
        return len(cls.rows) * len(cls.columns)

class PreyStoragePlate(WellPlate96):
    """
    A prey storage plate stores up to 46 proteins. The plate is divided in two
    equal areas with the same configuration of proteins,
    """
    def __init__(self, preys):
        super().__init__()
        self.preys = preys

        if len(preys) == 0:
            raise ValueError("No prey proteins provided to initialize the plate")

        elif len(preys) > self.__class__.capacity():
            raise ValueError("Plate can only store up to {capacity} prey proteins, {given} provided".format(given=len(preys), capacity=self.capacity()))

        wells = {}
        i = 0
        half = len(self.columns) // 2
        # TODO : What a piece of ugly code! don't do this with an exception!
        try:
            for col_A, col_B in zip(self.columns[:half], self.columns[half:]):
                for row in self.rows:
                    wells[self.cell_name(row, col_A)] = preys[i]
                    wells[self.cell_name(row, col_B)] = preys[i]
                    i += 1
                    if i == len(preys):
                        raise ValueError()
        except ValueError:
            pass

        self.update(wells)

    @classmethod
    def capacity(cls):
        """
        Number of proteins that can be stored in the plate. We split the plate
        in 2 and keep space for the controls
        """
        return (cls.size() // 2) - 2


class BaitStoragePlate(WellPlate96):
    """
    A bait storage plate stores up to 12 proteins. A whole column
    is filled with the same bait protein.
    """
    def __init__(self, baits):
        super().__init__()
        self.baits = baits

        if len(baits) > self.capacity():
            raise ValueError("Plate can only store up to {capacity} bait proteins, {given} provided".format(given=len(baits), capacity=self.capacity()))

        wells = {}
        i = 0
        for i, protein, column in zip(range(len(baits)), baits, self.columns):
            for row in self.rows:
                wells[self.cell_name(row, column)] = baits[i]

        self.update(wells)

    @classmethod
    def capacity(cls):
        """
        Number of proteins that can be stored in the plate. Each bait fills up one column
        """
        return len(cls.columns)

    @classmethod
    def bait_plate_index(cls, bait_index):
        """ Plate index given an index in the batch proteins list (1-indexed) """
        return (bait_index // cls.capacity()) + 1

    @classmethod
    def bait_plate_offset(cls, bait_index):
        """ Column offset given an index in the batch proteins list (0-indexed) """
        return (bait_index % cls.capacity())



class ScreenPlate(WellPlate96):
    """
    A screen plate combines 2 bait proteins with a prey storage plate (a full batch)
    """
    def __init__(self, baits, bait_plate_name, bait_plate_offset, prey_plate):
        # TODO: refactor this class, cleaner params
        super().__init__(default={'bait':None, 'prey': None})

        self.baits = baits
        self.bait_plate_name = bait_plate_name
        self.bait_plate_offset = bait_plate_name
        # Create a simulated plate with the stuff to pipette for baits
        # TODO: maybe different default value
        bait_plate = WellPlate96()
        for i, column in enumerate(WellPlate96.columns[bait_plate_offset:bait_plate_offset + len(baits)]):
            for row in WellPlate96.rows:
                bait_plate.values[bait_plate.cell_name(row, column)] = baits[i]
        self.bait_plate = bait_plate

        self.prey_plate = prey_plate
        self.prey_plate_name = prey_plate.name

        if len(baits) >  2:
            raise ValueError("Plate can only store up to 2 bait proteins, {given} provided".format(given=len(baits)))

        wells = {}
        half = len(self.columns) // 2
        for col_A, col_B in zip(self.columns[:half], self.columns[half:]):
            for row in self.rows:
                cell_A = self.cell_name(row, col_A)
                cell_B = self.cell_name(row, col_B)

                wells[cell_A] = {'bait': baits[0], 'prey': prey_plate.values[cell_A]}
                if len(baits) > 1:
                    wells[cell_B] = {'bait': baits[1], 'prey': prey_plate.values[cell_B]}

        # Controls go into fixed positions
        wells["G6"] = {'bait': baits[0], 'prey': NEG_CONTROL}
        if len(baits) > 1:
            wells["G12"] = {'bait': baits[1], 'prey': NEG_CONTROL}

        wells["H12"] = {'bait': POS_CONTROL, 'prey': POS_CONTROL}

        self.update(wells)


    @classmethod
    def capacity(cls):
        """
        Number of bait proteins that can be stored in the plate
        """
        return WellPlate96.size() // PreyStoragePlate.capacity()

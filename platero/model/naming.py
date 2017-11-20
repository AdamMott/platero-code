
def batch_name(batch_id):
    return "batch_{:02d}".format(batch_id)

def storage_prey_plate_name(batch_id):
    return "{}_prey".format(batch_name(batch_id))

def storage_bait_plate_name(batch_id, index):
    return "{batch}_bait_{i:d}".format(batch=batch_name(batch_id), i=index)

def screen_plate_name(id):
    return "plate_{:05d}".format(id)

class TypeOfFAT:
    fat16 = 0
    fat32 = 1

    get_name_by_type = {
        0: 'FAT 16',
        1: 'FAT 32'
    }

    get_length_fat_entry = {
        fat16: 2,
        fat32: 4
    }

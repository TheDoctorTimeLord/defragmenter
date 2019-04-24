from IOManager import IOManager
from enums import TypeOfFAT


class InfoAboutImage:
    def __init__(self, io_manager: IOManager):
        io_manager.seek(0)

        self.BS_jmpBoot = io_manager.read_bytes_and_convert_to_int(3)
        self.BS_OEMName = io_manager.read_bytes_and_convert_to_int(8)
        self.BPB_BytsPerSec = io_manager.read_bytes_and_convert_to_int(2)  # Количество байт в одном секторе
        #                                                               (512, 1024, 2048 or 4096)
        self.BPB_SecPerClus = io_manager.read_bytes_and_convert_to_int(1)  # Количество секторов в кластере
        self.BPB_ResvdSecCnt = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_NumFATs = io_manager.read_bytes_and_convert_to_int(1)  # Количество таблиц FAT на диске
        self.BPB_RootEntCnt = io_manager.read_bytes_and_convert_to_int(2)  # Для FAT16 поле содержит число 32-байтных
        #                                                               элементов корневой директории. Для FAT32 дисков,
        #                                                               это поле должно быть 0
        self.BPB_TotSec16 = io_manager.read_bytes_and_convert_to_int(2)  # Старое 16-битное поле: общее количество
        #                                                              секторов на диске
        self.BPB_Media = io_manager.read_bytes_and_convert_to_int(1)
        self.BPB_FATSz16 = io_manager.read_bytes_and_convert_to_int(2)  # FAT16 это количество секторов одной FAT. Для
        #                                                            FAT32 это значение 0
        self.BPB_SecPerTrk = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_NumHeads = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_HiddSec = io_manager.read_bytes_and_convert_to_int(4)
        self.BPB_TotSec32 = io_manager.read_bytes_and_convert_to_int(4)  # Новое 32-битное поле: общее количество
        #                                                             секторов на диске

        self.BPB_FATSz32 = io_manager.read_bytes_and_convert_to_int(4)  # Поле, необходимое для некоторых вычислений,
        #                                                            может быть некорректным в некоторых ситуациях
        io_manager.jump_back(4)  # сохранение целостности данных

        if self.BPB_FATSz16 != 0:
            fat_sz = self.BPB_FATSz16
        else:
            fat_sz = self.BPB_FATSz32

        self._root_dir_sectors = ((self.BPB_RootEntCnt * 32) + (self.BPB_BytsPerSec - 1)) // self.BPB_BytsPerSec
        self.first_data_sector = self.BPB_ResvdSecCnt + self._root_dir_sectors + self.BPB_NumFATs * fat_sz

        self.count_of_clusters = self._get_count_of_clusters()
        self.fat_type = self._get_fat_type()

        if self.fat_type == TypeOfFAT.fat16:
            self._parse_fat16_structure(io_manager)
        else:
            self._parse_fat32_structure(io_manager)

        self.first_root_dir_sec = self._get_first_root_dir_sec()

    def _parse_fat16_structure(self, io_manager: IOManager):
        self.BS_DrvNum = io_manager.read_bytes_and_convert_to_int(1)
        self.BS_Reserved1 = io_manager.read_bytes_and_convert_to_int(1)
        self.BS_bootSig = io_manager.read_bytes_and_convert_to_int(1)
        self.BS_VolID = io_manager.read_bytes_and_convert_to_int(4)
        self.BS_VolLab = io_manager.read_bytes_and_convert_to_int(11)
        self.BS_FilSysType = io_manager.read_bytes_and_convert_to_int(8)

    def _parse_fat32_structure(self, io_manager: IOManager):
        self.BPB_FATSz32 = io_manager.read_bytes_and_convert_to_int(4)
        self.BPB_ExtFlags = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_FSVer = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_RootClus = io_manager.read_bytes_and_convert_to_int(4)  # номер первого кластера корневой директории
        self.BPB_FSInfo = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_BkBootSec = io_manager.read_bytes_and_convert_to_int(2)
        self.BPB_Reserved = io_manager.read_bytes_and_convert_to_int(12)
        self.BS_DrvNum = io_manager.read_bytes_and_convert_to_int(1)
        self.BS_Reserved1 = io_manager.read_bytes_and_convert_to_int(1)
        self.BS_BootSig = io_manager.read_bytes_and_convert_to_int(1)
        self.BS_VolID = io_manager.read_bytes_and_convert_to_int(4)
        self.BS_VolLab = io_manager.read_bytes_and_convert_to_int(11)
        self.BS_FilSysType = io_manager.read_bytes_and_convert_to_int(8)

    def _get_first_root_dir_sec(self):
        if self.fat_type == TypeOfFAT.fat32:
            return (self.first_data_sector + (self.BPB_RootClus - 2) * self.BPB_SecPerClus) * self.BPB_BytsPerSec
        else:
            return (self.BPB_ResvdSecCnt + (self.BPB_NumFATs * self.BPB_FATSz16)) * self.BPB_BytsPerSec

    def _get_count_of_clusters(self):
        if self.BPB_TotSec16 != 0:
            tot_sec = self.BPB_TotSec16
        else:
            tot_sec = self.BPB_TotSec32

        data_sec = tot_sec - self.first_data_sector

        return data_sec // self.BPB_SecPerClus

    def _get_fat_type(self):
        if self.count_of_clusters <= 0:
            raise ValueError("Incorrect Image. Count of clusters: " + str(self.count_of_clusters))
        elif self.count_of_clusters < 65525:
            fat_type = TypeOfFAT.fat16
        else:
            fat_type = TypeOfFAT.fat32
        return fat_type

    def get_count_entries_in_dir_cluster(self):
        return self.BPB_BytsPerSec * self.BPB_SecPerClus // 32

    def get_bytes_per_cluster(self):
        return self.BPB_BytsPerSec * self.BPB_SecPerClus

    @classmethod
    def get_in_bytes(cls, value: int):
        return int.to_bytes(value, (value.bit_length() + 7) // 8, 'little')

    @classmethod
    def get_in_hex(cls, value: int):
        val = InfoAboutImage.get_in_bytes(value).hex()
        return val if val != '' else '0'


class DirectoryInfo:
    """
    Информация о содержимом директории
    """
    def __init__(self, entries_list: list):
        self.entries_list = entries_list

    def get_directories(self):
        return self._get_sublist_by_rule(lambda e: e.attr.is_directory())

    def get_files(self):
        return self._get_sublist_by_rule(lambda e: not e.attr.is_directory())

    def _get_sublist_by_rule(self, rule):
        elems = []
        for entry in self.entries_list:
            if rule(entry):
                elems.append(entry)
        return elems

    def merge(self, other_dir_info):
        return DirectoryInfo(self.entries_list + other_dir_info.entries_list)


class DirectoryEntryInfo:
    """
    Получение информации о записи в директории
    """
    def __init__(self, name: str, attr: int or None, first_cluster_num: int, entry_point: int):
        """
        :param name:
        :param attr:
        :param first_cluster_num: первый кластре расположения файла, соответсвующего записи
        :param entry_point: входная точка записи на диске
        """
        self.name = name
        self.attr = attribute_parser(attr)
        self.first_cluster_num = first_cluster_num
        self.entry_point = entry_point


class DirectoryEntryLongNameInfo:
    """
    олучение информации о записи в директории являющаяся частью длинного имени
    """
    def __init__(self, value: int, name1: bytes, check_sum: int, name2: bytes, name3: bytes):
        self.value = value
        self._names = [name1, name2, name3]
        self.check_sum = check_sum

    def get_full_name(self):
        return b''.join(self._names).decode('utf-16')


class Attribute:
    """
    Класс для обработки атрибутов файла
    """
    def __init__(self, archive: bool, directory: bool, volume_id: bool, system: bool, hidden: bool, read_only: bool):
        self.archive = archive
        self.dir = directory
        self.volume_id = volume_id
        self.system = system
        self.hidden = hidden
        self.read_only = read_only

    def is_long_name(self):
        return self.read_only and self.hidden and self.system and self.volume_id and not self.dir and not self.archive

    def is_directory(self):
        return self.dir


def attribute_parser(attr: int or None):
    """
    Парсинг атрибутов файла
    :param attr: число, обозначающее байт атрибутов
    :return: Attribute
    """
    if attr is None:
        return None
    return Attribute(attr & 0x20 == 32, attr & 0x10 == 16, attr & 0x08 == 8,
                     attr & 0x04 == 4, attr & 0x02 == 2, attr & 0x01 == 1)


class IndexedEntryInfo:
    """
    Сущность, которая ассоциируется с некоторым набором кластеров и показывает информацию о файле или директории,
    составляющим которых он является

    Если кластер являетяся первым в файле или дириктории, то last_clus - None
    """
    def __init__(self, dir_entry_info: DirectoryEntryInfo, cur_clus: int, last_clus: int or None, is_directory: bool):
        self.dir_entry_info = dir_entry_info
        self.cur_clus = cur_clus
        self.last_clus = last_clus
        self.is_directory = is_directory

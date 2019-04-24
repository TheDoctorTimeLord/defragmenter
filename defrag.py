from FileSystem import FileSystem
from IOManager import IOManager
from ImageTools import ClusterSwapper
from service_classes import DirectoryEntryInfo, IndexedEntryInfo


class Defragmenter:
    """
    Класс, используемы для дефрагментации образа FAT
    """
    def __init__(self, file_system: FileSystem, io_manager: IOManager):
        """
        :param file_system: Актуальная файловая система для образа
        :param io_manager: Актуальный IOManager для образа
        """
        self._file_system = file_system
        self._io_manager = io_manager
        self._cluster_swapper = ClusterSwapper(file_system.get_indexed_fat_table(), file_system.get_fat_processor(),
                                               io_manager)

    def defragmentation(self):  # подробнее описание алгоритма смотреть в README
        all_dir_entries_info_list = self._file_system.get_a_set_all_dir_entries_info()
        f_proc = self._file_system.get_fat_processor()
        ind_table = self._file_system.get_indexed_fat_table()

        current_cluster = 2

        for dir_entries_info in all_dir_entries_info_list:
            if dir_entries_info.name == '\\':
                continue

            current_file_cluster = dir_entries_info.first_cluster_num

            while True:
                if current_cluster in ind_table and ind_table[current_cluster].dir_entry_info.name == '\\' or\
                   f_proc.is_bad_cluster(f_proc.get_value_fat_cluster(current_cluster)):

                    current_cluster += 1
                    continue

                self._cluster_swapper.swap_cluster(current_cluster, current_file_cluster)
                next_clus = f_proc.get_value_fat_cluster(current_cluster)

                if f_proc.is_end_cluster(next_clus):
                    current_cluster += 1
                    break
                else:
                    current_file_cluster = next_clus

                current_cluster += 1

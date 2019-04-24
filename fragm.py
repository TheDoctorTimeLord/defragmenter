from random import Random

from FileSystem import FileSystem
from IOManager import IOManager

from ImageTools import ClusterSwapper


class Fragmenter:
    """
    Класс, отвечаюзий за фрагментацию образа доступ к которому получен через io_manager и данные о образе храняться в
    file_system
    """
    def __init__(self, file_system: FileSystem, io_manager: IOManager, random: Random):
        self._file_system = file_system
        self._io_manager = io_manager
        self._random = random
        self._cluster_swapper = ClusterSwapper(file_system.get_indexed_fat_table(), file_system.get_fat_processor(),
                                               io_manager)

    def fragmentation(self, num_of_swaps: int):
        """
        Фрагментирует файлы у данного образа
        :param num_of_swaps: количество перемещений, каждое из которых делается между двумя случайными кластерами
        :return:
        """
        indexed_table = self._file_system.get_indexed_fat_table()

        for _ in range(num_of_swaps):
            nums_clus = list(indexed_table.keys())
            first_clus = self._random.choice(nums_clus)
            second_clus = self._random.choice(nums_clus)
            if indexed_table[first_clus].dir_entry_info.name == '\\' or \
               indexed_table[second_clus].dir_entry_info.name == '\\' or \
               indexed_table[first_clus].is_directory or \
               indexed_table[second_clus].is_directory:
                continue

            self._cluster_swapper.swap_cluster(first_clus, second_clus)

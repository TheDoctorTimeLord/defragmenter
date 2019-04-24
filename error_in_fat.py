import random

import ImageTools
from FileSystem import FileSystem
from enums import TypeOfFAT


class ErrorDetector:
    """
    Класс, необходимый для выявляения ошибок и их исправления
    """
    def __init__(self, fat_processor: ImageTools.FatProcessor):
        self._fat_proc = fat_processor
        self.differences_fats_detected = None
        self.looped_files = None
        self.intersecting_files = None
        self.refresh_clus = None
        self._name_of_indexed_files_to_remove = set()

    def is_differences_fats(self):
        """
        Сообщает были ли найдены различия в таблицах FAT при последней проверке
        :return: bool
        """
        if self.differences_fats_detected is None:
            raise ValueError("Difference was not checked")

        return len(self.differences_fats_detected) != 0

    def is_looped_files(self):
        """
        Сообщает были ли найдены зацикленные файлы при последней проверке
        :return: bool
        """
        if self.looped_files is None:
            raise ValueError("Looped files were not checked")

        return len(self.looped_files) != 0

    def is_intersecting_files(self):
        """
        Сообщает были ли найдены пересекающиеся файлы при последней проверке
        :return: bool
        """
        if self.looped_files is None:
            raise ValueError("Intersecting files were not checked")

        return len(self.intersecting_files) != 0

    def found_orphan_clusters(self):
        """
        Сообщает были ли найдены не нулевые кластеры в FAT, не принадлежащие ни одному файлу (сиротские), при последней
        проверке
        :return: bool
        """
        return self.refresh_clus is not None and len(self.refresh_clus) != 0

    def check_differences_fats(self):
        """
        Проверяет таблицы FAT на совпадение, результат проверки сохраняет в специальное поле
        :return: True, если некторые кластеры в таблицах отличаются, False, если не отличаются
        """
        self.differences_fats_detected = []

        info = self._fat_proc.info
        for i in range(info.count_of_clusters):
            value_in_first_fat = self._fat_proc.get_cluster_value_in_certain_fat(i, 0)
            for j in range(info.BPB_NumFATs):
                if value_in_first_fat != self._fat_proc.get_cluster_value_in_certain_fat(i, j):
                    self.differences_fats_detected.append(i)
        return self.is_differences_fats()

    def analysis_fat_indexed_table(self, indexed_table):
        """
        Проверяет образ на наличие зацикленных и пересекающихся файлов. Все найденные файлы сохраняет во внутренние
        структуры
        :param indexed_table: индексированная таблица FAT
        :return: bool, были ли найдены зацикленныые или пересекающиеся файлы
        """
        self.looped_files = []
        self.intersecting_files = []

        for ind in indexed_table:
            list_values = indexed_table[ind]
            if len(list_values) == 1:
                continue

            d = {}
            for entity in list_values:
                if entity.dir_entry_info.name in d:
                    self.looped_files.append(entity)
                else:
                    d[entity.dir_entry_info.name] = entity

            if len(d):
                self.intersecting_files.append(list(d.values()))

        return self.is_intersecting_files() or self.is_looped_files()

    def clearing_fat_table(self, indexed_table):
        """
        Ищет и очищает таблицу FAT от сиротских кластеров
        :param indexed_table:
        :return: bool, были ли найдены сиротские файлы
        """
        info = self._fat_proc.info
        refresh_clus = []
        for i in range(2, info.count_of_clusters):
            if (self._fat_proc.get_value_fat_cluster(i) != 0 and i != 1 and i not in indexed_table) or\
               self._check_name_to_remove(i, indexed_table):
                self._fat_proc.write_val_in_all_fat(0, i)
                refresh_clus.append(i)
        self.refresh_clus = refresh_clus
        return self.found_orphan_clusters()

    def _check_name_to_remove(self, clus_num: int, indexed_table):
        """
        Проверка на принадлежность имени файла, которому принадлежит текущий кластер, к сиписку файлов на удаление
        :param clus_num: номер кластера
        :param indexed_table: индексированная таблица FAT
        :return: bool, результат проверки
        """
        if clus_num not in indexed_table:
            return False
        if type(indexed_table[clus_num]) == list:
            for entry in indexed_table[clus_num]:
                if entry.dir_entry_info.name in self._name_of_indexed_files_to_remove:
                    return True
            return False
        else:
            return indexed_table[clus_num].dir_entry_info.name in self._name_of_indexed_files_to_remove

    def fix_differences_fats(self, correct_fat_table_num: int):
        """
        Исправление несовпадения таблиц FAT
        :param correct_fat_table_num: номер корректной таблицы FAT
        :return: None
        """
        for clus in self.differences_fats_detected:
            correct_value = self._fat_proc.get_cluster_value_in_certain_fat(clus, correct_fat_table_num)
            for fat_num in range(self._fat_proc.info.BPB_NumFATs):
                if fat_num == correct_fat_table_num:
                    continue
                self._fat_proc.write_val_in_certain_fat(correct_value, clus, fat_num)
        self.differences_fats_detected = []

    def fix_looped_files(self):
        """
        Избавляется от найденных зацикленных файлов
        :return: None
        """
        dir_parser = ImageTools.DirectoryParser(self._fat_proc)
        for entry in self.looped_files:
            dir_parser.delete_entry_in_directory(entry.dir_entry_info.entry_point)
            self._name_of_indexed_files_to_remove.add(entry.dir_entry_info.name)
        self.looped_files = []

    def fix_intersecting_files(self):
        """
        Избавляется от найденных пересекающихся файлов
        :return: None
        """
        dir_parser = ImageTools.DirectoryParser(self._fat_proc)
        for list_entries in self.intersecting_files:
            for entry in list_entries:
                dir_parser.delete_entry_in_directory(entry.dir_entry_info.entry_point)
                self._name_of_indexed_files_to_remove.add(entry.dir_entry_info.name)
        self.intersecting_files = []


class ErrorMaker:
    """
    Класс внесения ошибок
    """
    def __init__(self, dir_parser: ImageTools.DirectoryParser, file_system: FileSystem):
        self._dir_parser = dir_parser
        self._file_system = file_system
        self._info = dir_parser.fat_proc.info
        self._ft_proc = self._dir_parser.fat_proc

        self.end_clus_val = (ImageTools.FatProcessor.END_CLUSTER_IN_WIN_FAT_16 if
                             self._info.fat_type == TypeOfFAT.fat16 else
                             ImageTools.FatProcessor.END_CLUSTER_IN_WIN_FAT_32)

    def make_error_in_fat_table(self, fat_num: int):
        """
        Создает различающийся кластер в определённой таблице FAT
        :param fat_num: номер таблицы FAT, в которой будет создано различие
        :return: None
        """
        if fat_num < 0 or fat_num >= self._info.BPB_NumFATs:
            raise ValueError("Incorrect fat number: " + str(fat_num))

        clus = random.randint(0, self._info.count_of_clusters)
        val = self._ft_proc.get_cluster_value_in_certain_fat(clus, fat_num)
        self._ft_proc.write_val_in_certain_fat(val + 1, clus, fat_num)

    def make_looped_file(self, name_dir: str):
        """
        Создаёт зацикленный файл в директории с названием name_dir, отличной от корневой директории
        :param name_dir: название директории, в которой будет создан зацикленный файл
        :return: None
        """
        empty_entry_point = self._get_free_entry_point_in_dir(name_dir)

        free_clusters = ImageTools.find_empty_clusters(3, self._info, self._file_system.get_indexed_fat_table())

        if free_clusters is None:
            raise ValueError("Not enough free image clusters. Clusters required: " + str(3))

        self._dir_parser.create_entry_in_directory(empty_entry_point, 'ERRORLOOP  ', 0x00, free_clusters[0])

        for i in range(len(free_clusters)):
            if i == len(free_clusters) - 1:
                self._ft_proc.write_val_in_all_fat(free_clusters[0], free_clusters[i])
            else:
                self._ft_proc.write_val_in_all_fat(free_clusters[i + 1], free_clusters[i])

    def make_intersecting_files(self, name_dir: str):
        """
        Создаёт два пересекающихся файла в директории с названием name_dir, отличной от корневой директории
        :param name_dir: название директории, в которой будут созданы файлы
        :return: None
        """
        empty_entry_point = self._get_free_entry_point_in_dir(name_dir)
        free_clusters = ImageTools.find_empty_clusters(3, self._info, self._file_system.get_indexed_fat_table())

        if free_clusters is None:
            raise ValueError("Not enough free image clusters. Clusters required: " + str(3))

        self._dir_parser.create_entry_in_directory(empty_entry_point, 'ERRINTERSEC', 0x00, free_clusters[0])

        for i in range(len(free_clusters)):
            if i == len(free_clusters) - 1:
                self._ft_proc.write_val_in_all_fat(self.end_clus_val, free_clusters[i])
            else:
                self._ft_proc.write_val_in_all_fat(free_clusters[i + 1], free_clusters[i])

        empty_entry_point = self._get_free_entry_point_in_dir(name_dir)
        new_free_clusters = ImageTools.find_empty_clusters(1, self._info, self._file_system.get_indexed_fat_table())

        if new_free_clusters is None:
            raise ValueError("Not enough free image clusters. Clusters required: " + str(1))

        self._dir_parser.create_entry_in_directory(empty_entry_point, 'ERRINTERS 2', 0x00, new_free_clusters[0])
        self._ft_proc.write_val_in_all_fat(free_clusters[1], new_free_clusters[0])

    def _get_free_entry_point_in_dir(self, name_dir: str):
        """
        Получение точки входа для свободной записи в директории name_dir
        :param name_dir: название директории
        :return: int, точка входа в свободную записись
        """
        if name_dir == '\\':
            dir_entry_point = self._file_system.get_fat_processor().info.first_root_dir_sec
        else:
            set_of_files = self._file_system.get_a_set_all_dir_entries_info()

            for dir_entry_info in set_of_files:
                if dir_entry_info.name.strip() == name_dir.strip() and dir_entry_info.attr.is_directory():
                    dir_entry_point = self._ft_proc.get_entry_for_cluster_in_data(dir_entry_info.first_cluster_num)
                    break
            else:
                raise ValueError(f"Directory \"{name_dir}\" does not exist")

        empty_entry_point = self._dir_parser.find_empty_entry_in_directory(dir_entry_point)

        if empty_entry_point is None:
            raise ValueError(f'No free entries in directory "{name_dir}"')

        return empty_entry_point

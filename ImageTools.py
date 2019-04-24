from IOManager import IOManager
from service_classes import InfoAboutImage, attribute_parser, DirectoryEntryInfo, DirectoryEntryLongNameInfo, \
    DirectoryInfo, IndexedEntryInfo
from enums import TypeOfFAT


class FatProcessor:
    """
    Организует работу с таблицей FAT, и её связь с областью данных
    """

    VALUE_MASK_FAT32 = 0x0FFFFFFF
    MINIMAL_END_CLUSTER_FAT16 = 0xFFF8
    MINIMAL_END_CLUSTER_FAT32 = 0x0FFFFFF8
    BAD_CLUSTER_FAT16 = 0xFFF7
    BAD_CLUSTER_FAT32 = 0x0FFFFFF7
    LENGTH_CLUSTER_FAT16 = 2
    LENGTH_CLUSTER_FAT32 = 4
    END_CLUSTER_IN_WIN_FAT_16 = 0xFFFF
    END_CLUSTER_IN_WIN_FAT_32 = 0x0FFFFFFF

    def __init__(self, info: InfoAboutImage, io_manager: IOManager):
        self.fat_type = info.fat_type
        self.info = info
        self.io_manager = io_manager

        if self.fat_type == TypeOfFAT.fat16:
            self.end_cluster = FatProcessor.MINIMAL_END_CLUSTER_FAT16
            self.bad_cluster = FatProcessor.BAD_CLUSTER_FAT16
        else:
            self.end_cluster = FatProcessor.MINIMAL_END_CLUSTER_FAT32
            self.bad_cluster = FatProcessor.BAD_CLUSTER_FAT32

    def get_entry_for_cluster_in_fat(self, n: int, fat_number: int):
        """
        Возвращает входную точку в n-го кластера в fat_number-ую таблицу FAT
        :param n: номер кластера
        :param fat_number: номер таблицы FAT
        :return: int
        """
        if n < 0 or self.info.count_of_clusters < n:
            raise ValueError(f'Out of fat-section, n: {n} / {self.info.count_of_clusters}')

        if self.info.BPB_FATSz16 != 0:
            fat_sz = self.info.BPB_FATSz16
        else:
            fat_sz = self.info.BPB_FATSz32

        if self.fat_type == TypeOfFAT.fat16:
            fat_offset = n * FatProcessor.LENGTH_CLUSTER_FAT16
        else:
            fat_offset = n * FatProcessor.LENGTH_CLUSTER_FAT32

        result = (self.info.BPB_ResvdSecCnt + fat_number * fat_sz) * self.info.BPB_BytsPerSec + fat_offset

        return result

    def get_entry_for_cluster_in_data(self, n: int):
        """
        Получение входной точки кластера n в области данных
        :param n: номер кластреа
        :return: int
        """
        if n < 0 or self.info.count_of_clusters < n:
            raise ValueError('Out of data-section')

        return (self.info.first_data_sector + (n - 2) * self.info.BPB_SecPerClus) * self.info.BPB_BytsPerSec

    def get_cluster_value_in_certain_fat(self, n: int, fat_number: int):
        """
        Получение значения n-го кластера в области fat_number-ой таблицы FAT
        :param n: номер кластера
        :param fat_number: номер таблицы FAT
        :return: int
        """
        entry = self.get_entry_for_cluster_in_fat(n, fat_number)
        self.io_manager.seek(entry)
        fat_cluster = self.io_manager.read_bytes_and_convert_to_int(TypeOfFAT.get_length_fat_entry[self.fat_type])

        if self.fat_type == TypeOfFAT.fat32:
            fat_cluster = fat_cluster & FatProcessor.VALUE_MASK_FAT32
        return fat_cluster

    def get_value_fat_cluster(self, n: int):
        """
        Получение значения n-го кластера в области таблицы FAT
        :param n: номер кластера
        :return: int
        """
        return self.get_cluster_value_in_certain_fat(n, 0)

    def is_end_cluster(self, fat_cluster_value: int):
        """
        Проверка значения кластера из таблицы FAT на эквивалентность EOC значению
        :param fat_cluster_value: значение кластера из таблицы FAT
        :return: bool
        """
        return fat_cluster_value >= self.end_cluster

    def is_bad_cluster(self, fat_cluster_value: int):
        """
        Проверка значения кластера из таблицы FAT на эквивалентность BAD CLUSTER значению
        :param fat_cluster_value: значение кластера из таблицы FAT
        :return: bool
        """
        return fat_cluster_value == self.bad_cluster

    def write_val_in_all_fat(self, val: int, clus: int):
        """
        Запись значения в кластер номер clus во все таблицы FAT
        :param val: записываемое значение
        :param clus: номер кластера в который будет идти запись
        :return: None
        """
        for i in range(self.info.BPB_NumFATs):
            self.write_val_in_certain_fat(val, clus, i)

    def write_val_in_certain_fat(self, val: int, clus: int, fat_num: int):
        """
        Запись значения в кластер clus в таблицу FAT под номером fat_num (нумерация с нуля)
        :param val: записываемое значение
        :param clus: номер кластера в который будет идти запись
        :param fat_num: номер таблицы FAT (нумерация с нуля)
        :return: None
        """
        entry = self.get_entry_for_cluster_in_fat(clus, fat_num)
        length = self.LENGTH_CLUSTER_FAT16 if \
            self.info.fat_type == TypeOfFAT.fat16 else \
            self.LENGTH_CLUSTER_FAT32
        self.io_manager.seek(entry)
        self.io_manager.write_int_value(val, length)

    def read_all_cluster_in_data(self, clus_num: int):
        """
        Чтение кластера из области данных
        :param clus_num: номер кластера
        :return: bytes
        """
        entry = self.get_entry_for_cluster_in_data(clus_num)
        bytes_len = self.info.get_bytes_per_cluster()

        self.io_manager.seek(entry)
        return self.io_manager.read_some_bytes(bytes_len)

    def write_all_cluster_in_data(self, val: bytes, clus_num: int):
        """
        Запись кластера в области данных
        :param val: записываемое значение
        :param clus_num: номер кластера
        :return: None
        """
        entry = self.get_entry_for_cluster_in_data(clus_num)

        self.io_manager.seek(entry)
        self.io_manager.write_some_bytes(val)


class DirectoryParser:
    """
    Организует работу с директориями в FAT, позволяет парсить директории и собирать о них информацию
    """

    EMPTY_RECORD = 0xe5
    END_OF_RECORDS = 0x00
    ENTRY_SIZE = 32

    def __init__(self, fat_proc: FatProcessor):
        self._io_manager = fat_proc.io_manager
        self.fat_proc = fat_proc
        self._info = fat_proc.info

    def get_full_directory_info(self, dir_ent_clus_num: int):
        """
        Получение информации о директории, располагающуюся на одном и более кластеров
        :param dir_ent_clus_num: номер первого кластера в таблице FAT
        :return: DirectoryInfo
        """
        fat_clus_value = dir_ent_clus_num
        dir_info = None
        while True:
            new_dir_info = self.get_dir_info_on_one_cluster(fat_clus_value,
                                                            self._info.get_count_entries_in_dir_cluster())
            if dir_info is None:
                dir_info = new_dir_info
            else:
                dir_info = dir_info.merge(new_dir_info)
            fat_clus_value = self.fat_proc.get_value_fat_cluster(fat_clus_value)
            if self.fat_proc.is_end_cluster(fat_clus_value):
                break

        return dir_info

    def get_fat16_root_directory_info(self):
        """
        Получение информации о корневой директории FAT 16
        :return: DirectoryInfo
        """
        return self._get_dir_info_on_one_cluster(self._info.first_root_dir_sec, self._info.BPB_RootEntCnt)

    def get_dir_info_on_one_cluster(self, dir_num_clus: int, max_entries_num: int):
        """
        Получение информации о директории на одном конктретном кластере
        :param dir_num_clus: номер кластера
        :param max_entries_num: максимальное количество записей в одном кластере директории
        :return: DirectoryInfo
        """
        entry_point = self.fat_proc.get_entry_for_cluster_in_data(dir_num_clus)
        return self._get_dir_info_on_one_cluster(entry_point, max_entries_num)

    def _get_dir_info_on_one_cluster(self, directory_entry_point: int, max_entries_num: int):
        """
        Получение информации о директории на одном конктретном кластере
        :param directory_entry_point: входная точка кластера
        :param max_entries_num: максимальное количество записей в одном кластере директории
        :return: DirectoryInfo
        """
        current_point = directory_entry_point

        entries_with_long_name = {}
        entries = []

        for i in range(max_entries_num):
            entry = self._parse_entry(current_point)

            self._io_manager.seek(current_point)
            type_entry = self._io_manager.read_bytes_and_convert_to_int(1)

            current_point = current_point + DirectoryParser.ENTRY_SIZE

            if type_entry == DirectoryParser.EMPTY_RECORD:
                continue
            elif type_entry == DirectoryParser.END_OF_RECORDS:
                break

            if isinstance(entry, DirectoryEntryInfo):
                if len(entries_with_long_name) != 0:
                    keys = [e.value for e in entries_with_long_name.values()]
                    keys.sort()

                    entry.name = ''.join([entries_with_long_name[v].get_full_name() for v in keys])
                    cut = entry.name.find('\x00')
                    if cut != -1:
                        entry.name = entry.name[:cut]

                    entries_with_long_name = {}
                else:
                    entry.name = entry.name.decode()
                entries.append(entry)
            else:
                entries_with_long_name[entry.value] = entry

        return DirectoryInfo(entries)

    def _parse_entry(self, input_recording_point: int):
        """
        Парсинг одной записи в директории
        :param input_recording_point: входная точка записи
        :return: DirectoryEntryInfo or DirectoryEntryLongNameInfo
        """
        self._io_manager.seek(input_recording_point + 11)
        attr = attribute_parser(self._io_manager.read_bytes_and_convert_to_int(1))

        self._io_manager.seek(input_recording_point)
        if attr.is_long_name():
            Ord = self._io_manager.read_bytes_and_convert_to_int(1)
            Name1 = self._io_manager.read_some_bytes(10)
            Attr = self._io_manager.read_bytes_and_convert_to_int(1)
            Type = self._io_manager.read_bytes_and_convert_to_int(1)
            Chksum = self._io_manager.read_bytes_and_convert_to_int(1)
            Name2 = self._io_manager.read_some_bytes(12)
            FstClusLO = self._io_manager.read_bytes_and_convert_to_int(2)
            Name3 = self._io_manager.read_some_bytes(4)
            return DirectoryEntryLongNameInfo(Ord, Name1, Chksum, Name2, Name3)
        else:
            name = self._io_manager.read_some_bytes(11)
            attr = self._io_manager.read_bytes_and_convert_to_int(1)
            NTRes = self._io_manager.read_bytes_and_convert_to_int(1)
            CrtTimeTenth = self._io_manager.read_bytes_and_convert_to_int(1)
            CrtTime = self._io_manager.read_bytes_and_convert_to_int(2)
            CrtDate = self._io_manager.read_bytes_and_convert_to_int(2)
            LstAccDate = self._io_manager.read_bytes_and_convert_to_int(2)
            FstClusHI = self._io_manager.read_bytes_and_convert_to_int(2)
            WrtTime = self._io_manager.read_bytes_and_convert_to_int(2)
            WrtDate = self._io_manager.read_bytes_and_convert_to_int(2)
            FstClusLO = self._io_manager.read_bytes_and_convert_to_int(2)
            FileSize = self._io_manager.read_bytes_and_convert_to_int(4)
            return DirectoryEntryInfo(name,
                                      attr,
                                      ((FstClusHI << 16) + FstClusLO if FstClusHI != 0 else FstClusLO),
                                      input_recording_point)

    def find_empty_entry_in_directory(self, directory_entry_point: int):
        """
        Ищет входную точку записи, которая является пустой
        :param directory_entry_point: входная точка директории в области данных
        :return: int, если была найдена пустая запись, None в противном случае
        """
        current_point = directory_entry_point

        for i in range(self._info.get_count_entries_in_dir_cluster()):
            self._io_manager.seek(current_point)
            type_entry = self._io_manager.read_bytes_and_convert_to_int(1)

            if type_entry == DirectoryParser.EMPTY_RECORD or type_entry == DirectoryParser.END_OF_RECORDS:
                return current_point

            current_point += DirectoryParser.ENTRY_SIZE

        return None

    def create_entry_in_directory(self, entry_point: int, name: str, attr: int, first_clus: int):
        """
        Создаёт запись в директории
        :param entry_point: входная точка записи в директории
        :param name: имя записываемого файла или директории
        :param attr: атрибуты записи
        :param first_clus: первый кластер файла или директории
        :return: None
        """
        if len(name) > 11:
            name = name[:11]
        elif len(name) < 11:
            name = '{:<11}'.format(name)
        name = name.upper()

        if not (attr == 0 or attr.bit_length() == 1):
            raise ValueError("Incorrect attributes of entry: " + str(attr))

        self._io_manager.seek(entry_point)
        self._io_manager.write_some_bytes(name.encode())
        self._io_manager.write_int_value(attr, 1)
        self._io_manager.seek(entry_point + 20)
        self._io_manager.write_int_value(first_clus >> 16, 2)
        self._io_manager.seek(entry_point + 26)
        self._io_manager.write_int_value(first_clus & 0xFFFF, 2)
        self._io_manager.write_int_value(1, 4)

    def delete_entry_in_directory(self, entry_point: int):
        """
        Удаляет запись в директории
        :param entry_point: входная точка записи
        :return: None
        """
        self._io_manager.seek(entry_point)
        self._io_manager.write_int_value(self.EMPTY_RECORD, 1)


class FileTreePrinter:  # pragma: no cover
    """
    Позволяет вывести на консоль структуру дерево файлов
    """

    def __init__(self, dir_parser: DirectoryParser):
        self._dir_parser = dir_parser
        self._info = dir_parser.fat_proc.info

    def print_tree(self):
        """
        Выводит дерево файлов
        :return: None
        """
        if self._info.fat_type == TypeOfFAT.fat16:
            dir_info = self._dir_parser.get_fat16_root_directory_info()
        else:
            dir_info = self._dir_parser.get_full_directory_info(self._info.BPB_RootClus)

        stack = [(0, '', dir_info)]

        while stack:
            tup = stack.pop()
            off = tup[0]
            name = tup[1]
            dir_info = tup[2]

            print(self._get_offset(off) + ('' if name == '' else '/') + name)

            for f in dir_info.get_files():
                print(self._get_offset(off + 1) + f.name)

            for d in dir_info.get_directories():
                if d.name.strip() != '.' and d.name.strip() != '..':
                    stack.append((off + 1, d.name, self._dir_parser.get_full_directory_info(d.first_cluster_num)))

    @staticmethod
    def _get_offset(n):
        """
        Получает отступ из пробелов длины n * 4 пробела
        :param n: количество отступов по 4 пробела
        :return: str
        """
        res = ''
        for i in range(1, n):
            res += '    '
        return res


class FatTableIndexer:
    """
    Индерксирует таблицу FAT, составляя словарь номер_кластера: сущность_файла, которому принадлежит кластер
    """

    def __init__(self, dir_parser: DirectoryParser):
        self._dir_parser = dir_parser
        self._info = dir_parser.fat_proc.info
        self._indexed_fat_table = {}
        self._index_fat_table()

    def get_full_indexed_fat_table(self):
        """
        Получения полного словаря, индексирующего таблицу FAT
        :return: dict {int: list[IndexedEntryInfo]}
        """
        return self._indexed_fat_table

    def get_correct_indexed_fat_table(self):
        """
        Получения необходимого для обработки файловой системы словаря, индексирующего таблицу FAT
        :return: dict {int: IndexedEntryInfo}
        """
        result = {}
        for i in self._indexed_fat_table:
            result[i] = self._indexed_fat_table[i][0]
        return result

    def _index_fat_table(self):
        if self._info.fat_type == TypeOfFAT.fat16:
            root_dir = self._dir_parser.get_fat16_root_directory_info()
        else:
            root_dir = self._get_all_dir_info_and_index(self._info.BPB_RootClus,
                                                        DirectoryEntryInfo('\\', None, self._info.BPB_RootClus, -1))
        stack = [root_dir]
        while stack:
            cur_dir = stack.pop()
            for f in cur_dir.get_files():
                self._index_all_file(f.first_cluster_num, f)

            for d in cur_dir.get_directories():
                if d.name.strip() != '.' and d.name.strip() != '..':
                    stack.append(self._get_all_dir_info_and_index(d.first_cluster_num, d))

    def _get_all_dir_info_and_index(self, num_first_dir_clus: int, dir_entry_info: DirectoryEntryInfo):
        """
        Получение полной информации о директории, и индексировании последней
        :param num_first_dir_clus: номер первого кластера директории в таблице FAT
        :param dir_entry_info: информация о записи в директории
        :return: DirectoryInfo
        """
        fat_clus_value = num_first_dir_clus
        last_clus = None
        dir_info = None
        while True:
            new_dir_info = self._dir_parser.get_dir_info_on_one_cluster(fat_clus_value,
                                                                        self._info.get_count_entries_in_dir_cluster())
            if self._index_cluster(num_first_dir_clus, last_clus, dir_entry_info, True):
                break
            if dir_info is None:
                dir_info = new_dir_info
            else:
                dir_info = dir_info.merge(new_dir_info)
            last_clus = fat_clus_value
            fat_clus_value = self._dir_parser.fat_proc.get_value_fat_cluster(fat_clus_value)
            if self._dir_parser.fat_proc.is_end_cluster(fat_clus_value):
                break

        return dir_info

    def _index_all_file(self, num_first_file_clus: int, dir_entry_info: DirectoryEntryInfo):
        """
        Индексирование всего файла
        :param num_first_file_clus: номер первого кластера файла
        :param dir_entry_info: информация о записи в директории
        :return: None
        """
        fat_clus_value = num_first_file_clus
        last_clus = None
        while True:
            if self._index_cluster(fat_clus_value, last_clus, dir_entry_info, False):
                break
            last_clus = fat_clus_value
            fat_clus_value = self._dir_parser.fat_proc.get_value_fat_cluster(fat_clus_value)
            if self._dir_parser.fat_proc.is_end_cluster(fat_clus_value):
                break

    def _index_cluster(self, clus_num: int, last_clus: int or None, dir_entry_info: DirectoryEntryInfo, is_dir: bool):
        """
        Индексирование кластера
        :param clus_num: номер кластера
        :param dir_entry_info: информация о записи в директории
        :param is_dir: является ли кластер частью дириктории
        :return: True, если требуется завершить дальнейшее индексирование файла, False - в противном случае
        """
        if clus_num not in self._indexed_fat_table:
            self._indexed_fat_table[clus_num] = []

        has_loop = False

        for entry in self._indexed_fat_table[clus_num]:
            if entry.dir_entry_info.name == dir_entry_info.name:
                has_loop = True

        self._indexed_fat_table[clus_num].append(IndexedEntryInfo(dir_entry_info, clus_num, last_clus, is_dir))

        is_next_cluster_bad = False
        f_proc = self._dir_parser.fat_proc

        if f_proc.is_bad_cluster(f_proc.get_value_fat_cluster(clus_num)):
            is_next_cluster_bad = True

        return has_loop or is_next_cluster_bad


class ClusterSwapper:
    """
    Класс, позволяющий безопасно менять менять местами два кластера
    """
    def __init__(self, indexed_fat_table: dict, ft_proc: FatProcessor, io_manager: IOManager):
        """
        :param indexed_fat_table: индексированная таблица FAT, в которой храняться данные о принадлежности кластеров
                                  файлам
        :param ft_proc: класс, умеющий получать данные о таблице фат и её отображении на область данных
        :param io_manager: менеджер работы с вводом/выводом
        """
        self._indexed_fat_table = indexed_fat_table
        self._ft_proc = ft_proc
        self._io_manager = io_manager
        self._info = ft_proc.info

    def swap_cluster(self, first_clus: int, second_clus: int):
        """
        Меняет местами два кластера. Если один из них - первый кластер файла или дириктории, то изменяет записи в нужной
        директории. Меняет indexed_fat_table, делая его актуальным для свопнутых файлов (включая измение данных внутри
        IndexedEntryInfo.
        :param first_clus: номер первого кластера, который нужно поменять
        :param second_clus: номер второго кластера, который нужно поменять
        :return: None
        """
        if first_clus == second_clus:
            return

        value_in_fat_first = self._ft_proc.get_value_fat_cluster(first_clus)
        value_in_fat_second = self._ft_proc.get_value_fat_cluster(second_clus)

        # меняем значения во всех FATs ---------------
        self._swap_value_in_fats(first_clus, second_clus)

        # меняем значение в предыдущих кластерах -----
        first_indexed_entry_info = self._get_indexed_entry_info(first_clus)
        second_indexed_entry_info = self._get_indexed_entry_info(second_clus)
        self._change_all_reference(second_clus, value_in_fat_first, first_indexed_entry_info)
        self._change_all_reference(first_clus, value_in_fat_second, second_indexed_entry_info)

        # меняем записи в индексированной таблице ----
        self._swap_value_in_indexed_table_fat(first_clus, second_clus)

        # меняем записи в области данных -------------
        self._swap_cluster_in_data(first_clus, second_clus)

        # сохраняем правильность хранения файлов в директории
        dir_parser = DirectoryParser(self._ft_proc)
        cnt_entries = dir_parser.fat_proc.info.get_count_entries_in_dir_cluster()
        for i in [first_clus, second_clus]:
            if i in self._indexed_fat_table and self._indexed_fat_table[i].is_directory:
                dir_info = dir_parser.get_dir_info_on_one_cluster(i, cnt_entries)
                for entry in dir_info.entries_list:
                    if entry.name.strip() == '.' or entry.name.strip() == '..':
                        continue
                    clus_num = entry.first_cluster_num
                    dir_entry_info = self._indexed_fat_table[clus_num].dir_entry_info
                    dir_entry_info.entry_point = entry.entry_point

    def _swap_value_in_indexed_table_fat(self, first_clus: int, second_clus: int):
        """
        Меняет значения в индексированном словаре у двух кластеров
        :param first_clus: номер первого кластера
        :param second_clus: номер второго кластера
        :return: None
        """
        if first_clus in self._indexed_fat_table and second_clus in self._indexed_fat_table:
            first_indexed_entry_info = self._indexed_fat_table[first_clus]
            self._indexed_fat_table[first_clus].cur_clus = second_clus
            self._indexed_fat_table[second_clus].cur_clus = first_clus

            self._indexed_fat_table[first_clus] = self._indexed_fat_table[second_clus]
            self._indexed_fat_table[second_clus] = first_indexed_entry_info

        elif first_clus not in self._indexed_fat_table and second_clus in self._indexed_fat_table:
            self._swap_ind_tab_fat_val_with_zero(second_clus, first_clus)

        elif second_clus not in self._indexed_fat_table and first_clus in self._indexed_fat_table:
            self._swap_ind_tab_fat_val_with_zero(first_clus, second_clus)

    def _swap_ind_tab_fat_val_with_zero(self, clus_without_zero: int, clus_with_zero):
        """
        Меняет значения в индексированном словаре у кластера из словаря и свободного кластера
        :param clus_without_zero: номер кластера из словаря
        :param clus_with_zero: номер свободного кластера
        :return:
        """
        self._indexed_fat_table[clus_without_zero].cur_clus = clus_with_zero
        self._indexed_fat_table[clus_with_zero] = self._indexed_fat_table[clus_without_zero]
        self._indexed_fat_table.pop(clus_without_zero)

    def _swap_value_in_fats(self, first_clus: int, second_clus: int):
        """
        Меняет местами два значения в таблице FAT
        :param first_clus: номер первого кластера
        :param second_clus: номер второго кластера
        :return: None
        """
        val_first_in_fat = self._ft_proc.get_value_fat_cluster(first_clus)
        val_second_in_fat = self._ft_proc.get_value_fat_cluster(second_clus)
        self._ft_proc.write_val_in_all_fat(val_second_in_fat, first_clus)
        self._ft_proc.write_val_in_all_fat(val_first_in_fat, second_clus)

    def _swap_cluster_in_data(self, first_clus: int, second_clus: int):
        """
        Меняет местами кластеры в области данных
        :param first_clus: номер первого кластера
        :param second_clus: номер второго кластера
        :return: None
        """
        first_val_in_data = self._ft_proc.read_all_cluster_in_data(first_clus)
        second_val_in_data = self._ft_proc.read_all_cluster_in_data(second_clus)
        self._ft_proc.write_all_cluster_in_data(first_val_in_data, second_clus)
        self._ft_proc.write_all_cluster_in_data(second_val_in_data, first_clus)

    def _change_all_reference(self, new_value: int, next_value_for_cur_clus: int,
                              indexed_entry_info_of_ch_clus: IndexedEntryInfo or None):
        """
        Изменяет сслыки на текущий кластер у предыдущего кластера и правит значение ссылки на текущий у слудующего
        кластера в цепочке
        :param new_value: значение, которые будет записана, в вышеуказанные ссылки
        :param next_value_for_cur_clus: номер следующего в цепочке кластера для текущего (значение из таблицы FAT)
        :param indexed_entry_info_of_ch_clus: IndexedEntryInfo для меняемого кластера
        :return: None
        """
        if indexed_entry_info_of_ch_clus is not None:
            last_clus = indexed_entry_info_of_ch_clus.last_clus
            cur_value_in_fat = self._ft_proc.get_value_fat_cluster(indexed_entry_info_of_ch_clus.cur_clus)

            if last_clus is None:
                self._write_first_clus_in_dir_entry(new_value, indexed_entry_info_of_ch_clus.dir_entry_info.entry_point)
                indexed_entry_info_of_ch_clus.dir_entry_info.first_cluster_num = new_value
            elif indexed_entry_info_of_ch_clus.cur_clus == cur_value_in_fat:  # особый случай при свопе
                self._ft_proc.write_val_in_all_fat(new_value, indexed_entry_info_of_ch_clus.cur_clus)
                indexed_entry_info_of_ch_clus.last_clus = indexed_entry_info_of_ch_clus.cur_clus
            else:
                self._ft_proc.write_val_in_all_fat(new_value, last_clus)

            if not self._ft_proc.is_end_cluster(next_value_for_cur_clus) and next_value_for_cur_clus != new_value:
                self._indexed_fat_table[next_value_for_cur_clus].last_clus = new_value

    def _write_first_clus_in_dir_entry(self, val: int, dir_entry_point: int):
        """
        Запись ного значения в запись в дириктории
        :param val: записываемое значение
        :param dir_entry_point: входная точка записи в дириктории
        :return: None
        """
        first_clus_hi = val >> 16
        first_clus_lo = val & 0xFFFF

        self._io_manager.seek(dir_entry_point + 20)
        self._io_manager.write_int_value(first_clus_hi, 2)

        self._io_manager.seek(dir_entry_point + 26)
        self._io_manager.write_int_value(first_clus_lo, 2)

    def _get_indexed_entry_info(self, clus_num: int):
        """
        Получение данных в индексированной таблице FAT по номеру кластера
        :param clus_num: номер кластера
        :return: IndexedEntryInfo, если такой кластер есть в таблице, None - в противном случае
        """
        if clus_num in self._indexed_fat_table:
            return self._indexed_fat_table[clus_num]
        return None


def get_fragmentation_data(fat_processor: FatProcessor):
    """
    Выдаёт данные о фрагментированности образа - float на отрезке [0, 100]
    :param fat_processor: FatProcessor
    :return: float [0, 100]
    """
    incorrect_clusters = 0
    count = 0
    for i in range(fat_processor.info.count_of_clusters):
        val_clus = fat_processor.get_value_fat_cluster(i)
        if val_clus == 0:
            continue
        count += 1
        if fat_processor.is_end_cluster(val_clus):
            continue
        if val_clus != i + 1:
            incorrect_clusters += 1
    return incorrect_clusters * 100 / count


def find_empty_clusters(num_of_clusters: int, info: InfoAboutImage, indexed_fat_table: dict):
    """
    Ищет набор из num_of_clusters свободных файлов
    :param indexed_fat_table: индексированная таблица FAT
    :param info: информация об образе
    :param num_of_clusters: количество необходимых кластеров
    :return: list [номера кластеров], None, если не удалось найти ни одного значения
    """
    result = []
    for i in range(2, info.count_of_clusters):
        if len(result) == num_of_clusters:
            break
        if i not in indexed_fat_table:
            result.append(i)
    else:
        if len(result):
            return None
        ValueError('Incorrect num_of_clusters: ' + str(num_of_clusters))
    return result

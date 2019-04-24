from ImageTools import FatProcessor
from enums import TypeOfFAT
from service_classes import InfoAboutImage


class FileSystem:
    """
    Абстаркция описания файловой системы
    """
    def __init__(self, info: InfoAboutImage, fr_proc: FatProcessor, indexed_fat_table: dict,
                 error_detector):
        self._type_of_fat = info.fat_type
        self._info = info
        self._ft_proc = fr_proc
        self._indexed_fat_table = indexed_fat_table
        self._error_detector = error_detector
        self._file_tree_printer = None

    def set_file_tree_printer(self, file_tree_printer):
        self._file_tree_printer = file_tree_printer

    def print_file_tree(self):
        if self._file_tree_printer is not None:
            self._file_tree_printer.print_tree()
        else:
            raise ValueError("File Tree Printer isn't initialize")

    def get_type_of_fat(self):
        """
        Возвращает тип FAT текущей файловой системы
        :return: TypeOfFAT
        """
        return self._type_of_fat

    def get_name_type_of_fat(self):
        """
        Возвращает название FAT текущей файловой системы
        :return: string
        """
        return TypeOfFAT.get_name_by_type[self._type_of_fat]

    def get_fat_processor(self):
        """
        :return: FatProcessor
        """
        return self._ft_proc

    def get_indexed_fat_table(self):
        """
        :return: dict {int: IndexedEntryInfo}
        """
        return self._indexed_fat_table

    def get_a_set_all_dir_entries_info(self):
        """
        Получение набора всех данных о записях в деректориях без повторений
        :return: set {DirectoryEntryInfo}
        """
        return set(map(lambda x: x.dir_entry_info, self._indexed_fat_table.values()))

    def get_error_detector(self):
        """
        :return: ErrorDetector
        """
        return self._error_detector

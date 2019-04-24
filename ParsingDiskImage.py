from FileSystem import FileSystem
from IOManager import IOManager
from error_in_fat import ErrorDetector
from service_classes import InfoAboutImage
import ImageTools


def parse_disk_image(io_manager: IOManager):
    """
    Разбирает образ диска, доступ к которому получен через io_manager
    :param io_manager: менеджер, необходимый для работы с образом
    :return: FileSystem
    """
    info = InfoAboutImage(io_manager)

    f_processor = ImageTools.FatProcessor(info, io_manager)
    error_detector = ErrorDetector(f_processor)
    d_parser = ImageTools.DirectoryParser(f_processor)
    ft_printer = ImageTools.FileTreePrinter(d_parser)

    if error_detector.check_differences_fats():
        return FileSystem(info, f_processor, {}, error_detector)

    ft_indexer = ImageTools.FatTableIndexer(d_parser)
    full_indexed_fat_table = ft_indexer.get_full_indexed_fat_table()

    if error_detector.analysis_fat_indexed_table(full_indexed_fat_table):
        return FileSystem(info, f_processor, full_indexed_fat_table, error_detector)

    correct_indexed_fat_table = ft_indexer.get_correct_indexed_fat_table()

    file_system = FileSystem(info, f_processor, correct_indexed_fat_table, error_detector)
    file_system.set_file_tree_printer(ft_printer)

    return file_system

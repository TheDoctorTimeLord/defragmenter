import argparse
from random import Random
from sys import stderr

from IOManager import IOManager
from ImageTools import get_fragmentation_data, DirectoryParser
from ParsingDiskImage import parse_disk_image
from defrag import Defragmenter
from error_in_fat import ErrorMaker, ErrorDetector
from fragm import Fragmenter


class ArgumentsException(Exception):  # pragma: no cover
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def error_handler(file_system, error_detector: ErrorDetector):  # pragma: no cover
    if error_detector.is_differences_fats():
        print("Таблицы FAT различаются", file=stderr)
        fat_nums = [i for i in range(file_system.get_fat_processor().info.BPB_NumFATs)]
        correct_fat = -1
        while correct_fat == -1:
            print(f"Выберете номер правильной таблицы FAT ({fat_nums}): ", end='')
            try:
                correct_fat = int(input())
                if correct_fat < 0 or correct_fat >= file_system.get_fat_processor().info.BPB_NumFATs:
                    raise ValueError()
            except Exception:
                correct_fat = -1
                print("Неверное значение")

        error_detector.fix_differences_fats(correct_fat)
        print("Таблицы исправлены", file=stderr)

        raise SystemExit

    if error_detector.is_looped_files():
        print("Некоторые файлы зациклены: " + str([i.dir_entry_info.name for i in error_detector.looped_files]),
              file=stderr)

        error_detector.fix_looped_files()
        error_detector.clearing_fat_table(file_system.get_indexed_fat_table())

        print("Зацикленные файлы удалены: " + str(error_detector.refresh_clus), file=stderr)
        raise SystemExit

    if error_detector.is_intersecting_files():
        list_files = []
        for int_fls in error_detector.intersecting_files:
            all_files = ', '.join(list(map(lambda x: x.dir_entry_info.name, int_fls)))
            list_files.append(f'{int_fls[0].cur_clus}: [{all_files}]')

        print("Некоторые файлы пересекаются: " + ', '.join(list_files), file=stderr)

        error_detector.fix_intersecting_files()
        error_detector.clearing_fat_table(file_system.get_indexed_fat_table())

        print("Пересекающиеся файлы удалены: " + str(error_detector.refresh_clus), file=stderr)
        raise SystemExit

    error_detector.clearing_fat_table(file_system.get_indexed_fat_table())
    if error_detector.found_orphan_clusters():
        print("Были удалены кластеры, не принадлежащие ни одному файлу: " + str(error_detector.refresh_clus),
              file=stderr)


def main(parsed_args):  # pragma: no cover
    try:
        io_manager = IOManager(parsed_args.path)
    except FileNotFoundError:
        print('Неверный параметр пути до файла', file=stderr)
        return
    except PermissionError:
        print('Выбранный файл используется каким-то другим процессом', file=stderr)
        return

    file_system_of_image = parse_disk_image(io_manager)
    print(file_system_of_image.get_name_type_of_fat(), end='\n')

    error_handler(file_system_of_image, file_system_of_image.get_error_detector())

    if parsed_args.type_action == 'tree':
        file_system_of_image.print_file_tree()

    elif parsed_args.type_action == 'fragmentation':
        print(f'Fragmentation (BEFORE): ~{int(get_fragmentation_data(file_system_of_image.get_fat_processor()))}%')
        fragm = Fragmenter(file_system_of_image, io_manager, Random())
        fragm.fragmentation(1000)

    elif parsed_args.type_action == 'defragmentation':
        defrag = Defragmenter(file_system_of_image, io_manager)
        defrag.defragmentation()

    elif parsed_args.type_action == 'error_fat_table':
        if parsed_args.fat_num is None:
            print("Не указана таблица FAT, в которую будут вноситься ошибки")
            exit(50)
        er = ErrorMaker(DirectoryParser(file_system_of_image.get_fat_processor()), file_system_of_image)
        er.make_error_in_fat_table(parsed_args.fat_num)

    elif parsed_args.type_action == 'error_looped_file':
        if parsed_args.folder is None:
            print("Не указана папка, в которую будут вноситься ошибки")
            raise SystemExit(50)
        er = ErrorMaker(DirectoryParser(file_system_of_image.get_fat_processor()), file_system_of_image)
        try:
            er.make_looped_file(parsed_args.folder)
        except ValueError as ex:
            print(ex.args[0], file=stderr)

    elif parsed_args.type_action == 'error_intersected_files':
        if parsed_args.folder is None:
            print("Не указана папка, в которую будут вноситься ошибки")
            raise SystemExit(51)
        er = ErrorMaker(DirectoryParser(file_system_of_image.get_fat_processor()), file_system_of_image)
        try:
            er.make_intersecting_files(parsed_args.folder)
        except ValueError as er:
            print(er.args[0], file=stderr)

    print()
    print(f'Fragmentation: ~{int(get_fragmentation_data(file_system_of_image.get_fat_processor()))}%')

    io_manager.close()


if __name__ == '__main__':  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="path to FAT image")
    parser.add_argument("type_action", choices=["tree", "fragmentation", "defragmentation", "error_fat_table",
                                                "error_looped_file", "error_intersected_files"],
                        help='type of action with this image. "tree" - print file tree, "fragmentation" - '
                             'fragmentation image, "defragmentation - defragmentation image, "error_fat_table" - make '
                             'error in second fat table, "error_looped_file" - make looped file, '
                             '"error_intersected_files" - make intersected files')
    parser.add_argument("-f", "--folder", type=str, help='only name of error folder')
    parser.add_argument("-n", "--fat_num", type=int, help='table number with error')
    parsed_args = parser.parse_args()
    main(parsed_args)

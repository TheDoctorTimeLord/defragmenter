import unittest
from random import Random

from IOManager import IOManager
from ImageTools import FatProcessor, DirectoryParser, get_fragmentation_data
from ParsingDiskImage import parse_disk_image
from defrag import Defragmenter
from enums import TypeOfFAT
from error_in_fat import ErrorMaker
from fragm import Fragmenter
from service_classes import InfoAboutImage


FAT_16_IMAGE = 'fat16_test'
FAT_32_IMAGE = 'fat32_test'  # Не будут работать тесты на Fat 32 (образ не влез на GitHub)


class TestParseDiskImage(unittest.TestCase):
    def test_fat16_recognition(self):
        io_manager = IOManager(FAT_16_IMAGE)
        file_system = parse_disk_image(io_manager)
        self.assertEqual(file_system.get_type_of_fat(), TypeOfFAT.fat16)

    def test_fat32_recognition(self):
        io_manager = IOManager(FAT_32_IMAGE)
        file_system = parse_disk_image(io_manager)
        self.assertEqual(file_system.get_type_of_fat(), TypeOfFAT.fat32)


class TestIOManager(unittest.TestCase):
    def test_io_manager_with_wrong_path(self):
        self.check_error(IOManager, FileNotFoundError, True, 'wrong_path')

    def test_io_manager_with_correct_path(self):
        self.check_error(IOManager, FileNotFoundError, False, 'test_io_manager')

    def test_read_some_bytes_with_correct_value(self):
        io_manager = IOManager('test_io_manager')
        result = io_manager.read_some_bytes(1)
        self.assertEqual(b'5', result)

    def test_read_some_bytes_with_incorrect_value(self):
        io_manager = IOManager('test_io_manager')
        self.check_error(io_manager.read_some_bytes, ValueError, True, 0)
        self.check_error(io_manager.read_some_bytes, ValueError, True, -10)

    def test_read_bytes_and_convert_to_int_with_correct_value(self):
        io_manager = IOManager('test_io_manager')
        result = io_manager.read_bytes_and_convert_to_int(1)
        self.assertEqual(53, result)

    def test_read_bytes_and_convert_to_int_with_incorrect_value(self):
        io_manager = IOManager('test_io_manager')
        self.check_error(io_manager.read_bytes_and_convert_to_int, ValueError, True, 0)
        self.check_error(io_manager.read_bytes_and_convert_to_int, ValueError, True, -10)

    def test_jump_back_with_correct_value(self):
        io_manager = IOManager('test_io_manager')
        io_manager.read_some_bytes(1)
        io_manager.jump_back(1)
        self.assertEqual(io_manager._current_position, 0)

    def test_jump_back_with_incorrect_value(self):
        io_manager = IOManager('test_io_manager')
        io_manager.read_some_bytes(1)
        self.check_error(io_manager.jump_back, ValueError, True, 2)
        self.check_error(io_manager.jump_back, ValueError, True, 0)
        self.check_error(io_manager.jump_back, ValueError, True, -10)

    def check_error(self, method, error, get_except, *args):
        has_except = False
        try:
            method(*args)
        except error:
            has_except = True

        if has_except == get_except:
            self.assertTrue(self)
        else:
            self.assertFalse(self)


class TestFatProcessor(unittest.TestCase):
    def setUp(self):
        self.fp_16 = self._init_fp(FAT_16_IMAGE)
        self.fp_32 = self._init_fp(FAT_32_IMAGE)

    @staticmethod
    def _init_fp(file_name):
        io_manager = IOManager(file_name)
        info = InfoAboutImage(io_manager)
        return FatProcessor(info, io_manager)

    def check_error(self, method, error, *args):
        try:
            method(*args)
        except error:
            self.assertTrue(self)
        else:
            self.assertFalse(self)

    def test_incorrect_num_of_clus_data_less_zero(self):
        self.check_error(self.fp_16.get_entry_for_cluster_in_data, ValueError, -5)

    def test_incorrect_num_of_clus_data_bigger_max(self):
        self.check_error(self.fp_16.get_entry_for_cluster_in_data, ValueError, 10000000)

    def test_incorrect_num_of_clus_fat_less_zero(self):
        self.check_error(self.fp_16.get_entry_for_cluster_in_fat, ValueError, -5, self.fp_16.info.fat_type)

    def test_incorrect_num_of_clus_fat_bigger_max(self):
        self.check_error(self.fp_16.get_entry_for_cluster_in_fat, ValueError, 10000000, self.fp_16.info.fat_type)

    def test_correct_num_of_clus_data(self):
        value_for_16 = self.fp_16.get_entry_for_cluster_in_data(1)
        answer_for_16 = 278528
        value_for_32 = self.fp_32.get_entry_for_cluster_in_data(1)
        answer_for_32 = 1063936

        self.assertEqual(value_for_16, answer_for_16)
        self.assertEqual(value_for_32, answer_for_32)

    def test_correct_num_of_clus_fat(self):
        value_for_16 = self.fp_16.get_entry_for_cluster_in_fat(1, 0)
        answer_for_16 = 1026
        value_for_32 = self.fp_32.get_entry_for_cluster_in_fat(1, 0)
        answer_for_32 = 16388

        self.assertEqual(value_for_16, answer_for_16)
        self.assertEqual(value_for_32, answer_for_32)


class TestDirectoryParser(unittest.TestCase):
    def setUp(self):
        self.dp_16 = self._init_dp(FAT_16_IMAGE)
        self.dp_32 = self._init_dp(FAT_32_IMAGE)

    @staticmethod
    def _init_dp(file_name):
        io_manager = IOManager(file_name)
        info = InfoAboutImage(io_manager)
        fp = FatProcessor(info, io_manager)
        return DirectoryParser(fp)

    def test_root_dir_info_for_fat16(self):
        self.folder_content(['NewVHD'],
                            ['System Volume Information', '$RECYCLEBIN', 'FIRST', 'second_with_long_name'],
                            self.dp_16.get_fat16_root_directory_info)

    def test_not_root_folder_in_fat16(self):
        first_clus_folder = 8
        self.folder_content(['first file.txt'],
                            ['inside_folder', '.', '..'],
                            self.dp_16.get_full_directory_info,
                            first_clus_folder)

    def test_root_dir_info_for_fat32(self):
        first_clus_folder = self.dp_32.fat_proc.info.BPB_RootClus
        self.folder_content(['NewVHD'],
                            ['System Volume Information', '$RECYCLEBIN', 'FOLDER', 'big folder'],
                            self.dp_32.get_full_directory_info,
                            first_clus_folder)

    def test_not_root_dir_info_for_fat32(self):
        first_clus_folder = 6
        self.folder_content(['new_text_folder.txt'],
                            ['.', '..'],
                            self.dp_32.get_full_directory_info,
                            first_clus_folder)

    def test_big_folder(self):
        first_clus_folder = 15
        self.folder_content(['GEN     PY'] + [str(i) for i in range(100)],
                            ['.', '..'],
                            self.dp_32.get_full_directory_info,
                            first_clus_folder)

    def folder_content(self, file_names, dir_names, method, *args, **kwargs):
        dir_info = method(*args, **kwargs)

        self.assertEqual(len(dir_info.get_files()), len(file_names))
        self.assertEqual(len(dir_info.get_directories()), len(dir_names))

        for i in file_names:
            self.assertIn(i, map(lambda x: x.name.strip(), dir_info.get_files()))
        for i in dir_names:
            self.assertIn(i, map(lambda x: x.name.strip(), dir_info.get_directories()))


FAT_16_IMAGE_FOR_DEFRAG = "fat16.vhd"
FAT_32_IMAGE_FOR_DEFRAG = "fat32.vhd"


class DefragFragmTests(unittest.TestCase):
    def setUp(self):
        self.file_system_16, self.io_manager_16 = self._get_file_system(TypeOfFAT.fat16)
        self.file_system_32, self.io_manager_32 = self._get_file_system(TypeOfFAT.fat32)

    @staticmethod
    def _get_file_system(type_of_fat: TypeOfFAT):
        io_manager = IOManager(FAT_16_IMAGE_FOR_DEFRAG if type_of_fat == TypeOfFAT.fat16 else FAT_32_IMAGE_FOR_DEFRAG)
        return parse_disk_image(io_manager), io_manager

    def test_get_fragmentation_data(self):
        value = get_fragmentation_data(self.file_system_16.get_fat_processor())
        self.assertEqual(int(value), 0)

    def test_defragmentation_fat_16(self):
        fragm = Fragmenter(self.file_system_16, self.io_manager_16, Random(1))
        fragm.fragmentation(100)

        value = get_fragmentation_data(self.file_system_16.get_fat_processor())
        self.assertTrue(value > 10)

        defrag = Defragmenter(self.file_system_16, self.io_manager_16)
        defrag.defragmentation()

        value = get_fragmentation_data(self.file_system_16.get_fat_processor())
        self.assertTrue(value < 2)

    def test_defragmentation_fat_32(self):
        fragm = Fragmenter(self.file_system_32, self.io_manager_32, Random(1))
        fragm.fragmentation(100)

        value = get_fragmentation_data(self.file_system_32.get_fat_processor())
        self.assertTrue(value > 10)

        defrag = Defragmenter(self.file_system_32, self.io_manager_32)
        defrag.defragmentation()

        value = get_fragmentation_data(self.file_system_32.get_fat_processor())
        self.assertTrue(value < 10)


class ErrorTest(unittest.TestCase):
    def setUp(self):
        self.io_manager_16 = IOManager(FAT_16_IMAGE_FOR_DEFRAG)
        self.error_maker_16 = self.initialisation_error_maker(self.io_manager_16)

        self.io_manager_32 = IOManager(FAT_32_IMAGE_FOR_DEFRAG)
        self.error_maker_32 = self.initialisation_error_maker(self.io_manager_32)

    @staticmethod
    def initialisation_error_maker(io_manager):
        file_system = parse_disk_image(io_manager)
        return ErrorMaker(DirectoryParser(file_system.get_fat_processor()), file_system)

    def test_error_in_fat_16_table(self):
        self.error_in_fat_table(self.error_maker_16, self.io_manager_16)

    def test_error_in_fat_32_table(self):
        self.error_in_fat_table(self.error_maker_32, self.io_manager_32)

    def error_in_fat_table(self, error_maker, io_manager):
        error_maker.make_error_in_fat_table(1)
        file_system = parse_disk_image(io_manager)
        error_detector = file_system.get_error_detector()

        self.assertTrue(error_detector.is_differences_fats())

        error_detector.fix_differences_fats(0)
        self.assertFalse(error_detector.check_differences_fats())

    def test_looped_file_fat_16(self):
        self.looped_file_fat(self.error_maker_16, self.io_manager_16, '\\')

    def test_looped_file_fat_32(self):
        self.looped_file_fat(self.error_maker_32, self.io_manager_32, '\\')

    def looped_file_fat(self, error_maker, io_manager, folder_name):
        error_maker.make_looped_file(folder_name)
        file_system = parse_disk_image(io_manager)
        error_detector = file_system.get_error_detector()

        self.assertTrue(error_detector.is_looped_files())

        error_detector.fix_looped_files()
        error_detector.clearing_fat_table(file_system.get_indexed_fat_table())
        self.assertFalse(error_detector.is_looped_files())

    def test_intersecting_files_fat_16(self):
        self.intersecting_files(self.error_maker_16, self.io_manager_16, "\\")

    def test_intersecting_files_fat_32(self):
        self.intersecting_files(self.error_maker_32, self.io_manager_32, "\\")

    def intersecting_files(self, error_maker, io_manager, folder_name):
        error_maker.make_intersecting_files(folder_name)
        file_system = parse_disk_image(io_manager)
        error_detector = file_system.get_error_detector()

        self.assertTrue(error_detector.is_intersecting_files())

        error_detector.fix_intersecting_files()
        error_detector.clearing_fat_table(file_system.get_indexed_fat_table())
        self.assertFalse(error_detector.is_intersecting_files())


if __name__ == '__main__':
    unittest.main()

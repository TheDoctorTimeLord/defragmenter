class IOManager:
    """
    Менеджер работы с образом
    """
    def __init__(self, file_path):
        try:
            self._image = open(file_path, 'r+b')
        except FileNotFoundError:
            raise
        self._current_position = 0

    def __del__(self):
        try:
            self._image.close()
        except AttributeError:
            pass

    def close(self):
        """
        Корректное закрытие файла
        """
        self._image.close()

    def read_some_bytes(self, count: int):
        """
        Считывает следующие count байт в файле
        :param count: Число байт, которые необходимо считать
        :return: bytes, считанные из файла
        """
        if count <= 0:
            raise ValueError('Некорректное число байт')
        self._current_position += count
        result = self._image.read(count)
        return result

    def read_bytes_and_convert_to_int(self, count: int):
        """
        Считывает следующие count байт в файле и преобразует их к int
        :param count: Число байт, которые необходимо считать
        :return: int, преобразованные байты
        """
        result = self.read_some_bytes(count)
        result = int.from_bytes(result, 'little')
        return result

    def jump_back(self, count_of_bytes: int):
        """
        Возвращает указатель в файле на count_of_bytes байт назад
        :param count_of_bytes: число байт, на которые требуется вернуть указатель в файле
        """
        if count_of_bytes <= 0:
            raise ValueError('Некорректный прыжок')
        if count_of_bytes > self._current_position:
            raise ValueError("Выход за границы файла")
        self._current_position -= count_of_bytes
        self._image.seek(self._current_position)

    def seek(self, position: int):
        """
        Смещение в файле на позицию, относительно начала файла
        :param position: позция, относительно начала файла
        :return: None
        """
        self._current_position = position
        self._image.seek(position)

    def write_int_value(self, value: int, length: int):
        """
        Запись интового значения на образ в current_position
        :param value: записываемое значение
        :param length: длинна записываемого значения
        :return: None
        """
        self._current_position += length
        self._image.write(int.to_bytes(value, length, 'little'))

    def write_some_bytes(self, value: bytes):
        """
        Записывает некоторое количество байт на образ в current_position
        :param value: записываемые байты
        :return: None
        """
        self._current_position += len(value)
        self._image.write(value)

import os


# 定义恢复文件的类
class Recovery:
    def __init__(self):
        """
        初始化方法
        """
        self.recovery_path = os.path.join('recovery_file')
        pass

    @staticmethod
    def get_resident_file_data(disk):
        """
        读取并返回常驻文件的文件数据
        :param disk: 打开的磁盘指针，目前指向偏移该属性起始位置0x9的地方
        :return: 读取到的文件数据
        """
        disk.seek(7, 1)  # 因为数据长度存放在偏移该属性起始位置0x10的地方，而磁盘指针目前位于偏移该属性起始位置9个字节的地方，所以可以从当前位置开始向前7个字节来到文件数据长度的起始位置
        data_length = int.from_bytes(disk.read(4), 'little')  # 读取文件数据长度
        data_start_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取文件数据起始位置的偏移地址
        disk.seek(data_start_offset_address - 0x16,
                  1)  # 因为磁盘指针目前位于偏移该属性起始位置0x16个字节的地方，所以可以从当前位置开始向前（文件数据起始位置的偏移地址-0x16）个字节来到文件数据长度的起始位置
        return disk.read(data_length)  # 读取文件数据并返回

    @staticmethod
    def get_nonresident_file_data(disk, attribute_length, sectors_num_per_cluster, bytes_num_per_sector):
        """
        读取并返回非常驻文件的文件数据
        :param disk: 打开的磁盘指针，目前指向偏移该属性起始位置0x9的地方
        :param attribute_length: 该80H属性的长度
        :param sectors_num_per_cluster: 每一簇的扇区数
        :param bytes_num_per_sector: 每一扇区的字节数
        :return: 读取到的文件数据
        """
        disk.seek(0x17,
                  1)  # 因为Data Run偏移地址存放在偏移该属性起始位置0x20的地方，而磁盘指针目前位于偏移该属性起始位置9个字节的地方，所以可以从当前位置开始向前0x17个字节来到Data Run偏移地址存放的位置
        data_run_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取Data Run偏移地址
        disk.seek(14, 1)  # 移动到文件实际大小的存放地址起始处
        attribute_actual_size = int.from_bytes(disk.read(8), 'little')  # 读取属性实际大小
        disk.seek(data_run_offset_address - 0x38, 1)  # 移动到Data Run起始位置
        compress_byte = int.from_bytes(disk.read(1), 'little')  # 读取80H的数据流的压缩字节
        data_run_offset_address_end = data_run_offset_address  # 记录当前80H的数据流的终止偏移地址
        pre_run_list_start_position_in_byte = 0  # 记录前一个数据流真正起始位置的字节号，初始化为0
        run_list_list = []  # 存有每一个数据流信息的列表
        # 因为80H的数据流可能不止一个，所以需要循环遍历，直到压缩字节为0x00或解析得出的80H数据流信息终止偏移地址超出80H属性长度为止
        while compress_byte:
            compress_byte_high = compress_byte >> 4  # 获取数据流压缩字节的高位，即真正数据流起始簇号信息占用的字节数
            compress_byte_low = compress_byte & 0x0f  # 获取数据流压缩字节的低位，即真正数据流空间大小信息占用的字节数
            data_run_offset_address_end += 1 + compress_byte_high + compress_byte_low  # 更新当前80H的数据流的终止偏移地址
            # 判断当前80H数据流的终止偏移地址是否已经大于等于80H属性的长度，若大于，则当前80H数据流无效，可以直接跳出循环
            if data_run_offset_address_end >= attribute_length:
                break
            run_list_bytes_num = int.from_bytes(disk.read(compress_byte_low),
                                                'little') * sectors_num_per_cluster * bytes_num_per_sector  # 计算数据流占用的字节数
            run_list_start_position_in_byte = int.from_bytes(disk.read(compress_byte_high),
                                                             'little') * sectors_num_per_cluster * bytes_num_per_sector + pre_run_list_start_position_in_byte  # 计算以字节为单位的数据流起始位置
            pre_run_list_start_position_in_byte = run_list_start_position_in_byte  # 更新前一个数据流真正起始位置的字节号
            run_list_list.append((run_list_start_position_in_byte, run_list_bytes_num))  # 保存当前数据流信息
            compress_byte = int.from_bytes(disk.read(1), 'little')  # 读取下一个80H的数据流的压缩字节
        recovered_data = b''  # 初始化要恢复的数据
        # 遍历所有数据流，恢复文件数据
        for run_list in run_list_list:
            # 数据流大小大于等于实际还没读取的文件数据大小
            if attribute_actual_size <= run_list[1]:
                disk.seek(run_list[0])  # 移动到文件数据起始位置
                recovered_data += disk.read(attribute_actual_size)  # 读取文件数据
                break
            # 数据流大小小于实际还没读取的文件数据大小
            else:
                disk.seek(run_list[0])  # 移动到文件数据起始位置
                recovered_data += disk.read(run_list[1])  # 读取文件数据
                attribute_actual_size -= run_list[1]  # 更新实际还没读取的文件数据大小
        return recovered_data

    def recover_file(self, disk, file_offset_address, file_recovered_name, sectors_num_per_cluster,
                     bytes_num_per_sector):
        """
        恢复指定的被删除文件
        :param disk: 打开的磁盘指针
        :param file_offset_address: 被删除文件记录的起始位置偏移量
        :param file_recovered_name: 恢复后的文件名
        :param sectors_num_per_cluster: 每一簇的扇区数
        :param bytes_num_per_sector: 每一扇区的字节数
        :return: None
        """
        disk.seek(file_offset_address)  # 不知道为什么，需要先跳到离目标位置较近的512倍数字节位置，然后读一下才能重新一次定位到目标位置，不然两行后的代码会报错
        disk.read(1)
        disk.seek(file_offset_address + 0x14)  # 跳转到要恢复的文件记录中第一个属性的偏移地址存放的位置
        first_attribute_stream_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取第一个属性流偏移地址
        disk.seek(file_offset_address + first_attribute_stream_offset_address)  # 移动到第一个属性流的起始位置
        attribute_type = hex(int.from_bytes(disk.read(4), 'little'))  # 读取第一个属性的类型
        # 文件数据流的起始位置和占用空间都存放在80H属性，所以需要遍历属性直到找到80H属性为止
        while attribute_type != '0x80':
            attribute_length = int.from_bytes(disk.read(4), 'little')  # 读取属性长度
            disk.seek(attribute_length - 8, 1)  # 因为磁盘指针位于偏移该属性流起始位置8个字节的地方，所以可以从当前位置开始向前（属性长度-8）个字节来到下一个属性流的起始位置
            attribute_type = hex(int.from_bytes(disk.read(4), 'little'))  # 读取下一个属性的类型
        attribute_length = int.from_bytes(disk.read(4), 'little')  # 读取80H属性长度
        resident_sign = int.from_bytes(disk.read(1), 'little')  # 读取常驻标志
        if resident_sign:
            # 获取非常驻文件数据
            recovered_data = self.get_nonresident_file_data(disk=disk, attribute_length=attribute_length,
                                                            sectors_num_per_cluster=sectors_num_per_cluster,
                                                            bytes_num_per_sector=bytes_num_per_sector)
        else:
            # 获取常驻文件数据
            recovered_data = self.get_resident_file_data(disk=disk)
        # 目录不存在时需要创建目录
        if not os.path.exists(self.recovery_path):
            os.mkdir(self.recovery_path)
            print('目录' + self.recovery_path + '不存在，已帮您创建该目录！')
        # 将恢复的文件数据写入新文件
        file_save_path = os.path.join(self.recovery_path, file_recovered_name)
        # 将新文件名称拆分成名字和后缀
        suffix = '.' + file_recovered_name.split('.')[-1]
        if file_recovered_name.split('.')[:-1]:
            file_recovered_name = '.'.join(file_recovered_name.split('.')[:-1])
        index = 0
        # 检查该文件是否已经存在
        while os.path.exists(file_save_path):
            print(file_save_path + '已存在，尝试使用新路径', end='')
            file_save_path = os.path.join(self.recovery_path, file_recovered_name + str(index) + suffix)
            print(file_save_path)
            index += 1
        with open(file_save_path, 'wb') as file:
            file.write(recovered_data)
        print(file_save_path + '恢复成功！\n\n')

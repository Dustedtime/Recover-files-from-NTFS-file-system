# 定义MFT文件类
class MFT:
    def __init__(self, drive_name, bytes_num_per_sector, sectors_num_per_cluster, start_position_in_bytes, sectors_num):
        """
        类初始化方法
        :param drive_name: 驱动盘名称
        :param bytes_num_per_sector: 每一扇区的字节数
        :param sectors_num_per_cluster: 每一簇的扇区数
        :param start_position_in_bytes: 以字节为单位的$MFT起始位置
        :param sectors_num: 该逻辑盘扇区总数
        """
        self.drive_name = drive_name
        self.bytes_num_per_sector = bytes_num_per_sector
        self.sectors_num_per_cluster = sectors_num_per_cluster
        self.start_position_in_bytes = start_position_in_bytes
        self.sectors_num = sectors_num
        self.mft_data_stream_list = []  # 记录mft每一个数据流以字节为单位的起始位置以及其占用的扇区数，其中每一个mft数据流的信息用一个元组存放
        self.deleted_file_list = []  # 记录所处的MFT数据流序号、被删除的文件记录在其所处数据流中的序号以及文件名，其中每一个文件的信息用一个元组存放

    def find_mft_data_stream(self):
        """
        查找每一个mft数据流并记录其以字节为单位的起始位置和占用空间
        :return: None
        """
        print('正在查找' + self.drive_name + '盘的mft数据流...')
        # 打开磁盘
        with open(r'\\.\\' + self.drive_name + ':', 'rb') as disk:
            disk.seek(self.start_position_in_bytes)  # 这两行省略会报错，原因不知
            disk.read(1)
            disk.seek(self.start_position_in_bytes + 0x14)  # 移动到$MFT第一个属性流的偏移地址的存放处
            first_attribute_stream_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取第一个属性流偏移地址
            disk.seek(self.start_position_in_bytes + first_attribute_stream_offset_address)  # 移动到第一个属性流的起始位置
            attribute_type = hex(int.from_bytes(disk.read(4), 'little'))  # 读取第一个属性的类型
            # mft所有数据流的起始位置和占用空间都存放在80H属性，所以需要遍历属性直到找到80H属性为止
            while attribute_type != '0x80':
                attribute_length = int.from_bytes(disk.read(4), 'little')  # 读取属性长度
                disk.seek(attribute_length - 8, 1)  # 因为磁盘指针位于偏移该属性流起始位置8个字节的地方，所以可以从当前位置开始向前（属性长度-8）个字节来到下一个属性流的起始位置
                attribute_type = hex(int.from_bytes(disk.read(4), 'little'))  # 读取下一个属性的类型
            attribute_length = int.from_bytes(disk.read(4), 'little')  # 读取80H属性的长度
            disk.seek(0x18, 1)  # 因为MFT的80H属性肯定是非常驻属性，所以直接向前0x18个字节来到80H的数据流信息的偏移地址的存放处
            data_run_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取80H的数据流信息的偏移地址
            disk.seek(data_run_offset_address - 0x22,
                      1)  # 因为磁盘指针位于偏移该属性流起始位置0x22个字节的地方，所以可以从当前位置开始向前（80H的数据流信息的偏移地址-0x22）个字节来到80H的数据流信息的起始位置
            compress_byte = int.from_bytes(disk.read(1), 'little')  # 读取80H的数据流的压缩字节
            data_run_offset_address_end = data_run_offset_address  # 记录当前80H的数据流的终止偏移地址
            pre_run_list_start_position_in_byte = 0  # 记录前一个数据流真正起始位置的字节号，初始化为0
            # 因为80H的数据流可能不止一个，所以需要循环遍历，直到压缩字节为0x00或解析得出的80H数据流信息终止偏移地址超出80H属性长度为止
            while compress_byte:
                compress_byte_high = compress_byte >> 4  # 获取数据流压缩字节的高位，即真正数据流起始簇号信息占用的字节数
                compress_byte_low = compress_byte & 0x0f  # 获取数据流压缩字节的低位，即真正数据流空间大小信息占用的字节数
                data_run_offset_address_end += 1 + compress_byte_high + compress_byte_low  # 更新当前80H的数据流的终止偏移地址
                # 判断当前80H数据流的终止偏移地址是否已经大于等于80H属性的长度，若大于，则当前80H数据流无效，可以直接跳出循环
                if data_run_offset_address_end >= attribute_length:
                    break
                run_list_sectors_num = int.from_bytes(disk.read(compress_byte_low),
                                                      'little') * self.sectors_num_per_cluster  # 计算数据流占用的扇区数
                run_list_start_position_in_byte = int.from_bytes(disk.read(compress_byte_high),
                                                                 'little') * self.sectors_num_per_cluster * self.bytes_num_per_sector + pre_run_list_start_position_in_byte  # 计算以字节为单位的数据流起始位置
                pre_run_list_start_position_in_byte = run_list_start_position_in_byte  # 更新前一个数据流真正起始位置的字节号
                self.mft_data_stream_list.append((run_list_start_position_in_byte, run_list_sectors_num))  # 保存该数据流信息
                compress_byte = int.from_bytes(disk.read(1), 'little')  # 读取下一个80H的数据流的压缩字节
        print(self.drive_name + '盘所有MFT数据流列表加载完成！')

    def find_deleted_file(self):
        """
        查找被删除的文件，并记录其属性的起始位置、所处的MFT数据流序号以及文件名
        :return: None
        """
        print('正在查找' + self.drive_name + '盘的被删除文件...')
        # 打开磁盘
        with open(r'\\.\\' + self.drive_name + ':', 'rb') as disk:
            for index, mft_data_stream in enumerate(self.mft_data_stream_list):
                disk.seek(mft_data_stream[0])  # 移动到对应的数据流起始位置
                file_num = mft_data_stream[1] // 2  # 因为每两个扇区表示一个文件的属性，所以可以计算该数据流最多可以存放文件属性的数目
                # 遍历该数据流所有文件记录
                for file_index in range(file_num):
                    # MFT有几段数据流会越界，原因不知，所以需要检测数据流真实地址是否超过最大扇区号
                    if (mft_data_stream[0] + (
                            file_index + 1) * self.bytes_num_per_sector * 2) / self.bytes_num_per_sector > self.sectors_num:
                        break
                    file_flag = disk.read(4)  # 尝试获取FILE标志
                    disk.seek(mft_data_stream[
                                  0] + file_index * self.bytes_num_per_sector * 2 + 20)  # 因为磁盘指针位于偏移该文件记录起始位置4个字节的地方，而文件记录第一个属性起始位置的偏移地址为0x14，所以可以从当前位置开始向前0x10个字节来到文件第一个属性起始位置偏移地址的存放位置
                    first_attribute_stream_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取第一个属性起始位置的偏移地址
                    using_flag = int.from_bytes(disk.read(2), 'little')  # 读取文件使用标志
                    # 当成功获取到FILE标志且文件使用标志为0时，该文件才有可能是被删除的文件
                    if file_flag == b'FILE' and using_flag == 0:
                        filename = self.find_filename(disk=disk,
                                                      first_attribute_stream_offset_address=first_attribute_stream_offset_address)  # 获取文件名
                        # 若文件名不为空，则将该文件相关信息保存起来
                        if filename != '':
                            self.deleted_file_list.append((index, file_index, filename))
                    disk.seek(mft_data_stream[0] + (file_index + 1) * self.bytes_num_per_sector * 2)  # 跳转到下一个文件记录的起始位置
        print(self.drive_name + '盘所有被删除文件记录列表加载完成，', end='')
        print('总共有' + str(len(self.deleted_file_list)) + '项！')

    @staticmethod
    def find_filename(disk, first_attribute_stream_offset_address):
        """
        找到并返回这个文件的名字
        :param disk: 打开的磁盘指针，目前指向偏移该文件记录起始位置0x18的地方
        :param first_attribute_stream_offset_address: 文件记录中第一个属性起始位置的偏移地址
        :return: 找到的文件名
        """
        disk.seek(first_attribute_stream_offset_address - 0x18,
                  1)  # 因为磁盘指针位于偏移该文件记录起始位置0x18个字节的地方，所以可以从当前位置开始向前(第一个属性起始位置的偏移地址-0x18)个字节来到文件第一个属性起始位置
        attribute_type = hex(int.from_bytes(disk.read(4), 'little'))  # 读取第一个属性的类型
        # 文件名存放在30H属性，所以需要遍历属性直到找到30H属性或文件记录终止符为止
        while attribute_type != '0x30' and attribute_type != '0xffffffff':
            attribute_length = int.from_bytes(disk.read(4), 'little')  # 读取属性长度
            disk.seek(attribute_length - 8, 1)  # 因为磁盘指针位于偏移该属性起始位置8个字节的地方，所以可以从当前位置开始向前（属性长度-8）个字节来到下一个属性的起始位置
            attribute_type = hex(int.from_bytes(disk.read(4), 'little'))  # 读取下一个属性的类型
        # 没有找到30H属性，直接返回空字符串表示文件名查找失败，这个文件记录不是被删除文件的记录
        if attribute_type == '0xffffffff':
            return ''
        # 找到30H属性，接下来从30H属性中提取文件名并返回
        else:
            disk.seek(0x10, 1)  # 定位到30H属性体内容开始的偏移量存放的地方
            attribute_body_offset_address = int.from_bytes(disk.read(2), 'little')  # 读取属性体内容开始的偏移量
            disk.seek(attribute_body_offset_address - 0x16 + 0x40,
                      1)  # 因为磁盘指针位于偏移该属性起始位置0x16个字节的地方，而文件名长度存放的地方相对于属性体内容开始的地方偏移0x40个字节，所以可以从当前位置向前（属性体内容开始的偏移量-0x16+0x40）个字节来到文件名长度所在的地方
            filename_length = int.from_bytes(disk.read(1), 'little')  # 读取文件名长度
            disk.seek(1, 1)  # 向前移动一位，找到存放文件名的起始位置
            return str(disk.read(filename_length * 2), encoding='utf-16')  # 读取文件名并返回

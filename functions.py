import win32api


class Function:
    def __init__(self):
        pass

    @staticmethod
    def get_drives_name():
        """
        获取系统中所有逻辑驱动器的盘符
        :return: 统中所有逻辑驱动器的盘符组成的列表
        """
        drives_name = []  # 初始化盘符空列表
        drives_name_strings_list = win32api.GetLogicalDriveStrings().split('\x00')  # 获取所有逻辑驱动器盘符
        for drive_name in drives_name_strings_list:
            if drive_name and drive_name[0] not in ['A', 'B']:
                drives_name.append(drive_name[0])
        return drives_name

    @staticmethod
    def get_basic_info_of_mft(drive_name):
        """
        获取逻辑驱动器的相关BPB信息
        :param drive_name: 逻辑驱动器盘符
        :return: 逻辑驱动器的相关BPB信息
        """
        # 打开磁盘
        with open(r'\\.\\' + drive_name + ':', 'rb') as disk:
            disk.read(1)
            disk.seek(0xB)  # 移动到存储每个扇区字节总数的位置
            bytes_num_per_sector = int.from_bytes(disk.read(2), 'little')  # 读取每个扇区的字节总数
            sectors_num_per_cluster = int.from_bytes(disk.read(1), 'little')  # 读取每一簇的扇区数
            disk.seek(0x28)  # 移动到存储扇区总数的位置
            sectors_num = int.from_bytes(disk.read(8), 'little')  # 读取扇区总数
            mft_start_position_in_bytes = int.from_bytes(disk.read(8),
                                                         'little') * sectors_num_per_cluster * bytes_num_per_sector  # 读取并计算以字节为单位的$MFT起始位置
        return bytes_num_per_sector, sectors_num_per_cluster, mft_start_position_in_bytes, sectors_num

    @staticmethod
    def menu():
        """
        交互菜单
        :return: 选中的选项
        """
        print('1.按文件名恢复文件')
        print('2.结束程序')
        choice = input('请输入你的选择：')
        return choice

    def recover_base_on_filename(self, mfts, recovery_device):
        """
        根据文件名恢复文件
        :param mfts: 所有实例化的mft对象列表
        :param recovery_device: 实例化的恢复文件对象
        :return: None
        """
        eligible_files = []  # 初始化符合条件的文件列表
        recovered_file_name = input('输入要恢复的文件的文件名，有后缀的文件不要加后缀：')
        # 遍历每一个磁盘的mft
        for index, mft in enumerate(mfts):
            # 遍历每一个被删除的文件
            for deleted_file in mft.deleted_file_list:
                # 若名字相同则加入符合条件的文件列表
                if self.is_file_name_same(recovered_file_name=recovered_file_name, deleted_file_name=deleted_file[2]):
                    eligible_files.append((mft.drive_name, deleted_file[0], deleted_file[1], deleted_file[2], index))
        if len(eligible_files) == 0:
            print('没有找到你要恢复的文件！\n')
            return
        while True:
            print("\n\n下面是所有符合条件的文件：")
            # 展示所有符合条件的文件
            for index, file in enumerate(eligible_files):
                print(str(index + 1) + '. 文件名：' + file[3] + '  所处磁盘：' + file[0] + '盘  所处MFT数据流段号：',
                      end='')
                print(str(file[1]) + '  位于该段的文件序列号：' + str(file[2]))
            choice = input('\n输入你要恢复的文件的序号：')
            try:
                choice = int(choice) - 1
            except ValueError:
                print('输入有误，请重新输入！\n')
                continue
            if choice < 0 or choice >= len(eligible_files):
                print('输入超出范围，请重新输入！\n')
            else:
                break
        recovered_file_name = input('请输入恢复后的文件名称，有后缀的需要输入后缀：')  # 从键盘录入恢复后的文件名
        # 打开磁盘
        with open(r'\\.\\' + eligible_files[choice][0] + ':', 'rb') as disk:
            file = eligible_files[choice]
            # 获取文件属性的起始地址以及相关BPB基本信息
            file_offset_address = mfts[file[4]].mft_data_stream_list[file[1]][0] + file[2] * mfts[
                file[4]].bytes_num_per_sector * 2
            sectors_num_per_cluster = mfts[file[4]].sectors_num_per_cluster
            bytes_num_per_sector = mfts[file[4]].bytes_num_per_sector
            recovery_device.recover_file(disk=disk, file_offset_address=file_offset_address,
                                         file_recovered_name=recovered_file_name,
                                         sectors_num_per_cluster=sectors_num_per_cluster,
                                         bytes_num_per_sector=bytes_num_per_sector)  # 恢复文件

    @staticmethod
    def is_file_name_same(recovered_file_name, deleted_file_name):
        """
        判断两个文件名是否相同
        :param recovered_file_name: 要恢复的文件的文件名，不带后缀
        :param deleted_file_name: 删除文件列表中的文件名，可能带后缀
        :return: 是或否
        """
        # 不对后缀进行比较，需要剔除文件后缀名
        if deleted_file_name.split('.')[:-1]:
            return '.'.join(deleted_file_name.split('.')[:-1]) == recovered_file_name
        else:
            return recovered_file_name == deleted_file_name

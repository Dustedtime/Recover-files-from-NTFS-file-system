from functions import Function
from mft import MFT
from recovery import Recovery


def main():
    function = Function()  # 实例化函数方法类
    recovery_device = Recovery()
    mfts = []  # 初始化存储每一个逻辑驱动器mft对象的列表
    drives_name = function.get_drives_name()  # 获取系统中所有逻辑驱动器的盘符
    # 遍历每一个逻辑驱动器
    for drive_name in drives_name:
        bytes_num_per_sector, sectors_num_per_cluster, mft_start_position_in_bytes, sectors_num = function.get_basic_info_of_mft(
            drive_name=drive_name)  # 获取该盘基本BPB信息
        mfts.append(MFT(drive_name=drive_name, bytes_num_per_sector=bytes_num_per_sector,
                        sectors_num_per_cluster=sectors_num_per_cluster,
                        start_position_in_bytes=mft_start_position_in_bytes, sectors_num=sectors_num))  # 实例化mft对象并加入列表
        mfts[-1].find_mft_data_stream()  # 初始化所有MFT数据流列表
        mfts[-1].find_deleted_file()  # 初始化所有被删除文件记录列表
    # 进入主循环
    while True:
        try:
            choice = int(function.menu())
            if choice == 1:
                function.recover_base_on_filename(mfts=mfts, recovery_device=recovery_device)
            elif choice == 2:
                break
            else:
                print('无效输入！')
        except ValueError:
            print('无效输入！')


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
Created on 2017/9/18
@author: MG
"""
import click
import easytrader
from termcolor import cprint
import os
from datetime import datetime, time
import logging
import pandas as pd

logger = logging.getLogger()


def load_stock_order():
    """加载csv文件，导入并备份为 [.yyyy-mm-dd HH_MM_SS.bak 结尾的文件"""
    base_dir = './auto_order_dir'
    file_name_list = os.listdir(base_dir)
    if file_name_list is None:
        logger.info('No file')

    data_df = None
    for file_name in file_name_list:
        file_base_name, file_extension = os.path.splitext(file_name)
        if file_extension != '.csv':
            continue
        file_path = os.path.join(base_dir, file_name)
        data_df_tmp = pd.read_csv(file_path, index_col=0, header=None, skipinitialspace=True)
        if data_df is None:
            data_df = data_df_tmp
        else:
            data_df = data_df.append(data_df_tmp)

        backup_file_name = file_base_name + datetime.now().strftime('%Y-%m-%d %H_%M_%S') + file_extension + '.bak'
        os.rename(file_path, os.path.join(base_dir, backup_file_name))
    if data_df is not None:
        data_df.rename(columns={k1: k2 for k1, k2 in
                                zip(data_df.columns, ['final_position', 'ref_price', 'wap_mode'])}, inplace=True)
    return data_df


# @click.command()
# @click.option('--use', help='指定券商 [ht, yjb, yh, gzzq]')
# @click.option('--prepare', type=click.Path(exists=True), help='指定登录账户文件路径')
# @click.option('--debug', default=False, help='是否输出 easytrader 的 debug 日志')
def main(config_path, use, debug=False):
    if config_path is not None and use in ['ht', 'yjb', 'yh', 'gf', 'xq', 'gzzq']:
        user = easytrader.use(use, debug)
        user.prepare(config_path)
    else:
        raise ValueError("prepare=%s, use=%s" % (config_path, use))

    # 根据输入命令执行，相应指令
    print_red = lambda x: cprint(x, 'red')
    print_green = lambda x: cprint(x, 'green')
    print("*"*10, '欢迎使用广发证券版 easytrader 控制台 version:0.1', '*'*10)
    stock_target_df = None
    while True:
        print('输入 0：退出')
        print('输入 1：导入股票列表')
        print('输入 2：查询目标股票列表')
        print('输入 3：查询当前持仓')
        print('输入 4：查询合并后交易列表')
        print('输入 5：执行算法交易')
        command_num = int(input("输入："))
        try:
            if command_num == 0:
                print_green('退出')
                break
            elif command_num == 1:
                print_green('导入列表')
                stock_target_df = load_stock_order()
                print(stock_target_df)
            elif command_num == 2:
                print_green('查询目标股票列表')
                # position_df = user.position
                print(stock_target_df)
            elif command_num == 3:
                print_green('查询当前持仓')
                position_df = user.position
                print(position_df)
            elif command_num == 4:
                print_green('查询合并后交易列表')
                stock_bs_df = user.reform_order(stock_target_df)
                print(stock_bs_df)
            elif command_num == 5:
                # 设置执行参数
                # 为了让 datetime_start 等于实际开始执行时的“当前时间”，因此，直到开始执行才设置 datetime_start = datetime.now()
                datetime_start_str = input("起始执行时间(HH:MM:SS)(默认为当前时间)：")
                datetime_start = None if datetime_start_str == "" else datetime.strptime(
                    datetime.now().strftime('%Y-%m-%d ') + datetime_start_str, '%Y-%m-%d %H:%M:%S')

                timedelta_tot_str = input("执行持续时长(秒)(默认120)：")
                timedelta_tot = 120 if timedelta_tot_str == "" else int(timedelta_tot_str)

                interval_str = input("执行间隔时长(秒)(默认10)：")
                interval = 10 if interval_str == "" else int(interval_str)

                is_ok = False
                for _ in range(3):
                    ok_str = input("确认开始执行(y/n)(默认y)：")
                    ok_str = 'y' if ok_str == "" else ok_str
                    if ok_str == 'y' or ok_str == 'Y':
                        is_ok = True
                        break
                    elif ok_str == 'n' or ok_str == 'N':
                        is_ok = False
                        break
                    else:
                        pass
                if is_ok:
                    datetime_start = datetime.now() if datetime_start is None else datetime_start
                    print_green('执行算法交易 开始')
                    config = {'timedelta_tot': timedelta_tot, 'datetime_start': datetime_start, 'interval': 10}
                    print_green('算法交易将于 %s 开始执行' % datetime_start.strftime('%Y-%m-%d %H:%M:%S'))
                    while datetime_start > datetime.now():
                        time.sleep(1)
                    user.auto_order(stock_target_df, config)
                    print_green('执行算法交易 结束')
                else:
                    print_green('取消算法交易')
            else:
                print_red('未知命令')
        except:
            logger.exception('table')

if __name__ == "__main__":
    main(config_path="gzzq.json", use="gzzq")
    # 测试文件导入
    # data_df = load_stock_order()
    # print(data_df)

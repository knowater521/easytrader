# -*- coding: utf-8 -*-
"""
Created on 2017/9/18
@author: MG
"""
import click
import easytrader
from termcolor import cprint
import os
from datetime import datetime
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
def main(prepare, use, debug=False):
    if prepare is not None and use in ['ht', 'yjb', 'yh', 'gf', 'xq', 'gzzq']:
        user = easytrader.use(use, debug)
        user.prepare(prepare)
    else:
        raise ValueError("prepare=%s, use=%s" % (prepare, use))

    # 根据输入命令执行，相应指令
    print_red = lambda x: cprint(x, 'red')
    print_green = lambda x: cprint(x, 'green')
    print("")
    print_red('输入 1：导入股票列表')
    print_red('输入 2：查询目标股票列表')
    print_red('输入 3：查询当前持仓')
    print_red('输入 4：查询合并后交易列表')
    print_red('输入 5：执行算法交易')
    stock_target_df = None
    while True:
        command_num = int(input("输入："))
        try:
            if command_num == 1:
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
                print_green('执行算法交易 开始')
                config = {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
                user.auto_order(stock_target_df, config)
                print_green('执行算法交易 结束')
            else:
                print_red('未知命令')
        except:
            logger.exception('table')

if __name__ == "__main__":
    main(prepare="gzzq.json", use="gzzq")
    # 测试文件导入
    # data_df = load_stock_order()
    # print(data_df)

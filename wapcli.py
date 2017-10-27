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
import time
import logging
import pandas as pd
from collections import OrderedDict
from easytrader.log import log


def load_stock_order():
    """加载csv文件，导入并备份为 [.yyyy-mm-dd HH_MM_SS.bak 结尾的文件"""
    base_dir = './auto_order_dir'
    file_name_list = os.listdir(base_dir)
    if file_name_list is None:
        log.info('No file')

    data_df = None
    for file_name in file_name_list:
        file_base_name, file_extension = os.path.splitext(file_name)
        if file_extension != '.csv':
            continue
        file_path = os.path.join(base_dir, file_name)
        data_df_tmp = pd.read_csv(file_path, index_col=0, header=None, skipinitialspace=True)
        if data_df is None:
            data_df_tmp.index = ['%06d' % stock_code for stock_code in data_df_tmp.index]
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
    print("*" * 10, '欢迎使用广发证券版 easytrader 控制台 version:0.1', '*' * 10)
    stock_target_df = None
    command_num_desc_dic = OrderedDict([
        (0, '退出'),
        (1, '导入股票列表'),
        (2, '查询目标股票列表'),
        (3, '查询当前持仓'),
        (4, '查询合并后交易列表'),
        (5, '执行算法交易'),
        (6, '对比执行结果'),
        (7, '全部撤单'),
        (8, '全部买/卖1档±0.01下单'),
        (9, '全部对手价下单'),
    ])
    while True:
        for command_num_desc in command_num_desc_dic.items():
            print('输入 %d：%s' % command_num_desc)

        try:
            command_num = int(input("输入："))
            if command_num == 0:
                log.info('退出')
                break
            elif command_num == 1:
                log.info('导入列表')
                stock_target_df = load_stock_order()
                print(stock_target_df)
            elif command_num == 2:
                log.info('查询目标股票列表')
                # position_df = user.position
                print(stock_target_df)
            elif command_num == 3:
                log.info('查询当前持仓')
                position_df = user.position
                print(position_df)
            elif command_num == 4:
                log.info('查询合并后交易列表')
                stock_bs_df = user.reform_order(stock_target_df)
                log.info('\n%s', stock_bs_df)
            elif command_num == 5:
                log.info(command_num_desc_dic[command_num])
                # 设置执行参数
                # 为了让 datetime_start 等于实际开始执行时的“当前时间”，因此，直到开始执行才设置 datetime_start = datetime.now()
                for _ in range(3):
                    try:
                        datetime_start_str = input("起始执行时间(HH:MM:SS)(默认为当前时间)：")
                        datetime_start = None if datetime_start_str == "" else datetime.strptime(
                            datetime.now().strftime('%Y-%m-%d ') + datetime_start_str, '%Y-%m-%d %H:%M:%S')
                        break
                    except:
                        print_red("%s 格式不对" % datetime_start_str)
                else:
                    continue

                for _ in range(3):
                    try:
                        datetime_end_str = input("结束执行时间(HH:MM:SS)(默认为9:35)：")
                        datetime_end_str = "9:35:00" if datetime_end_str is "" else datetime_end_str
                        datetime_end = datetime.strptime(
                            datetime.now().strftime('%Y-%m-%d ') + datetime_end_str, '%Y-%m-%d %H:%M:%S')
                        break
                    except:
                        print_red("%s 格式不对" % datetime_end_str)
                else:
                    continue

                # timedelta_tot_str = input("执行持续时长(秒)(默认120)：")
                # timedelta_tot = 120 if timedelta_tot_str == "" else int(timedelta_tot_str)

                for _ in range(3):
                    try:
                        interval_str = input("执行间隔时长(秒)(默认10)：")
                        interval = 10 if interval_str == "" else int(interval_str)
                        break
                    except:
                        print_red("%s 格式不对" % interval_str)
                else:
                    continue

                is_ok = inputYN()
                if is_ok:
                    datetime_start = datetime.now() if datetime_start is None else datetime_start
                    log.info('执行算法交易 开始')
                    config = {'datetime_end': datetime_end, 'datetime_start': datetime_start, 'interval': 10}
                    log.info('算法交易将于 %s 开始执行' % datetime_start.strftime('%Y-%m-%d %H:%M:%S'))
                    while datetime_start > datetime.now():
                        time.sleep(1)
                    user.auto_order(stock_target_df, config)
                    log.info('执行算法交易 结束')
                else:
                    log.info('取消算法交易')
            elif command_num == 6:
                log.info(command_num_desc_dic[command_num])
                stock_bs_df = user.reform_order(stock_target_df)
                res_df = stock_bs_df[['sec_name', 'final_position', 'init_position', 'ref_price', 'cost_price']]
                res_df['gap_position'] = (res_df['init_position'] - res_df['final_position']).apply(
                    lambda x: '%d ' % x + ('↑' if x > 0 else '↓' if x < 0 else 'ok'))
                res_df['gap_price'] = (res_df['cost_price'] - res_df['ref_price']).apply(
                    lambda x: '%.3f ' % x + ('↑' if x > 0 else '↓' if x < 0 else ''))
                res_df.rename(columns={'final_position': '目标仓位',
                                       'init_position': '当前仓位',
                                       'ref_price': '目标价格',
                                       'cost_price': '持仓成本',
                                       'gap_position': '目标持仓差',
                                       'gap_price': '目标成本差',
                                       }, inplace=True)
                log.info('\n%s',res_df)
                res_df.to_csv('对比执行结果.csv')
            elif command_num == 7:
                log.info(command_num_desc_dic[command_num])
                is_ok = inputYN()
                if is_ok:
                    user.cancel_all_apply()
            elif command_num == 8:
                log.info(command_num_desc_dic[command_num])
                is_ok = inputYN()
                if is_ok:
                    datetime_start = datetime.now()
                    datetime_end = datetime.now()
                    config = {'datetime_end': datetime_end, 'datetime_start': datetime_start,
                              'aggregate_auction': False, 'once': True, 'final_deal': False,
                              'wap_mode': 'twap_half_initiative'}
                    user.auto_order(stock_target_df, config)
            elif command_num == 9:
                log.info(command_num_desc_dic[command_num])
                is_ok = inputYN()
                if is_ok:
                    datetime_start = datetime.now()
                    datetime_end = datetime.now()
                    config = {'datetime_end': datetime_end, 'datetime_start': datetime_start,
                              'aggregate_auction': False, 'once': True, 'final_deal': False,
                              'wap_mode': 'twap_initiative'}
                    user.auto_order(stock_target_df, config)
            else:
                log.warning('未知命令')
        except:
            log.exception('')


def inputYN():
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
            print("%s 格式不对" % ok_str)
    return is_ok


if __name__ == "__main__":
    main(config_path="json/gzzq.json", use="gzzq")
    # 测试文件导入
    # data_df = load_stock_order()
    # print(data_df)

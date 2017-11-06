# -*- coding: utf-8 -*-
"""
Created on 2017/9/18
@author: MG
"""
import click
import easytrader
from termcolor import cprint
import os
from datetime import datetime, timedelta
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
        data_df_tmp = pd.read_csv(file_path, index_col=0, header=0, skipinitialspace=True)
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


def validate_time(ctx, param, value: str):
    try:
        time_obj = None if value.strip() == "" else datetime.strptime(
        datetime.now().strftime('%Y-%m-%d ') + value, '%Y-%m-%d %H:%M:%S')
        return time_obj
    except:
        raise click.BadParameter('时间格式：HH:MM:SS')


def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


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
        (8, '执行一次买/卖操作'),
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
                @click.command()
                @click.option('--datetime_start', callback=validate_time, prompt="起始执行时间(HH:MM:SS)(空格为当前时刻)")
                @click.option('--datetime_end', callback=validate_time, prompt="结束执行时间(HH:MM:SS)",
                              default='9:35:00')
                @click.option('--interval', type=click.INT, prompt="执行间隔时长(秒)", default=10)
                @click.option('--side', type=click.IntRange(0,2), prompt="执行买卖方向 0 买卖 / 1 只买 / 2 只卖", default=0)
                @click.option('--yes', is_flag=True, callback=abort_if_false, expose_value=True, default=True,
                              prompt='确认开始执行')
                def run_auto_order(**kwargs):
                    config = kwargs.copy()
                    if 'datetime_start' not in config or config['datetime_start'] is None:
                        config['datetime_start'] = datetime.now()
                    datetime_start = config['datetime_start']
                    if datetime_start > datetime.now():
                        log.info('算法交易将于 %s 开始执行' % datetime_start.strftime('%Y-%m-%d %H:%M:%S'))
                        while datetime_start > datetime.now():
                            time.sleep(1)
                    log.info("执行算法交易 开始")
                    user.auto_order(stock_target_df, config)
                    log.info("执行算法交易 结束")
                    log.info("对比执行结果")
                    user.compare_result(stock_target_df)
                run_auto_order(standalone_mode=False)
            elif command_num == 6:
                log.info(command_num_desc_dic[command_num])

                user.compare_result(stock_target_df)
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
                              'side': 0}
                    user.auto_order(stock_target_df, config)
            elif command_num == 9:
                log.info(command_num_desc_dic[command_num])
                is_ok = inputYN()
                if is_ok:
                    datetime_start = datetime.now()
                    datetime_end = datetime.now()
                    config = {'datetime_end': datetime_end, 'datetime_start': datetime_start,
                              'aggregate_auction': False, 'once': True, 'final_deal': False,
                              'side': 0, 'keep_wap_mode': 'twap_initiative'}
                    user.auto_order(stock_target_df, config)
            else:
                log.warning('未知命令')
        except click.exceptions.Abort:
            pass
        except:
            log.exception('command run exception')


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

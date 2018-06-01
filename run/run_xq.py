#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/1 11:09
@File    : run_xq.py
@contact : mmmaaaggg@163.com
@desc    : 
"""
import pandas as pd
import os
import easytrader


def login_xq(**kwargs):
    """
    输入 user, password 或者输入 config_file 配置路径
    否则默认读取 account.json 文件
    :param kwargs:
    :return:
    """
    user = easytrader.use('xq')
    # user.prepare(config_file='../json/xq.json')
    if ('user' in kwargs and 'password' in kwargs and 'cookies' in kwargs) or 'config_file' in kwargs:
        user.prepare(**kwargs)
    else:
        user.prepare(os.path.dirname(__file__) + r"\account.json")
    return user


def trade_xq_weighted(position_new_df, **kwargs):
    """
    第一列，股票代码，第二列，对应股票权重
    :param position_new_df:
    :return:
    """
    user = login_xq(**kwargs)
    user.adjust_weights(position_new_df)

    # stock_buy_list = list(position_new_df.ix[:, 0])
    # # stock_codes = [s for s in stock_list_buy]
    # xq_code_set = set([transfer_xq_code(s) for s in stock_buy_list])
    # # 将全部非持仓股票仓位清理
    # holding_pos = user.position
    # for pos in holding_pos:
    #     xq_code = pos['stock_code']
    #     # stock_code = transfor_stockcode(xqcode)
    #     if xq_code not in xq_code_set:
    #         # close = dfCloses[stock_code][-1]
    #         # print '雪球组合 卖出 %s %d手 价格：%f ' % (stock_code, pos['enable_amount'], close)
    #         try:
    #             user.adjust_weight(xq_code[2:], 0)
    #         except:
    #             pass
    #
    # totcount = len(stock_buy_list)
    # totpos = 0
    # for n in range(totcount):
    #     s = stock_buy_list[n]
    #     if n < totcount - 1:
    #         pos = 100 / totcount
    #         totpos += pos
    #         user.adjust_weight(s, pos)
    #     else:
    #         user.adjust_weight(s, 100 - totpos)
    #         # user.buy(g.security[1][:6], price=10000, amount=1) #买入1%
    #         # user.sell(g.security[0][:6], price=10000, amount=1) #卖出1%


def trade_xq(stock_buy_list):

    stock_list_count = len(stock_buy_list)
    stock_buy_df = pd.DataFrame([[s, round(1.0/stock_list_count, 2)] for s in stock_buy_list])
    trade_xq_weighted(stock_buy_df)


def transfer_xq_code(stock_code):
    if stock_code[0] == '6':
        return 'SH' + stock_code[:6]
    else:
        return 'SZ' + stock_code[:6]


def check_account_info():
    ''' 获取信息并输出 '''
    user = login_xq()
    # loger.info('获取今日委托单:')
    # loger.info('今日委托单:', json.dumps(user.entrust, ensure_ascii=False))
    # loger.info('-' * 30)
    # loger.info('获取资金状况:')
    # loger.info('资金状况:', json.dumps(user.balance, ensure_ascii=False))
    # loger.info('enable_balance(可用金额):', json.dumps(user.balance[0]['enable_balance'], ensure_ascii=False))
    # loger.info('-' * 30)
    # loger.info('持仓:')
    # loger.info('获取持仓:', json.dumps(user.position, ensure_ascii=False))
    # loger.info('enable_amount(可卖数量):', json.dumps(user.position[0]['enable_amount'], ensure_ascii=False))
    ret_info = {
        'entrust': user.entrust,
        'balance': user.balance,
        'enable_balance': user.balance[0]['enable_balance'],
        'position': user.position,
        'enable_amount': user.position[0]['enable_amount'],
    }
    return ret_info


if __name__ == "__main__":
    # 支持两种方式调用

    # 1）输入股票列表，默认等权重买入
    # trade_xq(['600123', '300123', '002778'])

    # 2）输入股票列表及对应权重 DataFrame
    stock_buy_df = pd.DataFrame([['600123', 20],
                                 ['600978', 30],
                                 ['300254', 40]])
    trade_xq_weighted(stock_buy_df, config_file='../json/xq.json')

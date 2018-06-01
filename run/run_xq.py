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


if __name__ == "__main__":
    # 支持两种方式调用

    # 1）输入股票列表，默认等权重买入
    # trade_xq(['600123', '300123', '002778'])

    # 2）输入股票列表及对应权重 DataFrame
    stock_buy_df = pd.DataFrame([['600123', 20],
                                 ['600978', 30],
                                 ['300254', 40]])
    trade_xq_weighted(stock_buy_df, config_file='../json/xq.json')

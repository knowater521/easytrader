# -*- coding: utf-8 -*-
"""
Created on 2017/10/3
@author: MG
"""


def get_min_move_unit(stock_code):
    """获取股票最小移动单位 股票为0.01，ETF及分基金等0.001"""
    if stock_code < 100000:
        return 0.01
    elif 600000 <= stock_code <= 699999:
        return 0.01
    elif 300000 <= stock_code <= 399999:
        return 0.01
    else:
        return 0.001

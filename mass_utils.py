# -*- coding: utf-8 -*-
"""
Created on 2017/10/3
@author: MG
"""


def get_min_move_unit(stock_code):
    """获取股票最小移动单位 股票为0.01，ETF及分基金等0.001"""
    stock_code_int = int(stock_code)
    if stock_code_int < 100000:
        return 0.01
    elif 600000 <= stock_code_int <= 699999:
        return 0.01
    elif 300000 <= stock_code_int <= 399999:
        return 0.01
    else:
        return 0.001

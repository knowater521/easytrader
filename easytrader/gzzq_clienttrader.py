# coding:utf8
from __future__ import division

import os
import subprocess
from datetime import datetime, timedelta
import tempfile
import time
import traceback
import win32api
import win32gui
from io import StringIO
import re
import winsound
import math
import pandas as pd
import pyperclip
import win32com.client
import win32con
from PIL import ImageGrab
import pythoncom
from . import helpers
from .log import log
from win32_utils import find_window_whnd, filter_hwnd_func
from mass_utils import get_min_move_unit
from termcolor import cprint
import tushare as ts

# 仅用于调试阶段，防止价格成交，进行买卖价格偏移使用
SHIFT_PRICE = 0.0


class GZZQClientTrader():
    def __init__(self):
        self.Title = ' - 广州总部电信交易1'
        self.re_lpClassName = r'Afx:400000:0:0:.+:0'
        self.lpClassName = None
        # self.base_dir 仅用于在导出持仓信息文件时默认的保存目录
        self.base_dir = r'd:\Downloads'
        # 最小阈值金额，小于改金额的订单将被一次性下单
        self.min_threshold_amount = 50000
        # 最小忽略金额，小于该金额的订单将被忽略
        self.ignore_mini_order = 10000
        self._csv_data_dic = {}
        # 统计twap期间的交易情况
        self._stock_deal_datetime_dic = {}
        # 为了防止频繁获取 csv文件耽误时间，做了一个小的缓存机制，超时时间设置
        self.csv_expire_timedelta = timedelta(seconds=15)
        # 涨跌停价格字典
        self._stock_limit_price_dic = {}
        # 控制监控器终止执行
        self.monitor_running = True

    def prepare(self, config_path=None, user=None, password=None, exe_path='D:\TradeTools\广州证券网上交易\hexin.exe'):
        """
        登陆银河客户端
        :param config_path: 银河登陆配置文件，跟参数登陆方式二选一
        :param user: 银河账号
        :param password: 银河明文密码
        :param exe_path: 银河客户端路径
        :return:
        """
        if config_path is not None:
            account = helpers.file2dict(config_path)
            user = account['user']
            password = account['password']
            exe_path = account['exe_path'] if 'exe_path' in account else exe_path
            self.base_dir = account['base_dir'] if 'base_dir' in account else self.base_dir
        self.login(user, password, exe_path)

    def login(self, user, password, exe_path):
        if self._has_main_window():
            self._get_handles()
            log.info('检测到交易客户端已启动，连接完毕')
            return
        if not self._has_login_window():
            if not os.path.exists(exe_path):
                raise FileNotFoundError('在　{} 未找到应用程序，请用 exe_path 指定应用程序目录'.format(exe_path))
            subprocess.Popen(exe_path)
        # 检测登陆窗口
        for _ in range(30):
            if self._has_login_window():
                break
            time.sleep(1)
        else:
            raise Exception('启动客户端失败，无法检测到登陆窗口')
        log.info('成功检测到客户端登陆窗口')

        # 登陆
        self._set_trade_mode()
        self._set_login_name(user)
        self._set_login_password(password)
        for _ in range(10):
            self._set_login_verify_code()
            self._click_login_button()
            time.sleep(3)
            if not self._has_login_window():
                break
            self._click_login_verify_code()

        for _ in range(60):
            if self._has_main_window():
                self._get_handles()
                break
            time.sleep(1)
        else:
            raise Exception('启动交易客户端失败')
        log.info('客户端登陆成功')

    def _set_login_verify_code(self):
        verify_code_image = self._grab_verify_code()
        image_path = tempfile.mktemp() + '.jpg'
        verify_code_image.save(image_path)
        result = helpers.recognize_verify_code(image_path, 'yh_client')
        time.sleep(0.2)
        self._input_login_verify_code(result)
        time.sleep(0.4)

    def _set_trade_mode(self):
        input_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x4f4d)
        win32gui.SendMessage(input_hwnd, win32con.BM_CLICK, None, None)

    def _set_login_name(self, user):
        time.sleep(0.5)
        input_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x5523)
        win32gui.SendMessage(input_hwnd, win32con.WM_SETTEXT, None, user)

    def _set_login_password(self, password):
        time.sleep(0.5)
        input_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x5534)
        win32gui.SendMessage(input_hwnd, win32con.WM_SETTEXT, None, password)

    def _has_login_window(self):
        self.login_hwnd = win32gui.FindWindow(None, self.Title)
        if self.login_hwnd != 0:
            return True
        return False

    def _input_login_verify_code(self, code):
        input_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x56b9)
        win32gui.SendMessage(input_hwnd, win32con.WM_SETTEXT, None, code)

    def _click_login_verify_code(self):
        input_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x56ba)
        rect = win32gui.GetWindowRect(input_hwnd)
        self._mouse_click(rect[0] + 5, rect[1] + 5)

    @staticmethod
    def _mouse_click(x, y):
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def _click_login_button(self):
        time.sleep(1)
        input_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x1)
        win32gui.SendMessage(input_hwnd, win32con.BM_CLICK, None, None)

    def _has_main_window(self):
        try:
            self._get_handles()
        except:
            return False
        return True

    def _grab_verify_code(self):
        verify_code_hwnd = win32gui.GetDlgItem(self.login_hwnd, 0x56ba)
        self._set_foreground_window(self.login_hwnd)
        time.sleep(1)
        rect = win32gui.GetWindowRect(verify_code_hwnd)
        return ImageGrab.grab(rect)

    @staticmethod
    def _filter_trade_client(pattern, hWnd, hWndList):
        clsname = win32gui.GetClassName(hWnd)
        if re.match(pattern, clsname) is not None:
            hWndList.append((hWnd, clsname))

    def _find_trade_client_hwnd(self):
        trade_client_hWnd = None
        if self.lpClassName is None:
            hwnd_list = []
            win32gui.EnumWindows(lambda hWnd, param:
                                 GZZQClientTrader._filter_trade_client(self.re_lpClassName, hWnd, param),
                                 hwnd_list)
            if len(hwnd_list) > 0:
                trade_client_hWnd, self.lpClassName = hwnd_list[0]
                # self.lpClassName = win32gui.GetClassName(trade_client_hWnd)
        else:
            trade_client_hWnd = win32gui.FindWindow(self.lpClassName, None)  # 交易窗口
        return trade_client_hWnd

    @staticmethod
    def _filter_offer_frame_hwnd(hwnd, hwnd_list):
        x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
        if x2 - x1 == 216 and y2 - y1 == 218:
            hwnd_list.append(hwnd)

    def _find_offer_frame_hwnd(self, entrust_window_hwnd):
        """查找买入、卖出界面五档行情的外层框架hwnd"""
        hWndChildList = []
        win32gui.EnumChildWindows(entrust_window_hwnd, GZZQClientTrader._filter_offer_frame_hwnd, hWndChildList)
        if len(hWndChildList) > 0:
            offer_frame_hwnd = hWndChildList[0]
        else:
            offer_frame_hwnd = None
        return offer_frame_hwnd

    @staticmethod
    def _find_capital_frame_hwnd(capital_window_hwnd):
        """根据 capital_window_hwnd 查找可用资金、冻结资金、股票市值、总资产相关控件的母控件"""
        hWndChildList = []
        win32gui.EnumChildWindows(capital_window_hwnd, lambda hwnd, hwnd_list: hwnd_list.append(hwnd), hWndChildList)
        for hwnd in hWndChildList:
            if filter_hwnd_func(hwnd, '可用金额'):
                ret_hwnd = hwnd
                break
        else:
            ret_hwnd = None
        return ret_hwnd

    def close_confirm_win_if_exist(self):
        """ 查找 标题为“提示”的确认框"""
        # hwnd = win32_utils.find_window_whnd(GZZQClientTrader._filter_confirm_win_func, ret_first=True)
        hwnd = find_window_whnd(lambda x: filter_hwnd_func(x, '提示'), ret_first=True)
        if hwnd is not None:
            shell = GZZQClientTrader._set_foreground_window(hwnd)
            # Enter 热键 切断
            shell.SendKeys('~')
            return True
        return False

    def goto_buy_win(self, sub_win=None):
        # 获取委托窗口所有控件句柄
        win32api.PostMessage(self.tree_view_hwnd, win32con.WM_KEYDOWN, win32con.VK_F1, 0)
        time.sleep(0.5)
        if sub_win is None:
            pass
        elif sub_win == 'holding':
            win32api.PostMessage(self.position_list_hwnd, win32con.WM_KEYDOWN, 87, 0)  # 热键 w
        elif sub_win == 'deal':
            win32api.PostMessage(self.position_list_hwnd, win32con.WM_KEYDOWN, 69, 0)  # 热键 e
        elif sub_win == 'apply':
            win32api.PostMessage(self.position_list_hwnd, win32con.WM_KEYDOWN, 82, 0)  # 热键 r
        else:
            log.error('sub_win:%s 无效', sub_win)

    def _get_handles(self):
        # 同花顺有改版，无法依靠窗体名称捕获句柄
        # trade_main_hwnd = win32gui.FindWindow(0, self.Title)  # 交易窗口
        trade_main_hwnd = self._find_trade_client_hwnd()  # 交易窗口
        if trade_main_hwnd is None:
            raise Exception()
        trade_frame_hwnd = win32gui.GetDlgItem(trade_main_hwnd, 0)  # 交易窗口
        operate_frame_hwnd = win32gui.GetDlgItem(trade_frame_hwnd, 59648)  # 操作窗口框架
        operate_frame_afx_hwnd = win32gui.GetDlgItem(operate_frame_hwnd, 59648)  # 操作窗口框架
        hexin_hwnd = win32gui.GetDlgItem(operate_frame_afx_hwnd, 129)
        scroll_hwnd = win32gui.GetDlgItem(hexin_hwnd, 200)  # 左部折叠菜单控件
        self.tree_view_hwnd = win32gui.GetDlgItem(scroll_hwnd, 129)  # 左部折叠菜单控件

        # 获取委托窗口所有控件句柄
        # win32api.PostMessage(self.tree_view_hwnd, win32con.WM_KEYDOWN, win32con.VK_F1, 0)
        # time.sleep(0.5)
        self.goto_buy_win()

        # 买入相关
        entrust_window_hwnd = win32gui.GetDlgItem(operate_frame_hwnd, 59649)  # 委托窗口框架
        self.buy_stock_code_hwnd = win32gui.GetDlgItem(entrust_window_hwnd, 1032)  # 买入代码输入框
        self.buy_price_hwnd = win32gui.GetDlgItem(entrust_window_hwnd, 1033)  # 买入价格输入框
        self.buy_amount_hwnd = win32gui.GetDlgItem(entrust_window_hwnd, 1034)  # 买入数量输入框
        self.buy_btn_hwnd = win32gui.GetDlgItem(entrust_window_hwnd, 1006)  # 买入确认按钮
        self.refresh_entrust_hwnd = win32gui.GetDlgItem(entrust_window_hwnd, 32790)  # 刷新持仓按钮
        entrust_frame_hwnd = win32gui.GetDlgItem(entrust_window_hwnd, 1047)  # 持仓显示框架
        entrust_sub_frame_hwnd = win32gui.GetDlgItem(entrust_frame_hwnd, 200)  # 持仓显示框架
        self.position_list_hwnd = win32gui.GetDlgItem(entrust_sub_frame_hwnd, 1047)  # 持仓列表

        # position_df = self.get_position()
        # log.info(position_df)

        # 获取盘口5档买卖price，盘口买卖vol
        offer_price_frame_hwnd = self._find_offer_frame_hwnd(entrust_window_hwnd)  # 五档行情的外层框架
        # [买一、买二。。。。[价格、vol]]
        offer_buy_5_item_id_list = [[1018, 1014], [1025, 1013], [1026, 1012], [1035, 1015], [1036, 1037]]
        self.offer_buy_5_hwnd_list = [
            [win32gui.GetDlgItem(offer_price_frame_hwnd, price_id), win32gui.GetDlgItem(offer_price_frame_hwnd, vol_id)]
            for price_id, vol_id in offer_buy_5_item_id_list
        ]
        # [卖一、卖二。。。。[价格、vol]]
        offer_sell_5_item_id_list = [[1021, 1016], [1022, 1017], [1023, 1019], [1033, 1034], [1032, 1020]]
        self.offer_sell_5_hwnd_list = [
            [win32gui.GetDlgItem(offer_price_frame_hwnd, price_id), win32gui.GetDlgItem(offer_price_frame_hwnd, vol_id)]
            for price_id, vol_id in offer_sell_5_item_id_list
        ]
        self.high_limit_price_hwnd = win32gui.GetDlgItem(offer_price_frame_hwnd, 1028)
        self.low_limit_price_hwnd = win32gui.GetDlgItem(offer_price_frame_hwnd, 1029)
        # 仅用于测试买卖盘口函数是否有效
        # offer_buy_list, offer_sell_list = self.get_bs_offer_data()
        # print("offer_buy_list:\n", offer_buy_list)
        # print("offer_sell_list:\n", offer_sell_list)
        win32api.PostMessage(self.tree_view_hwnd, win32con.WM_KEYDOWN, win32con.VK_F2, 0)
        time.sleep(0.5)

        # 卖出相关
        sell_entrust_frame_hwnd = win32gui.GetDlgItem(operate_frame_hwnd, 59649)  # 委托窗口框架
        self.sell_stock_code_hwnd = win32gui.GetDlgItem(sell_entrust_frame_hwnd, 1032)  # 卖出代码输入框
        self.sell_price_hwnd = win32gui.GetDlgItem(sell_entrust_frame_hwnd, 1033)  # 卖出价格输入框
        self.sell_amount_hwnd = win32gui.GetDlgItem(sell_entrust_frame_hwnd, 1034)  # 卖出数量输入框
        self.sell_btn_hwnd = win32gui.GetDlgItem(sell_entrust_frame_hwnd, 1006)  # 卖出确认按钮

        # 撤单窗口
        win32api.PostMessage(self.tree_view_hwnd, win32con.WM_KEYDOWN, win32con.VK_F3, 0)
        time.sleep(0.5)
        cancel_entrust_window_hwnd = win32gui.GetDlgItem(operate_frame_hwnd, 59649)  # 撤单窗口框架
        self.cancel_stock_code_hwnd = win32gui.GetDlgItem(cancel_entrust_window_hwnd, 3348)  # 卖出代码输入框
        self.cancel_query_hwnd = win32gui.GetDlgItem(cancel_entrust_window_hwnd, 3349)  # 查询代码按钮
        self.cancel_all_hwnd = win32gui.GetDlgItem(cancel_entrust_window_hwnd, 30001)  # 撤买
        self.cancel_buy_hwnd = win32gui.GetDlgItem(cancel_entrust_window_hwnd, 30002)  # 撤买
        self.cancel_sell_hwnd = win32gui.GetDlgItem(cancel_entrust_window_hwnd, 30003)  # 撤卖

        chexin_hwnd = win32gui.GetDlgItem(cancel_entrust_window_hwnd, 1047)
        chexin_sub_hwnd = win32gui.GetDlgItem(chexin_hwnd, 200)
        self.entrust_list_hwnd = win32gui.GetDlgItem(chexin_sub_hwnd, 1047)  # 委托列表

        # 资金股票
        win32api.PostMessage(self.tree_view_hwnd, win32con.WM_KEYDOWN, win32con.VK_F4, 0)
        time.sleep(0.5)
        self.capital_window_hwnd = win32gui.GetDlgItem(operate_frame_hwnd, 0xE901)  # 资金股票窗口框架
        capital_frame_hwnd = GZZQClientTrader._find_capital_frame_hwnd(self.capital_window_hwnd)
        self.available_amount_hwnd = win32gui.GetDlgItem(capital_frame_hwnd, 0x3F8)  # 可用金额
        self.freezing_amount_hwnd = win32gui.GetDlgItem(capital_frame_hwnd, 0x3F5)  # 冻结资金
        self.tot_stock_value_hwnd = win32gui.GetDlgItem(capital_frame_hwnd, 0x3F6)  # 股票市值
        self.tot_capital_hwnd = win32gui.GetDlgItem(capital_frame_hwnd, 0x3F7)  # 总资产

        # 关闭提示框
        self.close_confirm_win_if_exist()

    def balance(self):
        return self.get_balance()

    def get_balance(self):
        self._set_foreground_window(self.capital_window_hwnd)
        time.sleep(0.3)
        data = self._read_clipboard()
        return self.project_copy_data(data)[0]

    def get_available_amount(self):
        return helpers.get_text_by_hwnd(self.available_amount_hwnd, cast=float)

    def get_freezing_amount(self):
        return helpers.get_text_by_hwnd(self.freezing_amount_hwnd, cast=float)

    def get_tot_stock_value(self):
        return helpers.get_text_by_hwnd(self.tot_stock_value_hwnd, cast=float)

    def get_tot_capital(self):
        return helpers.get_text_by_hwnd(self.tot_capital_hwnd, cast=float)

    def buy(self, stock_code, price, amount, remark="", **kwargs):
        """
        买入股票
        :param stock_code: 股票代码
        :param price: 买入价格
        :param amount: 买入股数
        :return: bool: 买入信号是否成功发出
        """
        if math.isnan(price):
            log.error("%s 买入价格 is nan, %s", stock_code, remark)
            return
        if math.isnan(amount):
            log.error("%s 买入金额 is nan, %s", stock_code, remark)
            return
        amount_str = str(amount // 100 * 100)
        # price = str(price)
        price_str = '%.3f' % price

        try:
            win32gui.SendMessage(self.buy_stock_code_hwnd, win32con.WM_SETTEXT, None, stock_code)  # 输入买入代码
            time.sleep(0.2)
            win32gui.SendMessage(self.buy_price_hwnd, win32con.WM_SETTEXT, None, price_str)  # 输入买入价格
            win32gui.SendMessage(self.buy_amount_hwnd, win32con.WM_SETTEXT, None, amount_str)  # 输入买入数量
            time.sleep(0.2)
            win32gui.SendMessage(self.buy_btn_hwnd, win32con.BM_CLICK, None, None)  # 买入确定
            log.info("买入： %s 价格：%s 数量：%s 金额：%.3f %s", stock_code, price_str, amount_str, amount * price, remark)
            time.sleep(0.5)
            # 查找是否存在确认框，如果有，将其关闭
            self.close_confirm_win_if_exist()
        except:
            traceback.print_exc()
            return False
        return True

    def sell(self, stock_code, price, amount, remark="", **kwargs):
        """
        卖出股票
        :param stock_code: 股票代码
        :param price: 卖出价格
        :param amount: 卖出股数
        :return: bool 卖出操作是否成功
        """
        if math.isnan(price):
            log.error("%s 卖出价格 nan, %s", stock_code, remark)
            return
        if math.isnan(amount):
            log.error("%s 卖出金额 nan, %s", stock_code, remark)
            return
        amount_str = str(amount)
        # price = str(price)
        price_str = '%.3f' % price

        try:
            win32gui.SendMessage(self.sell_stock_code_hwnd, win32con.WM_SETTEXT, None, stock_code)  # 输入卖出代码
            win32gui.SendMessage(self.sell_price_hwnd, win32con.WM_SETTEXT, None, price_str)  # 输入卖出价格
            win32gui.SendMessage(self.sell_price_hwnd, win32con.BM_CLICK, None, None)  # 输入卖出价格
            time.sleep(0.2)
            win32gui.SendMessage(self.sell_amount_hwnd, win32con.WM_SETTEXT, None, amount_str)  # 输入卖出数量
            time.sleep(0.2)
            win32gui.SendMessage(self.sell_btn_hwnd, win32con.BM_CLICK, None, None)  # 卖出确定
            log.info("卖出： %s 价格：%s 数量：%s 金额：%.3f %s", stock_code, price_str, amount_str, amount * price, remark)
            time.sleep(0.5)
            # 查找是否存在确认框，如果有，将其关闭
            self.close_confirm_win_if_exist()
        except:
            traceback.print_exc()
            return False
        return True

    def cancel_entrust(self, stock_code, direction, check_final_position=None, **kwargs):
        """
        撤单
        如果 委托价格超出5档买卖盘价格则撤销
        如果 持仓 + 未成交委托总量 > 目标持仓（卖出相反）则撤单
        :param stock_code: str 股票代码
        :param direction: str 1 撤买， 0 撤卖，None 全撤
        :param final_position: int 默认None，如果不为空，检查当前持仓+全部申请是否等于final_position，如果为成交金额小于 ignore_mini_order 则放弃撤单
        :return: bool 撤单信号是否发出
        """

        if kwargs.setdefault('only_dealvol_0', False):
            # 仅撤销未成交委托，且未成交委托价格不在1档盘口
            apply_df = self.get_apply(stock_code)
            if apply_df is not None and apply_df.shape[0] > 0:
                apply_vol = apply_df['apply_vol'].sum()
                deal_vol = apply_df['deal_vol'].sum()
                if not (apply_vol > 0 and deal_vol == 0):
                    log.debug('%s 累计申请买入：%d 已成交：%d，无需撤单', stock_code, apply_vol, deal_vol)
                    return

                # 获取盘口价格
                offer_buy_list = kwargs.setdefault('offer_buy_list', None)
                offer_sell_list = kwargs.setdefault('offer_sell_list', None)
                if offer_buy_list is not None and direction == 1:
                    apply_price = apply_df['apply_price'].max()
                    offer_price = offer_buy_list[0][0]
                    if (not math.isnan(offer_price)) and apply_price >= offer_price:
                        log.debug('%s 当前买入委托价格：%.3f 盘口价格：%.3f，无需撤单', stock_code, apply_price, offer_price)
                        return
                if offer_sell_list is not None and direction == 0:
                    apply_price = apply_df['apply_price'].min()
                    offer_price = offer_sell_list[0][0]
                    if (not math.isnan(offer_price)) and apply_price >= offer_price:
                        log.debug('%s 当前买入委托价格：%.3f 盘口价格：%.3f，无需撤单', stock_code, apply_price, offer_price)
                        return

        elif check_final_position is not None:
            # 检查委托执行情况与目标仓位之间差距，决定是否取消 撤销委托
            # 用于终止检查，直接执行 撤单指令
            go_straight_to_cancel_action = False

            # 获取持仓状态
            position_df = self.get_position(stock_code)
            apply_df = self.get_apply(stock_code)
            if position_df is None or position_df.shape[0] == 0:
                holding_vol = 0
            else:
                holding_vol = position_df['holding_position'].sum()

            # 获取委托单状态
            if apply_df is None or apply_df.shape[0] == 0:
                apply_vol = 0
                deal_vol = 0
            else:
                apply_vol = apply_df['apply_vol'].sum()
                deal_vol = apply_df['deal_vol'].sum()

                # 如果 持仓 + 未成交委托总量 > 目标持仓（卖出相反）则撤单
                if direction == 1:
                    if holding_vol + (apply_vol - deal_vol) > check_final_position:
                        go_straight_to_cancel_action = True
                        log.warning('%s 持仓：%d 累计申请买入：%d 已成交：%d 已持仓+申请但尚未成交数量大于最终数量%d，立刻撤单',
                                    stock_code, holding_vol, apply_vol, deal_vol, check_final_position)
                elif direction == 0:
                    if holding_vol - (apply_vol - deal_vol) < check_final_position:
                        go_straight_to_cancel_action = True
                        log.warning('%s 持仓：%d 累计申请卖出：%d 已成交：%d 已持仓-申请但尚未成交数量小于最终数量%d，立刻撤单',
                                    stock_code, holding_vol, apply_vol, deal_vol, check_final_position)

                # 如果委托价格超出5档买卖盘价格则撤单
                if not go_straight_to_cancel_action:
                    # 获取盘口价格
                    offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
                    # 获取涨跌停价格
                    high_limit_price, low_limit_price = self.get_limit_price(stock_code)
                    if direction == 1:
                        apply_price = min(apply_df['apply_price'])
                        price_list = [pri for pri, vol in offer_buy_list if not math.isnan(pri)]
                        if len(price_list) == 0:
                            # 有可能跌停，有可能没有获取到盘口价格
                            # 跌停的情况无需撤单，应该全部成交了
                            # 没有获得盘口价格的情况，发一个warning
                            log.warning('%s 目标持仓：%d -> %d 累计申请买入：%d 已成交：%d 没有获得盘口价格',
                                        stock_code, holding_vol, check_final_position, apply_vol, deal_vol)
                        else:
                            # 获取第5档价格（最高一档价格）
                            offer5_price = min(price_list)
                            if apply_price < offer5_price:
                                log.warning('%s 目标持仓：%d -> %d 累计申请买入：%d 已成交：%d 委托价格%.3f 盘口最低价%.3f',
                                            stock_code, holding_vol, check_final_position, apply_vol, deal_vol, apply_price, offer5_price)
                                go_straight_to_cancel_action = True
                    elif direction == 0:
                        apply_price = max(apply_df['apply_price'])
                        price_list = [pri for pri, vol in offer_buy_list if not math.isnan(pri)]
                        if len(price_list) == 0:
                            # 有可能跌停，有可能没有获取到盘口价格
                            # 跌停的情况无需撤单，应该全部成交了
                            # 没有获得盘口价格的情况，发一个warning
                            log.warning('%s 目标持仓：%d -> %d 累计申请买入：%d 已成交：%d 没有获得盘口价格',
                                        stock_code, holding_vol, check_final_position, apply_vol, deal_vol)
                        else:
                            offer5_price = max(price_list)
                            if apply_price < offer5_price:
                                log.warning('%s 目标持仓：%d -> %d 累计申请卖出：%d 已成交：%d 委托价格%.3f 盘口最高价%.3f',
                                            stock_code, holding_vol, check_final_position, apply_vol, deal_vol, apply_price, offer5_price)
                                go_straight_to_cancel_action = True

                if not go_straight_to_cancel_action:
                    apply_amount = (apply_df['apply_vol'] * apply_df['apply_price']).sum()
                    deal_amount = apply_df['deal_amount'].sum()
                    gap_amount = apply_amount - deal_amount
                    if 0 < deal_amount < self.ignore_mini_order:
                        log.warning('%s 累计申购金额：%.2f 累计成交金额：%.2f 剩余未成交金额：%.2f 累计成交金额太小，取消撤单',
                                    stock_code, apply_amount, deal_amount, gap_amount)
                        return False
                    if gap_amount < self.ignore_mini_order:
                        log.warning('%s 累计申购金额：%.2f 累计成交金额：%.2f 剩余未成交金额：%.2f 未成交金额太小，取消撤单',
                                    stock_code, apply_amount, deal_amount, gap_amount)
                        return False

            if not go_straight_to_cancel_action and apply_vol > 0 and deal_vol == apply_vol:
                # 正常情况想不应该出现这种情况，界面上"只显示可撤单委托"被勾选的情况下，应该不会显示已经完全成交的交易
                log.warning('%s 累计申请数量：%d 已经全部成交，无需撤单', stock_code, apply_vol)
                log.warning('请勾选委托界面上"只显示可撤单委托"选框')
                self.clean_csv_cache()
                return False

        try:
            win32gui.SendMessage(self.refresh_entrust_hwnd, win32con.BM_CLICK, None, None)  # 刷新持仓
            time.sleep(0.2)
            win32gui.SendMessage(self.cancel_stock_code_hwnd, win32con.WM_SETTEXT, None, stock_code)  # 输入撤单
            win32gui.SendMessage(self.cancel_query_hwnd, win32con.BM_CLICK, None, None)  # 查询代码
            time.sleep(0.2)
            action = "撤销"
            if direction is None:
                win32gui.SendMessage(self.cancel_all_hwnd, win32con.BM_CLICK, None, None)  # 全撤
            elif direction == 1:
                action = '撤销买入'
                win32gui.SendMessage(self.cancel_buy_hwnd, win32con.BM_CLICK, None, None)  # 撤买
            elif direction == 0:
                action = '撤销卖出'
                win32gui.SendMessage(self.cancel_sell_hwnd, win32con.BM_CLICK, None, None)  # 撤卖
            time.sleep(0.5)
            # 查找是否存在确认框，如果有，将其关闭
            if not self.close_confirm_win_if_exist():
                log.info('%s %s 委托', action, stock_code)
            # 撤单后需要清除相关持仓缓存
            if 'apply' in self._csv_data_dic:
                del self._csv_data_dic['apply']
        except:
            traceback.print_exc()
            return False
        return True

    @property
    def position(self) -> pd.DataFrame:
        return self.get_position()

    def get_position(self, stock_code=None, refresh=False) -> pd.DataFrame:
        """
        获取当前持仓信息
        :return: 
        """
        _, position_df = self._get_csv_data(refresh=refresh)
        if position_df is not None:
            position_df.rename(columns={'证券代码': 'stock_code',
                                        '证券名称': 'sec_name',
                                        '股票余额': 'holding_position',
                                        '可用余额': 'sellable_position',
                                        '参考盈亏': 'profit',
                                        '盈亏比例(%)': 'profit_rate',
                                        '参考成本价': 'cost_price',
                                        '成本金额': 'cost_tot',
                                        '市价': 'market_price',
                                        '市值': 'market_value'}, inplace=True)
            position_df['stock_code'] = ['%06d' % stock_code for stock_code in position_df['stock_code']]
            position_df.set_index('stock_code', inplace=True)
        if stock_code is None:
            ret_df = position_df
        elif position_df is None:
            ret_df = None
        else:
            gdf = position_df.groupby(level=0)
            if stock_code in gdf.groups:
                ret_df = gdf.get_group(stock_code)
            else:
                ret_df = None
        return ret_df

    def get_apply(self, stock_code=None, refresh=False) -> pd.DataFrame:
        """
        获取全部委托单信息
        :return: 
        """
        # apply_df = self._get_csv_data(sub_win_from='holding', sub_win_to='apply')
        apply_df, _ = self._get_csv_data(refresh=refresh)
        if apply_df is not None:
            apply_df.rename(columns={'委托日期': 'apply_date',
                                     '委托时间': 'apply_time',
                                     '证券代码': 'stock_code',
                                     '证券名称': 'sec_name',
                                     '操作': 'operation',
                                     '委托数量': 'apply_vol',
                                     '委托价格': 'apply_price',
                                     '合同编号': 'sid',
                                     '成交数量': 'deal_vol',
                                     '成交金额': 'deal_amount',
                                     '成交均价': 'deal_price',
                                     '委托状态': 'status'}, inplace=True)
            apply_df['stock_code'] = ['%06d' % stock_code for stock_code in apply_df['stock_code']]
            apply_df.set_index('stock_code', inplace=True)
        if stock_code is None:
            ret_df = apply_df
        elif apply_df is None:
            ret_df = None
        else:
            # 按 stock_code 进行group
            gdf = apply_df.groupby(level=0)
            if stock_code in gdf.groups:
                ret_df = gdf.get_group(stock_code)
            else:
                ret_df = None
        return ret_df

    def clean_csv_cache(self):
        self._csv_data_dic = {}

    def _get_csv_data(self, win_name_list=['apply', 'holding'], refresh=False) -> pd.DataFrame:
        """
        获取全部委托单信息
        :param win_name_list: 
        :param refresh: 默认False，强制刷新。不进行强制刷新的情况下，数据超过“self.csv_expire_timedelta”也会自动刷新
        :return: 
        """
        data_df_list = []
        datetime_now = datetime.now()
        for win_name in win_name_list:
            is_ok = False
            if win_name in self._csv_data_dic:
                update_datetime, data_df = self._csv_data_dic[win_name]
                if update_datetime + self.csv_expire_timedelta > datetime_now:
                    is_ok = True
                    data_df = data_df.copy()

            if (not is_ok) or refresh:
                file_name = 'table.xls'
                file_path = os.path.join(self.base_dir, file_name)
                # 如果文件存在，将其删除
                if os.path.exists(file_path):
                    os.remove(file_path)
                # win32gui.SendMessage(self.refresh_entrust_hwnd, win32con.BM_CLICK, None, None)  # 刷新持仓
                # time.sleep(0.1)
                # 多次尝试获取仓位
                # fast_mode = True
                for try_count in range(3):
                    self.goto_buy_win(sub_win=win_name)
                    time.sleep(0.5)
                    win32gui.SendMessage(self.refresh_entrust_hwnd, win32con.BM_CLICK, None, None)  # 刷新持仓
                    time.sleep(0.2)
                    shell = GZZQClientTrader._set_foreground_window(self.position_list_hwnd)

                    # Ctrl +s 热键保存
                    shell.SendKeys('^s')
                    # 停顿时间太短可能导致窗口还没打开，或者及时窗口打开，但最终保存的文件大小为0
                    time.sleep(1)
                    # Enter 热键 切断
                    shell.SendKeys('~')
                    time.sleep(0.2)
                    for try_count_sub in range(3):
                        if not os.path.exists(file_path):
                            log.warning('文件：%s 没有找到，重按 Enter 尝试', file_path)
                            shell.SendKeys('~')
                            time.sleep(0.2)
                        else:
                            break
                    # 检查文件是否ok
                    if os.path.exists(file_path):
                        if os.path.getsize(file_path) > 0:
                            break
                        else:
                            os.remove(file_path)
                # 读取文件
                data_df = GZZQClientTrader.read_export_csv(file_path)
                # 保存 cache
                if data_df is not None:
                    self._csv_data_dic[win_name] = (datetime_now, data_df.copy())  # 暂不考虑 deep copy
            data_df_list.append(data_df)
        return data_df_list

    @staticmethod
    def read_export_csv(file_path):
        """读取持仓数据文件，并备份"""
        # file_name = 'table.xls'
        # file_path = os.path.join(self.base_dir, file_name)
        data_df = None
        if os.path.exists(file_path):
            if os.path.getsize(file_path) > 0:
                data_df = pd.read_csv(file_path, sep='\t', encoding='gbk')
            GZZQClientTrader.back_file(file_path)
        else:
            data_df = None
        return data_df

    @staticmethod
    def back_file(file_path):
        if os.path.exists(file_path):
            base_name, extension = os.path.splitext(file_path)
            new_file_name = base_name + datetime.now().strftime('%Y-%m-%d %H_%M_%S') + extension
            os.rename(file_path, os.path.join(base_name, new_file_name))

    @staticmethod
    def project_copy_data(copy_data):
        reader = StringIO(copy_data)
        df = pd.read_csv(reader, sep='\t')
        return df.to_dict('records')

    def _read_clipboard(self):
        for _ in range(15):
            try:
                win32api.keybd_event(17, 0, 0, 0)
                win32api.keybd_event(67, 0, 0, 0)
                win32api.keybd_event(67, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(17, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.2)
                return pyperclip.paste()
            except Exception as e:
                log.error('open clipboard failed: {}, retry...'.format(e))
                time.sleep(1)
        else:
            raise Exception('read clipbord failed')

    @staticmethod
    def _project_position_str(raw):
        reader = StringIO(raw)
        df = pd.read_csv(reader, sep='\t')
        return df

    @staticmethod
    def _set_foreground_window(hwnd):
        import pythoncom
        pythoncom.CoInitialize()
        shell = win32com.client.Dispatch('WScript.Shell')
        shell.SendKeys('%')
        win32gui.SetForegroundWindow(hwnd)
        return shell

    @property
    def entrust(self):
        return self.get_entrust()

    def get_entrust(self):
        win32gui.SendMessage(self.refresh_entrust_hwnd, win32con.BM_CLICK, None, None)  # 刷新持仓
        time.sleep(0.2)
        self._set_foreground_window(self.entrust_list_hwnd)
        time.sleep(0.2)
        data = self._read_clipboard()
        return self.project_copy_data(data)

    def get_bs_offer_data(self, stock_code):
        """
        获取股票当前盘口价格，同时获取当日涨跌停价格
        :param stock_code: 
        :return: 
        """
        win32gui.SendMessage(self.buy_stock_code_hwnd, win32con.WM_SETTEXT, None, stock_code)  # 输入买入代码
        win32gui.SendMessage(self.refresh_entrust_hwnd, win32con.BM_CLICK, None, None)  # 刷新持仓
        time.sleep(0.5)
        max_try_count = 3
        for try_count in range(max_try_count):
            offer_buy_list = [[helpers.get_text_by_hwnd(hwnd_price, cast=float),
                               helpers.get_text_by_hwnd(hwnd_vol, cast=float)]
                              for hwnd_price, hwnd_vol in self.offer_buy_5_hwnd_list]
            offer_sell_list = [[helpers.get_text_by_hwnd(hwnd_price, cast=float),
                                helpers.get_text_by_hwnd(hwnd_vol, cast=float)]
                               for hwnd_price, hwnd_vol in self.offer_sell_5_hwnd_list]
            high_limit_price = helpers.get_text_by_hwnd(self.high_limit_price_hwnd, cast=float)
            low_limit_price = helpers.get_text_by_hwnd(self.low_limit_price_hwnd, cast=float)
            if not (math.isnan(offer_buy_list[0][0]) and math.isnan(high_limit_price) and math.isnan(low_limit_price)):
                self._stock_limit_price_dic[stock_code] = (high_limit_price, low_limit_price)
                break
            else:
                time.sleep(0.3)
        else:
            log.warning('%s has no bs offer data' % stock_code)
        return offer_buy_list, offer_sell_list

    def get_limit_price(self, stock_code):
        """
        获取当日股票涨跌停价格
        :return: 
        """
        if stock_code not in self._stock_limit_price_dic:
            self.get_bs_offer_data(stock_code)
        if stock_code in self._stock_limit_price_dic:
            high_limit_price, low_limit_price = self._stock_limit_price_dic[stock_code]
        else:
            high_limit_price, low_limit_price = None, None
        return high_limit_price, low_limit_price

    def auto_order(self, stock_target_df: pd.DataFrame, config):
        """
        对每一只股票使用对应的算法交易
        :param stock_target_df: 每一行一只股票，列信息分别为 stock_code(index), final_position, price, wap_mode[对应不同算法名称]
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """
        # rename stock_target_df column name
        col_name_set = set(stock_target_df.columns)
        for col_name in {'ref_price', 'wap_mode', 'final_position'}:
            if col_name not in col_name_set:
                raise ValueError('stock_target_df should has %s column' % col_name)
        # stock_target_df.rename(columns={k1: k2 for k1, k2 in
        #                                 zip(stock_target_df.columns, ['final_position', 'price', 'wap_mode'])})
        # stock_code, init_position, final_position, target_price, direction, wap_mode[对应不同算法名称]
        interval = config.setdefault('interval', 20)
        datetime_start = config.setdefault('datetime_start', datetime.now())

        # 如果设置的是 timedelta_tot 则将其转化为 datetime_end
        if 'timedelta_tot' in config:
            datetime_end = datetime.now() + timedelta(seconds=config['timedelta_tot'])
            config['datetime_end'] = datetime_end
        elif 'datetime_end' in config:
            datetime_end = config['datetime_end']
        else:
            raise ValueError("'datetime_end' or 'timedelta_tot' 至少有一个需要在config中配置")

        stock_bs_df = self.reform_order(stock_target_df)

        # 集合竞价时段 算法交易
        if config.setdefault('aggregate_auction', True):
            datetime_now = datetime.now()
            aggregate_auction_datetime = datetime.strptime(datetime_now.strftime('%Y-%m-%d ') + '9:25:00',
                                                           '%Y-%m-%d %H:%M:%S')
            if datetime.now() < aggregate_auction_datetime:
                log.info('开始集合竞价交易')
                try:
                    # 为提高集合竞价期间性能，降低刷新频率
                    csv_expire_timedelta = self.csv_expire_timedelta
                    self.csv_expire_timedelta = timedelta(seconds=120)
                    # 每个股票执行独立的算法交易
                    for idx in stock_bs_df.index:
                        bs_s = stock_bs_df.ix[idx]
                        self.wap_aggregate_auction(bs_s, config)
                    # 清空 csv 缓存
                    self.clean_csv_cache()
                finally:
                    self.csv_expire_timedelta = csv_expire_timedelta
                    # 休息 继续
                    time.sleep(interval)

        start_datetime = datetime.strptime(datetime.now().strftime('%Y-%m-%d ') + '9:30:02', '%Y-%m-%d %H:%M:%S')
        if datetime.now() < start_datetime:
            wait_seconds = (start_datetime - datetime.now()).seconds
            log.info('交易时段为开始，等待 %d 秒后启动', wait_seconds)
            time.sleep(wait_seconds)
        config['deal_end_datetime'] = config['datetime_end']
        config['deal_start_datetime'] = max([config['datetime_start'], start_datetime])
        config['deal_seconds'] = (config['deal_end_datetime'] - config['deal_start_datetime']).seconds
        keep_wap_mode = config.setdefault('keep_wap_mode', None)
        # 开市时段 循环执行算法交易
        self.init_twap()
        log.info('开始交易时段算法交易')
        while datetime.now() < datetime_end or config.setdefault('once', False):
            # 每个股票执行独立的算法交易
            self.clean_csv_cache()
            log.info('* ' * 30)
            for idx in stock_bs_df.index:
                bs_s = stock_bs_df.ix[idx]
                # 将小额买入卖出过滤掉，除了建仓、清仓指令
                if self.ignore_order(bs_s, config):
                    continue
                wap_mode = bs_s.wap_mode
                if (wap_mode in ('twap', 'twap_initiative')) if keep_wap_mode is None else keep_wap_mode == 'twap_initiative':
                    self.twap_initiative(bs_s, config)  # self.twap_initiative(bs_s, config)
                elif (wap_mode in ("twap_half_passive")) if keep_wap_mode is None else keep_wap_mode == "twap_half_passive":
                    self.twap_half_passive(bs_s, config)
                elif (wap_mode in ("twap_half_initiative")) if keep_wap_mode is None else keep_wap_mode == "twap_half_initiative":
                    self.twap_half_initiative(bs_s, config)
                elif (wap_mode in ("twap_half_initiative_by_offer", 'auto')) if keep_wap_mode is None else keep_wap_mode == "twap_half_initiative_by_offer":
                    self.twap_half_initiative_by_offer(bs_s, config)
                elif (wap_mode in ("twap_half_passive_by_offer")) if keep_wap_mode is None else keep_wap_mode == "twap_half_passive_by_offer":
                    self.twap_half_passive_by_offer(bs_s, config)
                else:
                    raise ValueError('%s) %s wap_mode %s error' % (idx, bs_s.name, wap_mode))
            # 清空 csv 缓存
            self.clean_csv_cache()
            if config.setdefault('once', False):
                break
            # 休息 继续
            time.sleep(interval)

        # 循环结束，再次执行一遍确认所有单子都已经下出去了，价格主动成交
        if config.setdefault('final_deal', True):
            log.info("剩余未完成订单统一执行对手价买入")
            for idx in stock_bs_df.index:
                bs_s = stock_bs_df.ix[idx]
                self.deal_order_active(bs_s, config)

    def sort_order(self, stock_bs_df):
        """
        对order进行排序
        按照先卖后买，穿插组合
        :param stock_bs_df: 
        :return: 
        """
        # stock_bs_df.sort_values(by='direction', inplace=True)
        buy_first = True if self.get_available_amount() > 20000 else False
        stock_bs_df['orderbyvalue'] = 0
        stock_bs_dfg = stock_bs_df.groupby('direction')
        for direction in stock_bs_dfg.groups:
            stock_bs_df_sub = stock_bs_dfg.get_group(direction)
            for n, idx in zip(range(stock_bs_df_sub.shape[0]), stock_bs_df_sub.index):
                stock_bs_df['orderbyvalue'][idx] = n + (-0.5 if buy_first and direction == 1 else 0.5)
        stock_bs_df.sort_values(by='orderbyvalue', inplace=True)
        stock_bs_df.drop('orderbyvalue', axis=1, inplace=True)
        # stock_bs_df['orderbyvalue'] = stock_bs_df['direction'].apply(lambda x: orderbyvalue_0++ if x == 0 else orderbyvalue_1++)
        return stock_bs_df

    def reform_order(self, stock_target_df):
        """
        根据持仓及目标仓位进行合并，生成新的 df：
        stock_code(index), init_position, final_position, target_price, direction, wap_mode[对应不同算法名称]
        :param stock_target_df: 
        :return: 
        """
        position_df = self.position
        # position_df['wap_mode'] = 'twap'
        stock_bs_df = pd.merge(position_df, stock_target_df, left_index=True, right_index=True, how='outer').fillna(0)
        stock_bs_df.rename(columns={'holding_position': 'init_position'}, inplace=True)
        stock_bs_df['direction'] = (stock_bs_df.init_position < stock_bs_df.final_position).apply(
            lambda x: 1 if x else 0)
        stock_bs_df['wap_mode'] = stock_bs_df['wap_mode'].apply(lambda x: 'auto' if x == 0 else x)
        # 如果 refprice == 0，则以 market_price 为准
        for stock_code in stock_bs_df.index:
            if stock_bs_df['ref_price'][stock_code] == 0 and stock_bs_df['market_price'][stock_code] != 0:
                # log.info('%s ref_price --> market_price %f', stock_code, stock_bs_df['market_price'][stock_code])
                stock_bs_df['ref_price'][stock_code] = stock_bs_df['market_price'][stock_code]
        stock_bs_df = self.sort_order(stock_bs_df)
        stock_bs_df = stock_bs_df[['sec_name', 'init_position', 'final_position', 'wap_mode', 'direction',
                                   'sellable_position', 'ref_price', 'cost_price', 'market_price',
                                   'profit_rate', 'profit', 'cost_tot', 'market_value']]
        return stock_bs_df

    def calc_order_bs(self, stock_code, ref_price, direction, target_position, limit_position=None):
        """
        计算买卖股票的 order_vol, price
        :param stock_code:
        :param ref_price: 盘口确实价格时，将使用默认价格
        :param direction:
        :param target_position:
        :param limit_position:  对于买入来说，最大持有仓位，对于卖出来说，最低持有仓位
        :return:
        """
        order_vol, price = 0, 0
        position_df = self.position
        if stock_code in position_df.index:
            # 如果股票存在持仓，轧差后下单手数
            holding_position = position_df.ix[stock_code].holding_position
            order_vol_target = target_position - holding_position
            order_limit = None if limit_position is None else abs(math.floor(limit_position - holding_position))
        else:
            # 如果股票没有持仓，直接目标仓位
            order_vol_target = target_position
            order_limit = abs(math.floor(limit_position))
        # 若 买入 仓位为负，取消；若卖出，仓位为正，取消 —— 不支持融资融券，防止出现日内的仓位震荡
        if direction == 1 and order_vol_target <= 0:
            return order_vol, price
        elif direction == 0 and order_vol_target >= 0:
            return order_vol, price
        if order_vol_target > 0:
            order_vol_target = math.ceil(order_vol_target / 100) * 100
        else:
            order_vol_target = abs(math.floor(order_vol_target / 100) * 100)

        # 获取盘口价格
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return order_vol, price
        # 手续费 万2.5的情况下，最低5元，因此最少每单价格在2W以上
        if direction == 1:
            price = offer_sell_list[0][0]
            if math.isnan(price) or price == 0.0:
                price = ref_price
            order_vol_min = math.ceil(20000 / price / 100) * 100
        else:
            price = offer_buy_list[0][0]
            if math.isnan(price) or price == 0.0:
                price = ref_price
            order_vol_min = math.ceil(20000 / price)

        # 计算最适合的下单数量
        if order_limit is None:
            order_vol = order_vol_target
        elif order_limit < order_vol_min:
            order_vol = order_limit
        elif order_vol_target < order_vol_min < order_limit:
            order_vol = order_vol_min
        else:
            order_vol = order_vol_target
        return order_vol, price

    def calc_order_by_price(self, stock_code, ref_price, direction, target_position, limit_position,
                            include_apply=True, refresh=True):
        """
        计算买卖股票的 order_vol ，根据最大持有金额来计算当前价格下，还可以买入多少股票
        :param stock_code: 
        :param ref_price: 
        :param direction: 
        :param target_position: 
        :param limit_position:  对于买入来说，最大持有仓位，对于卖出来说，最低持有仓位
        :param include_apply: 计算申请单数量
        :param refresh: 强制刷新仓位
        :return: 
        """
        order_vol = 0
        limit_amount = limit_position * ref_price

        # 获取持仓信息
        position_df = self.get_position(stock_code, refresh=refresh)
        if position_df is None or stock_code not in position_df.index:
            holding_position = 0
            holding_amount = 0
        else:
            holding_position = position_df.holding_position.sum()
            holding_amount = position_df.market_value.sum()

        # 获取委托单数据
        apply_vol_has = 0
        apply_vol_deal = 0
        apply_vol_un_deal = 0
        if include_apply:
            apply_df = self.get_apply(stock_code)
            if apply_df is not None and apply_df.shape[0] > 0:
                apply_vol_has = apply_df.apply_vol.sum()
                apply_vol_deal = apply_df.deal_vol.sum()
                apply_vol_un_deal = apply_vol_has - apply_vol_deal

        # 计算 目标委托数量 最终委托数量
        order_vol_target = abs(target_position - holding_position) - apply_vol_un_deal
        order_vol_limit = abs(limit_position - holding_position) - apply_vol_un_deal
        # 如果 目标委托数量 与最大委托数量 差距小于 最小忽略金额 则直接按 最大委托数量 执行
        if (order_vol_limit - order_vol_target) * ref_price < self.min_threshold_amount:
            order_vol_target = order_vol_limit
        # 计算 最小委托数量
        order_vol_min = math.ceil(self.min_threshold_amount / ref_price / 100) * 100
        # 如果 最小委托数量 > 最终委托数量 则直接按 最小委托数量 = 最终委托数量
        if order_vol_min > order_vol_limit:
            order_vol_min = order_vol_limit
        # 如果 目标委托数量 < 最小委托数量 则直接按 最小委托数量 执行
        if order_vol_target < order_vol_min:
            order_vol_target = order_vol_min
        # 如果委托金额 < 最小忽略金额 则放弃，清仓指令除外
        if target_position > 0 and order_vol_target * ref_price < self.ignore_mini_order:  # 如果去掉此限制，则需增加 apply_amount_target < 0 检查
            return order_vol

        order_vol = order_vol_target

        log.info('%s %s %d -> %d -> %d 价格：%.3f 已申请委托：%d 已成交：%d 继续申请：%d',
                 stock_code, '买入' if direction == 1 else '卖出',
                 holding_position, target_position, limit_position, ref_price,
                 apply_vol_has, apply_vol_deal, order_vol)

        return order_vol

    def calc_order_by_offer(self, stock_code, ref_price, direction, target_position,
                            offer_buy_list, offer_sell_list,
                            include_apply=True, refresh=True):
        """
        计算买卖股票的 order_vol ，对手方盘口最大承载量下单
        :param stock_code: 
        :param direction: 
        :param target_position: 
        :param offer_buy_list: 
        :param offer_sell_list: 
        :param include_apply: 
        :param refresh: 
        :return: 
        """
        order_vol = 0

        # 获取持仓信息
        position_df = self.get_position(stock_code, refresh=refresh)
        if position_df is None or stock_code not in position_df.index:
            holding_position = 0
            holding_amount = 0
        else:
            holding_position = position_df.holding_position.sum()
            holding_amount = position_df.market_value.sum()

        # 获取委托单数据
        apply_vol_has = 0
        apply_vol_deal = 0
        apply_vol_un_deal = 0
        if include_apply:
            apply_df = self.get_apply(stock_code)
            if apply_df is not None and apply_df.shape[0] > 0:
                apply_vol_has = apply_df.apply_vol.sum()
                apply_vol_deal = apply_df.deal_vol.sum()
                apply_vol_un_deal = apply_vol_has - apply_vol_deal

        # 计算 目标委托数量 最终委托数量
        order_vol_target = abs(target_position - holding_position) - apply_vol_un_deal
        # 计算 最小委托数量
        order_vol_min = math.ceil(self.min_threshold_amount / ref_price / 100) * 100
        # 如果 最小委托数量 > 最终委托数量 则直接按 最小委托数量 = 最终委托数量
        if order_vol_min > order_vol_target:
            order_vol_min = order_vol_target
        if abs(order_vol_target - order_vol_min) * ref_price < self.ignore_mini_order:
            order_vol_min = order_vol_target
        # 根据盘口决定最大申请仓位
        if direction == 1:
            offer_vol = offer_sell_list[0][1]
            offer_vol = 0 if math.isnan(offer_vol) else offer_vol * 100
        else:
            offer_vol = offer_buy_list[0][1]
            offer_vol = 0 if math.isnan(offer_vol) else offer_vol * 100
        if offer_vol < order_vol_min:
            offer_vol = order_vol_min
        if offer_vol != 0 and offer_vol < order_vol_target:
            order_vol_target = offer_vol
        # 如果委托金额 < 最小忽略金额 则放弃，清仓指令除外
        if target_position > 0 and order_vol_target * ref_price < self.ignore_mini_order:  # 如果去掉此限制，则需增加 apply_amount_target < 0 检查
            return order_vol

        order_vol = order_vol_target

        log.info('%s %s %d -> %d 价格：%.3f 已申请委托：%d 已成交：%d 继续申请：%d',
                 stock_code, '买入' if direction == 1 else '卖出',
                 holding_position, target_position, ref_price,
                 apply_vol_has, apply_vol_deal, order_vol)

        return order_vol

    def init_twap(self):
        self.clean_csv_cache()
        self._stock_deal_datetime_dic = {}

    def calc_order_rate(self, bs_s, config, speed=1):
        """
        如果下单金额小于 min_threshold_amount 直接全部下单
        否则，按照时间按比例下单
        :param bs_s: 
        :param config: 
        :param speed: 默认1：加速买入、卖出 
        :return: 
        """
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        if init_position == final_position:
            return 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        gap_amount = abs(gap_position) * ref_price
        if (gap_amount < self.min_threshold_amount) or \
                ('deal_start_datetime' not in config) or \
                ('deal_seconds' not in config) or \
                (config['deal_seconds'] == 0):
            order_rate = 1
        else:
            # 检查时间进度
            datetime_now = datetime.now()
            timedelta_consume = datetime_now - config['deal_start_datetime']
            order_rate = timedelta_consume.seconds / config['deal_seconds'] * speed

            if order_rate > 1:
                order_rate = 1
            elif order_rate < 0:
                order_rate = 0
        return order_rate

    def twap_initiative(self, bs_s, config):
        """
        简单twap算法交易，对手价成交
        :param bs_s: 
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        min_move = get_min_move_unit(stock_code)
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return
        key_price_last_period = 'apply_price_%s' % stock_code

        # 获取盘口价格
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 如果盘口买一、卖一档差距大于1%则放弃挂单
        price_sell1 = offer_sell_list[0][0]
        price_buy1 = offer_buy_list[0][0]
        if not (math.isnan(price_sell1) or math.isnan(price_buy1)):
            if (price_sell1 / price_buy1) > 1.01:
                log.warning('%s 买1/卖1: %.3f/%.3f 盘口差距过大，取消对手价买入')
                return
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return

        # 计算该时段目标仓位
        target_position = final_position
        # 设置价格
        if direction == 1:
            order_price = offer_sell_list[0][0]
        else:
            order_price = offer_buy_list[0][0]
        if math.isnan(order_price):
            log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
            order_price = ref_price
        remark_str = "算法 %s" % ('买入 卖1' if direction == 1 else '卖出 买1')

        # 获取两个价格分别下单数量
        order_vol = self.calc_order_by_price(stock_code,
                                             ref_price=order_price,
                                             direction=direction,
                                             target_position=target_position,
                                             limit_position=final_position)

        if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
            # 执行买卖逻辑
            if direction == 1:
                order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                self.buy(stock_code, order_price, order_vol, remark=remark_str)
            else:
                order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                self.sell(stock_code, order_price, order_vol, remark=remark_str)

            config[key_price_last_period] = order_price

    def twap_half_passive(self, bs_s, config):
        """
        第一时间段：自 deal_start_datetime 开始（至少2分钟，至多60% 的时间）：
        首次执行时，先将历史挂单撤掉
        买入：买1价挂单
        卖出：卖1价挂单
        每一轮次不撤单
        
        第二时间段：第一时间段之后的时间
        一次性全部撤单
        买入：买1价+0.01(1Move)挂单
        卖出：卖1价-0.01(1Move)挂单
        :param bs_s: 
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        min_move = get_min_move_unit(stock_code)
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return

        # 获取盘口价格
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return
        if direction == 1:
            order_price = offer_buy_list[0][0]
        else:
            order_price = offer_sell_list[0][0]
        if math.isnan(order_price):
            log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
            order_price = ref_price

        # 检查时间进度
        datetime_now = datetime.now()
        section1_len_pct = 0.6
        section1_time_spend = max([timedelta(minutes=2), timedelta(seconds=config['deal_seconds'] * section1_len_pct)])
        section1_end_time = config['deal_start_datetime'] + section1_time_spend

        if datetime_now < section1_end_time or config.setdefault('once', False):
            # 每只股票首次执行时，撤历史委托
            if stock_code not in self._stock_deal_datetime_dic:
                self.cancel_entrust(stock_code, direction, check_final_position=final_position)
            self._stock_deal_datetime_dic[stock_code] = datetime_now  # 防止出现时间差导致的漏洞
            # 计算下单比例
            order_rate = self.calc_order_rate(bs_s, config, speed=2)
            target_position = init_position + gap_position * order_rate
            shift_price = 0
        else:
            # 每只股票首次进入第二时段时执行撤单
            if stock_code not in self._stock_deal_datetime_dic or self._stock_deal_datetime_dic[
                stock_code] < section1_end_time:
                self.cancel_entrust(stock_code, direction, check_final_position=final_position)
            self._stock_deal_datetime_dic[stock_code] = datetime_now  # 防止出现时间差导致的漏洞
            # 计算该时段目标仓位
            target_position = final_position
            shift_price = min_move if direction == 1 else -min_move

        # 设置目标价格
        order_price = order_price + shift_price
        # 计算买卖股票的 order_vol, price，根据最大持有金额来计算当前价格下，还可以买入多少股票
        order_vol = self.calc_order_by_price(stock_code,
                                             ref_price=order_price,
                                             direction=direction,
                                             target_position=target_position,
                                             limit_position=final_position)

        if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
            # 执行买卖逻辑
            if direction == 1:
                order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                self.buy(stock_code, order_price, order_vol,
                         remark="算法买入 买1" + ('' if shift_price == 0 else '%+.3f' % shift_price))
            else:
                order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                self.sell(stock_code, order_price, order_vol,
                          remark="算法卖出 卖1" + ('' if shift_price == 0 else '%+.3f' % shift_price))

    def twap_half_passive_by_offer(self, bs_s, config):
        """
        根据盘口承载量最大限度挂单，尽可能成交原则
        如果价格已经涨停则不买卖
        第一时间段：自 deal_start_datetime 开始（至少2分钟，至多60% 的时间）：
        首次执行时，先将历史挂单撤掉
        买入：买1价挂单
        卖出：卖1价挂单
        每一轮次不撤单

        第二时间段：第一时间段之后的时间
        一次性全部撤单
        买入：买1价+0.01(1Move)挂单
        卖出：卖1价-0.01(1Move)挂单
        :param bs_s: 
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        min_move = get_min_move_unit(stock_code)
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return

        # 获取盘口价格
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return
        if direction == 1:
            order_price = offer_buy_list[0][0]
        else:
            order_price = offer_sell_list[0][0]
        if math.isnan(order_price):
            log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
            order_price = ref_price

        # 检查时间进度
        datetime_now = datetime.now()
        section1_len_pct = 0.6
        section1_time_spend = max([timedelta(minutes=2), timedelta(seconds=config['deal_seconds'] * section1_len_pct)])
        section1_end_time = config['deal_start_datetime'] + section1_time_spend

        if datetime_now < section1_end_time or config.setdefault('once', False):
            # 每一轮次进行撤单，仅撤销“未成交委托”的委托
            self.cancel_entrust(stock_code, direction, check_final_position=final_position,
                                only_dealvol_0=True, offer_buy_list=offer_buy_list, offer_sell_list=offer_sell_list)
            # 计算价格偏移量
            shift_price = 0
        else:
            # 每只股票首次进入第二时段时执行撤单
            if stock_code not in self._stock_deal_datetime_dic or self._stock_deal_datetime_dic[
                stock_code] < section1_end_time:
                self.cancel_entrust(stock_code, direction, check_final_position=final_position)
            self._stock_deal_datetime_dic[stock_code] = datetime_now  # 防止出现时间差导致的漏洞
            # 计算价格偏移量
            shift_price = min_move if direction == 1 else -min_move

        # 设置目标价格
        order_price = order_price + shift_price
        # 计算买卖股票的 order_vol, price，根据最大持有金额来计算当前价格下，还可以买入多少股票
        order_vol = self.calc_order_by_offer(stock_code, ref_price, direction, final_position,
                                             offer_buy_list, offer_sell_list)

        if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
            # 执行买卖逻辑
            if direction == 1:
                order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                self.buy(stock_code, order_price, order_vol,
                         remark="算法买入 买1" + ('' if shift_price == 0 else '%+.3f' % shift_price))
            else:
                order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                self.sell(stock_code, order_price, order_vol,
                          remark="算法卖出 卖1" + ('' if shift_price == 0 else '%+.3f' % shift_price))

    def twap_half_initiative_by_offer(self, bs_s, config):
        """
        根据盘口承载量最大限度挂单，尽可能成交原则
        如果价格已经涨停则不买卖
        第一时间段：自 deal_start_datetime 开始（60% 的时间）：
        买入：卖1价挂单
        卖出：买1价挂单
        委托份额：max([盘口数量,目标持仓量])
        每一轮次进行撤单，仅撤销“未成交委托”的委托

        第二时间段：第一时间段之后的时间
        一次性全部撤单
        每一轮次进行撤单，仅撤销“未成交委托”的委托，以及，已成交金额大于2W且未成交金额+后续委托金额大于2W的订单
        买入：买1价+0.01(1Move)挂单
        卖出：卖1价-0.01(1Move)挂单
        :param bs_s: 
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        min_move = get_min_move_unit(stock_code)
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return
        key_price_last_period = 'apply_price_%s' % stock_code

        # 获取盘口价格
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return

        # 检查时间进度
        datetime_now = datetime.now()
        section1_len_pct = 0.8
        section1_time_spend = max([timedelta(minutes=2), timedelta(seconds=config['deal_seconds'] * section1_len_pct)])
        section1_end_time = config['deal_start_datetime'] + section1_time_spend

        if datetime_now < section1_end_time or config.setdefault('once', False):
            # 第一时段盘口价格±1 跳挂单

            # 获取盘口价格
            shift_price = min_move if direction == 1 else -min_move
            if direction == 1:
                order_price = offer_buy_list[0][0]
            else:
                order_price = offer_sell_list[0][0]
            if math.isnan(order_price):
                log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
                order_price = ref_price

            # 每一轮次进行撤单，仅撤销“未成交委托”的委托
            self.cancel_entrust(stock_code, direction, check_final_position=final_position,
                                only_dealvol_0=True, offer_buy_list=offer_buy_list, offer_sell_list=offer_sell_list)

            # 获取上一周期时的委托价格
            order_price_on_last_period = config.setdefault(key_price_last_period, ref_price)
            # 设置目标价格
            if direction == 1:
                # 如果当前 买1 价与上一次的 order_price 委托价格相同，则继续使用上一个周期时的委托价格
                # 此逻辑是为了防止出现过大的冲击成本，造成一轮轮的委托推动价格上涨
                if order_price != order_price_on_last_period:
                    # 设置 order_price 价格
                    order_price = order_price + shift_price
            else:
                # 如果当前 卖1 价与上一次的 price2 委托价格相同，则继续使用上一个周期时的委托价格
                # 此逻辑是为了防止出现过大的冲击成本，造成一轮轮的委托推动价格上涨
                if order_price != order_price_on_last_period:
                    # 设置 order_price 价格
                    order_price = order_price + shift_price

            remark_str = "算法 %s%+.3f" % ('买入 买1' if direction == 1 else '卖出 卖1', shift_price)
        else:
            # 第二时段，以对手价委托
            # 每只股票首次进入第二时段时执行撤单
            if stock_code not in self._stock_deal_datetime_dic or self._stock_deal_datetime_dic[
                stock_code] < section1_end_time:
                self.cancel_entrust(stock_code, direction, check_final_position=final_position)
            self._stock_deal_datetime_dic[stock_code] = datetime_now  # 防止出现时间差导致的漏洞
            # 如果盘口买一、卖一档差距大于1%则放弃挂单
            price_sell1 = offer_sell_list[0][0]
            price_buy1 = offer_buy_list[0][0]
            if not (math.isnan(price_sell1) or math.isnan(price_buy1)):
                if (price_sell1 / price_buy1) > 1.01:
                    log.warning('%s 买1/卖1: %.3f/%.3f 盘口差距过大，取消对手价买入')
                    return
            # 设置价格
            if direction == 1:
                order_price = offer_sell_list[0][0]
            else:
                order_price = offer_buy_list[0][0]
            if math.isnan(order_price):
                log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
                order_price = ref_price
            remark_str = "算法 %s" % ('买入 卖1' if direction == 1 else '卖出 买1')

        # 获取两个价格分别下单数量
        order_vol = self.calc_order_by_offer(stock_code, ref_price, direction=direction,
                                             offer_buy_list=offer_buy_list, offer_sell_list=offer_sell_list,
                                             target_position=final_position)

        if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
            # 执行买卖逻辑
            if direction == 1:
                order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                self.buy(stock_code, order_price, order_vol, remark=remark_str)
            else:
                order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                self.sell(stock_code, order_price, order_vol, remark=remark_str)

            config[key_price_last_period] = order_price

    def twap_half_initiative(self, bs_s, config):
        """
        9：30分开始：
        首次执行时，先将历史挂单撤掉
        买入：买1价+0.01(1Move)挂单
        卖出：卖1价-0.01(1Move)挂单
        每一轮次不撤单
        执行剩余最后1分钟时
        撤单买入：买1价+0.01(1Move)挂单
        撤单卖出：卖1价-0.01(1Move)挂单
        挂单原则 
        :param bs_s: 
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """

        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        min_move = get_min_move_unit(stock_code)
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return
        key_price_last_period = 'apply_price_%s' % stock_code

        # 获取盘口价格
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return

        # 检查时间进度
        datetime_now = datetime.now()
        section1_len_pct = 0.8
        section1_time_spend = max([timedelta(minutes=2), timedelta(seconds=config['deal_seconds'] * section1_len_pct)])
        section1_end_time = config['deal_start_datetime'] + section1_time_spend

        if datetime_now < section1_end_time or config.setdefault('once', False):
            # 第一时段盘口价格±1 跳挂单
            # 每只股票首次执行时，撤历史委托
            if stock_code not in self._stock_deal_datetime_dic:
                self.cancel_entrust(stock_code, direction, check_final_position=final_position)
            self._stock_deal_datetime_dic[stock_code] = datetime.now()
            # 计算该时段目标仓位
            # 计算下单比例
            order_rate = self.calc_order_rate(bs_s, config, speed=1.5)
            target_position = init_position + gap_position * order_rate
            # 设置价格
            shift_price = min_move if direction == 1 else -min_move
            if direction == 1:
                order_price = offer_buy_list[0][0]
            else:
                order_price = offer_sell_list[0][0]
            if math.isnan(order_price):
                log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
                order_price = ref_price
            # 获取上一周期时的委托价格
            order_price_on_last_period = config.setdefault(key_price_last_period, ref_price)
            # 设置目标价格
            if direction == 1:
                # 如果当前 买1 价与上一次的 order_price 委托价格相同，则继续使用上一个周期时的委托价格
                # 此逻辑是为了防止出现过大的冲击成本，造成一轮轮的委托推动价格上涨
                if order_price != order_price_on_last_period:
                    # 设置 order_price 价格
                    order_price = order_price + shift_price
            else:
                # 如果当前 卖1 价与上一次的 price2 委托价格相同，则继续使用上一个周期时的委托价格
                # 此逻辑是为了防止出现过大的冲击成本，造成一轮轮的委托推动价格上涨
                if order_price != order_price_on_last_period:
                    # 设置 order_price 价格
                    order_price = order_price + shift_price

            remark_str = "算法 %s%+.3f" % ('买入 买1' if direction == 1 else '卖出 卖1', shift_price)
        else:
            # 第二时段，以对手价委托
            # 每只股票首次进入第二时段时执行撤单
            if stock_code not in self._stock_deal_datetime_dic or self._stock_deal_datetime_dic[
                stock_code] < section1_end_time:
                self.cancel_entrust(stock_code, direction, check_final_position=final_position)
            self._stock_deal_datetime_dic[stock_code] = datetime_now  # 防止出现时间差导致的漏洞
            # 计算该时段目标仓位
            target_position = final_position
            # 如果盘口买一、卖一档差距大于1%则放弃挂单
            price_sell1 = offer_sell_list[0][0]
            price_buy1 = offer_buy_list[0][0]
            if not(math.isnan(price_sell1) or math.isnan(price_buy1)):
                if (price_sell1 / price_buy1) > 1.01:
                    log.warning('%s 买1/卖1: %.3f/%.3f 盘口差距过大，取消对手价买入')
                    return
            # 设置价格
            if direction == 1:
                order_price = offer_sell_list[0][0]
            else:
                order_price = offer_buy_list[0][0]
            if math.isnan(order_price):
                log.warning('未能获取%s盘口价格，参考价格：%.3f', stock_code, ref_price)
                order_price = ref_price
            remark_str = "算法 %s" % ('买入 卖1' if direction == 1 else '卖出 买1')

        # 获取两个价格分别下单数量
        order_vol = self.calc_order_by_price(stock_code,
                                             ref_price=order_price,
                                             direction=direction,
                                             target_position=target_position,
                                             limit_position=final_position)

        if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
            # 执行买卖逻辑
            if direction == 1:
                order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                self.buy(stock_code, order_price, order_vol, remark=remark_str)
            else:
                order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                self.sell(stock_code, order_price, order_vol, remark=remark_str)

            config[key_price_last_period] = order_price

    def wap_aggregate_auction(self, bs_s, config):
        """
        集合竞价9：25分前，根据盘口加±0.01(1Move)主动挂单（如果没有盘口则不挂单）
        一次性全部委托挂单
        :param bs_s: 
        :param config: {'timedelta_tot': 120, 'datetime_start': datetime.now(), 'interval': 10}
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        # 将小额买入卖出过滤掉，除了清仓指令
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return

        datetime_now = datetime.now()
        aggregate_auction_datetime = datetime.strptime(datetime_now.strftime('%Y-%m-%d ') + '9:24:58',
                                                       '%Y-%m-%d %H:%M:%S')
        if datetime_now < aggregate_auction_datetime:
            # 检查当前时刻是否超过 集合竞价 时间
            offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
            # 获取涨跌停价格
            high_limit_price, low_limit_price = self.get_limit_price(stock_code)
            #  如果价格已经涨停则不买卖
            if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
                log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
                return
            if direction == 1:
                offer_price = offer_buy_list[0][0]
                offer_vol = offer_buy_list[0][1]
                offer_vol = 0 if math.isnan(offer_vol) else offer_vol * 100
            else:
                offer_price = offer_sell_list[0][0]
                offer_vol = offer_sell_list[0][1]
                offer_vol = 0 if math.isnan(offer_vol) else offer_vol * 100
            # if math.isnan(offer_price):
            #     return
            # 获取已发送的买卖申请
            apply_df = self.get_apply(stock_code)
            if apply_df is None or apply_df.shape[0] == 0:
                apply_vol_has = 0
            else:
                apply_vol_has = apply_df.apply_vol.sum()
            # 设置移动点差
            min_move = get_min_move_unit(stock_code)
            shift_price = min_move if direction == 1 else -min_move
            # 集合竞价盘口价格±0.01(1 move)
            if direction == 1:
                apply_vol_allow = abs(gap_position) - apply_vol_has
                order_vol = apply_vol_allow  # min([apply_vol_allow, math.floor(math.ceil(offer_vol * 0.8 / 100) * 100)]) if offer_vol > 0 else apply_vol_allow;
                order_price = ref_price if math.isnan(offer_price) else offer_price + shift_price
            else:
                apply_vol_allow = abs(gap_position) - apply_vol_has
                order_vol = apply_vol_allow  # min([apply_vol_allow, math.floor(math.ceil(offer_vol * 0.8 / 100) * 100)]) if offer_vol > 0 else apply_vol_allow;
                order_price = ref_price if math.isnan(offer_price) else offer_price + shift_price
            if order_vol <= 0:
                log.info('%s %s %d -> %d 已报数量：%d 买卖价格：%f 忽略',
                         stock_code, '买入' if direction == 1 else '卖出',
                         init_position, final_position, apply_vol_has, order_price)
                return
            # 执行买卖操作
            if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
                # 执行买卖逻辑
                if direction == 1:
                    order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                    # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                    self.buy(stock_code, order_price, order_vol, remark="集合买入 买1 %+.3f" % shift_price)
                else:
                    order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                    # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                    self.sell(stock_code, order_price, order_vol, remark="集合卖出 卖1 %+.3f" % shift_price)

    def deal_order_active(self, bs_s, config):
        """
        主动成交，撤销此前全部委托，卖2 或 买2 档价格直接委托下单
        :param bs_s: 
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        # 将小额买入卖出过滤掉，除了建仓、清仓指令
        if self.ignore_order(bs_s, config):
            return
        self.cancel_entrust(stock_code, direction, check_final_position=final_position)
        position_df = self.position
        if stock_code in position_df.index:
            order_vol = final_position - position_df.ix[stock_code].holding_position
        else:
            order_vol = final_position
        direction = 1 if order_vol > 0 else 0
        offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
        # 如果盘口买一、卖一档差距大于1%则放弃挂单
        price_sell1 = offer_sell_list[0][0]
        price_buy1 = offer_buy_list[0][0]
        if not (math.isnan(price_sell1) or math.isnan(price_buy1)):
            if (price_sell1 / price_buy1) > 1.01:
                log.warning('%s 买1/卖1: %.3f/%.3f 盘口差距过大，取消对手价买入')
                return
        # 获取涨跌停价格
        high_limit_price, low_limit_price = self.get_limit_price(stock_code)
        #  如果价格已经涨停则不买卖
        if high_limit_price == offer_buy_list[0][0] or high_limit_price == offer_sell_list[0][0]:
            log.warning('%s 已经处于涨停价格%.3f，取消卖出', stock_code, high_limit_price)
            return
        # 主动成交选择买卖五档价格中的二挡买卖价格进行填报
        if direction == 1:
            price = offer_sell_list[1][0]
            price = ref_price if math.isnan(price) else price
            order_price = price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交
            # log.debug('主动买入 %s卖2委托价格 %f', stock_code_str, price)
            # self.buy(stock_code, price, order_vol, remark="主动买入 卖2")
            remark_str = "主动买入 卖2"
        else:
            price = offer_buy_list[1][0]
            price = ref_price if math.isnan(price) else price
            order_price = price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交
            # log.debug('主动卖出 %s买2委托价格 %f', stock_code_str, price)
            # self.sell(stock_code, price, abs(order_vol), remark="主动卖出 买2")
            remark_str = "主动卖出 买2"

        # 获取两个价格分别下单数量
        order_vol = self.calc_order_by_price(stock_code,
                                             ref_price=order_price,
                                             direction=direction,
                                             target_position=final_position,
                                             limit_position=final_position)




        if not (math.isnan(order_vol) or order_vol <= 0 or math.isnan(order_price) or order_price <= 0):
            # 执行买卖逻辑
            if direction == 1:
                order_price = order_price - SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法买入 %s 买1委托价格 %f', stock_code_str, order_price)
                self.buy(stock_code, order_price, order_vol, remark=remark_str)
            else:
                order_price = order_price + SHIFT_PRICE  # 测试用价格，调整一下防止真成交了
                # log.debug('算法卖出 %s 卖1委托价格 %f', stock_code_str, order_price)
                self.sell(stock_code, order_price, order_vol, remark=remark_str)

    def ignore_order(self, bs_s, config=None):
        """
        忽略小额订单，及已经达成目标的订单
        :param bs_s: 
        :return: 
        """
        stock_code = bs_s.name
        final_position = bs_s.final_position
        init_position = bs_s.init_position
        direction = 1 if init_position < final_position else 0
        if config is not None:
            # config["side"] 0 买卖 / 1 只买 / 2 只卖
            if config["side"] not in ((0, 1) if direction == 1 else (0, 2)):
                log.debug('%s 跳过%s', stock_code, '买入' if direction == 1 else '卖出')
                return True
        # 将小额买入卖出过滤掉，除了清仓指令
        ref_price = bs_s.ref_price
        # gap_position 可能为负数
        gap_position = final_position - init_position
        # 将小额买入卖出过滤掉，除了清仓指令
        if (direction == 1 and gap_position <= 0) or (direction == 0 and gap_position >= 0):
            log.info('%s %s %d -> %d 参考价格：%.3f 已经达成目标仓位',
                     stock_code, '买入' if direction == 1 else '卖出', init_position, final_position, ref_price)
            return True
        # 仅限于调仓阶段（建仓、清仓阶段不忽略小额单子）
        if final_position != 0 and init_position != 0 and abs(gap_position * ref_price) < self.ignore_mini_order:
            log.info('%s %s %d -> %d 参考价格：%.3f 参考金额：%.3f 单子太小，忽略',
                     stock_code, '买入' if direction == 1 else '卖出', init_position, final_position, ref_price,
                     gap_position * ref_price)
            return True
        return False

    def cancel_all_apply(self):
        apply_df = self.get_apply()
        if apply_df is None:
            return
        for stock_code in apply_df.index:
            self.cancel_entrust(stock_code, direction=None)

    def compare_result(self, stock_target_df: pd.DataFrame):
        if stock_target_df is None:
            log.warning('stock_target_df is None')
        stock_bs_df = self.reform_order(stock_target_df)
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
        log.info('\n%s', res_df)
        res_df.to_csv('对比执行结果.csv')

    def monitor_md(self, stock_target_df: pd.DataFrame, second_interval=60, warning_line=-0.01):
        """
        监控组合净值表现情况
        :param stock_target_df: 
        :param second_interval: 监测间隔
        :param warning_line: 预警线
        :return: 
        """
        if stock_target_df is None or stock_target_df.shape[0] == 0:
            log.warning("目标股票列表为空，无需监控")
            return
        try:
            stock_target_dic = stock_target_df.T.to_dict()
            while self.monitor_running:
                # 通过 tushare 获取行情数据
                stock_code_list = list(stock_target_dic.keys())
                bs_df = ts.get_realtime_quotes(stock_code_list)
                bs_df.set_index('code', inplace=True)
                for n_stock, (stock_code, data_dic) in enumerate(stock_target_dic.items()):
                    sell_price = float(bs_df['ask'][stock_code])
                    if sell_price == 0:
                        price_df = ts.get_k_data(stock_code)
                        if price_df is not None or price_df.shape[0] > 0:
                            sell_price = price_df['close'].iloc[-1]
                    price = data_dic['ref_price'] if math.isnan(sell_price) else sell_price
                    data_dic["cur_price"] = price
                # 通过交易软件获取行情数据
                # for n_stock, (stock_code, data_dic) in enumerate(stock_target_dic.items()):
                #     offer_buy_list, offer_sell_list = self.get_bs_offer_data(stock_code)
                #     price = data_dic['ref_price'] if math.isnan(offer_sell_list[0][0]) else offer_sell_list[0][0]
                #     data_dic["cur_price"] = price
                stock_target_cur_df = pd.DataFrame(stock_target_dic).T
                stock_target_cur_df['当日涨跌幅'] = (stock_target_cur_df['cur_price'] - stock_target_cur_df['ref_price']) / stock_target_cur_df['ref_price']
                rr_percent = ((stock_target_cur_df['当日涨跌幅'] * stock_target_cur_df['final_position']) / stock_target_cur_df['final_position'].sum()).sum() * 100
                data_df_4_shown = stock_target_cur_df[['final_position', 'ref_price', 'cur_price', '当日涨跌幅']].rename(columns={
                    "final_position": "目标仓位",
                    "ref_price": "参考价格",
                    "cur_price": "当前价格",
                })
                data_df_4_shown['当日涨跌幅'] = data_df_4_shown['当日涨跌幅'].apply(lambda x: "%.2f%%" % (x * 100))

                log.info("当日组合涨跌幅 %+.2f%% 各个股票涨跌幅\n%s\n输入任意字符回车后退出监控",
                         rr_percent, data_df_4_shown)

                if warning_line != 0 and rr_percent <= warning_line:
                    warning_line_str = "↓" * 30
                    log.warning("到达预警线")
                    cprint("↓" * 30, 'green')
                    cprint("↑" * 30, 'red')
                    winsound.Beep(600, 1000)

                time.sleep(second_interval)
        except:
            log.exception("监控程序执行异常，已经退出")
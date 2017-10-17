# easytrader

[![Package](https://img.shields.io/pypi/v/easytrader.svg)](https://pypi.python.org/pypi/easytrader)
[![Travis](https://img.shields.io/travis/shidenggui/easytrader.svg)](https://travis-ci.org/shidenggui/easytrader)
[![License](https://img.shields.io/github/license/shidenggui/easytrader.svg)](https://github.com/shidenggui/easytrader/blob/master/LICENSE)

* 进行自动的程序化股票交易
* 支持跟踪 `joinquant`, `ricequant` 的模拟交易
* 支持跟踪 雪球组合 调仓
* 支持通用的同花顺客户端模拟操作
* 实现自动登录
* 支持通过 webserver 远程操作客户端
* 支持命令行调用，方便其他语言适配
* 支持 Python3, Linux / Win, 推荐使用 `Python3`
* 有兴趣的可以加群 `556050652` 一起讨论
* 捐助:

![微信](http://7xqo8v.com1.z0.glb.clouddn.com/wx.png?imageView2/1/w/300/h/300)             ![支付宝](http://7xqo8v.com1.z0.glb.clouddn.com/zhifubao2.png?imageView2/1/w/300/h/300)

## 公众号

扫码关注“易量化”的微信公众号，不定时更新一些个人文章及与大家交流

![](http://7xqo8v.com1.z0.glb.clouddn.com/easy_quant_qrcode.jpg?imageView2/1/w/300/h/300)


**开发环境** : `Ubuntu 16.04` / `Python 3.5`

### 相关

[获取新浪免费实时行情的类库: easyquotation](https://github.com/shidenggui/easyquotation)

[简单的股票量化交易框架 使用 easytrader 和 easyquotation](https://github.com/shidenggui/easyquant)

### 支持券商（同花顺内核）

* 银河客户端, 须在 `windows` 平台下载 `银河双子星` 客户端
* 华泰客户端(网上交易系统（专业版Ⅱ）)
* 国金客户端(全能行证券交易终端PC版)
* 其他券商通用同花顺客户端(需要手动登陆)

注: 现在有些新的同花顺客户端对拷贝剪贴板数据做了限制，我在 [issue](https://github.com/shidenggui/easytrader/issues/272) 里提供了几个券商老版本的下载地址。


### 实盘易

如果有对其他券商或者通达信版本的需求，可以查看 [实盘易](http://www.iguuu.com/e?x=19828)
* 银河
* 广发
* 银河客户端(支持自动登陆), 须在 `windows` 平台下载 `银河双子星` 客户端
* 湘财证券
* 华泰证券
* 广州证券

> 软件交易前请先进行必要的设置，关闭不必要的弹框及自动填补，修改价格等功能。
>- 系统设置：
>- 是否计算可买数量作为参考（否）
>- 强制使用本地计算可买数量（否）
>- 交易设置：
>- 默认买入价格：空
>- 默认买入数量：空
>- 默认卖出价格：空
>- 默认卖出数量：空
>- 快速交易：
>- 委托价格超出涨跌停价格是否提示：否
>- 卖出后是否查询股票：否
>- 是否弹出成交回报提示窗口：否
>- 委托价格是否跟随买卖盘变化：否
>- 撤单前是否需要确认：否
>- 委托前是否需要确认：否
>- 委托成功后是否弹出提示对话框：否
>- 路径及其他环境变量设置
>- gzzq_clienttrader.py 文件 SHIFT_PRICE 字段设置为 0
>- gzzq_clienttrader.py 文件 self.base_dir = r'd:\Downloads' 设置为文件保存默认路径

### 控制台操作程序
仅针对广州证券
> python wapcli.py \
\
输入 0：退出 \
输入 1：导入股票列表 \
输入 2：查询目标股票列表 \
输入 3：查询当前持仓 \
输入 4：查询合并后交易列表 \
输入 5：执行算法交易 \
输入 6：对比执行结果 \
输入 7：全部撤单 \
输入 8：全部买/卖1档±0.01下单 \
输入 9：全部对手价下单 

### 模拟交易

* 雪球组合 by @[haogefeifei](https://github.com/haogefeifei)（[说明](doc/xueqiu.md)）

### 使用文档

[中文文档](http://easytrader.readthedocs.io/zh/master/)

### 其他

[软件实现原理](http://www.jisilu.cn/question/42707)

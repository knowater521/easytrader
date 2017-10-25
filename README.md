# easytrader

* 进行自动的程序化股票交易
* 实现自动登录
* 支持跟踪 `joinquant`, `ricequant` 的模拟交易
* 支持跟踪 雪球组合 调仓
* 支持命令行调用，方便其他语言适配
* 支持 Python3 / Python2, Linux / Win, 推荐使用 `Python3`

**开发环境** : `Ubuntu 16.04` / `Python 3.5`

### 相关

[获取新浪免费实时行情的类库: easyquotation](https://github.com/shidenggui/easyquotation)

[简单的股票量化交易框架 使用 easytrader 和 easyquotation](https://github.com/shidenggui/easyquant)


### 支持券商（同花顺内核）

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
>- 交易软件委托列表界面 勾线 仅显示可撤销委托

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


### 算法交易模式设置
>- twap_initiative 主动成交，买卖均以对手价盘口价格成交
>- twap_half_initiative 半被动成交，第一时段（前80%的时间）：以盘扣价±1跳挂单，第二时段，对手价下单
>- twap_half_passive 半被动成交，第一时段（前60%的时间）：以买卖盘口价格挂单，第二时段，以盘扣价±1跳挂单

 
### 实盘易

如果有对其他券商或者通达信版本的需求，可以查看 [实盘易](http://6du.in/0s15Iru)

### 模拟交易

* 雪球组合 by @[haogefeifei](https://github.com/haogefeifei)（[说明](doc/xueqiu.md)）

### 使用文档

[中文文档](http://easytrader.readthedocs.io/zh/master/)

### 其他

[软件实现原理](http://www.jisilu.cn/question/42707)

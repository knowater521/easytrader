# coding:utf8
import logging

log = logging.getLogger('easytrader')
log.setLevel(logging.DEBUG)
log.propagate = False

fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s %(lineno)s: %(message)s')
ch = logging.StreamHandler()

ch.setFormatter(fmt)
log.handlers.append(ch)

from logging.handlers import TimedRotatingFileHandler
flog = TimedRotatingFileHandler('trflog.log', when='D')
flog.setFormatter(fmt)
flog.suffix = "%Y-%m-%d_%H-%M.log"
log.handlers.append(flog)

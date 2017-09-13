# -*- coding: utf-8 -*-
import unittest
import easytrader
import base64


class TestEasytrader(unittest.TestCase):

    def test_login(self):
        user_str = '050000006***'
        password_str = '123123'  # bytes.decode(base64.decodebytes(b'123123'))
        user = easytrader.use('ht_client')
        # user.prepare(user='100053072', password=password_str)
        # user = easytrader.use('hb_client')
        user.prepare(user=user_str, password=password_str)


if __name__ == '__main__':
    unittest.main()

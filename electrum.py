
import logging

import random
from . import bitcoin
from .bitcoin import is_valid, Transaction
import requests
import re
import json
import time


SERVER = 'http://54.200.53.221:8081/'
FEE_PER_KB = 20000

def update_tx_outputs(tx, prevout_values):
    for i, (addr, value) in enumerate(tx.outputs):
        key = tx.hash() + ':%d' % i
        prevout_values[key] = value

class ElectrumClient(object):
    def __init__(self, server=None, cache=None):
        self.message_id = 1
        self.server = server if server else SERVER
        self.session = self.get_session()
        self.cache = cache

    def get_session(self):
        headers = {'Content-Type': 'application/json-rpc'}
        response = requests.post(self.server, data=json.dumps([]), headers=headers)
        return re.search("=([\w\d]+)$", response.headers['set-cookie']).group(1)


    def call_server(self, messages):
        """
        Call electrum server

        :param messages:
        :param state:
        :return:
        """
        headers = {'Content-Type': 'application/json-rpc'}
        cookies = {'SESSION': self.session}

        for message in messages:
            message['id'] = self.message_id
            self.message_id += 1

        #call once to send the message

        #call again to get the response
        logging.info(messages)

        for i in range(3):
            r = requests.post(self.server, data=json.dumps(messages), headers=headers, cookies=cookies)
            time.sleep(0.01)
            r = requests.post(self.server, data=json.dumps([]), headers=headers, cookies=cookies)
            if r.content != "":
                break
            else:
                logging.error("retry!")


        if r.status_code != 200:
            raise Exception("error calling electrum server")

        r.encoding = 'utf-8' #work-around gae issue
        return r

    def get_history(self, address):
        #start session
        m = [
            {'params': [address], 'method': 'blockchain.address.get_history'},
        ]
        r = self.call_server(m)
        return r.json()['result']

    def get_transaction(self, transaction, height):

        cache_key = "%s%s" % (transaction, height)
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        #start session
        m = [
            {'params': [transaction, height], 'method': 'blockchain.transaction.get'},
        ]
        r = self.call_server(m)
        v = r.json()['result']

        if self.cache:
            self.cache.set(cache_key, v, 30 * 86300)

        return v

    def broadcast(self, tx_hash):
        m = [{
            'params': [tx_hash],
            'method': 'blockchain.transaction.get'
        }]
        r = self.call_server(m)
        return r.json()['result']


    def get_balance(self, address):
        prevout_values = {}
        h = self.get_history(address)
        if h == ['*']:
            return 0, 0
        c = u = 0
        received_coins = []   # list of coins received at address
        transactions = {}

        # fetch transactions
        for t in h:
            tx_hash = t['tx_hash']
            tx_height = t['height']

            transactions[(tx_hash, tx_height)] = self.get_transaction(tx_hash, tx_height)

        for t in h:
            tx_hash = t['tx_hash']
            tx_height = t['height']

            tx = Transaction(transactions[(tx_hash, tx_height)])

            if not tx:
                continue

            update_tx_outputs(tx, prevout_values)
            for i, (addr, value) in enumerate(tx.outputs):
                if addr == address:
                    key = tx_hash + ':%d' % i
                    received_coins.append(key)

        for t in h:
            tx_hash = t['tx_hash']
            tx_height = t['height']

            tx = Transaction(transactions[(tx_hash, tx_height)])

            if not tx:
                continue
            v = 0

            for item in tx.inputs:
                addr = item.get('address')
                if addr == address:
                    key = item['prevout_hash'] + ':%d' % item['prevout_n']
                    value = prevout_values.get(key)
                    if key in received_coins:
                        v -= value
            for i, (addr, value) in enumerate(tx.outputs):
                key = tx_hash + ':%d' % i
                if addr == address:
                    v += value
            if tx_height:
                c += v
            else:
                u += v
        return c, u


import random
from libs.pycoin import bitcoin
from libs.pycoin.bitcoin import is_valid, Transaction
import requests
import re
import json

SERVER = 'http://electrum.no-ip.org/'
FEE_PER_KB = 20000

class ElectrumClient(object):
    def __init__(self, server=None):
        self.message_id = 1
        self.server = server if server else SERVER
        self.session = self.get_session()

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
        r = requests.post(self.server, data=json.dumps(messages), headers=headers, cookies=cookies)
        #call again to get the response
        r = requests.post(self.server, data=json.dumps([]), headers=headers, cookies=cookies)
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
        return r.json['result']

    def get_transaction(self, transaction, height):
        #start session
        m = [
            {'params': [transaction, height], 'method': 'blockchain.transaction.get'},
        ]
        r = self.call_server(m)
        return r.json['result']

    def broadcast(self, tx_hash):
        m = [{
            'params': [tx_hash],
            'method': 'blockchain.transaction.get'
        }]
        r = self.call_server(m)
        return r.json['result']

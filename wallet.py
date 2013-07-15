__author__ = 'sserrano'


import random
from pycoin.bitcoin import Transaction, is_valid
from pycoin.electrum import ElectrumClient

FEE_PER_KB = 2000

def estimated_fee(inputs):
    estimated_size = len(inputs) * 180 + 80 # this assumes non-compressed keys
    fee = FEE_PER_KB * int(round(estimated_size/1024.))
    if fee == 0:
        fee = FEE_PER_KB
    return fee

class Wallet(object):
    def __init__(self, address, private_key):
        """

        :param address: bitcoin address
        """
        assert is_valid(address)
        self.client = ElectrumClient()
        self.address = address
        self.private_key = private_key
        self.history = None

    def update_history(self):
        self.history = self.client.get_history(self.address)

    def get_unspent_coins(self):

        if self.history is None:
            self.update_history()

        coins = []
        for tx in self.history:
            tx_hash, height = tx['tx_hash'], tx['height']
            tx_raw = self.client.get_transaction(tx['tx_hash'], tx['height'])
            tx = Transaction(tx_raw)

            for output in tx.d.get('outputs'):
                if output.get('address') != self.address: continue
                key = tx_hash + ":%d" % output.get('index')
                output['tx_hash'] = tx_hash
                coins.append(output)

        return coins


    def choose_tx_inputs(self, amount, fixed_fee = 0):
        """ todo: minimize tx size """
        total = 0
        fee = 0
        coins = []

        if self.history is None:
            self.update_history()

        coins = self.get_unspent_coins()
        inputs = []

        for item in coins:
            v = item.get('value')
            total += v
            inputs.append(item)
            fee = estimated_fee(inputs) if fixed_fee is None else fixed_fee
            if total >= amount + fee:
                break

        if total < (amount + fee):
            inputs = []

        return inputs, total, fee

    def add_tx_change(self, inputs, outputs, amount, fee, total, change_addr=None):
        "add change to a transaction"
        change_amount = total - ( amount + fee )
        if change_amount != 0:
            if not change_addr:
                change_addr = inputs[0].get('address')

            # Insert the change output at a random position in the outputs
            # why?
            # posn = random.randint(0, len(outputs))
            #outputs[posn:posn] = [( change_addr,  change_amount)]
            outputs.append(( change_addr,  change_amount))
        return outputs

    def make_transaction(self, outputs, fee=None, change_address=None, broadcast=False):
        """
        create a transaction
        :param outputs: tuples of (address, amount)
        :param fee:
        :param change_address:
        :argument
        """

        for address, x in outputs:
            assert is_valid(address)

        amount = sum( map(lambda x:x[1], outputs) )

        inputs, total, fee = self.choose_tx_inputs(amount, fee)
        if not inputs:
            raise ValueError("Not enough funds")

        outputs = self.add_tx_change(inputs, outputs, amount, fee, total, change_address)

        tx = Transaction.from_io(inputs, outputs)

        #tx.sign({self.address: self.private_key})

        # if broadcast:
        #     self.client.broadcast(tx.raw)

        return tx

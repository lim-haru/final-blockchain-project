from web3 import Web3
import os

import json, hashlib
from .models import Lot
from django.core import serializers

def sendTransaction(message):
    w3 = Web3(Web3.HTTPProvider(os.environ.get('WEB3_PROVIDER')))
    address = os.environ.get('ADDRESS')
    privateKey = os.environ.get('PRIVATE_KEY')

    nonce = w3.eth.get_transaction_count(address)
    gasPrice = w3.eth.gas_price
    value = w3.to_wei(0, 'ether')
    
    signedTx = w3.eth.account.sign_transaction(dict(
        nonce=nonce,
        gasPrice=gasPrice,
        gas=100000,
        to='0x0000000000000000000000000000000000000000',
        value=value,
        data=message.encode('utf-8')
    ), privateKey)
    
    tx = w3.eth.send_raw_transaction(signedTx.rawTransaction)
    txId = w3.to_hex(tx)
    return txId

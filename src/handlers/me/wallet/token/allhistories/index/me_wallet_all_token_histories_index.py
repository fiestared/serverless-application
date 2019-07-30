# -*- coding: utf-8 -*-
import settings
import os
import json
from private_chain_util import PrivateChainUtil
from user_util import UserUtil
from web3 import Web3, HTTPProvider
from lambda_base import LambdaBase

# from token_distributer_base.py
#from abc import *
#import os
#import boto3
#from web3 import Web3, HTTPProvider
#from lambda_base import LambdaBase
#from boto3.dynamodb.conditions import Key
#import copy
#from db_util import DBUtil

class MeWalletAllTokenHistoriesIndex(LambdaBase):

    def get_schema(self):
        pass

    def validate_params(self):
        UserUtil.verified_phone_and_email(self.event)

    web3 = None

    def exec_main_proc(self):
        self.web3 = Web3(HTTPProvider(os.environ['PRIVATE_CHAIN_OPERATION_URL']))
        address = self.web3.toChecksumAddress(os.environ['PRIVATE_CHAIN_ALIS_TOKEN_ADDRESS'])

        # lambda on VPCの要素が見当たらないが、、設定ファイルを見る必要があるか？
        # eoaの変数代入が必要、ユーザのprivate_eth_address
        eoa = self.__get_user_private_eth_address(self.params['user_id'])

        fromBlock = 1
        
        def padLeft(eoa):
            return '0x000000000000000000000000' + eoa[1:26]

        def removeLeft(eoa):
            return '0x' + eoa[1:26]

        def filterdata(transfer_result):
            for i in result.length:
                #このままではunixtimeが入ってしまうので、後ほどyyyy/mm/dd ttに変更する
                date = web3.eth.getBlock(web3.eth.getBlock(result[i].blockNumber).timestamp*1000)
                
                #print関数にしているが、S3にextractできるように将来調整が必要
                print('%s,%s,%s,%s,%s', date,result[i].transactionHash,removeLeft(result[i].topics[1]),
                    removeLeft(result[i].topics[2]), web3.fromWei(result[i].data, 'ether'))

        def getTransferHistory(address, fromBlock, eoa):
            fromfilter = web3.eth.filter({ address: address,
                            fromBlock: fromBlock,
                            toBlock: 'latest',
                            topics: [
                                web3.sha3('Transfer(address,address,uint256)'), padLeft(eoa)
                            ]
                        })

            tofilter = web3.eth.filter({ address: address,
                            fromBlock: fromBlock,
                            toBlock: 'latest',
                            topics: [
                                web3.sha3('Transfer(address,address,uint256)'),, padLeft(eoa)
                            ]
                        })

            # ステータスコードを確認して、失敗していたら例外を投げる処理を後々追加
            transfer_result_from = fromfilter.get
            filterdata(transfer_result_from)

            # ステータスコードを確認して、失敗していたら例外を投げる処理を後々追加
            transfer_result_to = tofilter.get
            filterdata(transfer_result_to)

        def __get_user_private_eth_address(self, user_id):
            # user_id に紐づく private_eth_address を取得
            user_info = UserUtil.get_cognito_user_info(self.cognito, user_id)
            private_eth_address = [a for a in user_info['UserAttributes'] if a.get('Name') == 'custom:private_eth_address']
            # private_eth_address が存在しないケースは想定していないため、取得出来ない場合は例外とする
            if len(private_eth_address) != 1:
                raise RecordNotFoundError('Record Not Found: private_eth_address')

            return private_eth_address[0]['Value']

        getTransferHistory(address, fromBlock, eoa)

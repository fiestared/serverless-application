# -*- coding: utf-8 -*-
import settings
import os
import json
import time
from datetime import datetime
from user_util import UserUtil
from web3 import Web3, HTTPProvider
from lambda_base import LambdaBase

class MeWalletAllTokenHistoriesIndex(LambdaBase):

    def get_schema(self):
        pass

    def validate_params(self):
        UserUtil.verified_phone_and_email(self.event)

    web3 = None

    def exec_main_proc(self):
        self.web3 = Web3(HTTPProvider(os.environ['PRIVATE_CHAIN_OPERATION_URL']))
        address = self.web3.toChecksumAddress(os.environ['PRIVATE_CHAIN_ALIS_TOKEN_ADDRESS'])
        user_id = self.event['requestContext']['authorizer']['claims']['cognito:username']
        eoa = self.__get_user_private_eth_address(user_id)
        
        def padLeft(eoa):
            return '0x000000000000000000000000' + eoa[2:]

        def removeLeft(eoa):
            return '0x' + eoa[26:]

        ### printではなく、S3に抽出できるように対応する
        ### ファイルを作成し、その中に出力結果を保持→そのファイルをS3へ書き込む手順で
        ### 特定のユーザのみがアクセス可能なS3のbacketを作成する
        def filter_transfer_data(transfer_result):
            for i in range(len(transfer_result)):
                print("%s,%s,%s,%s,%s"%(
                    datetime.fromtimestamp(self.web3.eth.getBlock(transfer_result[i]['blockNumber'])['timestamp']),
                    transfer_result[i]['transactionHash'].hex(),
                    removeLeft(transfer_result[i]['topics'][1].hex()),
                    removeLeft(transfer_result[i]['topics'][2].hex()),
                    self.web3.fromWei(int(transfer_result[i]['data'], 16), 'ether')
                    )   
                    )

        def filter_mint_data(mint_result):
            for i in range(len(mint_result)):
                print("%s,%s,%s,%s,%s"%(
                    datetime.fromtimestamp(self.web3.eth.getBlock(transfer_result[i]['blockNumber'])['timestamp']),
                    mint_result[i]['transactionHash'].hex(),
                    '---',
                    removeLeft(mint_result[i]['topics'][1].hex()),
                    self.web3.fromWei(int(mint_result[i]['data'], 16), 'ether')
                    )   
                    )

        def getTransferHistory(address, eoa):
            fromfilter = self.web3.eth.filter({
                "address": address,
                "fromBlock": 1,
                "toBlock": 'latest',
                "topics": [self.web3.sha3(text="Transfer(address,address,uint256)").hex(),
                           [padLeft(eoa)]
                ],
                })

            tofilter = self.web3.eth.filter({
                "address": address,
                "fromBlock": 1,
                "toBlock": 'latest',
                "topics": [self.web3.sha3(text="Transfer(address,address,uint256)").hex(),
                            # ここの１つ目の要素の任意指定のみ。公式ドキュメントではNone,nullとされているが、pythonだとsyntaxerrorになってしまう。
                            # jsではweb3.sha3('Transfer(address,address,uint256)'),, padLeft(eoa)と、空表記にしている
                            # 究極は、全部のデータを持ってきてtopicsのtoの部分がeoaと一致する数字が特定のものだけをtransfer_result_toに追加するとか？
#                            ['', padLeft(eoa)]
                ],
            })
            ### ステータスコードを確認して、失敗していたら例外を投げる処理を後々追加する
            transfer_result_from = fromfilter.get_all_entries()
            filter_transfer_data(transfer_result_from)

            transfer_result_to = tofilter.get_all_entries()
            filter_transfer_data(transfer_result_to)

        def getMintHistory(address, eoa):            
            to_filter = self.web3.eth.filter({
                "address": address,
                "fromBlock": 1,
                "toBlock": 'latest',
                "topics": [self.web3.sha3(text="Mint(address,uint256)").hex(),
                            [padLeft(eoa)]
                ],
            })

            ### ステータスコードを確認して、失敗していたら例外を投げる処理を後々追加する
            mint_result = to_filter.get_all_entries()
            filter_mint_data(mint_result)

        getTransferHistory(address, eoa)
        getMintHistory(address, eoa)

    def __get_user_private_eth_address(self, user_id):
        # user_id に紐づく private_eth_address を取得
        user_info = UserUtil.get_cognito_user_info(self.cognito, user_id)
        private_eth_address = [a for a in user_info['UserAttributes'] if a.get('Name') == 'custom:private_eth_address']
        # private_eth_address が存在しないケースは想定していないため、取得出来ない場合は例外とする
        if len(private_eth_address) != 1:
            raise RecordNotFoundError('Record Not Found: private_eth_address')

        return private_eth_address[0]['Value']

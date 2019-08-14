# -*- coding: utf-8 -*-
import settings
import os
import json
import time
import csv
import boto3
import hashlib
from datetime import datetime, timedelta, timezone
from time_util import TimeUtil
from user_util import UserUtil
from web3 import Web3, HTTPProvider
from lambda_base import LambdaBase

### TODO:全体的なCodingは他に合わせて修正
### TODO:例外処理を追加する→富樫さんに確認
### TODO:ユーザーのidentitypoolidをファイル名に挿入する
class MeWalletAllTokenHistoriesIndex(LambdaBase):

    def get_schema(self):
        pass

    def validate_params(self):
        UserUtil.verified_phone_and_email(self.event)

    web3 = None

    def __get_user_private_eth_address(self, user_id):
        # user_id に紐づく private_eth_address を取得
        user_info = UserUtil.get_cognito_user_info(self.cognito, user_id)
        private_eth_address = [a for a in user_info['UserAttributes'] if a.get('Name') == 'custom:private_eth_address']
        # private_eth_address が存在しないケースは想定していないため、取得出来ない場合は例外とする
        if len(private_eth_address) != 1:
            raise RecordNotFoundError('Record Not Found: private_eth_address')

        return private_eth_address[0]['Value']

    def __update_unread_notification_manager(self, user_id):
        unread_notification_manager_table = self.dynamodb.Table(os.environ['UNREAD_NOTIFICATION_MANAGER_TABLE_NAME'])

        unread_notification_manager_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression='set unread = :unread',
            ExpressionAttributeValues={':unread': True}
        )

    def __notification(self, user_id, announce_url):
        notification_table = self.dynamodb.Table(os.environ['NOTIFICATION_TABLE_NAME'])

        notification_table.put_item(Item={
            'notification_id': self.__get_randomhash(),
            'user_id': user_id,
            'sort_key': TimeUtil.generate_sort_key(),
            'type': settings.CSVDOWNLOAD_NOTIFICATION_TYPE,
            'created_at': int(time.time()),
            'announce_body': '全トークン履歴のcsvのダウンロード準備が完了しました。本通知をクリックしてダウンロードしてください。',
            'announce_url': announce_url
        })

        self.__update_unread_notification_manager(user_id)

    def __get_randomhash(self):
        return hashlib.sha256((str(time.time()) + str(os.urandom(16))).encode('utf-8')).hexdigest()

    def exec_main_proc(self):
        self.web3 = Web3(HTTPProvider(os.environ['PRIVATE_CHAIN_OPERATION_URL']))
        address = self.web3.toChecksumAddress(os.environ['PRIVATE_CHAIN_ALIS_TOKEN_ADDRESS'])
        user_id = self.event['requestContext']['authorizer']['claims']['cognito:username']
        eoa = self.__get_user_private_eth_address(user_id)

        tmp_csv_file = '/tmp/tmp_csv_file.csv'
        f = open(tmp_csv_file, 'a')
        writer = csv.writer(f)
        
        def padLeft(eoa):
            return '0x000000000000000000000000' + eoa[2:]

        def removeLeft(eoa):
            return '0x' + eoa[26:]

        def add_type(from_eoa, to_eoa):
            if from_eoa == eoa and to_eoa == '0x20326c2C26C5F5D314316131d815eb92940e761A':
                return 'withdraw'
            elif from_eoa == eoa and to_eoa != '0x0000000000000000000000000000000000000000':
                return 'give'
            elif from_eoa == eoa and to_eoa == '0x0000000000000000000000000000000000000000':
                return 'burn'
            elif from_eoa == '0x20326c2C26C5F5D314316131d815eb92940e761A' and to_eoa == eoa:
                return 'deposit'
            elif from_eoa == '---' and to_eoa == eoa:
                return 'get by like'            
            elif from_eoa != '0x20326c2C26C5F5D314316131d815eb92940e761A' and to_eoa == eoa:
                return 'get from user'
            else:
                return 'unknown'

        def filter_transfer_data(transfer_result):
            for i in range(len(transfer_result)):
                writer.writerow([
                    datetime.fromtimestamp(self.web3.eth.getBlock(transfer_result[i]['blockNumber'])['timestamp']),
                    transfer_result[i]['transactionHash'].hex(),
                    add_type(removeLeft(transfer_result[i]['topics'][1].hex()),removeLeft(transfer_result[i]['topics'][2].hex())),
                    self.web3.fromWei(int(transfer_result[i]['data'], 16), 'ether')
                ])

        def filter_mint_data(mint_result):
            for i in range(len(mint_result)):
                writer.writerow([
                    datetime.fromtimestamp(self.web3.eth.getBlock(mint_result[i]['blockNumber'])['timestamp']),
                    mint_result[i]['transactionHash'].hex(),
                    add_type('---', removeLeft(mint_result[i]['topics'][1].hex())),
                    self.web3.fromWei(int(mint_result[i]['data'], 16), 'ether')
                ])
            
        def getTransferHistory(address, eoa):
            fromfilter = self.web3.eth.filter({
                "address": address,
                "fromBlock": 1,
                "toBlock": 'latest',
                "topics": [self.web3.sha3(text="Transfer(address,address,uint256)").hex(),
                           padLeft(eoa)
                ],
                })

            tofilter = self.web3.eth.filter({
                "address": address,
                "fromBlock": 1,
                "toBlock": 'latest',
                "topics": [self.web3.sha3(text="Transfer(address,address,uint256)").hex(),
                            None,
                            padLeft(eoa)
                ],
            })
            
            ### ステータスコードを確認して、失敗していたら例外を投げる処理を後々追加する
            try:
                transfer_result_from = fromfilter.get_all_entries()
                filter_transfer_data(transfer_result_from)
                transfer_result_to = tofilter.get_all_entries()
                filter_transfer_data(transfer_result_to)    
            except ClientError as e:
                    logging.fatal(e)
                    return {
                        'statusCode': 500,
                        'body': json.dumps({'message': 'Internal server error'})
                    }

        def getMintHistory(address, eoa):            
            to_filter = self.web3.eth.filter({
                "address": address,
                "fromBlock": 1,
                "toBlock": 'latest',
                "topics": [self.web3.sha3(text="Mint(address,uint256)").hex(),
                            padLeft(eoa)
                ],
            })

            try:
                mint_result = to_filter.get_all_entries()
                filter_mint_data(mint_result)
            except ClientError as e:
                    logging.fatal(e)
                    return {
                        'statusCode': 500,
                        'body': json.dumps({'message': 'Internal server error'})
                    }

        def extract_file_to_s3():
            bucket = os.environ['ALL_TOKEN_HISTORY_CSV_DWONLOAD_S3_BUCKET']
            JST = timezone(timedelta(hours=+9), 'JST')
            ### TODO:keyの${cognito-identity.amazonaws.com:sub}は別途取得が必要
            key = 'private/ap-northeast-1:6eb2fb02-33b3-42de-8b9a-60d04afe3535/' + user_id + '_' + datetime.now(JST).strftime('%Y-%m-%d-%H-%M-%S') + '.csv'
            with open(tmp_csv_file, 'rb') as f:
                csv_file = f.read()
                res = upload_file(bucket, key, csv_file)
            
            announce_url = 'https://'+bucket+'.s3-ap-northeast-1.amazonaws.com/'+key
            return announce_url

        def upload_file(bucket, key, bytes):
            s3 = boto3.resource('s3')
            s3Obj = s3.Object(bucket, key)
            res = s3Obj.put(Body = bytes)
            return res

        getTransferHistory(address, eoa)
        getMintHistory(address, eoa)
        f.close()
        announce_url = extract_file_to_s3()

        self.__notification(user_id, announce_url)

        return {
            'statusCode': 200
        }

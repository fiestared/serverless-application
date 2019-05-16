import os
import boto3
import settings
import base64
from user_util import UserUtil
from crypto_util import CryptoUtil
from unittest import TestCase
from tests_util import TestsUtil
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

private_key_text = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEAxVGcUtXwqzv1F0XWBDMOUwcUTCqLofgVsiXrCSIrltU5BQQU
XOACdbECXiJUubP4l3KuIQCKeoGF283vU4POQGkF9dryJY2exo2lNvMiN62vcy3x
nBq8SWFweCNpFUzpZEpSCRMsjtOQN8SxNC/mXeIAmtiIAqWTXCaEtIMjc+S4EDTM
R2ff+zo+VclgxuxeXjUEZXeAHVkXWP2Ejpst+uPPa4njt07QLp1oMq9wR61kX8sL
Sqnk8AZ521IKumYR75tPdHoEf2uC14MGQ2tqD9GTjWWtjn1D88qUrcUREOoc/m0G
n3cX7NbIqMchOFIMdvh8B4wXMx8kfGF9GOmezwIDAQABAoIBAQCgbjNgsmvEfbJP
ostYjL53yUi6iNkQ7umM+AF6Ypr4PxLmPiPkQ4occLgRG26xsl9Lm8VyNcNhyY+x
YGXXDFKU0g8zjznUSKowm5gZ7mMCzCfbyR4pox81tpDATWIyHF+i2D6M/Fb9JYyb
m0PMv6lY6dk+DRHAvSjsArFhJ0KbBYorndjlXBwvZqfpDhG8f/jWgsgxyRhHve6o
Nd+FQk271bObh3NGc3aZNuGNeYAXoEqDkHt6i5Xs3buTZnzcBhgHz+fsuoZy2Yoo
Yz70cK4w6BQXRn3g3iILXliAiVX6f04fEg8f3ZgvyRh2a0paQDNHPMYxuIozq3Mv
Mmkqp9aJAoGBAP8gSn57utVv1s3Fmf9idxbZnM8T4q8oTeOES+dxd/kXVFAP+IF5
GPkJyPjCn29bo7dEii/IxZDmfP6WlLXRXyUzLRpOxv95Q+1YtMcDbHVOR0jc/LZH
TAyxCGHSklg3pGowo6ZAnKNnKz5pi1bAH5bDWQMYNWS4aoDMaGF3ekWTAoGBAMX+
oYK6ntY/I6kQViXUgbTkPJX6w+dE98zx5ZzPfYr7dcmKZUpT0RaLLfJDbggdEHu5
I4u+0MvbDT+Xznon7QYzF/JapVrty+5nsdx+Qd46+oMJpK7td1ENjaT6vBS0NwSn
YTeU+I8aUfsahlEvkSkgtJ58+OgubvF+3+Dm4IdVAoGBANE1u6DI+cb49V68QbJp
HltAjBRLrEISfPyrikr6g3ViKiOVVSVnFpFx8rn7bx60OSaaL+9LZqeSOsHS3ZPT
Y4Bv3PaLzyfEW22Qpn3kUtZHILGhdiJLiROHQOZm9Ncemdbyl+BHb6uXeKCvkDHN
TpolCyM8gNxdVgjUlmwGu9+9AoGAYqIew4lEZ2a81RQWVnIuy3aH2A88WJG7AJXg
1OVonTv3yZbwLr7igmCDWxTMU65m77ujQZKlYWiWiP+PFLufEF+TpmARz+J2nSV7
LWSYW6T19yFusNYLgo1F6tIdsBK29dKMU6waxu9Nt9HW58rSfbKVR/7p4ICBND0I
OnnJkKECgYEApYJFS8l+A+OpJIOvPeP0vqK/wIdwWjfgINaMv42fAkieGjC2+m3X
S44k6XXRMKucbx48XwzT0sWoG7BQL7QkDL+KuHAyCD4HdIvCgG2hlryH4hEX97Xj
OM7gH4lOBPAz3Xp5dS6jnKQT1OxPtYdn6VsN2yashViWkehB1AkTJjU=
-----END RSA PRIVATE KEY-----
"""

public_key_text = """-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAxVGcUtXwqzv1F0XWBDMOUwcUTCqLofgVsiXrCSIrltU5BQQUXOAC
dbECXiJUubP4l3KuIQCKeoGF283vU4POQGkF9dryJY2exo2lNvMiN62vcy3xnBq8
SWFweCNpFUzpZEpSCRMsjtOQN8SxNC/mXeIAmtiIAqWTXCaEtIMjc+S4EDTMR2ff
+zo+VclgxuxeXjUEZXeAHVkXWP2Ejpst+uPPa4njt07QLp1oMq9wR61kX8sLSqnk
8AZ521IKumYR75tPdHoEf2uC14MGQ2tqD9GTjWWtjn1D88qUrcUREOoc/m0Gn3cX
7NbIqMchOFIMdvh8B4wXMx8kfGF9GOmezwIDAQAB
-----END RSA PUBLIC KEY-----
"""


class TestCryptoUtil(TestCase):
    def setUp(self):
        self.cognito = boto3.client('cognito-idp')
        self.dynamodb = TestsUtil.get_dynamodb_client()
        os.environ['COGNITO_USER_POOL_ID'] = 'cognito_user_pool'
        os.environ['LOGIN_SALT'] = '4YGjw4llWxC46bNluUYu1bhaWQgfJjB4'
        TestsUtil.set_all_tables_name_to_env()
        TestsUtil.delete_all_tables(self.dynamodb)

        self.external_provider_users_table_items = [
            {
                'external_provider_user_id': 'external_provider_user_id'
            }
        ]
        TestsUtil.create_table(
            self.dynamodb,
            os.environ['EXTERNAL_PROVIDER_USERS_TABLE_NAME'],
            self.external_provider_users_table_items
        )
        TestsUtil.create_table(self.dynamodb, os.environ['USERS_TABLE_NAME'], [])

    def test_get_external_provider_password_ok(self):
        aes_iv = os.urandom(settings.AES_IV_BYTES)
        encrypted_password = CryptoUtil.encrypt_password('nNU8E9E6OSe9tRQn', aes_iv)
        iv = base64.b64encode(aes_iv).decode()

        UserUtil.add_external_provider_user_info(
            dynamodb=self.dynamodb,
            external_provider_user_id='user_id',
            password=encrypted_password,
            iv=iv,
            email='email'
        )

        password = CryptoUtil.get_external_provider_password(
            self.dynamodb,
            'user_id'
        )
        self.assertEqual(password, 'nNU8E9E6OSe9tRQn')

    def test_rsa_decrypt_ok(self):
        origin_text = "abcdef"
        # 暗号化
        public_key = RSA.importKey(public_key_text)
        encrypted_data = PKCS1_OAEP.new(public_key).encrypt(origin_text)

        # 復号化
        decrypted_data = CryptoUtil.rsa_decrypt(encrypted_data, private_key_text)
        self.assertEqual(decrypted_data.decode(), origin_text)

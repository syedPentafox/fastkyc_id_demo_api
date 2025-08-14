import os
import logging
import json
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AESUtil:
    def __init__(self):
        self.AES_SECRET_KEY = os.getenv("AES_SECRET_KEY")
        self.AD_PASSWORD_SECRET_KEY = os.getenv("KVB_KEY_VALUE")
        self.AD_OTP_SECRET_KEY = os.getenv("AD_OTP_SECRET_KEY")

    def aes_encrypt(self, key, plaintext):
        self.key = key.ljust(32)[:32].encode()
        cipher = AES.new(self.key, AES.MODE_ECB)
        ciphertext = cipher.encrypt(
            pad(plaintext.encode(), AES.block_size, style="pkcs7")
        )
        return base64.b64encode(ciphertext).decode()

    def aes_decrypt(self, key, ciphertext):
        self.key = key.ljust(32)[:32].encode()
        cipher = AES.new(self.key, AES.MODE_ECB)
        decrypted = unpad(
            cipher.decrypt(base64.b64decode(ciphertext)), AES.block_size, style="pkcs7"
        )
        return decrypted.decode()

    def decrypt_password_payload(self, ciphertext):
        return json.loads(self.aes_decrypt(self.AES_SECRET_KEY, ciphertext))

    def s(self, ciphertext):
        return json.loads(self.aes_encrypt(self.AES_SECRET_KEY, ciphertext))

    def encrypt_password_payload(self, ciphertext):
        return self.aes_encrypt(self.AES_SECRET_KEY, ciphertext)

    def encrypt_ad_password_payload(self, plaintext):
        return self.aes_encrypt(self.AD_PASSWORD_SECRET_KEY, plaintext)

    def decrypt_ad_password_payload(self, ciphertext):
        logger.info(f">>>>>>>>>>>>{ciphertext}")
        logger.info(f">>>>>>>>>>>>>>>>{self.aes_decrypt(self.AD_PASSWORD_SECRET_KEY, ciphertext)}")
        logger.info(f">>>>>>>>>>>>>>>>{type(self.aes_decrypt(self.AD_PASSWORD_SECRET_KEY, ciphertext))}")
        decrypted_str=self.aes_decrypt(self.AD_PASSWORD_SECRET_KEY, ciphertext)
        logger.info(">>>>>>>>>>>>>>>> ds {decrypted_str}")
        replaced_str= decrypted_str.replace('\\"','"')
        logger.info(f">>>>>>>>>>>>>>>>>>>>>>>cleaned str {replaced_str}")
        logger.info(f">>>>>>>>>>>>>>>>>>>>>string type {type(replaced_str)}")
        return json.loads(replaced_str)
        #return json.loads(self.aes_decrypt(self.AD_PASSWORD_SECRET_KEY, ciphertext))

    def encrypt_ad_otp_payload(self, plaintext):
        return self.aes_encrypt(self.AD_OTP_SECRET_KEY, plaintext)

    def decrypt_ad_otp_payload(self, ciphertext):
        return json.loads(self.aes_decrypt(self.AD_OTP_SECRET_KEY, ciphertext))

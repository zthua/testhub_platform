#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UberEncrypt - 高级加密工具
Python 3.11 Compatible Version

使用RSA + AES-CTR + HMAC-SHA256的组合加密方案
"""

import base64
import os
from typing import Union, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.hmac import HMAC
from cryptography.hazmat.backends import default_backend

# To generate a 2048-bit RSA keypair:
# openssl genrsa -des3 -out private.pem 2048
# openssl rsa -in private.pem -outform DER -out private.der
# openssl rsa -in private.pem -pubout -outform DER -out public.der

DEBUG = False  # True or False


class UberEncrypt:
    """
    高级加密类
    
    使用RSA加密AES密钥和HMAC密钥，使用AES-CTR模式加密数据，并用HMAC-SHA256签名
    """

    COUNTER_SIZE_BITS = 64
    VERSION_STRING = ""

    def __init__(self, key: Union[str, bytes]):
        """
        初始化加密器
        
        Args:
            key: RSA公钥文件路径或Base64编码的公钥
        """
        self.rsa_pub_key_path = key

    def encrypt(self, data: Union[str, bytes], version: str = '') -> bytes:
        """
        加密数据
        
        Args:
            data: 待加密的数据
            version: 版本字符串（可选）
            
        Returns:
            Base64编码的加密负载
        """
        # 生成随机nonce
        nonce = self._gen_nonce()

        if DEBUG:
            print("IV (nonce):")
            print(f"Length: {len(nonce)} bytes")
            print(f"Hex: {nonce.hex()}")
            print()

        if version != '':
            self.VERSION_STRING = version

        # 生成AES密钥和HMAC密钥
        aes_key = self._gen_key()
        hmac_key = self._gen_key()

        # 使用RSA加密密钥
        enc_aes_key = self._rsa_encrypt(self.rsa_pub_key_path, aes_key)
        enc_hmac_key = self._rsa_encrypt(self.rsa_pub_key_path, hmac_key)

        # 使用AES-CTR加密数据
        ciphertext = self._aes_encrypt(
            aes_key, nonce, data, counter_size_bits=self.COUNTER_SIZE_BITS
        )

        # 创建消息并生成签名
        message = self._create_message(nonce, ciphertext)
        signature = self._gen_signature(hmac_key, message)

        # 打包最终负载
        payload = self._wrap(
            self.VERSION_STRING, enc_hmac_key, enc_aes_key, 
            nonce, ciphertext, signature
        )

        return payload

    def _create_message(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """
        创建待签名的消息
        
        Args:
            nonce: 随机nonce
            ciphertext: 加密后的密文
            
        Returns:
            消息字节
        """
        b64_nonce = base64.b64encode(nonce)
        b64_ciphertext = base64.b64encode(ciphertext)
        message = b64_nonce + b'$' + b64_ciphertext
        return message

    def _gen_nonce(self) -> bytes:
        """
        生成随机nonce
        
        Returns:
            随机字节
        """
        return os.urandom(self.COUNTER_SIZE_BITS // 8)

    def _gen_key(self, keylength_bits: int = 256) -> bytes:
        """
        生成随机密钥
        
        Args:
            keylength_bits: 密钥长度（位）
            
        Returns:
            随机密钥字节
        """
        return os.urandom(keylength_bits // 8)

    def _load_rsa_key(self, key: Union[str, bytes]) -> rsa.RSAPublicKey:
        """
        加载RSA公钥
        
        Args:
            key: 公钥文件路径或Base64编码的公钥
            
        Returns:
            RSA公钥对象
        """
        # 如果是文件路径
        if isinstance(key, str) and os.path.exists(key):
            with open(key, 'rb') as f:
                key_data = f.read()
        elif isinstance(key, bytes):
            key_data = key
        else:
            # 假设是Base64编码的字符串
            key_data = base64.b64decode(key)

        return serialization.load_pem_public_key(
            key_data,
            backend=default_backend()
        )

    def _rsa_encrypt(self, rsa_pub_key: Union[str, bytes], data: bytes) -> bytes:
        """
        RSA加密
        
        Args:
            rsa_pub_key: RSA公钥（文件路径或Base64编码）
            data: 待加密数据
            
        Returns:
            加密后的数据
        """
        public_key = self._load_rsa_key(rsa_pub_key)

        cipher = public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return cipher

    def _aes_encrypt(self, aes_key: bytes, init_value: bytes, 
                     original_data: Union[str, bytes], 
                     counter_size_bits: int = 64) -> bytes:
        """
        AES-CTR模式加密
        
        Args:
            aes_key: AES密钥
            init_value: 初始化值（nonce）
            original_data: 原始数据
            counter_size_bits: 计数器大小（位）
            
        Returns:
            加密后的数据
        """
        if isinstance(original_data, str):
            original_data = original_data.encode('utf-8')

        if DEBUG:
            print("AES key:")
            print(f"Length: {len(aes_key)} bytes")
            print(f"Hex: {aes_key.hex()}")
            print()

        # 创建CTR模式的AES加密器
        # 由于cryptography不直接支持CTR模式，我们需要手动实现
        # 使用ECB模式 + 计数器实现CTR
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.ECB(),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # 将数据分成块并加密
        block_size = 16  # AES块大小
        counter = int.from_bytes(init_value, byteorder='big')
        ciphertext = b''

        for i in range(0, len(original_data), block_size):
            # 生成计数器块
            counter_bytes = counter.to_bytes(block_size, byteorder='big')
            
            # 加密计数器块
            keystream_block = encryptor.update(counter_bytes)
            
            # XOR加密
            plaintext_block = original_data[i:i+block_size]
            # 如果最后一个块不足16字节，只加密对应部分
            ciphertext_block = bytes(
                a ^ b for a, b in zip(keystream_block, plaintext_block)
            )
            ciphertext += ciphertext_block
            
            counter += 1

        # 完成加密
        encryptor.finalize()

        return ciphertext

    def _gen_signature(self, secret: bytes, message: bytes) -> bytes:
        """
        生成HMAC-SHA256签名
        
        Args:
            secret: 密钥
            message: 待签名的消息
            
        Returns:
            HMAC-SHA256签名
        """
        hmac_obj = HMAC(secret, hashes.SHA256(), backend=default_backend())
        hmac_obj.update(message)
        digest = hmac_obj.finalize()

        if DEBUG:
            print("HMAC-SHA256 secret:")
            print(f"Length: {len(secret)} bytes")
            print(f"Hex: {secret.hex()}")
            print()

            print("HMAC-SHA256 digest:")
            print(f"Length: {len(digest)} bytes")
            print(f"Hex: {digest.hex()}")
            print()

        return digest

    def _wrap(self, version: str, ciphertext_hmac: bytes, 
              ciphertext_key: bytes, nonce: bytes, 
              ciphertext: bytes, signature: bytes) -> bytes:
        """
        打包最终负载
        
        Args:
            version: 版本字符串
            ciphertext_hmac: 加密的HMAC密钥
            ciphertext_key: 加密的AES密钥
            nonce: 随机nonce
            ciphertext: 加密的数据
            signature: HMAC签名
            
        Returns:
            Base64编码的最终负载
        """
        b64_ciphertext_hmac = base64.b64encode(ciphertext_hmac)
        b64_ciphertext_key = base64.b64encode(ciphertext_key)
        b64_nonce = base64.b64encode(nonce)
        b64_ciphertext = base64.b64encode(ciphertext)
        b64_signature = base64.b64encode(signature)

        if version != '':
            return b'$'.join([
                version.encode('utf-8'),
                b64_ciphertext_hmac,
                b64_ciphertext_key,
                b64_nonce,
                b64_ciphertext,
                b64_signature
            ]).decode('utf-8')
        else:
            return b'$'.join([
                b64_ciphertext_hmac,
                b64_ciphertext_key,
                b64_nonce,
                b64_ciphertext,
                b64_signature
            ]).decode('utf-8')


class UberDecrypt:
    """
    高级解密类
    
    与UberEncrypt对应的解密工具
    """

    def __init__(self, key: Union[str, bytes]):
        """
        初始化解密器
        
        Args:
            key: RSA私钥文件路径或Base64编码的私钥
        """
        self.rsa_priv_key_path = key

    def _load_rsa_key(self, key: Union[str, bytes]) -> rsa.RSAPrivateKey:
        """
        加载RSA私钥
        
        Args:
            key: 私钥文件路径或Base64编码的私钥
            
        Returns:
            RSA私钥对象
        """
        # 如果是文件路径
        if isinstance(key, str) and os.path.exists(key):
            with open(key, 'rb') as f:
                key_data = f.read()
        elif isinstance(key, bytes):
            key_data = key
        else:
            # 假设是Base64编码的字符串
            key_data = base64.b64decode(key)

        return serialization.load_pem_private_key(
            key_data,
            password=None,
            backend=default_backend()
        )

    def _rsa_decrypt(self, rsa_priv_key: Union[str, bytes], data: bytes) -> bytes:
        """
        RSA解密
        
        Args:
            rsa_priv_key: RSA私钥（文件路径或Base64编码）
            data: 加密数据
            
        Returns:
            解密后的数据
        """
        private_key = self._load_rsa_key(rsa_priv_key)

        plaintext = private_key.decrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return plaintext

    def _aes_decrypt(self, aes_key: bytes, init_value: bytes, 
                     ciphertext: bytes, counter_size_bits: int = 64) -> bytes:
        """
        AES-CTR模式解密
        
        Args:
            aes_key: AES密钥
            init_value: 初始化值（nonce）
            ciphertext: 加密数据
            counter_size_bits: 计数器大小（位）
            
        Returns:
            解密后的数据
        """
        # 创建CTR模式的AES解密器
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.ECB(),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # 将数据分成块并解密
        block_size = 16
        counter = int.from_bytes(init_value, byteorder='big')
        plaintext = b''

        for i in range(0, len(ciphertext), block_size):
            # 生成计数器块
            counter_bytes = counter.to_bytes(block_size, byteorder='big')
            
            # 加密计数器块
            keystream_block = encryptor.update(counter_bytes)
            
            # XOR解密
            ciphertext_block = ciphertext[i:i+block_size]
            plaintext_block = bytes(
                a ^ b for a, b in zip(keystream_block, ciphertext_block)
            )
            plaintext += plaintext_block
            
            counter += 1

        encryptor.finalize()

        return plaintext

    def _verify_signature(self, secret: bytes, message: bytes, 
                         signature: bytes) -> bool:
        """
        验证HMAC-SHA256签名
        
        Args:
            secret: 密钥
            message: 消息
            signature: 签名
            
        Returns:
            验证结果
        """
        hmac_obj = HMAC(secret, hashes.SHA256(), backend=default_backend())
        hmac_obj.update(message)
        
        try:
            hmac_obj.verify(signature)
            return True
        except Exception:
            return False

    def decrypt(self, payload: str) -> str:
        """
        解密数据
        
        Args:
            payload: Base64编码的加密负载
            
        Returns:
            解密后的原始数据
        """
        # 解包负载
        parts = payload.split('$')
        
        if len(parts) == 6:
            # 带版本号
            version, enc_hmac_key, enc_aes_key, nonce, ciphertext, signature = parts
        elif len(parts) == 5:
            # 无版本号
            enc_hmac_key, enc_aes_key, nonce, ciphertext, signature = parts
            version = ''
        else:
            raise ValueError("Invalid payload format")

        # 解密密钥
        hmac_key = self._rsa_decrypt(self.rsa_priv_key_path, 
                                      base64.b64decode(enc_hmac_key))
        aes_key = self._rsa_decrypt(self.rsa_priv_key_path, 
                                    base64.b64decode(enc_aes_key))

        # 创建消息并验证签名
        nonce_bytes = base64.b64decode(nonce)
        ciphertext_bytes = base64.b64decode(ciphertext)
        message = self._create_message(nonce_bytes, ciphertext_bytes)
        signature_bytes = base64.b64decode(signature)

        if not self._verify_signature(hmac_key, message, signature_bytes):
            raise ValueError("Signature verification failed")

        # 解密数据
        plaintext = self._aes_decrypt(aes_key, nonce_bytes, ciphertext_bytes)

        return plaintext.decode('utf-8')

    def _create_message(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """
        创建待签名的消息
        
        Args:
            nonce: 随机nonce
            ciphertext: 加密后的密文
            
        Returns:
            消息字节
        """
        b64_nonce = base64.b64encode(nonce)
        b64_ciphertext = base64.b64encode(ciphertext)
        message = b64_nonce + b'$' + b64_ciphertext
        return message


def main():
    """
    测试主函数
    """
    # 原始数据
    original_data = '12345611ss'
    print(f"Original data: {original_data}")
    print()

    # 加密（需要有效的公钥文件）
    try:
        crypter = UberEncrypt('F:/llpay_public_key.pem')
        payload = crypter.encrypt(original_data)

        if DEBUG:
            print("Payload:")
            print(payload)
            print()

        with open("payload.txt", "w", encoding='utf-8') as output_file:
            output_file.write(payload)
        print("Payload written to payload.txt.")
        
        # 解密（需要对应的私钥文件）
        decrypter = UberDecrypt('F:/llpay_private_key.pem')
        decrypted = decrypter.decrypt(payload)
        print(f"Decrypted data: {decrypted}")
        print("Decryption successful!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure you have valid RSA key files.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

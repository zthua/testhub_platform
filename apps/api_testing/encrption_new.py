#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import base64
import hmac
import hashlib
import re
from typing import Union, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class Encryption:
    """
    加密相关类
    """

    def _load_rsa_key(self, key: Union[str, bytes], is_private: bool = False) -> rsa.RSAPublicKey | rsa.RSAPrivateKey:
        """
        加载RSA密钥
        支持 PEM 格式和纯 Base64 编码格式

        Args:
            key: 密钥内容或文件路径
            is_private: 是否为私钥

        Returns:
            RSA密钥对象
        """
        # 如果是文件路径
        if isinstance(key, str) and os.path.exists(key):
            with open(key, 'rb') as f:
                key_data = f.read()
        elif isinstance(key, bytes):
            key_data = key
        else:
            # 字符串形式，可能是 PEM 格式或纯 Base64 编码
            key_str = key.strip()

            # 检查是否已经是 PEM 格式（包含 BEGIN/END 标记）
            if key_str.startswith('-----BEGIN'):
                key_data = key_str.encode('utf-8')
            else:
                # 尝试 Base64 解码
                try:
                    # 如果是纯 Base64 编码，直接解码
                    key_data = base64.b64decode(key_str)
                except Exception:
                    # Base64 解码失败，尝试添加 PEM 头尾
                    if is_private:
                        pem_key = f"-----BEGIN PRIVATE KEY-----\n{key_str}\n-----END PRIVATE KEY-----"
                    else:
                        pem_key = f"-----BEGIN PUBLIC KEY-----\n{key_str}\n-----END PUBLIC KEY-----"
                    key_data = pem_key.encode('utf-8')

        if is_private:
            return serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend()
            )
        else:
            return serialization.load_pem_public_key(
                key_data,
                backend=default_backend()
            )

    def rsa_encrypt(self, key: Union[str, bytes], data: Union[str, bytes], 
                    pkcs_type: str = 'PKCS1_v1_5') -> bytes:
        """
        RSA加密
        
        Args:
            key: 公钥文件路径或Base64编码的公钥
            data: 需要加密的数据
            pkcs_type: 支持PKCS1_v1_5、PKCS1_OAEP，默认PKCS1_v1_5
            
        Returns:
            Base64编码的密文
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        public_key = self._load_rsa_key(key, is_private=False)

        if pkcs_type == 'PKCS1_v1_5':
            ciphertext = public_key.encrypt(
                data,
                padding.PKCS1v15()
            )
        elif pkcs_type == 'PKCS1_OAEP':
            ciphertext = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        else:
            raise ValueError(f"不支持的PKCS类型: {pkcs_type}")

        return base64.b64encode(ciphertext)

    def rsa_decrypt(self, key: Union[str, bytes], ciphertext: Union[str, bytes], 
                    pkcs_type: str = 'PKCS1_v1_5') -> bytes:
        """
        RSA解密
        
        Args:
            key: 私钥文件路径或Base64编码的私钥
            ciphertext: 密文
            pkcs_type: 支持PKCS1_v1_5、PKCS1_OAEP，默认PKCS1_v1_5
            
        Returns:
            解密后的明文
        """
        if isinstance(ciphertext, str):
            ciphertext = ciphertext.encode('utf-8')
        ciphertext = base64.b64decode(ciphertext)

        private_key = self._load_rsa_key(key, is_private=True)

        if pkcs_type == 'PKCS1_v1_5':
            plaintext = private_key.decrypt(
                ciphertext,
                padding.PKCS1v15()
            )
        elif pkcs_type == 'PKCS1_OAEP':
            plaintext = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        else:
            raise ValueError(f"不支持的PKCS类型: {pkcs_type}")

        return plaintext

    def rsa_long_encrypt(self, pub_key: Union[str, bytes], msg: Union[str, bytes], 
                         length: int = 117) -> bytes:
        """
        RSA长数据加密
        
        单次加密串的长度最大为 (key_size/8)-11
        例如1024 bit的证书，被加密的串最长 1024/8 - 11=117
        
        Args:
            pub_key: 公钥文件路径或Base64编码的公钥
            msg: 需要加密的消息
            length: 每次加密的最大长度
            
        Returns:
            加密后的数据
        """
        length = int(length)
        
        if isinstance(msg, str):
            msg = msg.encode('utf-8')
        
        public_key = self._load_rsa_key(pub_key, is_private=False)
        msg_len = len(msg)
        res = []
        
        for i in range(0, msg_len, length):
            chunk = msg[i:i+length]
            ciphertext = public_key.encrypt(
                chunk,
                padding.PKCS1v15()
            )
            res.append(base64.b64encode(ciphertext))
        
        return b"".join(res)

    def rsa_long_decrypt(self, priv_key: Union[str, bytes], msg: bytes, 
                        length: int = 128) -> bytes:
        """
        RSA长数据解密
        
        1024bit的证书用128，2048bit证书用256位
        
        Args:
            priv_key: 私钥文件路径或Base64编码的私钥
            msg: 加密后的数据
            length: 每次解密的长度
            
        Returns:
            解密后的数据
        """
        if isinstance(msg, str):
            msg = msg.encode('utf-8')
        
        private_key = self._load_rsa_key(priv_key, is_private=True)
        msg_len = len(msg)
        res = []
        
        for i in range(0, msg_len, length):
            chunk = msg[i:i+length]
            plaintext = private_key.decrypt(
                base64.b64decode(chunk),
                padding.PKCS1v15()
            )
            res.append(plaintext)
        
        return b"".join(res)

    def sign_md5(self, payload: Union[str, bytes]) -> str:
        """
        对传入的字符串进行MD5加密
        
        Args:
            payload: 待加密的数据
            
        Returns:
            MD5哈希值（十六进制字符串）
        """
        if payload:
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            m1 = hashlib.md5()
            m1.update(payload)
            return m1.hexdigest()
        else:
            return ''

    def sign_hmacsha256(self, key: Union[str, bytes], payload: Union[str, bytes]) -> str:
        """
        HMAC-SHA256加密
        
        Args:
            key: 密钥
            payload: 待加密的数据
            
        Returns:
            HMAC-SHA256哈希值（十六进制字符串）
        """
        if isinstance(key, str):
            key = key.encode('utf-8')
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def sign_rsa(self, privkey: Union[str, bytes], signdata: Union[str, bytes], 
                hash_type: str = 'sha256', encode_type: str = 'base64') -> bytes:
        """
        RSA签名
        
        Args:
            privkey: 私钥（文件路径或Base64编码的字符串）
            signdata: 需要签名的字符串
            hash_type: 哈希类型，支持sha1、sha256、sha512、md5
            encode_type: 编码类型，base64或hex
            
        Returns:
            签名后的数据
        """
        if isinstance(signdata, str):
            signdata = signdata.encode('utf-8')

        private_key = self._load_rsa_key(privkey, is_private=True)

        # 选择哈希算法
        hash_map = {
            'sha1': hashes.SHA1(),
            'sha256': hashes.SHA256(),
            'sha512': hashes.SHA512(),
            'md5': hashes.MD5()
        }
        
        hash_algo = hash_map.get(hash_type.lower(), hashes.SHA256())

        # 预哈希
        if hash_type.lower() == 'md5':
            prehashed = signdata
        else:
            digest = hashlib.new(hash_type.lower())
            digest.update(signdata)
            prehashed = digest.digest()

        # 使用PKCS1v15填充方案签名
        if hash_type.lower() == 'md5':
            # MD5withRSA使用PKCS1v15
            signature = private_key.sign(
                prehashed,
                padding.PKCS1v15(),
                hashes.MD5()
            )
        else:
            signature = private_key.sign(
                signdata,
                padding.PKCS1v15(),
                hash_algo
            )

        if encode_type == 'base64':
            return base64.b64encode(signature)
        elif encode_type == 'hex':
            return signature.hex().encode('utf-8')
        else:
            return signature

    def verify_rsa(self, pubkey: Union[str, bytes], data: Union[str, bytes], 
                   signature: Union[str, bytes], hash_type: str = 'sha256') -> bool:
        """
        RSA验签
        
        Args:
            pubkey: 公钥（文件路径或Base64编码的字符串）
            data: 待签名数据
            signature: 签名
            hash_type: 哈希类型，支持sha1、sha256、sha512、md5
            
        Returns:
            验签结果，True表示验签通过，False表示失败
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        if isinstance(signature, str):
            signature = base64.b64decode(signature)
        elif isinstance(signature, bytes) and signature.startswith(b'-----'):
            # 如果签名已经是PEM格式，先解码
            signature = base64.b64decode(signature)
        else:
            signature = base64.b64decode(signature)

        public_key = self._load_rsa_key(pubkey, is_private=False)

        hash_map = {
            'sha1': hashes.SHA1(),
            'sha256': hashes.SHA256(),
            'sha512': hashes.SHA512(),
            'md5': hashes.MD5()
        }
        
        hash_algo = hash_map.get(hash_type.lower(), hashes.SHA256())

        try:
            if hash_type.lower() == 'md5':
                public_key.verify(
                    signature,
                    data,
                    padding.PKCS1v15(),
                    hashes.MD5()
                )
            else:
                public_key.verify(
                    signature,
                    data,
                    padding.PKCS1v15(),
                    hash_algo
                )
            return True
        except Exception:
            return False

    def encrypt_aes(self, plaintext: Union[str, bytes], key: Union[str, bytes], 
                    iv: Optional[Union[str, bytes]] = None, mode: str = 'CBC') -> bytes:
        """
        AES加密
        
        Args:
            plaintext: 明文
            key: 密钥（16、24或32字节）
            iv: 初始化向量（CBC模式需要）
            mode: 加密模式，支持CBC、ECB
            
        Returns:
            Base64编码的密文
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        if isinstance(key, str):
            key = key.encode('utf-8')
        
        # PKCS7填充
        padding_length = 16 - (len(plaintext) % 16)
        padded_data = plaintext + bytes([padding_length] * padding_length)

        if mode == 'CBC':
            if iv is None:
                iv = key[:16]  # 默认使用密钥前16字节作为IV
            if isinstance(iv, str):
                iv = iv.encode('utf-8')
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
        elif mode == 'ECB':
            cipher = Cipher(
                algorithms.AES(key),
                modes.ECB(),
                backend=default_backend()
            )
        else:
            raise ValueError(f"不支持的AES模式: {mode}")

        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return base64.b64encode(ciphertext)

    def decrypt_aes(self, ciphertext: Union[str, bytes], key: Union[str, bytes], 
                    iv: Optional[Union[str, bytes]] = None, mode: str = 'CBC') -> bytes:
        """
        AES解密
        
        Args:
            ciphertext: 密文（Base64编码）
            key: 密钥（16、24或32字节）
            iv: 初始化向量（CBC模式需要）
            mode: 加密模式，支持CBC、ECB
            
        Returns:
            解密后的明文
        """
        if isinstance(ciphertext, str):
            ciphertext = base64.b64decode(ciphertext)
        else:
            ciphertext = base64.b64decode(ciphertext)
        
        if isinstance(key, str):
            key = key.encode('utf-8')
        
        if mode == 'CBC':
            if iv is None:
                iv = key[:16]
            if isinstance(iv, str):
                iv = iv.encode('utf-8')
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
        elif mode == 'ECB':
            cipher = Cipher(
                algorithms.AES(key),
                modes.ECB(),
                backend=default_backend()
            )
        else:
            raise ValueError(f"不支持的AES模式: {mode}")

        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # 去除PKCS7填充
        padding_length = padded_plaintext[-1]
        plaintext = padded_plaintext[:-padding_length]
        
        return plaintext

    def sign_hmac(self, key: Union[str, bytes], payload: Union[str, bytes], 
                  hash_algorithm: str = 'sha256') -> str:
        """
        HMAC签名
        
        Args:
            key: 密钥
            payload: 待签名的数据
            hash_algorithm: 哈希算法，支持md5、sha1、sha256、sha512
            
        Returns:
            HMAC哈希值（十六进制字符串）
        """
        hash_map = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512
        }
        
        hash_func = hash_map.get(hash_algorithm.lower(), hashlib.sha256)
        
        if isinstance(key, str):
            key = key.encode('utf-8')
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        
        return hmac.new(key, payload, hash_func).hexdigest()

    def sign_sha1(self, payload: Union[str, bytes]) -> str:
        """
        SHA1签名
        
        Args:
            payload: 待签名的数据
            
        Returns:
            SHA1哈希值（十六进制字符串）
        """
        if payload:
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            sha1 = hashlib.sha1()
            sha1.update(payload)
            return sha1.hexdigest()
        else:
            return ''

    def sign_sha256(self, payload: Union[str, bytes]) -> str:
        """
        SHA256签名
        
        Args:
            payload: 待签名的数据
            
        Returns:
            SHA256哈希值（十六进制字符串）
        """
        if payload:
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            sha256 = hashlib.sha256()
            sha256.update(payload)
            return sha256.hexdigest()
        else:
            return ''

    def encrypt_file(self, source_file: str, target_file: str, pub_key: Union[str, bytes]) -> None:
        """
        RSA对文件内容进行加密，并将加密后的内容写入指定文件
        
        Args:
            source_file: 源文件路径
            target_file: 目标文件路径
            pub_key: 公钥（文件路径或Base64编码）
        """
        if not pub_key:
            raise ValueError("请传入公钥")
        if not os.path.isfile(source_file):
            raise ValueError("请指定需要加密文件")
        if os.path.isfile(target_file):
            os.remove(target_file)

        with open(source_file, 'rb') as fd:
            data = fd.read()

        encrypted_data = self.rsa_long_encrypt(pub_key, data)

        with open(target_file, 'wb') as fout:
            fout.write(encrypted_data)

    def decrypt_file(self, source_file: str, target_file: str, priv_key: Union[str, bytes]) -> None:
        """
        RSA对文件内容进行解密，并将解密后的内容写入指定文件
        
        Args:
            source_file: 源文件路径
            target_file: 目标文件路径
            priv_key: 私钥（文件路径或Base64编码）
        """
        if not priv_key:
            raise ValueError("请传入私钥")
        if not os.path.isfile(source_file):
            raise ValueError("请指定需要解密文件")
        if os.path.isfile(target_file):
            os.remove(target_file)

        with open(source_file, 'rb') as fd:
            data = fd.read()

        decrypted_data = self.rsa_long_decrypt(priv_key, data)

        with open(target_file, 'wb') as fout:
            fout.write(decrypted_data)


# 兼容旧版本的类名
Encrption = Encryption


if __name__ == "__main__":
    # 测试示例
    enc = Encryption()
    
    # 测试MD5
    print("MD5测试:")
    md5_result = enc.sign_md5("test data")
    print(f"MD5('test data'): {md5_result}")
    
    # 测试HMAC-SHA256
    print("\nHMAC-SHA256测试:")
    hmac_result = enc.sign_hmacsha256("secret_key", "test data")
    print(f"HMAC-SHA256: {hmac_result}")
    
    # 测试SHA1
    print("\nSHA1测试:")
    sha1_result = enc.sign_sha1("test data")
    print(f"SHA1('test data'): {sha1_result}")
    
    # 测试SHA256
    print("\nSHA256测试:")
    sha256_result = enc.sign_sha256("test data")
    print(f"SHA256('test data'): {sha256_result}")
    
    # 测试AES加密
    print("\nAES加密测试:")
    key = "16bytesecretkey!!"  # 16字节
    plaintext = "这是需要加密的数据"
    ciphertext = enc.encrypt_aes(plaintext, key)
    print(f"加密后: {ciphertext}")
    decrypted = enc.decrypt_aes(ciphertext, key)
    print(f"解密后: {decrypted.decode('utf-8')}")
    
    print("\n所有测试完成！")

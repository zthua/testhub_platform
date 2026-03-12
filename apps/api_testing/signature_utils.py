"""
请求签名工具模块
支持多种签名算法
"""
import hashlib
import hmac
import json
import base64
import os
from typing import Dict, Any, Optional

from .UntilTestLib import *

# 尝试导入 PyCryptodome (原有加密库)
try:
    from Cryptodome.Hash import SHA256, MD5
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import pkcs1_15
    PYCRYPTODOME_AVAILABLE = True
except ImportError:
    PYCRYPTODOME_AVAILABLE = False

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    from gmssl import sm2, func
    GMSM_AVAILABLE = True
except ImportError:
    GMSM_AVAILABLE = False


class SignatureAlgorithm:
    """签名算法枚举"""
    MD5 = 'MD5'
    SHA1 = 'SHA1'
    SHA256 = 'SHA256'
    HMAC_SHA1 = 'HMAC-SHA1'
    HMAC_SHA256 = 'HMAC-SHA256'
    RSA_SHA256 = 'RSA-SHA256'
    RSA_SHA512 = 'RSA-SHA512'
    RSA_MD5 = 'RSA-MD5'
    SM2 = 'SM2'


def generate_signature(
    body: Any,
    algorithm: str = SignatureAlgorithm.MD5,
    secret_key: Optional[str] = None,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    rsa_private_key: Optional[str] = None,
    rsa_public_key: Optional[str] = None,
    sm2_private_key: Optional[str] = None,
    sm2_public_key: Optional[str] = None,
    sm2_mode: str = 'C1C2C3',
    extra_params_in_sign: bool = False
) -> str:
    """
    生成请求签名

    Args:
        body: 请求体数据（字典、字符串或None）
        algorithm: 签名算法
        secret_key: 签名密钥（用于HMAC算法）
        extra_params: 额外参数（如timestamp）
        encoding: 编码格式
        rsa_private_key: RSA私钥（用于RSA签名）
        rsa_public_key: RSA公钥（用于RSA验签）
        sm2_private_key: SM2私钥（用于SM2签名）
        sm2_public_key: SM2公钥（用于SM2验签）
        sm2_mode: SM2签名模式（C1C2C3或C1C3C2）
        extra_params_in_sign: 额外参数是否参与签名（默认为False，只有body参与签名）

    Returns:
        签名字符串
    """
    # 1. 准备待签名内容（RSA-MD5 需要特殊处理）
    is_rsa_md5 = algorithm == SignatureAlgorithm.RSA_MD5

    # 所有算法都需要准备签名内容，包括 RSA-MD5
    sign_content = prepare_sign_content(body, extra_params, encoding, is_rsa_md5=is_rsa_md5, extra_params_in_sign=extra_params_in_sign, caller="签名")

    # 2. 根据算法生成签名
    if algorithm == SignatureAlgorithm.MD5:
        return md5_sign(sign_content)

    elif algorithm == SignatureAlgorithm.SHA1:
        return sha1_sign(sign_content)

    elif algorithm == SignatureAlgorithm.SHA256:
        return sha256_sign(sign_content)

    elif algorithm == SignatureAlgorithm.HMAC_SHA1:
        if not secret_key:
            raise ValueError("HMAC-SHA1算法需要提供secret_key")
        return hmac_sha1_sign(sign_content, secret_key)

    elif algorithm == SignatureAlgorithm.HMAC_SHA256:
        if not secret_key:
            raise ValueError("HMAC-SHA256算法需要提供secret_key")
        return hmac_sha256_sign(sign_content, secret_key)

    elif algorithm == SignatureAlgorithm.RSA_SHA256:
        if not rsa_private_key:
            raise ValueError("RSA-SHA256算法需要提供rsa_private_key")
        return rsa_sha256_sign(sign_content, rsa_private_key)

    elif algorithm == SignatureAlgorithm.RSA_SHA512:
        if not rsa_private_key:
            raise ValueError("RSA-SHA512算法需要提供rsa_private_key")
        return rsa_sha512_sign(sign_content, rsa_private_key)

    elif algorithm == SignatureAlgorithm.RSA_MD5:
        if not rsa_private_key:
            raise ValueError("RSA-MD5算法需要提供rsa_private_key")
        # 使用 rsa_md5_sign 函数进行签名，sign_content 已经在 prepare_sign_content 中处理好
        return rsa_md5_sign(sign_content, rsa_private_key)

    elif algorithm == SignatureAlgorithm.SM2:
        if not sm2_private_key:
            raise ValueError("SM2算法需要提供sm2_private_key")
        return sm2_sign(sign_content, sm2_private_key, sm2_mode)

    else:
        raise ValueError(f"不支持的签名算法: {algorithm}")


def prepare_sign_content(
    body: Any,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    is_rsa_md5: bool = False,
    extra_params_in_sign: bool = False,
    caller: str = "签名"
) -> str:
    """
    准备待签名内容

    Args:
        body: 请求体
        extra_params: 额外参数
        encoding: 编码
        is_rsa_md5: 是否为 RSA-MD5 签名（需要特殊处理）
        extra_params_in_sign: 额外参数是否参与签名（默认为False）
        caller: 调用方标识（用于日志）

    Returns:
        待签名字符串
    """
    if is_rsa_md5:
        # RSA-MD5 特殊处理：默认只对 body 进行签名，不包括额外参数
        # 如果需要额外参数参与签名，需要设置 extra_params_in_sign=True
        if body and isinstance(body, dict):
            # 复制 body 避免修改原数据
            sign_body = body.copy()

            # 移除不应该参与签名的字段（与 UntilTestLib 保持一致）
            removed_fields = []
            if 'sign_type' in sign_body:
                sign_body.pop('sign_type')
                removed_fields.append('sign_type')

            if removed_fields:
                print(f"[DEBUG] RSA-MD5{caller} - 移除字段: {removed_fields}")

            # 按 key 排序
            sorted_body = {k: sign_body[k] for k in sorted(sign_body.keys())}

            # 如果配置了 extra_params_in_sign=True，额外参数才参与签名
            if extra_params and extra_params_in_sign:
                sorted_extra = {k: extra_params[k] for k in sorted(extra_params.keys())}
                # 将额外参数合并到 body 中
                sorted_body.update(sorted_extra)
                print(f"[DEBUG] RSA-MD5{caller} - 额外参数参与签名: {sorted_extra}")
            elif extra_params:
                print(f"[DEBUG] RSA-MD5{caller} - 额外参数（不参与签名）: {extra_params}")

            # 转为 JSON 字符串（使用默认格式，与 UntilTestLib.get_sign_4accp 保持一致）
            # 注意：不指定 separators，使用 Python 默认格式（有空格）
            sign_content = json.dumps(sorted_body, sort_keys=True)
            print(f"[DEBUG] RSA-MD5{caller} - 请求体排序后(JSON) 长度: {len(sign_content)}")
            print(f"[DEBUG] RSA-MD5{caller} - JSON内容(前200字符): {sign_content[:200]}")

            return sign_content
        elif body and isinstance(body, str):
            print(f"[DEBUG] RSA-MD5{caller} - 请求体(字符串): {body}")
            return body
        else:
            return ''

    # 其他签名算法的原有逻辑
    content_parts = []

    # 1. 处理请求体
    if body:
        if isinstance(body, dict):
            # 字典按key排序后拼接
            sorted_items = sorted(body.items())
            body_str = '&'.join([f"{k}={v}" for k, v in sorted_items])
            content_parts.append(body_str)
            print(f"[DEBUG] 签名 - 请求体排序后: {body_str}")
        elif isinstance(body, str):
            content_parts.append(body)
            print(f"[DEBUG] 签名 - 请求体(字符串): {body}")
        else:
            # 其他类型转JSON字符串
            json_str = json.dumps(body, ensure_ascii=False)
            content_parts.append(json_str)
            print(f"[DEBUG] 签名 - 请求体(JSON): {json_str}")

    # 2. 添加额外参数（如timestamp、nonce等）
    if extra_params:
        sorted_params = sorted(extra_params.items())
        param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
        content_parts.append(param_str)
        print(f"[DEBUG] 签名 - 额外参数: {param_str}")

    # 3. 拼接所有内容
    sign_content = '&'.join(content_parts)
    print(f"[DEBUG] 签名 - 最终待签名字符串: {sign_content}")

    return sign_content


def md5_sign(content: str, encoding: str = 'utf-8') -> str:
    """MD5签名"""
    return hashlib.md5(content.encode(encoding)).hexdigest()


def sha1_sign(content: str, encoding: str = 'utf-8') -> str:
    """SHA1签名"""
    return hashlib.sha1(content.encode(encoding)).hexdigest()


def sha256_sign(content: str, encoding: str = 'utf-8') -> str:
    """SHA256签名"""
    return hashlib.sha256(content.encode(encoding)).hexdigest()


def hmac_sha1_sign(content: str, secret_key: str, encoding: str = 'utf-8') -> str:
    """HMAC-SHA1签名"""
    return hmac.new(
        secret_key.encode(encoding),
        content.encode(encoding),
        hashlib.sha1
    ).hexdigest()


def hmac_sha256_sign(content: str, secret_key: str, encoding: str = 'utf-8') -> str:
    """HMAC-SHA256签名"""
    return hmac.new(
        secret_key.encode(encoding),
        content.encode(encoding),
        hashlib.sha256
    ).hexdigest()


def rsa_sha256_sign(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """RSA-SHA256签名"""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ValueError("RSA签名需要安装 cryptography 库: pip install cryptography")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()
        
        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名 - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名 - 私钥总长度: {len(key_data)}")

        # 如果没有PEM头尾,自动添加
        if not key_data.startswith('-----'):
            # 尝试Base64解码
            try:
                key_data = base64.b64decode(key_data).decode('utf-8')
            except Exception:
                # 如果不是Base64,假设已经是PEM格式但缺少头尾
                if 'PRIVATE KEY' not in key_data:
                    key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"

        # 加载私钥
        try:
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"私钥格式错误: {str(e)}\n\n请确保私钥是标准的PEM格式:\n-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")

        # 签名
        signature = private_key_obj.sign(
            content.encode(encoding),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"RSA-SHA256签名失败: {str(e)}")


def rsa_sha512_sign(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """RSA-SHA512签名"""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ValueError("RSA签名需要安装 cryptography 库: pip install cryptography")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()
        
        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名 - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名 - 私钥总长度: {len(key_data)}")

        # 如果没有PEM头尾,自动添加
        if not key_data.startswith('-----'):
            # 尝试Base64解码
            try:
                key_data = base64.b64decode(key_data).decode('utf-8')
            except Exception:
                # 如果不是Base64,假设已经是PEM格式但缺少头尾
                if 'PRIVATE KEY' not in key_data:
                    key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"

        # 加载私钥
        try:
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"私钥格式错误: {str(e)}\n\n请确保私钥是标准的PEM格式:\n-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")

        # 签名
        signature = private_key_obj.sign(
            content.encode(encoding),
            padding.PKCS1v15(),
            hashes.SHA512()
        )

        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"RSA-SHA512签名失败: {str(e)}")


def rsa_md5_sign_legacy(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """
    备份的 RSA-MD5 签名方法（使用 cryptography 库）

    Args:
        content: 待签名内容
        private_key: RSA私钥
        encoding: 编码格式

    Returns:
        Base64编码的签名字符串
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ValueError("RSA签名需要安装 cryptography 库: pip install cryptography")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()

        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名(legacy) - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名(legacy) - 私钥总长度: {len(key_data)}")

        # 如果没有PEM头尾,自动添加
        if not key_data.startswith('-----'):
            # 尝试Base64解码
            try:
                key_data = base64.b64decode(key_data).decode('utf-8')
            except Exception:
                # 如果不是Base64,假设已经是PEM格式但缺少头尾
                if 'PRIVATE KEY' not in key_data:
                    key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"

        # 1. 先计算MD5哈希（按照 encrption.sign_rsa 的逻辑）
        # 先对原始内容计算MD5
        md5_hex = hashlib.md5(content.encode(encoding)).hexdigest()
        print(f"[DEBUG] RSA-MD5签名(legacy) - 第一次MD5哈希值: {md5_hex} (长度: {len(md5_hex)})")

        # 对MD5哈希的十六进制字符串再次进行MD5哈希
        md5_hash = hashlib.md5(md5_hex.encode(encoding)).digest()
        print(f"[DEBUG] RSA-MD5签名(legacy) - 第二次MD5哈希已计算")

        # 2. 加载私钥 - 尝试两种方式
        private_key_obj = None
        try:
            # 首先尝试加载为 PRIVATE KEY (PKCS#8)
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )
        except Exception as e1:
            print(f"[DEBUG] 第一次加载私钥失败: {str(e1)}")
            try:
                # 尝试将转换为 RSA PRIVATE KEY 格式
                if '-----BEGIN PRIVATE KEY-----' in key_data:
                    # 使用 OpenSSL 命令转换（如果有）或跳过
                    # 这里我们尝试直接加载，cryptography 支持两种格式
                    print("[DEBUG] 尝试使用传统 RSA PRIVATE KEY 格式")
                    # 转换为 RSA PRIVATE KEY 格式（传统格式）
                    # 注意：cryptography 库会自动处理这种转换
                    pass
            except Exception as e2:
                raise ValueError(f"私钥加载失败: {str(e1)}; 尝试转换失败: {str(e2)}")

        # 如果仍然没有加载成功，再试一次
        if private_key_obj is None:
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )

        # 3. 使用MD5withRSA进行签名
        signature = private_key_obj.sign(
            md5_hash,
            padding.PKCS1v15(),
            hashes.MD5()
        )

        # 4. Base64编码
        signature_base64 = base64.b64encode(signature).decode('utf-8')
        print(f"[DEBUG] RSA-MD5签名(legacy) - 签名结果(前100字符): {signature_base64[:100]}...")

        return signature_base64
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"RSA-MD5签名失败: {str(e)}")


def rsa_md5_sign_pycryptodome(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """
    使用 PyCryptodome 的 RSA-MD5 签名方法（原有算法，与 UntilTestLib.get_sign_4accp 一致）

    Args:
        content: 待签名内容
        private_key: RSA私钥
        encoding: 编码格式

    Returns:
        Base64编码的签名字符串
    """
    if not PYCRYPTODOME_AVAILABLE:
        raise ValueError("RSA签名需要安装 PyCryptodome 库: pip install pycryptodome")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()

        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 私钥总长度: {len(key_data)}")

        # 加载私钥（参考 UntilTestLib.get_sign_4accp 的实现）
        if os.path.isfile(key_data):
            key = RSA.importKey(open(key_data, 'r').read())  # 从文件中读取key
        else:
            # 如果是PEM格式，转换为Base64-DER格式（参考 encrption.py 的实现）
            if key_data.startswith('-----'):
                # 从PEM格式提取Base64部分
                lines = key_data.strip().split('\n')
                base64_data = ''.join([line for line in lines if not line.startswith('-----')])
                key_der = base64.b64decode(base64_data)
                key = RSA.importKey(key_der)
            else:
                # 尝试Base64解码（参考 encrption.py 的实现）
                try:
                    key_der = base64.b64decode(key_data)
                    key = RSA.importKey(key_der)
                except Exception as e:
                    raise ValueError(f"无法解析私钥格式: {str(e)}")

        # 1. 先计算MD5哈希（按照 encrption.sign_rsa 的逻辑）
        # 先对原始内容计算MD5
        h1 = MD5.new(content.encode(encoding))
        md5_hex = h1.hexdigest()
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 第一次MD5哈希值: {md5_hex} (长度: {len(md5_hex)})")

        # 2. 对MD5哈希的十六进制字符串再次进行MD5哈希（这是关键！）
        # 参考 encrption.py line 279: h = MD5.new(signdata.encode('utf8'))
        # 这里 signdata 已经是 MD5 的十六进制字符串
        h = MD5.new(md5_hex.encode('utf8'))
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 第二次MD5哈希对象已创建")

        # 3. 使用MD5withRSA进行签名
        signer = pkcs1_15.new(key)
        signature = signer.sign(h)

        # 3. Base64编码
        signature_base64 = base64.b64encode(signature).decode('utf-8')
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 签名结果(前100字符): {signature_base64[:100]}...")

        return signature_base64
    except Exception as e:
        raise ValueError(f"RSA-MD5签名(PyCryptodome)失败: {str(e)}")


def rsa_md5_sign(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """
    RSA-MD5 签名方法（先MD5哈希，再RSA签名）
    优先使用 PyCryptodome 实现（与原有算法一致），失败则回退到 cryptography

    Args:
        content: 待签名内容
        private_key: RSA私钥
        encoding: 编码格式

    Returns:
        Base64编码的签名字符串
    """
    # 优先使用 PyCryptodome 实现（与 UntilTestLib.get_sign_4accp 一致）
    if PYCRYPTODOME_AVAILABLE:
        try:
            return rsa_md5_sign_pycryptodome(content, private_key, encoding)
        except Exception as e:
            print(f"[DEBUG] RSA-MD5签名(PyCryptodome)失败，回退到cryptography: {str(e)}")
            # 回退到 cryptography 实现
            pass
    else:
        print(f"[DEBUG] PyCryptodome不可用，使用cryptography实现")

    # 回退到 cryptography 实现
    return rsa_md5_sign_legacy(content, private_key, encoding)


def sm2_sign(content: str, private_key: str, mode: str = 'C1C2C3', encoding: str = 'utf-8') -> str:
    """SM2签名"""
    if not GMSM_AVAILABLE:
        raise ValueError("SM2签名需要安装 gmssl 库: pip install gmssl")

    try:
        # 创建SM2对象
        sm2_obj = sm2.CryptSM2(
            private_key=private_key,
            public_key=''
        )

        # 签名
        sign = sm2_obj.sign(content.encode(encoding), mode)

        # Base64编码
        return base64.b64encode(sign).decode('utf-8')
    except Exception as e:
        raise ValueError(f"SM2签名失败: {str(e)}")


def verify_signature_with_public_key(
    body: Any,
    signature: str,
    algorithm: str = SignatureAlgorithm.MD5,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    rsa_public_key: Optional[str] = None,
    extra_params_in_sign: bool = False
) -> bool:
    """
    使用公钥验证签名（真正的验签）

    Args:
        body: 请求体
        signature: 待验证的签名
        algorithm: 签名算法
        extra_params: 额外参数
        encoding: 编码
        rsa_public_key: RSA公钥（用于RSA验签）
        extra_params_in_sign: 额外参数是否参与签名（默认为False）

    Returns:
        验证结果
    """
    from cryptography.hazmat.primitives.asymmetric import utils
    from cryptography.exceptions import InvalidSignature

    # 准备待签名内容
    is_rsa_md5 = algorithm == SignatureAlgorithm.RSA_MD5
    sign_content = prepare_sign_content(body, extra_params, encoding, is_rsa_md5=is_rsa_md5, extra_params_in_sign=extra_params_in_sign, caller="验签")

    # 计算 MD5 哈希
    content_bytes = sign_content.encode(encoding)
    md5_hash = hashlib.md5(content_bytes).digest()
    md5_hex = hashlib.md5(content_bytes).hexdigest()
    print(f"[DEBUG] 验签 - MD5哈希值: {md5_hex}")

    # 加载公钥
    key_data = rsa_public_key.strip()
    print(f"[DEBUG] 验签 - 公钥前50字符: {key_data[:50]}...")
    if not key_data.startswith('-----'):
        try:
            key_data = base64.b64decode(key_data).decode('utf-8')
        except Exception:
            if 'PUBLIC KEY' not in key_data:
                key_data = f"-----BEGIN PUBLIC KEY-----\n{key_data}\n-----END PUBLIC KEY-----"

    try:
        public_key_obj = serialization.load_pem_public_key(
            key_data.encode(encoding),
            backend=default_backend()
        )
        print(f"[DEBUG] 验签 - 公钥加载成功")
    except Exception as e:
        print(f"[DEBUG] 验签 - 公钥加载失败: {str(e)}")
        return False

    # 根据算法选择不同的哈希函数
    hash_algorithm = None
    if algorithm == SignatureAlgorithm.RSA_MD5:
        hash_algorithm = hashes.MD5()
    elif algorithm == SignatureAlgorithm.RSA_SHA256:
        hash_algorithm = hashes.SHA256()
    elif algorithm == SignatureAlgorithm.RSA_SHA512:
        hash_algorithm = hashes.SHA512()

    if not hash_algorithm:
        raise ValueError(f"不支持的RSA签名算法: {algorithm}")

    # 计算对应哈希
    if algorithm == SignatureAlgorithm.RSA_MD5:
        digest = md5_hash
    else:
        digest = hashlib.new(hash_algorithm.name.replace('-', '').lower(), content_bytes).digest()

    # 验证签名
    try:
        signature_bytes = base64.b64decode(signature)
        print(f"[DEBUG] 验签 - 签名解码后长度: {len(signature_bytes)} bytes")
        public_key_obj.verify(
            signature_bytes,
            digest,
            padding.PKCS1v15(),
            hash_algorithm
        )
        print(f"[DEBUG] 验签 - 签名验证成功")
        return True
    except InvalidSignature:
        print(f"[DEBUG] 验签 - 签名无效（InvalidSignature）")
        return False
    except Exception as e:
        print(f"[DEBUG] 验签异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_signature(
    body: Any,
    signature: str,
    algorithm: str = SignatureAlgorithm.MD5,
    secret_key: Optional[str] = None,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    rsa_public_key: Optional[str] = None,
    sm2_public_key: Optional[str] = None,
    sm2_mode: str = 'C1C2C3',
    extra_params_in_sign: bool = False
) -> bool:
    """
    验证签名

    Args:
        body: 请求体
        signature: 待验证的签名
        algorithm: 签名算法
        secret_key: 签名密钥
        extra_params: 额外参数
        encoding: 编码
        rsa_public_key: RSA公钥（用于RSA验签）
        sm2_public_key: SM2公钥（用于SM2验签）
        sm2_mode: SM2签名模式
        extra_params_in_sign: 额外参数是否参与签名（默认为False）

    Returns:
        验证结果
    """
    # 对于RSA算法，验签应该使用公钥而不是重新生成签名
    if algorithm in [SignatureAlgorithm.RSA_MD5, SignatureAlgorithm.RSA_SHA256, SignatureAlgorithm.RSA_SHA512] and rsa_public_key:
        return verify_signature_with_public_key(
            body=body,
            signature=signature,
            algorithm=algorithm,
            extra_params=extra_params,
            encoding=encoding,
            rsa_public_key=rsa_public_key,
            extra_params_in_sign=extra_params_in_sign
        )
    else:
        # 其他算法使用重新生成签名的方式验证
        expected_signature = generate_signature(
            body=body,
            algorithm=algorithm,
            secret_key=secret_key,
            extra_params=extra_params,
            encoding=encoding,
            rsa_public_key=rsa_public_key,
            sm2_public_key=sm2_public_key,
            sm2_mode=sm2_mode,
            extra_params_in_sign=extra_params_in_sign
        )
        return signature == expected_signature

"""
请求签名工具模块
支持多种签名算法
"""
import hashlib
import hmac
import json
import base64
import os
from typing import Dict, Any, Optional

from .UntilTestLib import *

# 尝试导入 PyCryptodome (原有加密库)
try:
    from Cryptodome.Hash import SHA256, MD5
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import pkcs1_15
    PYCRYPTODOME_AVAILABLE = True
except ImportError:
    PYCRYPTODOME_AVAILABLE = False

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    from gmssl import sm2, func
    GMSM_AVAILABLE = True
except ImportError:
    GMSM_AVAILABLE = False


class SignatureAlgorithm:
    """签名算法枚举"""
    MD5 = 'MD5'
    SHA1 = 'SHA1'
    SHA256 = 'SHA256'
    HMAC_SHA1 = 'HMAC-SHA1'
    HMAC_SHA256 = 'HMAC-SHA256'
    RSA_SHA256 = 'RSA-SHA256'
    RSA_SHA512 = 'RSA-SHA512'
    RSA_MD5 = 'RSA-MD5'
    SM2 = 'SM2'


def generate_signature(
    body: Any,
    algorithm: str = SignatureAlgorithm.MD5,
    secret_key: Optional[str] = None,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    rsa_private_key: Optional[str] = None,
    rsa_public_key: Optional[str] = None,
    sm2_private_key: Optional[str] = None,
    sm2_public_key: Optional[str] = None,
    sm2_mode: str = 'C1C2C3',
    extra_params_in_sign: bool = False
) -> str:
    """
    生成请求签名

    Args:
        body: 请求体数据（字典、字符串或None）
        algorithm: 签名算法
        secret_key: 签名密钥（用于HMAC算法）
        extra_params: 额外参数（如timestamp）
        encoding: 编码格式
        rsa_private_key: RSA私钥（用于RSA签名）
        rsa_public_key: RSA公钥（用于RSA验签）
        sm2_private_key: SM2私钥（用于SM2签名）
        sm2_public_key: SM2公钥（用于SM2验签）
        sm2_mode: SM2签名模式（C1C2C3或C1C3C2）
        extra_params_in_sign: 额外参数是否参与签名（默认为False，只有body参与签名）

    Returns:
        签名字符串
    """
    # 1. 准备待签名内容（RSA-MD5 需要特殊处理）
    is_rsa_md5 = algorithm == SignatureAlgorithm.RSA_MD5

    # 所有算法都需要准备签名内容，包括 RSA-MD5
    sign_content = prepare_sign_content(body, extra_params, encoding, is_rsa_md5=is_rsa_md5, extra_params_in_sign=extra_params_in_sign, caller="签名")

    # 2. 根据算法生成签名
    if algorithm == SignatureAlgorithm.MD5:
        return md5_sign(sign_content)

    elif algorithm == SignatureAlgorithm.SHA1:
        return sha1_sign(sign_content)

    elif algorithm == SignatureAlgorithm.SHA256:
        return sha256_sign(sign_content)

    elif algorithm == SignatureAlgorithm.HMAC_SHA1:
        if not secret_key:
            raise ValueError("HMAC-SHA1算法需要提供secret_key")
        return hmac_sha1_sign(sign_content, secret_key)

    elif algorithm == SignatureAlgorithm.HMAC_SHA256:
        if not secret_key:
            raise ValueError("HMAC-SHA256算法需要提供secret_key")
        return hmac_sha256_sign(sign_content, secret_key)

    elif algorithm == SignatureAlgorithm.RSA_SHA256:
        if not rsa_private_key:
            raise ValueError("RSA-SHA256算法需要提供rsa_private_key")
        return rsa_sha256_sign(sign_content, rsa_private_key)

    elif algorithm == SignatureAlgorithm.RSA_SHA512:
        if not rsa_private_key:
            raise ValueError("RSA-SHA512算法需要提供rsa_private_key")
        return rsa_sha512_sign(sign_content, rsa_private_key)

    elif algorithm == SignatureAlgorithm.RSA_MD5:
        if not rsa_private_key:
            raise ValueError("RSA-MD5算法需要提供rsa_private_key")
        # 使用 rsa_md5_sign 函数进行签名，sign_content 已经在 prepare_sign_content 中处理好
        return rsa_md5_sign(sign_content, rsa_private_key)

    elif algorithm == SignatureAlgorithm.SM2:
        if not sm2_private_key:
            raise ValueError("SM2算法需要提供sm2_private_key")
        return sm2_sign(sign_content, sm2_private_key, sm2_mode)

    else:
        raise ValueError(f"不支持的签名算法: {algorithm}")


def prepare_sign_content(
    body: Any,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    is_rsa_md5: bool = False,
    extra_params_in_sign: bool = False,
    caller: str = "签名"
) -> str:
    """
    准备待签名内容

    Args:
        body: 请求体
        extra_params: 额外参数
        encoding: 编码
        is_rsa_md5: 是否为 RSA-MD5 签名（需要特殊处理）
        extra_params_in_sign: 额外参数是否参与签名（默认为False）
        caller: 调用方标识（用于日志）

    Returns:
        待签名字符串
    """
    if is_rsa_md5:
        # RSA-MD5 特殊处理：默认只对 body 进行签名，不包括额外参数
        # 如果需要额外参数参与签名，需要设置 extra_params_in_sign=True
        if body and isinstance(body, dict):
            # 复制 body 避免修改原数据
            sign_body = body.copy()

            # 移除不应该参与签名的字段（与 UntilTestLib 保持一致）
            removed_fields = []
            if 'sign_type' in sign_body:
                sign_body.pop('sign_type')
                removed_fields.append('sign_type')

            if removed_fields:
                print(f"[DEBUG] RSA-MD5{caller} - 移除字段: {removed_fields}")

            # 按 key 排序
            sorted_body = {k: sign_body[k] for k in sorted(sign_body.keys())}

            # 如果配置了 extra_params_in_sign=True，额外参数才参与签名
            if extra_params and extra_params_in_sign:
                sorted_extra = {k: extra_params[k] for k in sorted(extra_params.keys())}
                # 将额外参数合并到 body 中
                sorted_body.update(sorted_extra)
                print(f"[DEBUG] RSA-MD5{caller} - 额外参数参与签名: {sorted_extra}")
            elif extra_params:
                print(f"[DEBUG] RSA-MD5{caller} - 额外参数（不参与签名）: {extra_params}")

            # 转为 JSON 字符串（使用默认格式，与 UntilTestLib.get_sign_4accp 保持一致）
            # 注意：不指定 separators，使用 Python 默认格式（有空格）
            sign_content = json.dumps(sorted_body, sort_keys=True)
            print(f"[DEBUG] RSA-MD5{caller} - 请求体排序后(JSON) 长度: {len(sign_content)}")
            print(f"[DEBUG] RSA-MD5{caller} - JSON内容(前200字符): {sign_content[:200]}")

            return sign_content
        elif body and isinstance(body, str):
            print(f"[DEBUG] RSA-MD5{caller} - 请求体(字符串): {body}")
            return body
        else:
            return ''

    # 其他签名算法的原有逻辑
    content_parts = []

    # 1. 处理请求体
    if body:
        if isinstance(body, dict):
            # 字典按key排序后拼接
            sorted_items = sorted(body.items())
            body_str = '&'.join([f"{k}={v}" for k, v in sorted_items])
            content_parts.append(body_str)
            print(f"[DEBUG] 签名 - 请求体排序后: {body_str}")
        elif isinstance(body, str):
            content_parts.append(body)
            print(f"[DEBUG] 签名 - 请求体(字符串): {body}")
        else:
            # 其他类型转JSON字符串
            json_str = json.dumps(body, ensure_ascii=False)
            content_parts.append(json_str)
            print(f"[DEBUG] 签名 - 请求体(JSON): {json_str}")

    # 2. 添加额外参数（如timestamp、nonce等）
    if extra_params:
        sorted_params = sorted(extra_params.items())
        param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
        content_parts.append(param_str)
        print(f"[DEBUG] 签名 - 额外参数: {param_str}")

    # 3. 拼接所有内容
    sign_content = '&'.join(content_parts)
    print(f"[DEBUG] 签名 - 最终待签名字符串: {sign_content}")

    return sign_content


def md5_sign(content: str, encoding: str = 'utf-8') -> str:
    """MD5签名"""
    return hashlib.md5(content.encode(encoding)).hexdigest()


def sha1_sign(content: str, encoding: str = 'utf-8') -> str:
    """SHA1签名"""
    return hashlib.sha1(content.encode(encoding)).hexdigest()


def sha256_sign(content: str, encoding: str = 'utf-8') -> str:
    """SHA256签名"""
    return hashlib.sha256(content.encode(encoding)).hexdigest()


def hmac_sha1_sign(content: str, secret_key: str, encoding: str = 'utf-8') -> str:
    """HMAC-SHA1签名"""
    return hmac.new(
        secret_key.encode(encoding),
        content.encode(encoding),
        hashlib.sha1
    ).hexdigest()


def hmac_sha256_sign(content: str, secret_key: str, encoding: str = 'utf-8') -> str:
    """HMAC-SHA256签名"""
    return hmac.new(
        secret_key.encode(encoding),
        content.encode(encoding),
        hashlib.sha256
    ).hexdigest()


def rsa_sha256_sign(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """RSA-SHA256签名"""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ValueError("RSA签名需要安装 cryptography 库: pip install cryptography")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()
        
        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名 - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名 - 私钥总长度: {len(key_data)}")

        # 如果没有PEM头尾,自动添加
        if not key_data.startswith('-----'):
            # 尝试Base64解码
            try:
                key_data = base64.b64decode(key_data).decode('utf-8')
            except Exception:
                # 如果不是Base64,假设已经是PEM格式但缺少头尾
                if 'PRIVATE KEY' not in key_data:
                    key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"

        # 加载私钥
        try:
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"私钥格式错误: {str(e)}\n\n请确保私钥是标准的PEM格式:\n-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")

        # 签名
        signature = private_key_obj.sign(
            content.encode(encoding),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"RSA-SHA256签名失败: {str(e)}")


def rsa_sha512_sign(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """RSA-SHA512签名"""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ValueError("RSA签名需要安装 cryptography 库: pip install cryptography")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()
        
        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名 - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名 - 私钥总长度: {len(key_data)}")

        # 如果没有PEM头尾,自动添加
        if not key_data.startswith('-----'):
            # 尝试Base64解码
            try:
                key_data = base64.b64decode(key_data).decode('utf-8')
            except Exception:
                # 如果不是Base64,假设已经是PEM格式但缺少头尾
                if 'PRIVATE KEY' not in key_data:
                    key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"

        # 加载私钥
        try:
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"私钥格式错误: {str(e)}\n\n请确保私钥是标准的PEM格式:\n-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")

        # 签名
        signature = private_key_obj.sign(
            content.encode(encoding),
            padding.PKCS1v15(),
            hashes.SHA512()
        )

        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"RSA-SHA512签名失败: {str(e)}")


def rsa_md5_sign_legacy(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """
    备份的 RSA-MD5 签名方法（使用 cryptography 库）

    Args:
        content: 待签名内容
        private_key: RSA私钥
        encoding: 编码格式

    Returns:
        Base64编码的签名字符串
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ValueError("RSA签名需要安装 cryptography 库: pip install cryptography")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()

        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名(legacy) - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名(legacy) - 私钥总长度: {len(key_data)}")

        # 如果没有PEM头尾,自动添加
        if not key_data.startswith('-----'):
            # 尝试Base64解码
            try:
                key_data = base64.b64decode(key_data).decode('utf-8')
            except Exception:
                # 如果不是Base64,假设已经是PEM格式但缺少头尾
                if 'PRIVATE KEY' not in key_data:
                    key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"

        # 1. 先计算MD5哈希（按照 encrption.sign_rsa 的逻辑）
        # 先对原始内容计算MD5
        md5_hex = hashlib.md5(content.encode(encoding)).hexdigest()
        print(f"[DEBUG] RSA-MD5签名(legacy) - 第一次MD5哈希值: {md5_hex} (长度: {len(md5_hex)})")

        # 对MD5哈希的十六进制字符串再次进行MD5哈希
        md5_hash = hashlib.md5(md5_hex.encode(encoding)).digest()
        print(f"[DEBUG] RSA-MD5签名(legacy) - 第二次MD5哈希已计算")

        # 2. 加载私钥 - 尝试两种方式
        private_key_obj = None
        try:
            # 首先尝试加载为 PRIVATE KEY (PKCS#8)
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )
        except Exception as e1:
            print(f"[DEBUG] 第一次加载私钥失败: {str(e1)}")
            try:
                # 尝试将转换为 RSA PRIVATE KEY 格式
                if '-----BEGIN PRIVATE KEY-----' in key_data:
                    # 使用 OpenSSL 命令转换（如果有）或跳过
                    # 这里我们尝试直接加载，cryptography 支持两种格式
                    print("[DEBUG] 尝试使用传统 RSA PRIVATE KEY 格式")
                    # 转换为 RSA PRIVATE KEY 格式（传统格式）
                    # 注意：cryptography 库会自动处理这种转换
                    pass
            except Exception as e2:
                raise ValueError(f"私钥加载失败: {str(e1)}; 尝试转换失败: {str(e2)}")

        # 如果仍然没有加载成功，再试一次
        if private_key_obj is None:
            private_key_obj = serialization.load_pem_private_key(
                key_data.encode(encoding),
                password=None,
                backend=default_backend()
            )

        # 3. 使用MD5withRSA进行签名
        signature = private_key_obj.sign(
            md5_hash,
            padding.PKCS1v15(),
            hashes.MD5()
        )

        # 4. Base64编码
        signature_base64 = base64.b64encode(signature).decode('utf-8')
        print(f"[DEBUG] RSA-MD5签名(legacy) - 签名结果(前100字符): {signature_base64[:100]}...")

        return signature_base64
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"RSA-MD5签名失败: {str(e)}")


def rsa_md5_sign_pycryptodome(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """
    使用 PyCryptodome 的 RSA-MD5 签名方法（原有算法，与 UntilTestLib.get_sign_4accp 一致）

    Args:
        content: 待签名内容
        private_key: RSA私钥
        encoding: 编码格式

    Returns:
        Base64编码的签名字符串
    """
    if not PYCRYPTODOME_AVAILABLE:
        raise ValueError("RSA签名需要安装 PyCryptodome 库: pip install pycryptodome")

    try:
        # 检查并修正私钥格式
        key_data = private_key.strip()

        # 打印使用的私钥（脱敏处理，只显示部分）
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 使用的私钥(前100字符): {key_data[:100]}...")
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 私钥总长度: {len(key_data)}")

        # 加载私钥（参考 UntilTestLib.get_sign_4accp 的实现）
        if os.path.isfile(key_data):
            key = RSA.importKey(open(key_data, 'r').read())  # 从文件中读取key
        else:
            # 如果是PEM格式，转换为Base64-DER格式（参考 encrption.py 的实现）
            if key_data.startswith('-----'):
                # 从PEM格式提取Base64部分
                lines = key_data.strip().split('\n')
                base64_data = ''.join([line for line in lines if not line.startswith('-----')])
                key_der = base64.b64decode(base64_data)
                key = RSA.importKey(key_der)
            else:
                # 尝试Base64解码（参考 encrption.py 的实现）
                try:
                    key_der = base64.b64decode(key_data)
                    key = RSA.importKey(key_der)
                except Exception as e:
                    raise ValueError(f"无法解析私钥格式: {str(e)}")

        # 1. 先计算MD5哈希（按照 encrption.sign_rsa 的逻辑）
        # 先对原始内容计算MD5
        h1 = MD5.new(content.encode(encoding))
        md5_hex = h1.hexdigest()
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 第一次MD5哈希值: {md5_hex} (长度: {len(md5_hex)})")

        # 2. 对MD5哈希的十六进制字符串再次进行MD5哈希（这是关键！）
        # 参考 encrption.py line 279: h = MD5.new(signdata.encode('utf8'))
        # 这里 signdata 已经是 MD5 的十六进制字符串
        h = MD5.new(md5_hex.encode('utf8'))
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 第二次MD5哈希对象已创建")

        # 3. 使用MD5withRSA进行签名
        signer = pkcs1_15.new(key)
        signature = signer.sign(h)

        # 3. Base64编码
        signature_base64 = base64.b64encode(signature).decode('utf-8')
        print(f"[DEBUG] RSA-MD5签名(PyCryptodome) - 签名结果(前100字符): {signature_base64[:100]}...")

        return signature_base64
    except Exception as e:
        raise ValueError(f"RSA-MD5签名(PyCryptodome)失败: {str(e)}")


def rsa_md5_sign(content: str, private_key: str, encoding: str = 'utf-8') -> str:
    """
    RSA-MD5 签名方法（先MD5哈希，再RSA签名）
    优先使用 PyCryptodome 实现（与原有算法一致），失败则回退到 cryptography

    Args:
        content: 待签名内容
        private_key: RSA私钥
        encoding: 编码格式

    Returns:
        Base64编码的签名字符串
    """
    # 优先使用 PyCryptodome 实现（与 UntilTestLib.get_sign_4accp 一致）
    if PYCRYPTODOME_AVAILABLE:
        try:
            return rsa_md5_sign_pycryptodome(content, private_key, encoding)
        except Exception as e:
            print(f"[DEBUG] RSA-MD5签名(PyCryptodome)失败，回退到cryptography: {str(e)}")
            # 回退到 cryptography 实现
            pass
    else:
        print(f"[DEBUG] PyCryptodome不可用，使用cryptography实现")

    # 回退到 cryptography 实现
    return rsa_md5_sign_legacy(content, private_key, encoding)


def sm2_sign(content: str, private_key: str, mode: str = 'C1C2C3', encoding: str = 'utf-8') -> str:
    """SM2签名"""
    if not GMSM_AVAILABLE:
        raise ValueError("SM2签名需要安装 gmssl 库: pip install gmssl")

    try:
        # 创建SM2对象
        sm2_obj = sm2.CryptSM2(
            private_key=private_key,
            public_key=''
        )

        # 签名
        sign = sm2_obj.sign(content.encode(encoding), mode)

        # Base64编码
        return base64.b64encode(sign).decode('utf-8')
    except Exception as e:
        raise ValueError(f"SM2签名失败: {str(e)}")


def verify_signature_with_public_key(
    body: Any,
    signature: str,
    algorithm: str = SignatureAlgorithm.MD5,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    rsa_public_key: Optional[str] = None,
    extra_params_in_sign: bool = False
) -> bool:
    """
    使用公钥验证签名（真正的验签）

    Args:
        body: 请求体
        signature: 待验证的签名
        algorithm: 签名算法
        extra_params: 额外参数
        encoding: 编码
        rsa_public_key: RSA公钥（用于RSA验签）
        extra_params_in_sign: 额外参数是否参与签名（默认为False）

    Returns:
        验证结果
    """
    from cryptography.hazmat.primitives.asymmetric import utils
    from cryptography.exceptions import InvalidSignature

    # 准备待签名内容
    is_rsa_md5 = algorithm == SignatureAlgorithm.RSA_MD5
    sign_content = prepare_sign_content(body, extra_params, encoding, is_rsa_md5=is_rsa_md5, extra_params_in_sign=extra_params_in_sign, caller="验签")

    # 计算 MD5 哈希
    content_bytes = sign_content.encode(encoding)
    md5_hash = hashlib.md5(content_bytes).digest()
    md5_hex = hashlib.md5(content_bytes).hexdigest()
    print(f"[DEBUG] 验签 - MD5哈希值: {md5_hex}")

    # 加载公钥
    key_data = rsa_public_key.strip()
    print(f"[DEBUG] 验签 - 公钥前50字符: {key_data[:50]}...")
    if not key_data.startswith('-----'):
        try:
            key_data = base64.b64decode(key_data).decode('utf-8')
        except Exception:
            if 'PUBLIC KEY' not in key_data:
                key_data = f"-----BEGIN PUBLIC KEY-----\n{key_data}\n-----END PUBLIC KEY-----"

    try:
        public_key_obj = serialization.load_pem_public_key(
            key_data.encode(encoding),
            backend=default_backend()
        )
        print(f"[DEBUG] 验签 - 公钥加载成功")
    except Exception as e:
        print(f"[DEBUG] 验签 - 公钥加载失败: {str(e)}")
        return False

    # 根据算法选择不同的哈希函数
    hash_algorithm = None
    if algorithm == SignatureAlgorithm.RSA_MD5:
        hash_algorithm = hashes.MD5()
    elif algorithm == SignatureAlgorithm.RSA_SHA256:
        hash_algorithm = hashes.SHA256()
    elif algorithm == SignatureAlgorithm.RSA_SHA512:
        hash_algorithm = hashes.SHA512()

    if not hash_algorithm:
        raise ValueError(f"不支持的RSA签名算法: {algorithm}")

    # 计算对应哈希
    if algorithm == SignatureAlgorithm.RSA_MD5:
        digest = md5_hash
    else:
        digest = hashlib.new(hash_algorithm.name.replace('-', '').lower(), content_bytes).digest()

    # 验证签名
    try:
        signature_bytes = base64.b64decode(signature)
        print(f"[DEBUG] 验签 - 签名解码后长度: {len(signature_bytes)} bytes")
        public_key_obj.verify(
            signature_bytes,
            digest,
            padding.PKCS1v15(),
            hash_algorithm
        )
        print(f"[DEBUG] 验签 - 签名验证成功")
        return True
    except InvalidSignature:
        print(f"[DEBUG] 验签 - 签名无效（InvalidSignature）")
        return False
    except Exception as e:
        print(f"[DEBUG] 验签异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_signature(
    body: Any,
    signature: str,
    algorithm: str = SignatureAlgorithm.MD5,
    secret_key: Optional[str] = None,
    extra_params: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    rsa_public_key: Optional[str] = None,
    sm2_public_key: Optional[str] = None,
    sm2_mode: str = 'C1C2C3',
    extra_params_in_sign: bool = False
) -> bool:
    """
    验证签名

    Args:
        body: 请求体
        signature: 待验证的签名
        algorithm: 签名算法
        secret_key: 签名密钥
        extra_params: 额外参数
        encoding: 编码
        rsa_public_key: RSA公钥（用于RSA验签）
        sm2_public_key: SM2公钥（用于SM2验签）
        sm2_mode: SM2签名模式
        extra_params_in_sign: 额外参数是否参与签名（默认为False）

    Returns:
        验证结果
    """
    # 对于RSA算法，验签应该使用公钥而不是重新生成签名
    if algorithm in [SignatureAlgorithm.RSA_MD5, SignatureAlgorithm.RSA_SHA256, SignatureAlgorithm.RSA_SHA512] and rsa_public_key:
        return verify_signature_with_public_key(
            body=body,
            signature=signature,
            algorithm=algorithm,
            extra_params=extra_params,
            encoding=encoding,
            rsa_public_key=rsa_public_key,
            extra_params_in_sign=extra_params_in_sign
        )
    else:
        # 其他算法使用重新生成签名的方式验证
        expected_signature = generate_signature(
            body=body,
            algorithm=algorithm,
            secret_key=secret_key,
            extra_params=extra_params,
            encoding=encoding,
            rsa_public_key=rsa_public_key,
            sm2_public_key=sm2_public_key,
            sm2_mode=sm2_mode,
            extra_params_in_sign=extra_params_in_sign
        )
        return signature == expected_signature


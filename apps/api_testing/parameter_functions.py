"""
参数化函数模块
支持动态生成参数值
"""
import uuid
import time
import random
import string
import re
from datetime import datetime, timedelta


class ParameterFunctions:
    """参数化函数类"""
    
    @staticmethod
    def get_id(length=10):
        """生成随机数字ID"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def get_uuid():
        """生成UUID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def get_uuid_short():
        """生成短UUID（去掉横线）"""
        return str(uuid.uuid4()).replace('-', '')
    
    @staticmethod
    def get_timestamp():
        """获取当前时间戳（秒）"""
        return str(int(time.time()))
    
    @staticmethod
    def get_timestamp_ms():
        """获取当前时间戳（毫秒）"""
        return str(int(time.time() * 1000))
    
    @staticmethod
    def get_datetime(format='%Y-%m-%d %H:%M:%S'):
        """获取当前日期时间"""
        return datetime.now().strftime(format)
    
    @staticmethod
    def get_date(format='%Y-%m-%d'):
        """获取当前日期"""
        return datetime.now().strftime(format)
    
    @staticmethod
    def get_time(format='%H:%M:%S'):
        """获取当前时间"""
        return datetime.now().strftime(format)

    @staticmethod
    def get_timestamp_compact():
        """获取紧凑时间戳格式：年月日时分秒（如：20260129141904）"""
        return datetime.now().strftime('%Y%m%d%H%M%S')
    
    @staticmethod
    def get_random_string(length=10, chars=None):
        """生成随机字符串"""
        if chars is None:
            chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length))
    
    @staticmethod
    def get_random_int(min_val=0, max_val=100):
        """生成随机整数"""
        return str(random.randint(min_val, max_val))
    
    @staticmethod
    def get_random_float(min_val=0.0, max_val=100.0, decimal_places=2):
        """生成随机浮点数"""
        value = random.uniform(min_val, max_val)
        return str(round(value, decimal_places))
    
    @staticmethod
    def get_email(domain='example.com'):
        """生成随机邮箱"""
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{username}@{domain}"
    
    @staticmethod
    def get_phone(prefix='138'):
        """生成随机手机号"""
        suffix = ''.join(random.choices(string.digits, k=8))
        return f"{prefix}{suffix}"
    
    @staticmethod
    def get_increment(key='default', start=1):
        """获取递增数字（需要配合缓存使用）"""
        # 这里简化处理，实际应该使用缓存或数据库
        return str(start)
    
    @staticmethod
    def get_future_date(days=1, format='%Y-%m-%d'):
        """获取未来日期"""
        future = datetime.now() + timedelta(days=days)
        return future.strftime(format)
    
    @staticmethod
    def get_past_date(days=1, format='%Y-%m-%d'):
        """获取过去日期"""
        past = datetime.now() - timedelta(days=days)
        return past.strftime(format)

    @staticmethod
    def enc(value: str, length: int = None) -> str:
        """
        生成加密参数标记
        格式: Enc(value|length) 或 Enc(value)
        例如: ${Enc(621226|19)} 表示对"621226"后面补随机数字到19位
             ${Enc(李四)} 表示不对字符串做特殊处理

        Args:
            value: 原始值
            length: 目标长度（可选），如果指定则在后面补随机数字到指定长度

        Returns:
            标记字符串,后续会被加密处理
        """
        if length is not None:
            # 在原始值后面补随机数字到指定长度
            if isinstance(value, str) and value.isdigit():
                target_length = int(length)
                current_length = len(value)
                if current_length < target_length:
                    # 生成随机数字补位
                    padding_length = target_length - current_length
                    random_digits = ''.join(random.choices(string.digits, k=padding_length))
                    value = value + random_digits
        # 返回处理后的值，加密在后续流程中处理
        return value


def execute_parameter_function(func_str):
    """
    执行参数化函数

    格式示例:
    - ${get_id} 或 ${get_id()}
    - ${get_id(12)}
    - ${get_random_string(16)}
    - ${get_timestamp_compact()}  # 生成格式: 20260129141904

    Args:
        func_str: 函数字符串，如 ":${get_id()}" 或 "${get_id()}" 或 "get_id()"

    Returns:
        生成的参数值
    """
    import re

    # 移除 ${ 和 } 包装（支持带冒号和不带冒号）
    func_str = func_str.strip()
    if func_str.startswith(':${') and func_str.endswith('}'):
        func_str = func_str[3:-1]
    elif func_str.startswith('${') and func_str.endswith('}'):
        func_str = func_str[2:-1]

    # 解析函数名和参数
    match = re.match(r'(\w+)(?:\((.*?)\))?', func_str)
    if not match:
        return func_str
    
    func_name = match.group(1)
    params_str = match.group(2)
    
    # 获取函数
    if not hasattr(ParameterFunctions, func_name):
        return func_str
    
    func = getattr(ParameterFunctions, func_name)
    
    # 解析参数
    params = []
    kwargs = {}
    
    if params_str:
        # 简单解析参数（支持位置参数和关键字参数）
        param_parts = params_str.split(',')
        for part in param_parts:
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                kwargs[key.strip()] = eval(value.strip())
            else:
                params.append(eval(part))
    
    # 执行函数
    try:
        if params or kwargs:
            result = func(*params, **kwargs)
        else:
            result = func()
        return result
    except Exception as e:
        print(f"执行参数化函数失败: {func_name}, 错误: {str(e)}")
        return func_str


def replace_parameters(text, context=None):
    """
    替换文本中的参数化函数

    Args:
        text: 原始文本
        context: 上下文变量（可选）

    Returns:
        替换后的文本
    """
    import re

    if not isinstance(text, str):
        return text

    # 匹配 ${function_name(...)} 格式（支持带冒号和不带冒号）
    # 但要排除 ${Enc(...)} 格式，因为这是加密标记，不是参数函数
    pattern = r'\$\{\w+(?:\([^)]*\))?\}'

    def replacer(match):
        func_str = match.group(0)
        # 跳过 ${Enc(...)} 格式，这是加密标记，不是参数函数
        if func_str.startswith('${Enc('):
            return func_str  # 保持原样，不处理
        return execute_parameter_function(f':{func_str}')

    return re.sub(pattern, replacer, text)


def replace_parameters_in_dict(data, context=None):
    """
    递归替换字典中的参数化函数

    Args:
        data: 数据（字典、列表或字符串）
        context: 上下文变量

    Returns:
        替换后的数据
    """
    if isinstance(data, dict):
        return {k: replace_parameters_in_dict(v, context) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_parameters_in_dict(item, context) for item in data]
    elif isinstance(data, str):
        return replace_parameters(data, context)
    else:
        return data


def extract_enc_placeholders(data):
    """
    提取数据中所有需要加密的Enc()占位符
    支持 ${Enc(...)} 和 Enc(...) 两种格式

    Args:
        data: 数据（字典、列表或字符串）

    Returns:
        需要加密的项列表,每个元素包含路径、原始值、目标长度
    """
    print(f"[DEBUG] extract_enc_placeholders 被调用，data 类型: {type(data)}")
    placeholders = []

    def extract_from_value(value, path=''):
        """递归提取Enc()占位符"""
        if isinstance(value, str):
            print(f"[DEBUG] 检查字符串值: {value[:100]}... (路径: {path})")
            # 匹配 ${Enc(value|length)} 或 ${Enc(value)} 格式
            pattern1 = r'\$\{Enc\((.*?)\)\}'
            # 匹配 Enc(value|length) 或 Enc(value) 格式（不带${}）
            pattern2 = r'Enc\((.*?)\)'

            # 先匹配带${}的格式
            matches1 = list(re.finditer(pattern1, value))
            
            # 如果有带${}的匹配，就不再匹配不带${}的格式
            if matches1:
                matches = matches1
            else:
                # 只有在没有带${}的匹配时，才匹配不带${}的格式
                matches = list(re.finditer(pattern2, value))

            for match in matches:
                params = match.group(1)
                
                # 去除参数两端的引号（如果有）
                params = params.strip()
                if params.startswith('"') and params.endswith('"'):
                    params = params[1:-1]
                elif params.startswith("'") and params.endswith("'"):
                    params = params[1:-1]
                
                # 检查是否包含 | 分隔符
                if '|' in params:
                    raw_value, length = params.split('|', 1)
                    raw_value = raw_value.strip()
                    length = length.strip()
                    # 去除 length 两端的引号（如果有）
                    if length.startswith('"') and length.endswith('"'):
                        length = length[1:-1]
                    elif length.startswith("'") and length.endswith("'"):
                        length = length[1:-1]
                    
                    placeholders.append({
                        'path': path,
                        'full_match': match.group(0),
                        'raw_value': raw_value,
                        'target_length': int(length)
                    })
                    print(f"[DEBUG] 提取到加密占位符: {match.group(0)}, 原始值: {raw_value}, 目标长度: {length}, 路径: {path}")
                else:
                    placeholders.append({
                        'path': path,
                        'full_match': match.group(0),
                        'raw_value': params,
                        'target_length': None
                    })
                    print(f"[DEBUG] 提取到加密占位符: {match.group(0)}, 原始值: {params}, 路径: {path}")
        elif isinstance(value, dict):
            for key, val in value.items():
                extract_from_value(val, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                extract_from_value(item, f"{path}[{idx}]" if path else f"[{idx}]")

    extract_from_value(data)
    return placeholders


def apply_encrypted_values(data, encrypted_map):
    """
    将加密后的值替换回原始数据中
    支持 ${Enc(...)} 和 Enc(...) 两种格式的替换

    Args:
        data: 原始数据
        encrypted_map: 加密映射 {路径: 加密后的值}

    Returns:
        替换后的数据
    """
    if isinstance(data, dict):
        return {k: apply_encrypted_values(v, encrypted_map) for k, v in data.items()}
    elif isinstance(data, list):
        return [apply_encrypted_values(item, encrypted_map) for item in data]
    elif isinstance(data, str):
        # 先尝试匹配带${}的格式
        pattern1 = r'\$\{Enc\((.*?)\)\}'
        match1 = re.search(pattern1, data)
        if match1:
            print(f"[DEBUG] 匹配到${{Enc(...)}}格式: {match1.group(0)}")
            for item in encrypted_map:
                if item['full_match'] == match1.group(0):
                    print(f"[DEBUG] 替换为加密值: {item['encrypted_value'][:50]}...")
                    return item['encrypted_value']

        # 再尝试匹配不带${}的格式（完全匹配）
        pattern2 = r'^Enc\((.*?)\)$'
        match2 = re.search(pattern2, data)
        if match2:
            print(f"[DEBUG] 匹配到Enc(...)格式: {match2.group(0)}")
            for item in encrypted_map:
                if item['full_match'] == match2.group(0):
                    print(f"[DEBUG] 替换为加密值: {item['encrypted_value'][:50]}...")
                    return item['encrypted_value']
        return data
    else:
        return data

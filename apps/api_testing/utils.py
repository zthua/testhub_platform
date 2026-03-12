import json
import time
import re
from django.utils import timezone
from .models import RequestHistory


class TemporaryVariables:
    """临时变量管理器，用于在测试套件执行过程中存储和获取变量"""

    def __init__(self):
        self.variables = {}

    def set(self, key, value):
        """设置变量"""
        self.variables[key] = value

    def get(self, key, default=None):
        """获取变量"""
        return self.variables.get(key, default)

    def set_from_request_data(self, request_data, response_data):
        """
        从请求数据和响应数据中提取变量

        Args:
            request_data: 请求数据字典，包含 url, method, headers, params, body
            response_data: 响应数据字典，包含 status_code, headers, body, json
        """
        # 1. 提取请求参数到临时变量
        # URL 参数
        if 'params' in request_data:
            for key, value in request_data['params'].items():
                self.set(f'request.params.{key}', value)

        # 请求头
        if 'headers' in request_data:
            for key, value in request_data['headers'].items():
                self.set(f'request.headers.{key}', value)

        # 请求体（JSON）
        if 'body' in request_data and isinstance(request_data['body'], dict):
            self._extract_nested_variables(request_data['body'], 'request.body')

        # 2. 提取响应数据到临时变量
        # 响应状态码
        if 'status_code' in response_data:
            self.set('response.status_code', response_data['status_code'])

        # 响应头
        if 'headers' in response_data:
            for key, value in response_data['headers'].items():
                self.set(f'response.headers.{key}', value)

        # 响应体（JSON）
        if 'json' in response_data and response_data['json']:
            self._extract_nested_variables(response_data['json'], 'response.json')

    def _extract_nested_variables(self, data, prefix):
        """
        递归提取嵌套数据到变量
        例如: response.json.data.orderId -> response.json.data.orderId
        """
        if isinstance(data, dict):
            for key, value in data.items():
                variable_name = f'{prefix}.{key}'
                self.set(variable_name, value)
                # 递归处理嵌套对象
                if isinstance(value, (dict, list)):
                    self._extract_nested_variables(value, variable_name)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                variable_name = f'{prefix}[{index}]'
                self.set(variable_name, item)
                # 递归处理列表中的对象
                if isinstance(item, (dict, list)):
                    self._extract_nested_variables(item, variable_name)

    def replace_in_text(self, text):
        """
        替换文本中的临时变量引用
        支持格式: ${get} 或 ${get.variable_name}
        例如: ${get} 获取 response.json.data，或 ${get.response.json.data.xxx}

        Args:
            text: 要替换的文本

        Returns:
            替换后的文本
        """
        if not isinstance(text, str):
            return text

        def replace_match(match):
            var_name = match.group(1)  # 获取 ${xxx} 中的 xxx

            # 处理 ${get} 格式（默认获取 response.json.data）
            if var_name == 'get':
                var_name = 'response.json.data'
            # 处理 ${get.xxx} 格式
            elif var_name.startswith('get.'):
                var_name = var_name[4:]  # 去掉 'get.' 前缀
            # 处理 ${response.json.data.xxx} 等完整路径格式
            else:
                var_name = match.group(0)[2:-1]  # 去掉 ${和}

            # 获取变量值
            value = self.get(var_name)
            if value is not None:
                print(f"[临时变量] 替换: {var_name} -> {value}")
                return str(value)

            # 如果是路径格式（如 response.json.data.orderId），尝试解析嵌套访问
            if '.' in var_name:
                parts = var_name.split('.')
                current = self.variables
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        print(f"[临时变量] 警告: 变量路径 {var_name} 未找到")
                        return match.group(0)
                print(f"[临时变量] 替换路径: {var_name} -> {current}")
                return str(current)

            # 如果变量不存在，保持原样
            print(f"[临时变量] 警告: 变量 {var_name} 未找到")
            return match.group(0)

        # 匹配 ${variable_name} 格式
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_match, text)

    def replace_in_dict(self, data):
        """
        递归替换字典中的临时变量引用
        """
        if isinstance(data, dict):
            return {k: self.replace_in_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.replace_in_dict(item) for item in data]
        elif isinstance(data, str):
            return self.replace_in_text(data)
        else:
            return data

    def clear(self):
        """清空所有变量"""
        self.variables.clear()

    def set_from_dict(self, data_dict, prefix=''):
        """从字典批量设置变量"""
        for key, value in data_dict.items():
            var_key = f"{prefix}{key}" if prefix else key
            self.set(var_key, value)

    def to_dict(self):
        """返回所有变量的字典"""
        return self.variables.copy()


def _replace_with_temp_variables(text, temp_vars, user_inputs=None):
    """
    替换文本中的临时变量占位符 ${get}

    参数:
        text: 要处理的文本
        temp_vars: TemporaryVariables 实例
        user_inputs: 用户输入的参数字典

    返回:
        替换后的文本
    """
    if not isinstance(text, str):
        return text

    def replace_match(match):
        # 获取 ${xxx} 中的内容
        placeholder = match.group(1)

        # 处理 ${get} 格式（默认获取 response.json.data）
        if placeholder == 'get':
            var_name = 'response.json.data'
        # 处理 ${user_input.xxx} 格式
        elif placeholder.startswith('user_input.'):
            field_name = placeholder[11:]  # 去掉 'user_input.' 前缀
            # 从用户输入中获取
            if user_inputs and field_name in user_inputs:
                print(f"[临时变量] 从用户输入获取: {field_name} = {user_inputs[field_name]}")
                return str(user_inputs[field_name])
            else:
                print(f"[临时变量] 警告: 用户输入变量 {field_name} 未找到")
                print(f"[临时变量] 可用用户输入: {list(user_inputs.keys()) if user_inputs else '无'}")
                return match.group(0)
        # 处理 ${get.xxx} 格式
        elif placeholder.startswith('get.'):
            field_name = placeholder[4:]  # 去掉 'get.' 前缀
            # 优先从用户输入中获取
            if user_inputs and field_name in user_inputs:
                print(f"[临时变量] 从用户输入获取: {field_name} = {user_inputs[field_name]}")
                return str(user_inputs[field_name])
            
            # 尝试从多个位置查找变量
            # 1. 先从 request.body 中查找
            request_body_value = temp_vars.get('request.body')
            if request_body_value is not None and isinstance(request_body_value, dict):
                if field_name in request_body_value:
                    value = request_body_value[field_name]
                    print(f"[临时变量] 从request.body获取: {field_name} = {value}")
                    return str(value)
            
            # 2. 从 request.body.xxx 格式的临时变量中查找
            request_body_field_key = f'request.body.{field_name}'
            request_body_field_value = temp_vars.get(request_body_field_key)
            if request_body_field_value is not None:
                print(f"[临时变量] 从临时变量 {request_body_field_key} 获取: {field_name} = {request_body_field_value}")
                return str(request_body_field_value)
            
            # 3. 从 response.json.data 中获取指定字段
            base_value = temp_vars.get('response.json.data')
            if base_value is not None and isinstance(base_value, dict):
                # 首先检查根级别是否有该字段
                if field_name in base_value:
                    value = base_value[field_name]
                    print(f"[临时变量] 从response.json.data根级别获取: {field_name} = {value}")
                    return str(value)
                # 如果根级别没有，检查是否有 'data' 子字段
                elif 'data' in base_value and isinstance(base_value['data'], dict):
                    if field_name in base_value['data']:
                        value = base_value['data'][field_name]
                        print(f"[临时变量] 从response.json.data.data获取: {field_name} = {value}")
                        return str(value)
                    else:
                        print(f"[临时变量] 警告: 字段 {field_name} 在response.json.data.data中未找到")
                        print(f"[临时变量] data子字段可用字段: {list(base_value['data'].keys())}")
                        return match.group(0)
                else:
                    print(f"[临时变量] 警告: 字段 {field_name} 在response.json.data中未找到")
                    print(f"[临时变量] 根级别可用字段: {list(base_value.keys())}")
                    return match.group(0)
            else:
                print(f"[临时变量] 警告: 所有位置都未找到字段 {field_name}")
                print(f"[临时变量] 可用临时变量: {list(temp_vars.keys()) if temp_vars else '无'}")
                return match.group(0)
        # 处理 ${response.json.data.xxx} 等完整路径格式
        else:
            var_name = placeholder

        # 优先从用户输入中获取
        if user_inputs and var_name in user_inputs:
            print(f"[临时变量] 从用户输入获取: {var_name} = {user_inputs[var_name]}")
            return str(user_inputs[var_name])

        # 其次从临时变量中获取
        value = temp_vars.get(var_name)
        if value is not None:
            print(f"[临时变量] 从临时变量获取: {var_name} = {value}")
            return str(value)

        # 如果是路径格式（如 response.json.data.txn_seqno），尝试解析嵌套访问
        if '.' in var_name:
            parts = var_name.split('.')
            # 尝试从 response.json.data 开始查找
            base_value = temp_vars.get('response.json.data')
            if base_value is not None:
                current = base_value
                # 跳过 response.json.data 前缀
                if parts[:3] == ['response', 'json', 'data']:
                    parts_to_access = parts[3:]
                else:
                    parts_to_access = parts
                
                for part in parts_to_access:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        print(f"[临时变量] 警告: 变量路径 {var_name} 在 {part} 处未找到")
                        if isinstance(current, dict):
                            print(f"[临时变量] 当前层级可用字段: {list(current.keys())}")
                        return match.group(0)
                print(f"[临时变量] 从路径获取: {var_name} = {current}")
                return str(current)

        # 未找到变量，返回原占位符
        print(f"[临时变量] 警告: 变量 {var_name} 未找到")
        return match.group(0)

    # 匹配 ${xxx} 格式
    result = re.sub(r'\$\{([^}]+)\}', replace_match, text)
    
    # 处理裸变量（没有 ${} 包裹的变量，如 get_token, get_user_id）
    # 这些变量通常是从临时变量中获取的
    # 检查是否有以 get_ 开头的裸变量
    def replace_bare_variable(match):
        var_name = match.group(0)
        
        # 优先从用户输入中获取
        if user_inputs and var_name in user_inputs:
            print(f"[临时变量] 从用户输入获取裸变量: {var_name} = {user_inputs[var_name]}")
            return str(user_inputs[var_name])
        
        # 从临时变量中直接获取
        value = temp_vars.get(var_name)
        if value is not None:
            print(f"[临时变量] 从临时变量获取裸变量: {var_name} = {value}")
            return str(value)
        
        # 尝试从 request.body.xxx 格式的临时变量中查找
        request_body_field_key = f'request.body.{var_name}'
        request_body_field_value = temp_vars.get(request_body_field_key)
        if request_body_field_value is not None:
            print(f"[临时变量] 从临时变量 {request_body_field_key} 获取裸变量: {var_name} = {request_body_field_value}")
            return str(request_body_field_value)
        
        # 尝试从 request.body 字典中获取
        request_body_value = temp_vars.get('request.body')
        if request_body_value is not None and isinstance(request_body_value, dict):
            if var_name in request_body_value:
                value = request_body_value[var_name]
                print(f"[临时变量] 从request.body获取裸变量: {var_name} = {value}")
                return str(value)
        
        # 尝试从 response.json.data 中获取
        base_value = temp_vars.get('response.json.data')
        if base_value is not None and isinstance(base_value, dict):
            if var_name in base_value:
                value = base_value[var_name]
                print(f"[临时变量] 从response.json.data获取裸变量: {var_name} = {value}")
                return str(value)
            elif 'data' in base_value and isinstance(base_value['data'], dict):
                if var_name in base_value['data']:
                    value = base_value['data'][var_name]
                    print(f"[临时变量] 从response.json.data.data获取裸变量: {var_name} = {value}")
                    return str(value)
        
        # 未找到，返回原值
        print(f"[临时变量] 警告: 裸变量 {var_name} 未找到")
        print(f"[临时变量] 可用临时变量: {list(temp_vars.keys()) if temp_vars else '无'}")
        return var_name
    
    # 匹配以 get_ 开头的裸变量（单词边界）
    result = re.sub(r'\bget_\w+\b', replace_bare_variable, result)
    
    return result


def _replace_with_temp_variables_in_dict(data, temp_vars, user_inputs=None):
    """递归替换字典中的临时变量"""
    if isinstance(data, dict):
        return {k: _replace_with_temp_variables_in_dict(v, temp_vars, user_inputs) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_with_temp_variables_in_dict(item, temp_vars, user_inputs) for item in data]
    elif isinstance(data, str):
        return _replace_with_temp_variables(data, temp_vars, user_inputs)
    else:
        return data


def execute_assertions(response, assertions):
    """执行断言验证"""
    results = []
    
    for assertion in assertions:
        result = {
            'name': assertion.get('name', '未命名断言'),
            'type': assertion.get('type'),
            'passed': False,
            'expected': assertion.get('expected'),
            'actual': None,
            'error': None
        }
        
        try:
            assertion_type = assertion.get('type')
            expected = assertion.get('expected')
            actual = None
            passed = False
            
            if assertion_type == 'status_code':
                actual = response.status_code
                passed = actual == expected
                
            elif assertion_type == 'response_time':
                # 响应时间断言在调用方处理
                actual = assertion.get('actual_time')
                passed = actual <= expected if actual else False
                
            elif assertion_type == 'contains':
                text = response.text or ''
                pattern = str(expected)
                actual = text[:200] + '...' if len(text) > 200 else text
                passed = pattern in str(text)
                
            elif assertion_type == 'json_path':
                json_path = assertion.get('json_path', '')
                expected_value = assertion.get('expected')
                actual = None
                passed = False
                
                try:
                    # 检查响应是否为JSON格式
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        raise ValueError(f"响应不是JSON格式，Content-Type: {content_type}")
                    
                    response_json = json.loads(response.text)
                    
                    # 检查JSONPath表达式是否为空
                    if not json_path:
                        raise ValueError("JSON路径表达式不能为空")
                    
                    from jsonpath_ng import parse
                    matches = parse(json_path).find(response_json)
                    actual = matches[0].value if matches else None
                    passed = str(actual) == str(expected_value)
                    
                    # 确保actual值被正确设置到result中
                    result['actual'] = actual
                except json.JSONDecodeError as e:
                    actual = None
                    passed = False
                    result['error'] = f"JSON解析失败: {str(e)}"
                    result['actual'] = actual
                except ImportError as e:
                    actual = None
                    passed = False
                    result['error'] = f"缺少依赖库: {str(e)}，请安装jsonpath-ng"
                    result['actual'] = actual
                except Exception as e:
                    actual = None
                    passed = False
                    result['error'] = f"执行错误: {str(e)}"
                    result['actual'] = actual
                    
            elif assertion_type == 'header':
                header_name = assertion.get('header_name', '')
                expected_value = assertion.get('expected_value')
                actual = response.headers.get(header_name)
                passed = actual == expected_value
                
            elif assertion_type == 'equals':
                actual = response.text.strip()
                passed = actual == str(expected).strip()
            
            # 确保在所有情况下都设置actual值
            if 'actual' not in result or result['actual'] is None:
                result['actual'] = actual
            result['passed'] = passed
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        results.append(result)
    
    return results


def execute_test_suite_with_runtime_input(test_suite, environment, executed_by, runtime_inputs=None, input_callback=None):
    """
    执行测试套件并返回结果 - 支持运行时用户输入
    支持临时变量、等待时间和用户输入参数

    参数:
        test_suite: 测试套件对象
        environment: 环境对象
        executed_by: 执行者用户对象
        runtime_inputs: 运行时用户输入的参数字典
        input_callback: 用户输入回调函数，用于获取运行时输入
    """
    from .models import TestExecution, RequestHistory

    try:
        # 创建执行记录
        execution = TestExecution.objects.create(
            test_suite=test_suite,
            status='RUNNING',
            start_time=timezone.now(),
            executed_by=executed_by
        )

        # 获取套件中的请求
        suite_requests = test_suite.testsuiterequest_set.filter(enabled=True).order_by('order')

        execution.total_requests = suite_requests.count()
        execution.save()

        # 初始化临时变量管理器
        temp_vars = TemporaryVariables()

        results = []
        passed_count = 0
        failed_count = 0

        # 执行每个请求
        for suite_request in suite_requests:
            api_request = suite_request.request

            try:
                print(f"\n{'='*60}")
                print(f"[测试套件] 开始执行接口: {api_request.name}")
                print(f"[测试套件] 接口ID: {api_request.id}")
                print(f"[测试套件] 请求URL: {api_request.url}")
                print(f"{'='*60}")

                # 1. 执行等待时间（如果配置）
                wait_time = suite_request.wait_time or 0
                if wait_time > 0:
                    print(f"[测试套件] 等待 {wait_time} 秒...")
                    time.sleep(wait_time)

                # 2. 检查是否需要运行时用户输入
                user_inputs = {}
                if suite_request.user_inputs:
                    user_inputs = {**suite_request.user_inputs}
                    print(f"[测试套件] 配置的用户输入参数: {user_inputs}")

                # 如果需要运行时输入，暂停执行等待用户输入
                if suite_request.require_runtime_input:
                    print(f"[测试套件] 接口 {api_request.name} 需要运行时用户输入")
                    
                    # 返回需要用户输入的信息，暂停执行
                    return {
                        'success': False,
                        'need_user_input': True,
                        'execution_id': execution.id,
                        'current_request_id': api_request.id,
                        'current_request_name': api_request.name,
                        'input_config': suite_request.runtime_input_config,
                        'temp_vars': temp_vars.to_dict(),
                        'current_order': suite_request.order
                    }

                # 使用运行时输入覆盖配置的默认值
                if runtime_inputs:
                    request_runtime_inputs = runtime_inputs.get(str(api_request.id), {})
                    user_inputs.update(request_runtime_inputs)
                    print(f"[测试套件] 运行时输入覆盖后: {user_inputs}")

                # 3. 替换请求中的占位符
                # 需要先深拷贝 api_request 以避免修改原始对象
                from copy import deepcopy
                from .parameter_functions import replace_parameters, replace_parameters_in_dict
                modified_api_request = deepcopy(api_request)

                # 步骤1: 先处理参数函数（如 ${get_id()}）并写入临时变量
                # 导入参数函数模块
                from .parameter_functions import ParameterFunctions
                import re

                def _process_parameter_functions_and_store(text, temp_vars):
                    """处理参数函数并存储到临时变量"""
                    if not isinstance(text, str):
                        return text

                    def replace_func(match):
                        func_call = match.group(0)  # 完整的函数调用，如 ${get_id()}
                        func_name = match.group(1)  # 函数名，如 get_id

                        # 调用参数函数获取值
                        try:
                            # 动态调用函数
                            func = getattr(ParameterFunctions, func_name, None)
                            if func:
                                value = func()
                                # 将值存储到临时变量
                                temp_vars.set(func_name, value)
                                print(f"[临时变量] 参数函数 {func_name} 生成值: {value}，已存储到临时变量")
                                return str(value)
                        except Exception as e:
                            print(f"[临时变量] 参数函数 {func_name} 调用失败: {e}")
                        return func_call

                    # 匹配 ${函数名()} 格式
                    return re.sub(r'\$\{(\w+)\(\)\}', replace_func, text)

                def _process_parameter_functions_and_store_in_dict(data, temp_vars):
                    """递归处理字典中的参数函数"""
                    if isinstance(data, dict):
                        return {k: _process_parameter_functions_and_store_in_dict(v, temp_vars) for k, v in data.items()}
                    elif isinstance(data, list):
                        return [_process_parameter_functions_and_store_in_dict(item, temp_vars) for item in data]
                    elif isinstance(data, str):
                        return _process_parameter_functions_and_store(data, temp_vars)
                    else:
                        return data

                # 步骤2: 处理参数函数并存储到临时变量（不替换，只是生成值存储）
                print(f"[临时变量] 开始处理参数函数...")
                _process_parameter_functions_and_store_in_dict(modified_api_request.body.get('data', {}), temp_vars)
                _process_parameter_functions_and_store_in_dict(modified_api_request.params or {}, temp_vars)
                _process_parameter_functions_and_store(str(modified_api_request.headers or {}), temp_vars)

                # 步骤3: 替换临时变量占位符
                # 替换 URL
                modified_api_request.url = _replace_with_temp_variables(
                    modified_api_request.url or '',
                    temp_vars,
                    user_inputs
                )

                # 替换请求头
                if isinstance(modified_api_request.headers, list):
                    for header_item in modified_api_request.headers:
                        if header_item.get('enabled', True) and header_item.get('key'):
                            # 先处理参数函数
                            header_item['value'] = replace_parameters(header_item.get('value', ''))
                            # 再替换临时变量
                            header_item['value'] = _replace_with_temp_variables(
                                str(header_item['value']),
                                temp_vars,
                                user_inputs
                            )
                else:
                    for key, value in modified_api_request.headers.items():
                        # 先处理参数函数
                        value = replace_parameters(str(value))
                        # 再替换临时变量
                        modified_api_request.headers[key] = _replace_with_temp_variables(
                            str(value),
                            temp_vars,
                            user_inputs
                        )

                # 替换请求参数
                if modified_api_request.params:
                    for key, value in modified_api_request.params.items():
                        # 先处理参数函数
                        value = replace_parameters(str(value))
                        # 再替换临时变量
                        modified_api_request.params[key] = _replace_with_temp_variables(
                            str(value),
                            temp_vars,
                            user_inputs
                        )

                # 替换请求体
                if modified_api_request.body and modified_api_request.body.get('data'):
                    # 先处理参数函数
                    modified_api_request.body['data'] = replace_parameters_in_dict(modified_api_request.body['data'])
                    # 再替换临时变量
                    modified_api_request.body['data'] = _replace_with_temp_variables_in_dict(
                        modified_api_request.body['data'],
                        temp_vars,
                        user_inputs
                    )

                # 打印最终请求数据（调试用）
                print(f"[测试套件] 最终请求URL: {modified_api_request.url}")
                print(f"[测试套件] 最终请求头: {modified_api_request.headers}")
                print(f"[测试套件] 最终请求参数: {modified_api_request.params}")
                print(f"[测试套件] 最终请求体: {modified_api_request.body.get('data')}")

                # 4. 执行请求（传递临时变量管理器）
                request_result = execute_api_request(
                    modified_api_request,
                    environment,
                    executed_by,
                    temp_vars=temp_vars
                )

                if not request_result.get('success'):
                    # 请求执行失败
                    failed_count += 1
                    results.append({
                        'name': api_request.name,
                        'method': api_request.method,
                        'url': modified_api_request.url,
                        'passed': False,
                        'error': request_result.get('error', '请求执行失败'),
                        'assertions_results': []
                    })
                    continue

                # 5. 提取响应数据并存储到临时变量（简化逻辑）
                response_data = request_result.get('response_data', {})

                # 将完整的响应数据存储为临时变量
                # response.json.data.xxx 格式
                if response_data.get('json'):
                    print(f"[临时变量] 存储响应数据: response.json = {response_data['json']}")
                    temp_vars.set('response.json.data', response_data['json'])
                    
                    # 调试信息：显示存储的数据结构
                    if isinstance(response_data['json'], dict):
                        print(f"[临时变量] 可用字段: {list(response_data['json'].keys())}")
                        for key, value in response_data['json'].items():
                            print(f"[临时变量] - {key}: {value}")

                # 存储其他响应数据
                temp_vars.set('response.status_code', response_data.get('status_code'))
                temp_vars.set('response.headers', response_data.get('headers'))
                temp_vars.set('response.body', response_data.get('body'))

                # 存储请求数据（用于后续接口引用）
                if modified_api_request.params:
                    print(f"[临时变量] 存储请求参数: {modified_api_request.params}")
                    temp_vars.set('request.params', modified_api_request.params)

                if modified_api_request.body and modified_api_request.body.get('data'):
                    print(f"[临时变量] 存储请求体: {modified_api_request.body['data']}")
                    temp_vars.set('request.body.data', modified_api_request.body['data'])

                # 调试信息：显示当前所有临时变量
                print(f"[临时变量] 当前所有变量: {temp_vars.to_dict()}")

                # 打印当前所有临时变量
                print(f"[临时变量] 当前所有变量: {temp_vars.to_dict()}")

                # 6. 检查所有断言是否通过
                passed = True
                error_message = ''

                # 检查套件请求的断言
                for assertion in suite_request.assertions:
                    if assertion.get('type') == 'status_code':
                        expected = assertion.get('value')
                        if request_result.get('status_code') != expected:
                            passed = False
                            error_message = f'状态码断言失败: 期望 {expected}, 实际 {request_result.get("status_code")}'
                            break

                # 检查接口自身的断言
                if passed and request_result.get('assertions_results'):
                    for assertion_result in request_result['assertions_results']:
                        if not assertion_result.get('passed', True):
                            passed = False
                            error_message = f"断言失败: {assertion_result.get('name', '未命名断言')} - {assertion_result.get('error', '断言不通过')}"
                            break

                if passed:
                    passed_count += 1
                else:
                    failed_count += 1

                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': modified_api_request.url,
                    'status_code': request_result.get('status_code'),
                    'response_time': request_result.get('response_time'),
                    'passed': passed,
                    'error': error_message,
                    'assertions_results': request_result.get('assertions_results', [])
                })

            except Exception as e:
                import traceback
                failed_count += 1
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': api_request.url,
                    'passed': False,
                    'error': str(e),
                    'traceback': traceback.format_exc(),
                    'assertions_results': []
                })

        # 更新执行结果
        execution.end_time = timezone.now()
        execution.passed_requests = passed_count
        execution.failed_requests = failed_count
        execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
        execution.results = results
        execution.save()

        return {
            'success': True,
            'execution_id': execution.id,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'total_count': execution.total_requests,
            'results': results,
            'variables': temp_vars.to_dict()  # 返回所有临时变量供调试使用
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def execute_api_request(api_request, environment, executed_by, temp_vars=None):
    """
    执行单个API请求并返回结果
    包含完整的处理逻辑：
    1. 环境变量替换
    2. 参数化函数替换（如 ${get_id()}）
    3. 加密参数处理（${Enc(...)}）
    4. 签名生成
    5. 前置脚本执行
    6. HTTP 请求发送
    7. 断言验证
    8. 后置脚本执行
    9. 历史记录保存
    10. 提取请求和响应参数到临时变量

    参数:
        temp_vars: TemporaryVariables 实例，用于存储提取的变量
    """
    print(f"[DEBUG] ========== execute_api_request 被调用 ==========")
    print(f"[DEBUG] 接口ID: {api_request.id}, 接口名称: {api_request.name}")
    print(f"[DEBUG] 请求方法: {api_request.method}")
    print(f"[DEBUG] 启用签名: {api_request.enable_signature}")
    
    import requests
    import time
    from .parameter_functions import replace_parameters, replace_parameters_in_dict
    from .parameter_functions import extract_enc_placeholders, apply_encrypted_values
    from .parameter_functions import ParameterFunctions
    from .encrption_new import Encryption
    from .signature_utils import generate_signature, SignatureAlgorithm
    from .script_executor import ScriptExecutor
    from .models import SignatureConfig

    try:
        # 解析环境变量
        variables = {}
        if environment:
            variables.update(environment.variables)

        # 1. 替换URL中的变量和参数化函数
        url = _replace_variables(api_request.url or '', variables)
        url = replace_parameters(url)

        # 2. 准备请求头
        headers = {}
        if isinstance(api_request.headers, list):
            for header_item in api_request.headers:
                if header_item.get('enabled', True) and header_item.get('key'):
                    key = header_item['key']
                    value = _replace_variables(str(header_item.get('value', '')), variables)
                    value = replace_parameters(value)
                    headers[key] = value
        else:
            headers = api_request.headers.copy()
            for key, value in headers.items():
                value = _replace_variables(str(value), variables)
                value = replace_parameters(value)
                headers[key] = value

        # 3. 准备请求参数
        params = api_request.params.copy() if api_request.params else {}
        for key, value in params.items():
            value = _replace_variables(str(value), variables)
            params[key] = replace_parameters(value)

        # 4. 准备请求体
        body_data = None
        print(f"[DEBUG] 开始准备请求体")
        print(f"[DEBUG] api_request.body: {api_request.body}")
        print(f"[DEBUG] api_request.method: {api_request.method}")
        
        if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
            print(f"[DEBUG] 进入请求体处理分支")
            body_type = api_request.body.get('type') if isinstance(api_request.body, dict) else None
            print(f"[DEBUG] body type: {body_type}")
            
            if api_request.body.get('type') == 'json':
                print(f"[DEBUG] body type 是 json，开始处理")
                body_data = api_request.body.get('data', {})
                body_data = _replace_variables_in_dict(body_data, variables)
                body_data = replace_parameters_in_dict(body_data)

                # 调试：打印处理后的 body_data
                print(f"[DEBUG] 准备请求体完成，开始检查加密占位符")
                print(f"[DEBUG] body_data 类型: {type(body_data)}")
                if isinstance(body_data, dict):
                    print(f"[DEBUG] body_data 键: {list(body_data.keys())}")
                    # 检查 card_info 字段
                    if 'card_info' in body_data:
                        print(f"[DEBUG] card_info: {body_data['card_info']}")

                # 5. 处理加密参数 ${Enc(...)}
                enc_placeholders = extract_enc_placeholders(body_data)
                print(f"[DEBUG] extract_enc_placeholders 返回: {len(enc_placeholders) if enc_placeholders else 0} 个占位符")
                
                if enc_placeholders:
                    print(f"[加密] 检测到 {len(enc_placeholders)} 个加密占位符")
                    
                    # 获取加密公钥（优先从签名配置中获取）
                    encrypt_public_key = None
                    
                    # 尝试从接口的签名配置获取
                    signature_config = api_request.signature_config
                    if not signature_config:
                        # 尝试使用项目默认签名配置
                        project = api_request.collection.project
                        signature_config = SignatureConfig.objects.filter(
                            project=project,
                            is_default=True,
                            is_enabled=True
                        ).first()
                    
                    if signature_config:
                        encrypt_public_key = signature_config.rsa_encrypt_public_key
                        print(f"[加密] 从签名配置获取加密公钥: {'已配置' if encrypt_public_key else '未配置'}")

                    if encrypt_public_key:
                        print(f"[加密] 开始加密处理...")
                        enc = Encryption()
                        encrypted_map = []
                        for item in enc_placeholders:
                            try:
                                raw_value = item['raw_value']
                                target_length = item['target_length']
                                print(f"[加密] 处理字段: {item['path']}, 原始值: {raw_value}, 目标长度: {target_length}")
                                
                                # 使用 ParameterFunctions.enc 处理原始值
                                processed_value = ParameterFunctions.enc(raw_value, target_length)
                                print(f"[加密] 处理后的值: {processed_value}")
                                
                                # RSA 加密
                                encrypted_bytes = enc.rsa_long_encrypt(
                                    encrypt_public_key,
                                    processed_value.encode('utf-8')
                                )
                                encrypted_value = encrypted_bytes.decode('utf-8')
                                print(f"[加密] 加密后的值(前50字符): {encrypted_value[:50]}...")
                                
                                encrypted_map.append({
                                    'path': item['path'],
                                    'full_match': item['full_match'],
                                    'encrypted_value': encrypted_value
                                })
                            except Exception as e:
                                print(f"[加密] 加密失败: {str(e)}")
                                import traceback
                                traceback.print_exc()
                                # 加密失败时保持原值
                                encrypted_map.append({
                                    'path': item['path'],
                                    'full_match': item['full_match'],
                                    'encrypted_value': raw_value
                                })
                        
                        # 应用加密后的值
                        body_data = apply_encrypted_values(body_data, encrypted_map)
                        print(f"[加密] 加密处理完成")
                    else:
                        print(f"[加密] 警告: 检测到加密占位符但未配置加密公钥，跳过加密处理")
                        print(f"[加密] 请在项目的签名配置中配置 RSA 加密公钥")

            else:
                # 处理 raw 类型的请求体（JSON 字符串）
                print(f"[DEBUG] body type 是 raw，开始处理")
                raw_body_str = api_request.body.get('data', '')
                print(f"[DEBUG] raw body 长度: {len(raw_body_str)}")
                
                # 替换环境变量和参数函数
                raw_body_str = _replace_variables(raw_body_str, variables)
                raw_body_str = replace_parameters(raw_body_str)
                
                # 尝试解析为 JSON
                try:
                    body_data = json.loads(raw_body_str)
                    print(f"[DEBUG] raw body 解析为 JSON 成功")
                    print(f"[DEBUG] body_data 类型: {type(body_data)}")
                    
                    if isinstance(body_data, dict):
                        print(f"[DEBUG] body_data 键: {list(body_data.keys())}")
                        
                        # 5. 处理加密参数 ${Enc(...)}
                        enc_placeholders = extract_enc_placeholders(body_data)
                        print(f"[DEBUG] extract_enc_placeholders 返回: {len(enc_placeholders) if enc_placeholders else 0} 个占位符")
                        
                        if enc_placeholders:
                            print(f"[加密] 检测到 {len(enc_placeholders)} 个加密占位符")
                            
                            # 获取加密公钥
                            encrypt_public_key = None
                            signature_config = api_request.signature_config
                            if not signature_config:
                                project = api_request.collection.project
                                signature_config = SignatureConfig.objects.filter(
                                    project=project,
                                    is_default=True,
                                    is_enabled=True
                                ).first()
                            
                            if signature_config:
                                encrypt_public_key = signature_config.rsa_encrypt_public_key
                                print(f"[加密] 从签名配置获取加密公钥: {'已配置' if encrypt_public_key else '未配置'}")

                            if encrypt_public_key:
                                print(f"[加密] 开始加密处理...")
                                enc = Encryption()
                                encrypted_map = []
                                for item in enc_placeholders:
                                    try:
                                        raw_value = item['raw_value']
                                        target_length = item['target_length']
                                        print(f"[加密] 处理字段: {item['path']}, 原始值: {raw_value}, 目标长度: {target_length}")
                                        
                                        processed_value = ParameterFunctions.enc(raw_value, target_length)
                                        print(f"[加密] 处理后的值: {processed_value}")
                                        
                                        encrypted_bytes = enc.rsa_long_encrypt(
                                            encrypt_public_key,
                                            processed_value.encode('utf-8')
                                        )
                                        encrypted_value = encrypted_bytes.decode('utf-8')
                                        print(f"[加密] 加密后的值(前50字符): {encrypted_value[:50]}...")
                                        
                                        encrypted_map.append({
                                            'path': item['path'],
                                            'full_match': item['full_match'],
                                            'encrypted_value': encrypted_value
                                        })
                                    except Exception as e:
                                        print(f"[加密] 加密失败: {str(e)}")
                                        import traceback
                                        traceback.print_exc()
                                        encrypted_map.append({
                                            'path': item['path'],
                                            'full_match': item['full_match'],
                                            'encrypted_value': raw_value
                                        })
                                
                                body_data = apply_encrypted_values(body_data, encrypted_map)
                                print(f"[加密] 加密处理完成")
                            else:
                                print(f"[加密] 警告: 检测到加密占位符但未配置加密公钥")
                    
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] raw body 解析 JSON 失败: {str(e)}")
                    # 如果不是 JSON，保持字符串格式
                    body_data = raw_body_str

        # 6. 生成签名（如果启用）
        signature_config = None
        body_json_str_for_send = None

        if api_request.enable_signature:
            signature_config = api_request.signature_config
            if not signature_config:
                # 尝试使用项目默认签名配置
                project = api_request.collection.project
                signature_config = SignatureConfig.objects.filter(
                    project=project,
                    is_default=True,
                    is_enabled=True
                ).first()

            if signature_config and signature_config.is_enabled:
                # 准备额外签名参数
                extra_sign_params = {}
                if signature_config.extra_params:
                    for key, value in signature_config.extra_params.items():
                        resolved_value = _replace_variables(str(value), variables)
                        resolved_value = replace_parameters(resolved_value)
                        extra_sign_params[key] = resolved_value

                # 生成签名
                signature = generate_signature(
                    body=body_data,
                    algorithm=signature_config.algorithm,
                    secret_key=signature_config.secret_key if signature_config.secret_key else None,
                    extra_params=extra_sign_params,
                    rsa_private_key=signature_config.rsa_private_key if signature_config.rsa_private_key else None,
                    sm2_private_key=signature_config.sm2_private_key if signature_config.sm2_private_key else None,
                    sm2_mode=signature_config.sm2_mode if signature_config.sm2_mode else 'C1C2C3',
                    extra_params_in_sign=getattr(signature_config, 'extra_params_in_sign', False)
                )

                # 将签名添加到指定位置
                if signature_config.signature_location == 'header':
                    headers[signature_config.signature_field] = signature
                elif signature_config.signature_location == 'query':
                    params[signature_config.signature_field] = signature
                elif signature_config.signature_location == 'body' and isinstance(body_data, dict):
                    body_data[signature_config.signature_field] = signature

        # 7. 执行前置脚本
        if api_request.enable_pre_request_script and api_request.pre_request_script_ref:
            pre_script_context = {
                'request': {
                    'url': url,
                    'method': api_request.method,
                    'headers': headers,
                    'params': params,
                    'body': body_data,
                },
                'environment': variables,
                'variables': {}
            }

            result = ScriptExecutor.execute_script(
                script_type=api_request.pre_request_script_ref.script_type,
                script_content=api_request.pre_request_script_ref.content,
                context=pre_script_context
            )

            if result.success and result.modified_context:
                if 'request' in result.modified_context:
                    modified_request = result.modified_context['request']
                    if 'headers' in modified_request:
                        headers.update(modified_request['headers'])
                    if 'params' in modified_request:
                        params.update(modified_request['params'])
                    if 'body' in modified_request:
                        body_data = modified_request['body']
                    url = modified_request.get('url', url)

        # 8. 准备发送的 body（处理 RSA-MD5 的排序问题）
        body_to_send = body_data
        
        if signature_config and signature_config.is_enabled:
            is_rsa_md5 = signature_config.algorithm == SignatureAlgorithm.RSA_MD5
            if is_rsa_md5 and isinstance(body_to_send, dict):
                send_body = body_to_send.copy()
                if 'sign_type' in send_body:
                    send_body.pop('sign_type')
                # 使用默认格式（有空格），与签名计算时保持一致
                body_json_str_for_send = json.dumps(send_body, sort_keys=True)

        # 9. 发送HTTP请求
        start_time = time.time()
        if api_request.method.upper() in ['POST', 'PUT', 'PATCH'] and isinstance(body_to_send, dict):
            if body_json_str_for_send is not None:
                # RSA-MD5 签名时，使用排序后的 JSON 字符串（默认格式，有空格）
                response = requests.request(
                    method=api_request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=body_json_str_for_send.encode('utf-8'),
                    timeout=30
                )
            else:
                # 其他情况使用默认格式（有空格），保持与原有行为一致
                response = requests.request(
                    method=api_request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=json.dumps(body_to_send, ensure_ascii=False).encode('utf-8'),
                    timeout=30
                )
        else:
            response = requests.request(
                method=api_request.method,
                url=url,
                headers=headers,
                params=params,
                json=body_to_send,
                timeout=30
            )
        end_time = time.time()
        response_time = (end_time - start_time) * 1000

        # 10. 执行断言验证
        assertions = api_request.assertions or []
        for assertion in assertions:
            if assertion.get('type') == 'response_time':
                assertion['actual_time'] = response_time

        assertions_results = execute_assertions(response, assertions)

        # 11. 执行后置脚本
        if api_request.enable_post_request_script and api_request.post_request_script_ref:
            post_script_context = {
                'request': {
                    'url': url,
                    'method': api_request.method,
                    'headers': headers,
                    'params': params,
                    'body': body_data,
                },
                'response': {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'body': response.text,
                    'json': None,
                    'response_time': response_time
                },
                'environment': variables,
                'variables': {},
                'test': {
                    'passed': all(r.get('passed', False) for r in assertions_results) if assertions_results else True,
                    'results': assertions_results
                }
            }
            
            # 安全地提取 JSON 响应
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    post_script_context['response']['json'] = response.json()
            except:
                pass

            result = ScriptExecutor.execute_script(
                script_type=api_request.post_request_script_ref.script_type,
                script_content=api_request.post_request_script_ref.content,
                context=post_script_context
            )

        # 12. 提取请求和响应参数到临时变量（如果提供了 temp_vars）
        if temp_vars:
            # 准备请求和响应数据
            request_data_dict = {
                'url': url,
                'method': api_request.method,
                'headers': headers,
                'params': params,
                'body': body_data
            }

            response_data_dict = {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'body': response.text,
                'response_time': response_time
            }

            # 提取 JSON 响应
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    response_data_dict['json'] = response.json()
            except:
                response_data_dict['json'] = None

            # 使用 TemporaryVariables 的方法提取变量
            temp_vars.set_from_request_data(request_data_dict, response_data_dict)

        # 13. 保存请求历史
        response_json = None
        try:
            if response.headers.get('content-type', '').startswith('application/json'):
                response_json = response.json()
        except:
            pass
        
        history = RequestHistory.objects.create(
            request=api_request,
            environment=environment,
            request_data={
                'url': url,
                'method': api_request.method,
                'headers': headers,
                'params': params,
                'body': body_data
            },
            response_data={
                'headers': dict(response.headers),
                'body': response.text,
                'json': response_json
            },
            status_code=response.status_code,
            response_time=response_time,
            assertions_results=assertions_results,
            executed_by=executed_by
        )

        return {
            'success': True,
            'history_id': history.id,
            'status_code': response.status_code,
            'response_time': response_time,
            'assertions_results': assertions_results,
            'response_data': {
                'headers': dict(response.headers),
                'body': response.text,
                'json': response_json
            }
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def _replace_variables(text, variables):
    """替换文本中的变量"""
    if not isinstance(text, str):
        return text
    
    result = text
    for key, value in (variables or {}).items():
        if isinstance(value, dict):
            replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
        else:
            replacement = str(value) if value is not None else ''
        result = result.replace(f'{{{{{key}}}}}', replacement)
    return result


def _replace_variables_in_dict(data, variables):
    """递归替换字典中的变量"""
    if isinstance(data, dict):
        return {k: _replace_variables_in_dict(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_variables_in_dict(item, variables) for item in data]
    elif isinstance(data, str):
        return _replace_variables(data, variables)
    else:
        return data


def continue_test_suite_execution(execution_id, runtime_inputs, temp_vars_dict=None):
    """
    继续执行测试套件（在用户输入后）
    
    参数:
        execution_id: 执行记录ID
        runtime_inputs: 用户输入的参数
        temp_vars_dict: 临时变量字典
    """
    from .models import TestExecution, RequestHistory
    
    try:
        # 获取执行记录
        execution = TestExecution.objects.get(id=execution_id)
        test_suite = execution.test_suite
        
        # 恢复临时变量
        temp_vars = TemporaryVariables()
        if temp_vars_dict:
            for key, value in temp_vars_dict.items():
                temp_vars.set(key, value)
        
        # 获取套件中的请求，从当前位置继续执行
        suite_requests = test_suite.testsuiterequest_set.filter(enabled=True).order_by('order')
        
        # 找到当前需要执行的请求
        current_order = runtime_inputs.get('current_order', 0)
        remaining_requests = suite_requests.filter(order__gte=current_order)
        
        results = []
        passed_count = 0
        failed_count = 0
        
        # 继续执行剩余请求
        for suite_request in remaining_requests:
            api_request = suite_request.request
            
            try:
                print(f"\n{'='*60}")
                print(f"[测试套件] 继续执行接口: {api_request.name}")
                print(f"[测试套件] 接口ID: {api_request.id}")
                print(f"{'='*60}")
                
                # 获取用户输入参数
                user_inputs = {}
                if suite_request.user_inputs:
                    user_inputs = {**suite_request.user_inputs}
                
                # 使用运行时输入
                request_runtime_inputs = runtime_inputs.get(str(api_request.id), {})
                user_inputs.update(request_runtime_inputs)
                print(f"[测试套件] 用户输入参数: {user_inputs}")
                
                # 执行请求 - 使用和测试套件执行相同的逻辑
                from copy import deepcopy
                from .parameter_functions import replace_parameters, replace_parameters_in_dict
                modified_api_request = deepcopy(api_request)

                # 替换请求中的占位符
                # 步骤1: 先处理参数函数（如 ${get_id()}）并写入临时变量
                from .parameter_functions import ParameterFunctions
                import re

                print(f"[临时变量] 开始处理参数函数...")

                # 处理URL中的参数函数
                if modified_api_request.url:
                    modified_api_request.url = replace_parameters(modified_api_request.url)

                # 处理请求头中的参数函数
                if modified_api_request.headers:
                    modified_api_request.headers = replace_parameters_in_dict(modified_api_request.headers)

                # 处理URL参数中的参数函数
                if modified_api_request.params:
                    modified_api_request.params = replace_parameters_in_dict(modified_api_request.params)

                # 处理请求体中的参数函数
                if modified_api_request.body and modified_api_request.body.get('data'):
                    modified_api_request.body['data'] = replace_parameters_in_dict(modified_api_request.body['data'])

                # 步骤2: 处理临时变量替换（包括用户输入）
                print(f"[临时变量] 开始处理临时变量替换...")

                # 获取环境变量
                env_variables = {}
                if test_suite.environment and test_suite.environment.variables:
                    env_variables = test_suite.environment.variables

                # 处理URL中的环境变量和临时变量
                if modified_api_request.url:
                    # 先替换环境变量 {{xxx}}
                    modified_api_request.url = _replace_variables(modified_api_request.url, env_variables)
                    # 再替换临时变量 ${xxx}
                    modified_api_request.url = _replace_with_temp_variables(modified_api_request.url, temp_vars, user_inputs)
                    # 如果URL不是完整URL，添加环境变量中的base_url
                    if not modified_api_request.url.startswith(('http://', 'https://')):
                        base_url = ''
                        if test_suite.environment and test_suite.environment.variables:
                            base_url_value = test_suite.environment.variables.get('base_url', '')
                            # 处理字典格式的变量值
                            if isinstance(base_url_value, dict):
                                base_url = str(base_url_value.get('currentValue', '') or base_url_value.get('initialValue', ''))
                            else:
                                base_url = str(base_url_value) if base_url_value else ''
                        if base_url:
                            modified_api_request.url = base_url.rstrip('/') + '/' + modified_api_request.url.lstrip('/')

                # 处理请求头中的环境变量和临时变量
                if modified_api_request.headers:
                    modified_api_request.headers = _replace_variables_in_dict(modified_api_request.headers, env_variables)
                    modified_api_request.headers = _replace_with_temp_variables_in_dict(modified_api_request.headers, temp_vars, user_inputs)

                # 处理URL参数中的环境变量和临时变量
                if modified_api_request.params:
                    modified_api_request.params = _replace_variables_in_dict(modified_api_request.params, env_variables)
                    modified_api_request.params = _replace_with_temp_variables_in_dict(modified_api_request.params, temp_vars, user_inputs)

                # 处理请求体中的环境变量和临时变量
                if modified_api_request.body and modified_api_request.body.get('data'):
                    modified_api_request.body['data'] = _replace_variables_in_dict(modified_api_request.body['data'], env_variables)
                    modified_api_request.body['data'] = _replace_with_temp_variables_in_dict(modified_api_request.body['data'], temp_vars, user_inputs)

                print(f"[测试套件] 最终请求URL: {modified_api_request.url}")
                print(f"[测试套件] 最终请求头: {modified_api_request.headers}")
                print(f"[测试套件] 最终请求参数: {modified_api_request.params}")
                if modified_api_request.body and modified_api_request.body.get('data'):
                    print(f"[测试套件] 最终请求体: {modified_api_request.body['data']}")

                # 执行请求
                request_result = execute_api_request(
                    modified_api_request, 
                    test_suite.environment,
                    execution.executed_by,
                    temp_vars=temp_vars
                )
                
                if request_result.get('success'):
                    passed_count += 1
                    print(f"[测试套件] 接口 {api_request.name} 执行成功")
                    
                    # 更新临时变量
                    response_data = request_result.get('response_data', {})
                    if response_data.get('json'):
                        print(f"[临时变量] 存储响应数据: response.json = {response_data['json']}")
                        temp_vars.set('response.json.data', response_data['json'])
                        
                        # 调试信息：显示存储的数据结构
                        if isinstance(response_data['json'], dict):
                            print(f"[临时变量] 可用字段: {list(response_data['json'].keys())}")
                            for key, value in response_data['json'].items():
                                print(f"[临时变量] - {key}: {value}")

                    # 存储其他响应数据
                    temp_vars.set('response.status_code', response_data.get('status_code'))
                    temp_vars.set('response.headers', response_data.get('headers'))
                    temp_vars.set('response.body', response_data.get('body'))

                    # 调试信息：显示当前所有临时变量
                    print(f"[临时变量] 当前所有变量: {temp_vars.to_dict()}")
                    
                else:
                    failed_count += 1
                    print(f"[测试套件] 接口 {api_request.name} 执行失败: {request_result.get('error')}")
                
                results.append({
                    'request_id': api_request.id,
                    'request_name': api_request.name,
                    'success': request_result.get('success'),
                    'status_code': request_result.get('status_code'),
                    'response_time': request_result.get('response_time'),
                    'error': request_result.get('error'),
                    'history_id': request_result.get('history_id')
                })
                
                # 检查下一个请求是否需要用户输入
                next_requests = remaining_requests.filter(order__gt=suite_request.order)
                if next_requests.exists():
                    next_request = next_requests.first()
                    if next_request.require_runtime_input:
                        # 需要用户输入，暂停执行
                        return {
                            'success': False,
                            'need_user_input': True,
                            'execution_id': execution.id,
                            'current_request_id': next_request.request.id,
                            'current_request_name': next_request.request.name,
                            'input_config': next_request.runtime_input_config,
                            'temp_vars': temp_vars.to_dict(),
                            'current_order': next_request.order,
                            'partial_results': results
                        }
                
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                print(f"[测试套件] 接口 {api_request.name} 执行异常: {error_msg}")
                
                results.append({
                    'request_id': api_request.id,
                    'request_name': api_request.name,
                    'success': False,
                    'error': error_msg
                })
        
        # 更新执行记录
        execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
        execution.end_time = timezone.now()
        execution.passed_requests = passed_count
        execution.failed_requests = failed_count
        execution.save()
        
        return {
            'success': True,
            'execution_id': execution.id,
            'results': results,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'total_count': len(results)
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }

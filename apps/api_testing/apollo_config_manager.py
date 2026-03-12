"""
Apollo 配置管理工具
用于管理 Apollo 配置中心的配置项
"""
import requests
import json
from datetime import datetime
from typing import Dict, List, Optional


class ApolloConfigManager:
    """Apollo 配置管理器"""

    def __init__(self, portal_address: str):
        """
        初始化 Apollo 配置管理器

        Args:
            portal_address: Apollo 门户地址，例如 https://test-apollo.lianlianpay-inc.com
        """
        self.portal_address = portal_address.rstrip('/')
        self.session = requests.Session()

    def apollo_ids_login(
        self,
        username: str,
        password: str,
        target_url: str,
        appcode: str
    ) -> str:
        """
        Apollo IDs 登录流程

        Args:
            username: 用户名
            password: 密码
            target_url: 目标 URL
            appcode: 应用代码

        Returns:
            Cookie 字符串

        Raises:
            Exception: 登录失败时抛出异常
        """
        print("=" * 60)
        print("开始 Apollo IDs 登录")
        print("=" * 60)

        # 构建 IDS 登录 URL
        redirect_url = f"{target_url}/ids_login?callback={target_url}&appcode={appcode}"
        ids_get_url = f"https://ids-uat.lianlianpay.com/main/login?redirect_url={redirect_url}"

        # 初始化请求，获取 JSESSIONID
        init_response = self.session.get(
            ids_get_url,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://ids-uat.lianlianpay.com',
                'Referer': ids_get_url
            }
        )

        # 提取 JSESSIONID
        cookies = init_response.cookies.get_dict()
        if 'JSESSIONID' not in cookies:
            raise Exception("初始化请求未获取到 JSESSIONID")

        jsession_id = cookies['JSESSIONID']
        print(f"JSESSIONID: {jsession_id}")

        # 登录请求
        login_url = 'https://ids-uat.lianlianpay.com/user/login'
        login_data = {
            'username': username,
            'password': password,
            'verifyCode': '',
            'smsVerifyCode': ''
        }

        login_response = self.session.post(
            login_url,
            data=login_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://ids-uat.lianlianpay.com',
                'Referer': ids_get_url
            }
        )

        cookies = login_response.cookies.get_dict()
        if 'root_access_token' not in cookies:
            raise Exception("未找到 root_access_token")

        root_access_token = cookies['root_access_token']
        print("root_access_token 获取成功")

        # 导航请求
        nav_url = f"{target_url}/ids_login?callback={target_url}&appcode={appcode}&root_access_token={root_access_token}"
        nav_response = self.session.get(
            nav_url,
            headers={
                'Referer': 'https://ids-uat.lianlianpay.com/',
                'Host': 'gateway-test.lianlianpay-inc.com'
            },
            allow_redirects=False
        )

        # 提取 accesstoken
        location = nav_response.headers.get('Location', '')
        import re
        access_token_match = re.search(r'accesstoken=([^&]+)', location)
        if not access_token_match:
            raise Exception("未找到 accesstoken")

        access_token = access_token_match.group(1)
        print(f"accesstoken: {access_token}")

        # 获取最终 Cookie
        final_url = f"{target_url}/?accesstoken={access_token}"
        final_response = self.session.get(
            final_url,
            headers={
                'Referer': 'https://ids-uat.lianlianpay.com/',
                'Host': 'test-apollo.lianlianpay-inc.com'
            }
        )

        final_cookies = final_response.cookies.get_dict()
        if 'ids_token' not in final_cookies or 'JSESSIONID' not in final_cookies:
            raise Exception("未获取到最终 Cookie")

        ids_token = final_cookies['ids_token']
        final_jsession_id = final_cookies['JSESSIONID']

        cookie = f"ids_token={ids_token}; JSESSIONID={final_jsession_id}"
        print("Apollo IDS 登录成功\n")

        return cookie

    def apollo_login(
        self,
        apollo_username: str,
        apollo_password: str,
        apollo_host: str,
        ids_cookie: str
    ) -> str:
        """
        Apollo 登录

        Args:
            apollo_username: Apollo 用户名
            apollo_password: Apollo 密码
            apollo_host: Apollo 主机名
            ids_cookie: IDS Cookie

        Returns:
            Session Cookie 字符串

        Raises:
            Exception: 登录失败时抛出异常
        """
        print("=" * 60)
        print("开始 Apollo 登录")
        print("=" * 60)

        apollo_login_url = f"{self.portal_address}/signin"

        login_data = {
            'username': apollo_username,
            'password': apollo_password,
            'login-submit': '登录'
        }

        response = self.session.post(
            apollo_login_url,
            data=login_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Host': apollo_host,
                'Cookie': ids_cookie,
                'Referer': f"{self.portal_address}/signin"
            }
        )

        cookies = response.cookies.get_dict()
        if 'JSESSIONID' not in cookies:
            raise Exception("未找到 JSESSIONID")

        jsession_id = cookies['JSESSIONID']

        # 提取 ids_token
        ids_token_match = re.search(r'ids_token=([^;]+)', ids_cookie)
        ids_token = ids_token_match.group(1) if ids_token_match else ''

        session_cookie = f"JSESSIONID={jsession_id}; ids_token={ids_token}"
        print("Apollo 登录成功\n")

        return session_cookie

    def get_namespace_items(
        self,
        app_id: str,
        env: str,
        cluster_name: str,
        namespace_name: str,
        session_cookie: str
    ) -> List[Dict]:
        """
        获取命名空间的所有配置项

        Args:
            app_id: 应用 ID
            env: 环境
            cluster_name: 集群名称
            namespace_name: 命名空间名称
            session_cookie: Session Cookie

        Returns:
            配置项列表
        """
        url = (f"{self.portal_address}/apps/{app_id}/envs/{env}/clusters/"
                f"{cluster_name}/namespaces/{namespace_name}/items")

        response = self.session.get(
            url,
            headers={'Authorization': session_cookie}
        )

        if not response.ok:
            raise Exception(f"获取配置项失败: {response.status_code}")

        return response.json()

    def create_namespace_item(
        self,
        app_id: str,
        env: str,
        cluster_name: str,
        namespace_name: str,
        key: str,
        value: str,
        operator: str,
        session_cookie: str
    ):
        """
        创建配置项

        Args:
            app_id: 应用 ID
            env: 环境
            cluster_name: 集群名称
            namespace_name: 命名空间名称
            key: 配置键
            value: 配置值
            operator: 操作人
            session_cookie: Session Cookie

        Raises:
            Exception: 创建失败时抛出异常
        """
        url = (f"{self.portal_address}/apps/{app_id}/envs/{env}/clusters/"
                f"{cluster_name}/namespaces/{namespace_name}/item")

        data = {
            'key': key,
            'value': value,
            'dataChangeCreatedBy': operator,
            'comment': ''
        }

        response = self.session.post(
            url,
            json=data,
            headers={
                'Authorization': session_cookie,
                'Content-Type': 'application/json'
            }
        )

        if not response.ok:
            raise Exception(f"创建配置项失败: {response.status_code} - {response.text}")

        print(f"[{app_id}] 配置项 {key} 创建成功")

    def update_namespace_item(
        self,
        app_id: str,
        env: str,
        cluster_name: str,
        namespace_name: str,
        item_id: str,
        key: str,
        value: str,
        operator: str,
        namespace_id: str,
        comment: str = '',
        session_cookie: str = ''
    ):
        """
        更新配置项

        Args:
            app_id: 应用 ID
            env: 环境
            cluster_name: 集群名称
            namespace_name: 命名空间名称
            item_id: 配置项 ID
            key: 配置键
            value: 配置值
            operator: 操作人
            namespace_id: 命名空间 ID
            comment: 注释
            session_cookie: Session Cookie

        Raises:
            Exception: 更新失败时抛出异常
        """
        url = (f"{self.portal_address}/apps/{app_id}/envs/{env}/clusters/"
                f"{cluster_name}/namespaces/{namespace_name}/item")

        data = {
            'key': key,
            'value': value,
            'dataChangeLastModifiedBy': operator,
            'comment': comment,
            'id': item_id,
            'namespaceId': namespace_id
        }

        response = self.session.put(
            url,
            json=data,
            headers={
                'Authorization': session_cookie,
                'Content-Type': 'application/json;charset=utf-8'
            }
        )

        if not response.ok:
            raise Exception(f"更新配置项失败: {response.status_code} - {response.text}")

        print(f"[{app_id}] 配置项 {key} 更新成功")

    def release_config(
        self,
        app_id: str,
        env: str,
        cluster_name: str,
        namespace_name: str,
        session_cookie: str,
        is_emergency: bool = False
    ):
        """
        发布配置

        Args:
            app_id: 应用 ID
            env: 环境
            cluster_name: 集群名称
            namespace_name: 命名空间名称
            session_cookie: Session Cookie
            is_emergency: 是否紧急发布

        Raises:
            Exception: 发布失败时抛出异常
        """
        url = (f"{self.portal_address}/apps/{app_id}/envs/{env}/clusters/"
                f"{cluster_name}/namespaces/{namespace_name}/releases")

        # 生成发布标题
        now = datetime.now()
        release_title = (f"{now.year}{now.month:02d}{now.day:02d}"
                       f"{now.hour:02d}{now.minute:02d}{now.second:02d}-release")

        data = {
            'releaseTitle': release_title,
            'releaseComment': '',
            'isEmergencyPublish': is_emergency
        }

        response = self.session.post(
            url,
            json=data,
            headers={
                'Authorization': session_cookie,
                'Content-Type': 'application/json'
            }
        )

        if not response.ok:
            raise Exception(f"发布配置失败: {response.status_code} - {response.text}")

        print(f"[{app_id}] 配置发布成功 (标题: {release_title})\n")

    def update_config(
        self,
        app_id: str,
        env: str,
        cluster_name: str,
        namespace_name: str,
        key: str,
        value: str,
        operator: str,
        session_cookie: str
    ):
        """
        更新或创建配置项（自动检测）

        Args:
            app_id: 应用 ID
            env: 环境
            cluster_name: 集群名称
            namespace_name: 命名空间名称
            key: 配置键
            value: 配置值
            operator: 操作人
            session_cookie: Session Cookie

        Raises:
            Exception: 操作失败时抛出异常
        """
        # 获取所有配置项
        items = self.get_namespace_items(
            app_id, env, cluster_name, namespace_name, session_cookie
        )

        # 查找目标配置项
        target_item = None
        for item in items:
            if item.get('key') == key:
                target_item = item
                break

        if not target_item:
            # 创建新配置项
            self.create_namespace_item(
                app_id, env, cluster_name, namespace_name,
                key, value, operator, session_cookie
            )
        else:
            # 更新现有配置项
            self.update_namespace_item(
                app_id, env, cluster_name, namespace_name,
                target_item['id'], key, value, operator,
                target_item['namespaceId'],
                target_item.get('comment', ''),
                session_cookie
            )

        # 自动发布
        self.release_config(
            app_id, env, cluster_name, namespace_name, session_cookie
        )

    def batch_update_configs(
        self,
        operations: List[Dict],
        session_cookie: str
    ):
        """
        批量更新配置

        Args:
            operations: 操作列表，每个操作包含:
                - app_id: 应用 ID
                - env: 环境
                - cluster_name: 集群名称
                - namespace_name: 命名空间名称
                - key: 配置键
                - value: 配置值
                - operator: 操作人
            session_cookie: Session Cookie

        Raises:
            Exception: 操作失败时抛出异常
        """
        print(f"开始批量更新 {len(operations)} 个配置项\n")

        for i, op in enumerate(operations, 1):
            print(f"[{i}/{len(operations)}] 正在操作环境：{op['env']} 应用：{op['app_id']}")
            print(f"  配置键: {op['key']}")
            print(f"  配置值: {op['value']}")

            try:
                self.update_config(
                    op['app_id'],
                    op['env'],
                    op['cluster_name'],
                    op['namespace_name'],
                    op['key'],
                    op['value'],
                    op['operator'],
                    session_cookie
                )
                print(f"  ✓ 操作成功\n")
            except Exception as e:
                print(f"  ✗ 操作失败: {str(e)}\n")
                raise

        print("=" * 60)
        print("所有操作执行完毕")
        print("=" * 60)


# 预定义的环境配置
CONFIG_SETTINGS = {
    'CHANNELACCPLZB': {
        'portal_address': 'https://test-apollo.lianlianpay-inc.com',
        'clusterName': 'default',
        'appId': 'channel-accp-lzb',
        'env': 'TEST2',
        'namespaceName': 'application'
    },
    'CHANNELMPAY': {
        'portal_address': 'https://test-apollo.lianlianpay-inc.com',
        'clusterName': 'default',
        'appId': 'channel-mpay',
        'env': 'TEST2',
        'namespaceName': 'application'
    },
}


def main():
    """主执行函数 - 示例用法"""
    # 配置信息
    username = "wanghui"
    password = "123123"
    target_url = "https://test-apollo.lianlianpay-inc.com"
    appcode = "e387d5c4-1a05-4627-9d49-e8034a8f7ba7"
    apollo_username = "test"
    apollo_password = "test@123"
    apollo_host = "test-apollo.lianlianpay-inc.com"

    # 创建配置管理器
    portal_address = CONFIG_SETTINGS['CHANNELACCPLZB']['portal_address']
    manager = ApolloConfigManager(portal_address)

    try:
        # 1. IDS 登录
        ids_cookie = manager.apollo_ids_login(
            username, password, target_url, appcode
        )

        # 2. Apollo 登录
        session_cookie = manager.apollo_login(
            apollo_username, apollo_password, apollo_host, ids_cookie
        )

        # 3. 配置操作列表
        operations = [
            {
                'app_id': 'channel-accp-lzb',
                'env': 'TEST2',
                'cluster_name': 'default',
                'namespace_name': 'application',
                'key': 'payUrl',
                'value': 'http://10.19.17.6:8083/mock_func/llpay/mpayapi/bankcardprepay1',
                'operator': 'test'
            },
            {
                'app_id': 'channel-accp-lzb',
                'env': 'TEST2',
                'cluster_name': 'default',
                'namespace_name': 'application',
                'key': 'refundUrl',
                'value': 'http://10.19.17.6:8081/mock/llpay/traderapi/refund.htm',
                'operator': 'test'
            }
        ]

        # 4. 批量更新配置
        manager.batch_update_configs(operations, session_cookie)

    except Exception as e:
        print(f"\n执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

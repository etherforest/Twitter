import json
import time
import uuid

import primp
import requests
import platform
import hashlib
import base64
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from Crypto.Cipher import AES

# 常量
MARK = "a7f3e8d921c456b8e9f2a1d3c5b7e9f1a3d5c7b9e1f3a5d7c9b1e3f5a7"
HOST = "http://software.linglingjiu.shop"

BLOCK_SIZE = 16  # AES block size is 16 bytes
session = primp.AsyncClient(impersonate="chrome_131", verify=False)

class AESCipher:
    """AES加密解密类"""

    def __init__(self):
        """初始化AESCipher实例"""
        self.key = "hwWe/mS2`kvu8,z/".encode('utf-8')  # 密钥
        self.iv = "2312KndaagaVcw==".encode('utf-8')  # 偏移量

        # 确保密钥和IV长度正确
        if len(self.key) != 16:
            raise ValueError(f"密钥长度必须是16字节，当前长度: {len(self.key)}")
        if len(self.iv) != 16:
            raise ValueError(f"IV长度必须是16字节，当前长度: {len(self.iv)}")

    def pad(self, s: str) -> bytes:
        """
        补位函数 - 不足BLOCK_SIZE的补位

        Args:
            s: 待补位的字符串

        Returns:
            补位后的字节数组
        """
        data = s.encode('utf-8')
        padding = BLOCK_SIZE - len(data) % BLOCK_SIZE
        pad_text = bytes([padding] * padding)
        return data + pad_text

    def unpad(self, data: bytes) -> bytes:
        """
        去除补位函数

        Args:
            data: 待去除补位的字节数组

        Returns:
            去除补位后的字节数组

        Raises:
            ValueError: 当数据为空或补位无效时
        """
        length = len(data)
        if length == 0:
            raise ValueError("数据为空")

        padding = data[length - 1]
        if padding > length or padding > BLOCK_SIZE:
            raise ValueError("无效的补位")

        # 验证补位是否正确
        for i in range(length - padding, length):
            if data[i] != padding:
                raise ValueError("无效的补位")

        return data[:length - padding]

    def encrypt(self, text: str) -> str:
        """
        加密：先补位，再AES加密，后base64编码

        Args:
            text: 待加密的文本

        Returns:
            加密后的base64编码字符串
        """
        # 补位
        padded_text = self.pad(text)

        # 创建AES加密器
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

        # 加密
        encrypted = cipher.encrypt(padded_text)

        # base64编码
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt(self, encrypted_text: str) -> str:
        """
        解密：先base64解码，再AES解密，后取消补位

        Args:
            encrypted_text: 加密后的base64编码字符串

        Returns:
            解密后的原始文本
        """
        # base64解码
        encrypted = base64.b64decode(encrypted_text.encode('utf-8'))

        # 检查密文长度
        if len(encrypted) % BLOCK_SIZE != 0:
            raise ValueError("密文长度不是块大小的倍数")

        # 创建AES解密器
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

        # 解密
        decrypted = cipher.decrypt(encrypted)

        # 去除补位
        unpadded_data = self.unpad(decrypted)

        return unpadded_data.decode('utf-8')


def new_aes_cipher() -> AESCipher:
    """创建新的AESCipher实例"""
    return AESCipher()


def cbc_encrypter(data: str) -> str:
    """CBC加密器"""
    cipher = new_aes_cipher()
    return cipher.encrypt(data)


def cbc_decrypter(data: str) -> str:
    """CBC解密器"""
    cipher = new_aes_cipher()
    return cipher.decrypt(data)


def get_uuid() -> str:
    """
    生成基于机器的UUID

    Returns:
        机器唯一标识符
    """
    try:
        # 获取机器标识符
        machine_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
        return hashlib.md5(machine_info.encode()).hexdigest()
    except Exception:
        return str(uuid.uuid4())


def get_current_time() -> str:
    """
    获取当前时间的格式化字符串

    Returns:
        格式化的时间字符串
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Client:
    """客户端类"""

    def __init__(self, token: str, replace_device: str = ""):
        """
        初始化客户端

        Args:
            token: 认证令牌
            replace_device: 替换设备标识，默认为空字符串
        """
        self.token = token
        self.project = "warden"
        self.replace_device = replace_device if replace_device else "0"
        self.cipher = new_aes_cipher()

    async def sign_in(self) -> bool:
        """
        执行登录操作

        Returns:
            登录是否成功
        """
        try:
            # 构建请求参数
            params = {
                "token": self.token,
                "data": {
                    "replaceDevice": self.replace_device,
                    "project": self.project
                },
                "mark": MARK,
                "uuid": get_uuid(),
                "time": get_current_time()
            }

            # 转换为JSON
            params_json = json.dumps(params, separators=(',', ':'))

            # 加密参数 - 注意这里使用CBCEncrypter函数
            encrypted_params = cbc_encrypter(params_json)

            # 创建请求载荷
            request_payload = {"p": encrypted_params}

            # 发送HTTP POST请求
            response = await session.post(
                f"{HOST}/api/777",
                json=request_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                logging.error(f"HTTP error: {response.status_code}")
                return False

            # 读取响应
            body = response.content
            try:
                # 尝试解析为JSON字符串
                response_text = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                # 如果不是JSON字符串，直接使用原始数据
                response_text = body.decode('utf-8')

            # 解密响应 - 注意这里使用CBCDecrypter函数
            decrypted_text = cbc_decrypter(response_text)

            # 解析响应
            response_data = json.loads(decrypted_text)

            # 检查代码是否等于"777"
            return str(response_data.get("code")) == "777"

        except Exception as e:
            logging.error(f"Sign in error: {e}")
            return False

    async def update_time(self) -> bool:
        """
        执行更新时间操作

        Returns:
            更新是否成功
        """
        try:
            # 构建请求参数
            params = {
                "token": self.token,
                "data": {
                    "project": self.project
                },
                "mark": MARK,
                "uuid": get_uuid(),
                "time": get_current_time()
            }

            # 转换为JSON
            params_json = json.dumps(params, separators=(',', ':'))

            # 加密参数 - 注意这里使用cipher.encrypt方法
            encrypted_params = self.cipher.encrypt(params_json)

            # 创建请求载荷
            request_payload = {"p": encrypted_params}

            # 发送HTTP POST请求
            response = await session.post(
                f"{HOST}/api/888",
                json=request_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                logging.error(f"HTTP error: {response.status_code}")
                return False

            # 读取响应
            body = response.content
            try:
                # 尝试解析为JSON字符串
                response_text = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                # 如果不是JSON字符串，直接使用原始数据
                response_text = body.decode('utf-8')

            # 解密响应 - 注意这里使用CBCDecrypter函数
            decrypted_text = cbc_decrypter(response_text)

            # 解析响应
            response_data = json.loads(decrypted_text)

            # 检查代码是否等于"777"
            return str(response_data.get("code")) == "777"

        except Exception as e:
            logging.error(f"Update times error: {e}")
            return False


def new_client(token: str, replace_device: str = "") -> Client:
    """
    创建新的客户端实例

    Args:
        token: 认证令牌
        replace_device: 替换设备标识

    Returns:
        Client实例
    """
    return Client(token, replace_device)


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 创建客户端
    client = new_client("your_token_here", "0")

    try:
        # 执行登录
        if client.sign_in():
            print("✅ 登录成功")

            # 更新时间
            if client.update_time():
                print("✅ 更新时间成功")
            else:
                print("❌ 更新时间失败")
        else:
            print("❌ 登录失败")

    except Exception as e:
        print(f"❌ 运行出错: {e}")

    # 测试加密解密功能
    print("\n--- 测试加密解密功能 ---")
    test_text = '{"token":"test","data":{"project":"humanity"}}'

    try:
        encrypted = cbc_encrypter(test_text)
        print(f"加密: {test_text}")
        print(f"结果: {encrypted}")

        decrypted = cbc_decrypter(encrypted)
        print(f"解密: {decrypted}")

        if test_text == decrypted:
            print("✅ 加密解密测试成功")
        else:
            print("❌ 加密解密测试失败")

    except Exception as e:
        print(f"❌ 加密解密测试出错: {e}")
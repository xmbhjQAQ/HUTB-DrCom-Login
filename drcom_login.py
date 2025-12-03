#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
湖南工商大学 (HUTB) 校园网自动登录脚本 - OpenWrt Router V6
修复: "当前页面已超时,请重新刷新页面" 问题

关键修改:
1. queryPageSet 按 JS 一样使用 params= AES(JSON.stringify(...)) 的二次加密格式
2. 登录请求不再手拼 URL, 而是用 requests 的 params=, 自动对加密后的 params 做 URL 编码
3. login_method 从 page/loadConfig 中读取, 不再写死为 1
"""

import requests
import json
import base64
import time
import random
import socket
import struct
import fcntl
import sys
import subprocess

# ==================== 核心配置区域 ====================

USERNAME = " "   # 学号
PASSWORD = " "       # 密码
INTERFACE_NAME = "wan"    # OpenWrt 上 联网接口名, 比如 "wan" / "pppoe-wan"

# ====================================================

BASE_URL   = "https://portal.hutb.edu.cn:802" # Dr.COM 认证服务器地址，按照实际情况修改，具体获取方式请参考项目说明(待完善)
LOGIN_URL  = f"{BASE_URL}/eportal/portal/login"
CONFIG_URL = f"{BASE_URL}/eportal/portal/page/loadConfig"
QUERY_URL  = f"{BASE_URL}/eportal/portal/duodian/queryPageSet"
AES_KEY    = "5c1d5ad4dea0e8dd"   # a40.js 里的 AES key，按照实际情况修改，具体获取方式请参考项目说明(待完善)

# 忽略 SSL 警告
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
except ImportError:
    print("错误: 缺少加密库。请运行: pip3 install pycryptodome")
    sys.exit(1)


def get_ip_address(ifname: str):
    """获取指定网卡 IPv4 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(
            fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', ifname[:15].encode('utf-8'))
            )[20:24]
        )
    except Exception:
        return None


def aes_encrypt(data_str: str, key_str: str) -> str:
    """AES-128-ECB PKCS7 加密, 返回 Base64 文本 (兼容 CryptoJS 配置)"""
    key = key_str.encode('utf-8')
    data = data_str.encode('utf-8')
    cipher = AES.new(key, AES.MODE_ECB)
    pad_data = pad(data, AES.block_size)
    encrypted_bytes = cipher.encrypt(pad_data)
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def check_internet() -> bool:
    """简单 ping 百度测试是否已联网"""
    try:
        ret = subprocess.call(
            ["ping", "-c", "1", "-W", "3", "www.baidu.com"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return (ret == 0)
    except Exception:
        return False


def login() -> bool:
    sess = requests.Session()

    # 模拟浏览器 UA
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    sess.headers.update({
        "User-Agent": user_agent,
        "Referer"   : BASE_URL + "/"
    })

    # 1. 获取本机 IP
    wlan_user_ip = get_ip_address(INTERFACE_NAME)
    if not wlan_user_ip:
        print(f"错误: 无法获取接口 {INTERFACE_NAME} 的 IP 地址")
        return False
    print(f"当前 IP: {wlan_user_ip}")

    # 2. 预访问主页 (建立 Session, 拿 Cookie)
    try:
        sess.get(BASE_URL + "/", verify=False, timeout=5)
    except Exception:
        pass

    # --------------------------------------------------
    # 3. page/loadConfig 获取 rcn 和 login_method
    rcn = ""
    login_method = 1  # 默认值，死马当活马医

    try:
        print("步骤 1/3: 获取 rcn / login_method ...")

        ip_b64 = base64.b64encode(wlan_user_ip.encode()).decode()
        params = {
            "callback"    : "dr1001",
            "wlan_user_ip": ip_b64,
            "wlan_vlan_id": "1",
            "jsVersion"   : "4.2.1",
            "v"           : random.randint(1000, 9999),
            "lang"        : "zh"
        }
        res = sess.get(CONFIG_URL, params=params, verify=False, timeout=5)

        content = res.text
        start = content.find('{')
        end   = content.rfind('}') + 1
        if start != -1 and end > start:
            conf = json.loads(content[start:end])
            data = conf.get("data", {})
            rcn = data.get("rcn", "") or ""
            # 尽量还原前端的 page.login_method
            try:
                login_method = int(data.get("login_method", 1))
            except Exception:
                login_method = 1

            print(f">>> 获取成功 rcn: {rcn}, login_method: {login_method}")
        else:
            print("!!! loadConfig 返回内容异常, 解析不到 JSON")

    except Exception as e:
        print(f"获取 rcn 失败: {e}")

    if not rcn:
        # 实在没有就用你抓包时看到的备用值, 只能尽量靠近真实页面
        rcn = "L5GdwLmd"
        print(f"警告: 使用备用 rcn: {rcn}")

    # --------------------------------------------------
    # 4. 发送 queryPageSet 握手请求
    try:
        print("步骤 2/3: 发送 queryPageSet 握手 ...")

        inner = {
            "account"      : aes_encrypt(USERNAME, AES_KEY),           # term.account 不带前缀
            "wlan_user_ip" : aes_encrypt(wlan_user_ip, AES_KEY),
            "wlan_user_mac": aes_encrypt("000000000000", AES_KEY),
            "user_agent"   : aes_encrypt(user_agent.lower(), AES_KEY),
            "login_t"      : aes_encrypt("0", AES_KEY)                 # 对应 custom.login_t, PC 下基本为 0
        }

        inner_json = json.dumps(inner, separators=(",", ":"))
        enc_params = aes_encrypt(inner_json, AES_KEY)

        query_params = {
            "callback" : "dr1002",        # 回调名无所谓, 符合 drXXXX 即可
            "params"   : enc_params,
            "jsVersion": "4.2.1",
            "v"        : random.randint(1000, 9999),
            "lang"     : "zh"
        }

        # 用 params= 让 requests 自动对 params 做 URL 编码
        sess.get(QUERY_URL, params=query_params, verify=False, timeout=5)
        print(">>> 握手请求发送完毕")

    except Exception as e:
        print(f"握手请求异常(可能影响登录, 但尝试继续): {e}")

    # --------------------------------------------------
    # 5. 发送登录请求
    print("步骤 3/3: 发送登录请求 ...")

    payload = {
        "login_method" : login_method,           # 使用后台配置的 login_method
        "user_account" : f",0,{USERNAME}",       # 带前缀, 与页面一致
        "user_password": PASSWORD,
        "wlan_user_ip" : wlan_user_ip,
        "wlan_user_ipv6": "",
        "wlan_user_mac": "000000000000",
        "wlan_ac_ip"   : "",
        "wlan_ac_name" : "",
        "jsVersion"    : "4.2.1",
        "login_t"      : "0",
        "js_status"    : "0",
        "is_page"      : "1",
        "is_page_new"  : random.randint(1000, 9999),  # 和 JS 一样是 500~10500 的随机数, 这里无所谓
        "terminal_type": 1,          # PC
        "lang"         : "zh-cn",    # language.lang.toLowerCase()
        "rcn"          : rcn
    }

    json_data = json.dumps(payload, separators=(",", ":"))
    print("构造数据:", json_data)
    encrypted_params = aes_encrypt(json_data, AES_KEY)

    # 拼接登录请求参数
    login_params = {
        "callback" : "dr1005",              # 回调名无所谓, 符合 drXXXX 即可
        "params"   : encrypted_params,
        "jsVersion": "4.2.1",
        "v"        : random.randint(1000, 9999),
        "lang"     : "zh"                   # 与前端保持一致
    }

    try:
        res = sess.get(LOGIN_URL, params=login_params, verify=False, timeout=10)
        print("登录响应:", res.text)

        text = res.text
        if '"result":1' in text or '"result":true' in text or '"ok"' in text:
            print(">>> 登录成功！<<<")
            return True
        if "已在线" in text:
            print(">>> 设备已经在线，无需重复登录 <<<")
            return True

        print(">>> 登录失败, 原始返回前 200 字符:")
        print(text[:200])
        return False

    except Exception as e:
        print(f"登录请求异常: {e}")
        return False


if __name__ == "__main__":
    print("启动 V6 修正版脚本 ...")
    if not check_internet():
        print("状态: 离线 -> 执行登录")
        login()
    else:
        print("状态: 已在线")

    # 每分钟检查一次网络状态, 断线则重连
    while True:
        time.sleep(60)
        if not check_internet():
            print(f"[{time.strftime('%H:%M:%S')}] 网络断开, 尝试重连 ...")
            login()

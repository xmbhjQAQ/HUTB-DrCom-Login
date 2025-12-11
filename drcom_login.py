#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import base64
import time
import random
import socket
import struct
import fcntl
import sys
import re
import subprocess

# ==================== 核心配置区域 ====================

USERNAME = " "    # 账号
PASSWORD = " "        # 密码
INTERFACE_NAME = "wan"     # OpenWrt 上连外网的接口名，通常为wan或eth0

# ==================== 固定配置 ====================

BASE_URL   = "https://portal.hutb.edu.cn:802"
LOGIN_URL  = f"{BASE_URL}/eportal/portal/login"
CONFIG_URL = f"{BASE_URL}/eportal/portal/page/loadConfig"
QUERY_URL  = f"{BASE_URL}/eportal/portal/duodian/queryPageSet"

AES_KEY_DEFAULT = "5c1d5ad4dea0e8dd"  #  a40.js 默认 AES_KEY，后续会尝试自动提取以防止后台变更，正则见 fetch_aes_key()
AES_KEY = AES_KEY_DEFAULT

# 忽略证书告警
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
except ImportError:
    print("错误: 缺少加密库。请先安装 pycryptodome，例如: pip3 install pycryptodome(openwrt安装方法见readme)")
    sys.exit(1)


# ==================== 工具函数 ====================

def log(msg: str):
    """Log"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[drcom_login] {ts} {msg}"
    # 控制台输出
    print(line)
    # 系统日志输出
    try:
        subprocess.run(
            ["logger", "-t", "drcom_login", line],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def get_ip_address(ifname: str):
    """获取 IPv4 地址"""
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
    """加密 data_str，返回 base64 编码的密文"""
    key = key_str.encode('utf-8')
    data = data_str.encode('utf-8')
    cipher = AES.new(key, AES.MODE_ECB)
    pad_data = pad(data, AES.block_size)
    encrypted_bytes = cipher.encrypt(pad_data)
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def fetch_aes_key(sess: requests.Session, html_index: str = "") -> str:
    """
    从门户首页引用的 a40.js / a41.js 中自动提取 AES_KEY
    失败时回退到 AES_KEY_DEFAULT
    """
    # 1. 拿首页 HTML（如果调用者没传）
    try:
        if not html_index:
            resp = sess.get(BASE_URL + "/", verify=False, timeout=5)
            html_index = resp.text
    except Exception as e:
        log(f"获取门户首页失败: {e}")
        log("使用默认 AES_KEY")
        return AES_KEY_DEFAULT

    # 2. 在首页里找 a40.js / a41.js 的 <script src="..."> 引用
    m = re.search(r'<script[^>]+src="([^"]*a4[01]\.js[^"]*)"', html_index)
    if not m:
        log("未在首页中找到 a40.js/a41.js 脚本引用，使用默认 AES_KEY")
        return AES_KEY_DEFAULT

    js_src = m.group(1)
    # 处理各种可能的 src 写法：绝对 / 相对 / //xx
    if js_src.startswith("http://") or js_src.startswith("https://"):
        js_url = js_src
    elif js_src.startswith("//"):
        js_url = "https:" + js_src
    elif js_src.startswith("/"):
        js_url = BASE_URL + js_src
    else:
        js_url = BASE_URL + "/" + js_src.lstrip("./")

    # 3. 拉取 JS 文件内容
    try:
        resp_js = sess.get(js_url, verify=False, timeout=5)
        text_js = resp_js.text
    except Exception as e:
        log(f"获取 {js_url} 失败: {e}，使用默认 AES_KEY")
        return AES_KEY_DEFAULT

    # 4. 用正则匹配 Utf8.parse('XXXXXXXXXXXX')
    #   先匹配最典型的 CryptoJS.enc.Utf8.parse('16/32字节hex')
    m2 = re.search(r"Utf8\.parse\('([0-9a-fA-F]{16,32})'\)", text_js)
    if m2:
        key = m2.group(1)
        log(f"从 JS 自动提取 AES_KEY: {key}")
        return key

    # 兜底：匹配 _util.aes_en 里那一段（即便格式稍有变化也尽量能抓到） :contentReference[oaicite:1]{index=1}
    m2 = re.search(
        r"aes_en\s*:\s*function\s*\([^)]*\)\s*{[^}]*Utf8\.parse\('([^']{8,32})'\)",
        text_js,
        re.S
    )
    if m2:
        key = m2.group(1)
        log(f"从 _util.aes_en 中提取 AES_KEY: {key}")
        return key

    log("未能从 JS 中提取 AES_KEY，使用默认 AES_KEY")
    return AES_KEY_DEFAULT


def check_internet() -> bool:
    """ping个百度康康通不通喵"""
    try:
        ret = subprocess.call(
            ["ping", "-c", "1", "-W", "3", "www.baidu.com"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return ret == 0 # 0 表示通
    except Exception:
        return False


# ==================== 登录主流程 ====================

def login() -> bool:
    global AES_KEY

    sess = requests.Session()
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    sess.headers.update({
        "User-Agent": user_agent,
        "Referer": BASE_URL + "/"
    })

    # 1. 获取当前 IP
    wlan_user_ip = get_ip_address(INTERFACE_NAME)
    if not wlan_user_ip:
        log(f"错误: 无法获取接口 {INTERFACE_NAME} 的 IP")
        return False
    log(f"当前 IP: {wlan_user_ip}")

    # 2. 访问首页 + 自动获取 AES_KEY
    html_index = ""
    try:
        log("预访问门户首页 ...")
        r0 = sess.get(BASE_URL + "/", verify=False, timeout=5)
        html_index = r0.text
    except Exception as e:
        log(f"访问首页异常: {e}")

    AES_KEY = fetch_aes_key(sess, html_index)

    # 3. 调用 loadConfig 获取 rcn / login_method
    rcn = ""
    login_method = 1  # 默认值
    try:
        log("步骤 1/3: 获取 rcn / login_method ...")
        ip_b64 = base64.b64encode(wlan_user_ip.encode()).decode()
        params = {
            "callback": "dr1001",
            "wlan_user_ip": ip_b64,
            "wlan_vlan_id": "1",
            "jsVersion": "4.2.1",
            "v": random.randint(1000, 9999),
            "lang": "zh"
        }
        res = sess.get(CONFIG_URL, params=params, verify=False, timeout=5)
        content = res.text
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end > start:
            cfg = json.loads(content[start:end])
            data = cfg.get("data", {})
            rcn = data.get("rcn", "") or ""
            try:
                login_method = int(data.get("login_method", 1))
            except Exception:
                login_method = 1
            log(f">>> 获取成功 rcn: {rcn}, login_method: {login_method}")
        else:
            log("loadConfig 返回内容解析失败，使用默认 login_method=1")
    except Exception as e:
        log(f"获取 rcn/login_method 异常: {e}")

    if not rcn:
        rcn = "L5GdwLmd"
        log(f"警告: rcn 为空，使用备用 rcn: {rcn}")

    # 4. queryPageSet 握手（params = AES(JSON(inner))）
    try:
        log("步骤 2/3: 发送 queryPageSet 握手 ...")

        inner = {
            "account": aes_encrypt(USERNAME, AES_KEY),           # term.account（不带前缀）
            "wlan_user_ip": aes_encrypt(wlan_user_ip, AES_KEY),
            "wlan_user_mac": aes_encrypt("000000000000", AES_KEY),
            "user_agent": aes_encrypt(user_agent.lower(), AES_KEY),
            "login_t": aes_encrypt("0", AES_KEY)
        }
        inner_json = json.dumps(inner, separators=(",", ":"))
        enc_params = aes_encrypt(inner_json, AES_KEY)

        query_params = {
            "callback": "dr1002",
            "params": enc_params,
            "jsVersion": "4.2.1",
            "v": random.randint(1000, 9999),
            "lang": "zh"
        }
        sess.get(QUERY_URL, params=query_params, verify=False, timeout=5)
        log(">>> 握手请求发送完毕")
    except Exception as e:
        log(f"握手请求异常（可能影响登录，但继续尝试）: {e}")

    # 5. 最终登录请求
    log("步骤 3/3: 发送登录请求 ...")

    payload = {
        "login_method": login_method,
        "user_account": f",0,{USERNAME}",   # 前缀 + 账号（与网页一致） :contentReference[oaicite:2]{index=2}
        "user_password": PASSWORD,
        "wlan_user_ip": wlan_user_ip,
        "wlan_user_ipv6": "",
        "wlan_user_mac": "000000000000",
        "wlan_ac_ip": "",
        "wlan_ac_name": "",
        "jsVersion": "4.2.1",
        "login_t": "0",
        "js_status": "0",
        "is_page": "1",
        "is_page_new": random.randint(1000, 9999),
        "terminal_type": 1,          # PC
        "lang": "zh-cn",
        "rcn": rcn
    }

    json_data = json.dumps(payload, separators=(",", ":"))
    log("构造数据: " + json_data)
    encrypted_params = aes_encrypt(json_data, AES_KEY)

    login_params = {
        "callback": "dr1005",
        "params": encrypted_params,
        "jsVersion": "4.2.1",
        "v": random.randint(1000, 9999),
        "lang": "zh"
    }

    try:
        res = sess.get(LOGIN_URL, params=login_params, verify=False, timeout=10)
        text = res.text
        log("登录响应: " + text)

        if '"result":1' in text or "Portal协议认证成功" in text:
            log(">>> 登录成功！<<<")
            return True
        if "已在线" in text:
            log(">>> 设备已在线，无需重复登录 <<<")
            return True

        log(">>> 登录失败，返回内容前 200 字符: " + text[:200])
        return False

    except Exception as e:
        log(f"登录请求异常: {e}")
        return False


# ==================== 启动入口 ====================

if __name__ == "__main__":
    log("脚本启动 ...")
    if not check_internet():
        log("状态: 离线 -> 执行登录")
        login()
    else:
        log("状态: 已在线，无需登录")

    # 守护
    while True:
        time.sleep(60)
        if not check_internet():
            log("检测到网络断开，尝试重新登录 ...")
            login()

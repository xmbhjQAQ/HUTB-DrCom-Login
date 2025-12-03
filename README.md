-----

# HUTB 校园网自动登录脚本 (OpenWrt / Python)

这是一个专为 **湖南工商大学 (HUTB)** 校园网设计的自动登录脚本，适用于部署在 **OpenWrt 路由器** 或其他 Linux 环境上。

针对 Dr.COM 网页认证（Dr.COM Web Portal）进行了深度适配，**修复了旧版脚本常见的“当前页面已超时，请重新刷新页面”报错问题**。

## ✨ 主要特性

  * **AES 加密适配**：完美模拟浏览器端的 JS 加密逻辑（AES-128-ECB），解决服务端校验失败的问题。
  * **动态握手**：实现了 `queryPageSet` 握手流程，自动获取 `rcn` 和 `login_method`，而非硬编码。
  * **自动掉线重连**：脚本内置守护进程模式，每 60 秒检测一次网络，断网自动重连。
  * **OpenWrt 友好**：专为路由器环境优化，自动获取 WAN 口 IP。

## 🛠️ 环境要求

  * **硬件**：运行 OpenWrt 的路由器。
  * **软件**：
      * Python 3.x
      * 必需库：`requests`, `pycryptodome` (需通过 opkg 安装)

## 🚀 安装与使用

### 1\. 安装依赖

在 OpenWrt 环境下，建议直接使用 `opkg` 安装预编译的 Python 包，避免使用 `pip` 编译安装时报错。

通过 SSH 登录你的路由器，执行以下命令：

```bash
opkg update

# 安装 Python3 主程序及 pip (pip 可用于安装纯 Python 库，但本脚本主要依赖建议用 opkg)
opkg install python3 python3-pip

# 安装 requests 库和加密库 (OpenWrt 官方源通常已收录)
opkg install python3-requests python3-cryptodome python3-cryptodome-src
```

> **注意**：如果你的软件源中找不到 `python3-requests`，也可以尝试用 `pip3 install requests`，但 `cryptodome` 必须用 opkg 安装。

### 2\. 下载与配置

下载本项目中的 `drcom_login.py`，并使用文本编辑器（如 `vim` 或 `nano`）打开文件，修改顶部的 **配置区域**：

```python
# ==================== 核心配置区域 ====================

USERNAME = "你的学号"        # <--- 请在此处填入你的学号
PASSWORD = "你的校园网密码"   # <--- 请在此处填入你的密码
INTERFACE_NAME = "wan"      # OpenWrt 上连接外网的接口名
                            # 通常为 "wan" 或 "pppoe-wan"，如果不确定，请在终端输入 ifconfig 查看

# ====================================================
```

### 3\. 运行测试

在终端中直接运行脚本进行测试：

```bash
python3 drcom_login.py
```

  * 如果显示 **“\>\>\> 登录成功！\<\<\<”** 或 **“状态: 已在线”**，说明配置正确。
  * 如果提示 `ImportError`，请检查第一步的 `opkg install` 是否执行成功。

## ⚙️ 如何在 OpenWrt 设置开机自启

为了让路由器重启后自动登录，并将脚本在后台持续运行（守护进程模式），建议将其加入 `rc.local`。

1.  将脚本放置在稳定目录，例如 `/root/drcom_login.py`。

2.  编辑启动文件：

    ```bash
    vi /etc/rc.local
    ```

3.  在 `exit 0` 之前添加以下命令（注意修改路径）：

    ```bash
    # 延迟 30 秒等待网络接口准备好，然后后台运行脚本
    sleep 30 && python3 /root/drcom_login.py > /dev/null 2>&1 &
    ```

## 📝 常见问题 (FAQ)

**Q: 为什么提示 `ImportError: No module named Crypto`?**
A: 说明加密库未安装成功。OpenWrt 下请务必运行 `opkg install python3-cryptodome python3-cryptodome-src`。不要使用 pip 安装 `pycrypto`（已废弃）。

**Q: 如何查看我的 `INTERFACE_NAME` 是什么?**
A: 在路由器 SSH 中输入 `ifconfig`。找到那个分配了校园网内网 IP（通常是 `10.x.x.x` 或 `172.x.x.x`）的接口名称。

**Q: 脚本报错 "当前页面已超时"?**
A: 请确保路由器系统时间准确（NTP 同步正常），因为加密参数中包含时间相关的随机验证机制。

## ⚠️ 免责声明

本脚本仅供学习交流使用，请勿用于非法用途。使用本脚本产生的任何后果由用户自行承担。

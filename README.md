# HUTB-DrCom-Login (湖南工商大学校园网 Dr.COM 自动登录脚本)

这是一个用于 OpenWrt / LEDE (或任何支持 `sh` 和 `cron` 的 Linux 环境) 的校园网自动登录和断线重连脚本。

本项目基于湖南工商大学（HUTB）的 Dr.COM (Eportal) 认证系统编写，理论上稍加修改也可用于其他使用相同认证系统的高校。

## 🚀 功能

本项目包含两个脚本：

1.  **`drcom_login.sh`**:
    * 主登录脚本。
    * 它会等待网络接口就绪，自动获取 WAN 口的 IP 地址。
    * 使用 `curl` 命令模拟浏览器登录请求，完成校园网认证。

2.  **`check_network.sh`**:
    * 网络检测与自动重连脚本。
    * 通过 `ping` 命令检测公网连接是否正常。
    * 如果检测到网络断开（`ping` 失败），它会自动调用 `drcom_login.sh` 尝试重新登录。

## 🔧 如何使用

### 1. 关键：修改配置！

在上传到路由器之前，你**必须**修改 `drcom_login.sh` 文件。

打开 `drcom_login.sh`，找到并修改以下变量为**你自己的信息**：

```sh
# 你的账号和密码
USER_ACCOUNT="YOUR_USERNAME"
USER_PASSWORD="YOUR_PASSWORD"
```

### 2. (可选) 分析你自己的登录请求

本项目中的 `LOGIN_URL` 和 `curl` 命令头（Headers）是针对特定环境抓取的。**它可能不适用于你，或者在会话（Session）过期后失效**。

特别是 `curl` 命令中的 `-b 'JSESSIONID=...'` 这一行，它包含了一个硬编码的会话 ID。你**很可能需要删除这一行**，或者使用你自己的浏览器开发者工具 (F12) 重新抓取一次登录请求，并替换 `drcom_login.sh` 中的整个 `curl` 命令。

### 3. 上传脚本到路由器

将 `drcom_login.sh` 和 `check_network.sh` 上传到你的 OpenWrt 路由器（例如 `/etc/` 目录下）。

通过 SSH 连接到你的路由器，并给予这两个脚本执行权限：

```sh
chmod +x /etc/drcom_login.sh
chmod +x /etc/check_network.sh
```

### 4. 设置定时任务 (Cron Job)

为了实现自动检测和重连，我们需要使用 `cron` 定时执行 `check_network.sh`。

1.  在 OpenWrt 的 "系统" -> "计划任务" (Scheduled Tasks) 中添加一行：

    ```sh
    # 每5分钟检测一次网络连接
    */5 * * * * /etc/check_network.sh
    ```

2.  或者，通过 SSH 运行 `crontab -e` 并添加上面那一行。

保存后，`cron` 服务会每5分钟自动运行一次检测脚本，如果网络断开，它会自动尝试重新登录。

## ⚠️ 注意事项

1.  **安全风险**: 你的校园网密码将以**明文**形式存储在 `drcom_login.sh` 脚本中。请确保你的路由器固件是安全的，并修改了默认的 SSH/网页管理密码。
2.  **接口名称**: `drcom_login.sh` 默认从 `wan` 接口获取 IP。如果你的 OpenWrt 拨号接口名称不同（例如 `pppoe-wan` 或 `eth0.2`），请自行修改脚本中的 `ifconfig wan` 为你对应的接口名称。
3.  **检测目标**: `check_network.sh` 默认 `ping www.baidu.com` 来检测网络。你可以修改为任何你认为可靠的 IP 或域名，例如 `223.5.5.5` (阿里云 DNS) 或 `114.114.114.114`。

##  disclaimer

本项目仅供学习和技术交流使用。

作者不对使用本脚本可能导致的任何问题（包括但不限于账户被盗、网络计费异常等）负责。

请在完全理解脚本功能并自行承担风险的前提下使用。

#!/bin/sh

# 开机等待获取,各位看着改吧
sleep 10

# 获取路由器WAN口的IP地址
# 注意：'wan' 是你拨号或获取校园网IP的接口名称，通常是 'wan' 或 'eth0.2' 等
# 你可以通过 ifconfig 命令查看哪个接口获取到了校园网的IP地址
WAN_IP=$(ifconfig wan | grep 'inet addr' | cut -d ':' -f 2 | cut -d ' ' -f 1)

# 没ip就退出脚本
if [ -z "$WAN_IP" ]; then
    echo "未获取到 WAN IP 地址，退出脚本。"
    exit 1
fi

# 你的账号和密码
USER_ACCOUNT="YOUR_STUDENT_ID"
USER_PASSWORD="YOU_PASSWORD"

# 构建登录URL
LOGIN_URL="https://portal.hutb.edu.cn:802/eportal/portal/login?callback=dr1003&login_method=1&user_account=%2C0%2C${USER_ACCOUNT}&user_password=${USER_PASSWORD}&wlan_user_ip=${WAN_IP}&wlan_user_ipv6=&wlan_user_mac=000000000000&wlan_ac_ip=&wlan_ac_name=&jsVersion=4.1.3&terminal_type=1&lang=zh-cn&v=9845&lang=zh"


curl "${LOGIN_URL}" \
-H 'accept: */*' \
-H 'accept-language: zh-CN,zh;q=0.9,en-GB;q=0.8,en-US;q=0.7,en;q=0.6,sk;q=0.5' \
-b 'JSESSIONID=3CF6FF937C959B453662808A80E95477' \
-H 'referer: https://portal.hutb.edu.cn/' \
-H 'sec-ch-ua: "Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"' \
-H 'sec-ch-ua-mobile: ?0' \
-H 'sec-ch-ua-platform: "Windows"' \
-H 'sec-fetch-dest: script' \
-H 'sec-fetch-mode: no-cors' \
-H 'sec-fetch-site: same-site' \
-H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0'

echo "登录请求已发送，IP地址: ${WAN_IP}"

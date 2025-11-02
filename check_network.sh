#!/bin/sh

# ping to check alive
ping -c 3 -W 5 www.baidu.com > /dev/null

# verify respond
if [ $? -ne 0 ]; then
    echo "网络连接断开，正在尝试重新登录..."
    /etc/drcom_login.sh
else
    echo "网络连接正常。"
fi

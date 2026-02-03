#!/bin/bash

# Docker Hub 登录脚本
# 使用方法: ./docker-login.sh

echo "请输入你的 Docker Hub 用户名:"
read username

echo "请输入你的 Docker Hub 密码:"
read -s password

echo "$password" | docker login -u "$username" --password-stdin

if [ $? -eq 0 ]; then
    echo "✅ 登录成功！"
    echo "现在可以开始构建镜像了"
else
    echo "❌ 登录失败，请检查用户名和密码"
fi

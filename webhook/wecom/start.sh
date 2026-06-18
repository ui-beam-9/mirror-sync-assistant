#!/bin/bash

# 企业微信 Webhook 服务器启动脚本

set -e

echo "=========================================="
echo "  企业微信 Webhook 服务器启动脚本"
echo "=========================================="
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: 未找到 .env 文件"
    echo "请复制 .env.example 为 .env 并填写配置信息："
    echo "  cp .env.example .env"
    exit 1
fi

echo "✅ 找到配置文件 .env"
echo ""

# 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: 未安装 Docker Compose"
    echo "请先安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker 和 Docker Compose 已安装"
echo ""

# 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down

# 构建镜像
echo "🔨 构建 Docker 镜像..."
docker-compose build

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

echo ""
echo "=========================================="
echo "  ✅ 服务启动成功！"
echo "=========================================="
echo ""
echo "📊 查看服务状态："
echo "  docker-compose ps"
echo ""
echo "📋 查看日志："
echo "  docker-compose logs -f"
echo ""
echo "🔍 健康检查："
echo "  curl http://localhost:8080/health"
echo ""
echo "🛑 停止服务："
echo "  docker-compose down"
echo ""

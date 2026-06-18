#!/bin/bash

# Docker 镜像同步 Webhook 服务器快速部署脚本
# 支持企业微信和 Lark 两种平台
# 支持两种部署方式：Docker 镜像部署 和 服务器直接部署

set -e

echo "🚀 Docker 镜像同步 Webhook 服务器快速部署"
echo "============================================="
echo ""

# 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: 未安装 Docker Compose"
    exit 1
fi

# ==========================================
# 选择平台
# ==========================================
echo "📱 请选择要部署的 Webhook 服务器类型："
echo "1) 企业微信（WeCom）"
echo "2) Lark（飞书）"
echo ""
read -p "请输入选项 (1 或 2): " -n 1 -r PLATFORM
echo ""
echo ""

case "$PLATFORM" in
    1)
        PLATFORM_NAME="企业微信（WeCom）"
        PLATFORM_DIR="webhook/wecom"
        PLATFORM_IMAGE="swr.cn-east-3.myhuaweicloud.com/ui_beam-images/wecom-webhook-server:latest"
        DEFAULT_DIR="/opt/webhook-wecom"
        ;;
    2)
        PLATFORM_NAME="Lark（飞书）"
        PLATFORM_DIR="webhook/lark"
        PLATFORM_IMAGE="swr.cn-east-3.myhuaweicloud.com/ui_beam-images/lark-webhook-server:latest"
        DEFAULT_DIR="/opt/webhook-lark"
        ;;
    *)
        echo "❌ 无效的选项，请输入 1 或 2"
        exit 1
        ;;
esac

echo "✅ 已选择: $PLATFORM_NAME"
echo ""

# 检测是否有运行中的容器
RUNNING_CONTAINER=$(docker ps --filter "ancestor=$PLATFORM_IMAGE" --format "{{.ID}}" 2>/dev/null || true)

if [ -n "$RUNNING_CONTAINER" ]; then
    echo "🔍 检测到运行中的 $PLATFORM_NAME Webhook 服务器"
    CONTAINER_NAME=$(docker ps --filter "id=$RUNNING_CONTAINER" --format "{{.Names}}")
    CONTAINER_DIR=$(docker inspect --format='{{range .Mounts}}{{if eq .Destination "/app"}}{{.Source}}{{end}}{{end}}' "$RUNNING_CONTAINER" 2>/dev/null || echo "未知")
    
    echo "容器名称: $CONTAINER_NAME"
    echo "容器 ID: $RUNNING_CONTAINER"
    if [ "$CONTAINER_DIR" != "未知" ] && [ -n "$CONTAINER_DIR" ]; then
        DEPLOY_DIR=$(dirname "$CONTAINER_DIR" 2>/dev/null || echo "未知")
        echo "部署目录: $DEPLOY_DIR"
    fi
    echo ""
    echo "请选择操作："
    echo "1) 更新镜像（拉取最新镜像并重启）"
    echo "2) 重新安装（删除现有部署，重新配置）"
    echo "3) 停止并删除（停止服务并删除容器）"
    echo "4) 取消"
    echo ""
    read -p "请输入选项 (1/2/3/4): " -n 1 -r MANAGE_MODE
    echo ""
    echo ""
    
    case "$MANAGE_MODE" in
        1)
            # 更新镜像
            echo "🔄 更新镜像中..."
            echo ""
            
            # 查找 docker-compose.yml 所在目录
            COMPOSE_DIR=""
            for dir in "$DEFAULT_DIR" "$HOME/$PLATFORM_DIR" "./$PLATFORM_DIR"; do
                if [ -f "$dir/docker-compose.yml" ]; then
                    COMPOSE_DIR="$dir"
                    break
                fi
            done
            
            if [ -z "$COMPOSE_DIR" ]; then
                echo "❌ 错误: 未找到 docker-compose.yml 文件"
                echo "请手动进入部署目录执行以下命令："
                echo "  docker-compose pull"
                echo "  docker-compose up -d"
                exit 1
            fi
            
            cd "$COMPOSE_DIR"
            echo "📂 工作目录: $COMPOSE_DIR"
            echo ""
            
            echo "📥 拉取最新镜像..."
            docker-compose pull
            
            echo "🔄 重启服务..."
            docker-compose up -d
            
            echo ""
            echo "✅ 更新完成！"
            echo ""
            echo "📝 查看日志："
            echo "   cd $COMPOSE_DIR"
            echo "   docker-compose logs -f"
            echo ""
            exit 0
            ;;
        2)
            # 重新安装
            echo "🔄 重新安装..."
            echo ""
            
            # 查找 docker-compose.yml 所在目录
            COMPOSE_DIR=""
            for dir in "$DEFAULT_DIR" "$HOME/$PLATFORM_DIR" "./$PLATFORM_DIR"; do
                if [ -f "$dir/docker-compose.yml" ]; then
                    COMPOSE_DIR="$dir"
                    break
                fi
            done
            
            if [ -n "$COMPOSE_DIR" ]; then
                echo "📂 找到现有部署: $COMPOSE_DIR"
                read -p "是否备份现有配置? (Y/n): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                    BACKUP_FILE="${COMPOSE_DIR}/.env.backup.$(date +%Y%m%d_%H%M%S)"
                    cp "${COMPOSE_DIR}/.env" "$BACKUP_FILE" 2>/dev/null && echo "✅ 配置已备份到: $BACKUP_FILE" || echo "⚠️  备份失败"
                fi
                echo ""
                cd "$COMPOSE_DIR"
                docker-compose down
                cd ..
                rm -rf "$COMPOSE_DIR"
            fi
            
            echo "继续全新安装流程..."
            echo ""
            # 继续执行后续的安装流程
            ;;
        3)
            # 停止并删除
            echo "🛑 停止并删除服务..."
            echo ""
            
            # 查找 docker-compose.yml 所在目录
            COMPOSE_DIR=""
            for dir in "$DEFAULT_DIR" "$HOME/$PLATFORM_DIR" "./$PLATFORM_DIR"; do
                if [ -f "$dir/docker-compose.yml" ]; then
                    COMPOSE_DIR="$dir"
                    break
                fi
            done
            
            if [ -n "$COMPOSE_DIR" ]; then
                cd "$COMPOSE_DIR"
                docker-compose down
                echo "✅ 服务已停止"
                echo ""
                read -p "是否删除部署目录? (y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    cd ..
                    rm -rf "$COMPOSE_DIR"
                    echo "✅ 部署目录已删除: $COMPOSE_DIR"
                fi
            else
                docker stop "$RUNNING_CONTAINER"
                docker rm "$RUNNING_CONTAINER"
                echo "✅ 容器已停止并删除"
            fi
            echo ""
            exit 0
            ;;
        4)
            echo "已取消"
            exit 0
            ;;
        *)
            echo "❌ 无效的选项"
            exit 1
            ;;
    esac
fi

# 选择安装目录
echo "📂 设置安装目录"
echo "默认安装目录: $DEFAULT_DIR"
echo ""
read -p "请输入安装目录（直接回车使用默认）: " CUSTOM_DIR
echo ""

if [ -z "$CUSTOM_DIR" ]; then
    BASE_DIR="$DEFAULT_DIR"
else
    BASE_DIR="$CUSTOM_DIR"
fi

echo "✅ 安装目录: $BASE_DIR"
echo ""

# 检查目录权限
PARENT_DIR=$(dirname "$BASE_DIR")
if [ ! -w "$PARENT_DIR" ] 2>/dev/null; then
    echo "⚠️  警告: $PARENT_DIR 需要管理员权限"
    echo "请使用 sudo 运行此脚本，或选择其他目录"
    echo ""
    read -p "是否使用 sudo 继续? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
    echo ""
    # 使用 sudo 重新运行脚本
    exec sudo bash "$0"
fi

# 选择部署方式
echo "请选择部署方式："
echo "1) Docker 镜像部署（推荐，无需下载项目代码）"
echo "2) 服务器直接部署（需要克隆项目，适合自定义代码）"
echo ""
read -p "请输入选项 (1 或 2): " -n 1 -r DEPLOY_MODE
echo ""
echo ""

if [[ "$DEPLOY_MODE" == "1" ]]; then
    # ==========================================
    # 方式一：Docker 镜像部署
    # ==========================================
    echo "📦 方式一：使用预构建 Docker 镜像部署"
    echo "========================================="
    echo ""
    
    if [ -d "$BASE_DIR" ]; then
        echo "⚠️  目录 $BASE_DIR 已存在"
        read -p "是否覆盖? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
        rm -rf "$BASE_DIR"
    fi
    
    mkdir -p "$BASE_DIR"
    cd "$BASE_DIR"
    
    echo "📥 下载配置文件..."
    
    GITHUB_BASE="https://raw.githubusercontent.com/ui-beam-9/mirror-sync-assistant/main"
    
    # 下载 .env.example 和 docker-compose.yml
    if command -v curl &> /dev/null; then
        curl -sS -O "${GITHUB_BASE}/${PLATFORM_DIR}/.env.example"
        curl -sS -O "${GITHUB_BASE}/${PLATFORM_DIR}/docker-compose.yml"
    elif command -v wget &> /dev/null; then
        wget -q "${GITHUB_BASE}/${PLATFORM_DIR}/.env.example"
        wget -q "${GITHUB_BASE}/${PLATFORM_DIR}/docker-compose.yml"
    else
        echo "❌ 错误: 未安装 curl 或 wget"
        exit 1
    fi
    
    # 重命名 .env.example
    mv .env.example .env
    
    echo "✅ 配置文件下载完成！"
    echo ""
    echo "📝 下一步操作："
    echo "1. 编辑 .env 文件，填写你的 $PLATFORM_NAME 配置"
    echo "   cd $BASE_DIR"
    echo "   nano .env"
    echo ""
    echo "2. 启动服务（会自动拉取预构建镜像）"
    echo "   docker-compose up -d"
    echo ""
    echo "3. 查看日志"
    echo "   docker-compose logs -f"
    echo ""
    
elif [[ "$DEPLOY_MODE" == "2" ]]; then
    # ==========================================
    # 方式二：服务器直接部署
    # ==========================================
    echo "🔧 方式二：服务器直接部署"
    echo "========================================="
    echo ""
    
    # 检查 git
    if ! command -v git &> /dev/null; then
        echo "❌ 错误: 未安装 Git"
        exit 1
    fi
    
    if [ -d "$BASE_DIR" ]; then
        echo "⚠️  目录 $BASE_DIR 已存在"
        read -p "是否覆盖? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
        rm -rf "$BASE_DIR"
    fi
    
    echo "📥 克隆项目..."
    # 使用临时目录克隆
    TEMP_DIR=$(mktemp -d)
    git clone https://github.com/ui-beam-9/mirror-sync-assistant.git "$TEMP_DIR"
    
    # 复制平台目录到目标位置
    mkdir -p "$(dirname "$BASE_DIR")"
    cp -r "$TEMP_DIR/$PLATFORM_DIR" "$BASE_DIR"
    
    # 清理临时目录
    rm -rf "$TEMP_DIR"
    
    cd "$BASE_DIR"
    
    echo "📁 创建配置文件..."
    cp .env.example .env
    
    echo "✅ 项目克隆完成！"
    echo ""
    echo "📝 下一步操作："
    echo "1. 编辑 .env 文件，填写你的 $PLATFORM_NAME 配置"
    echo "   cd $BASE_DIR"
    echo "   nano .env"
    echo ""
    echo "2. 如需本地构建，编辑 docker-compose.yml"
    echo "   nano docker-compose.yml"
    echo "   注释: image: $PLATFORM_IMAGE"
    echo "   取消注释: # build: ."
    echo ""
    echo "3. 启动服务"
    echo "   docker-compose up -d"
    echo ""
    echo "4. 查看日志"
    echo "   docker-compose logs -f"
    echo ""
    
else
    echo "❌ 无效的选项，请输入 1 或 2"
    exit 1
fi

echo "🎉 $PLATFORM_NAME Webhook 服务器部署准备完成！"
echo ""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
企业微信消息接收服务器
接收企业微信应用消息，自动在 GitHub 创建镜像同步 Issues
"""

import os
import sys
import hashlib
import json
import time
import logging
import platform
from flask import Flask, request, jsonify
import requests
from WXBizMsgCrypt3 import WXBizMsgCrypt
import xmltodict

# ====================================
# 彩色日志配置
# ====================================

# ANSI 颜色码
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    # 前景色
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'

# Windows 控制台需要启用 ANSI 支持
if platform.system() == 'Windows':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# 彩色日志级别映射
LEVEL_COLORS = {
    logging.DEBUG:    Colors.GRAY,
    logging.INFO:     Colors.CYAN,
    logging.WARNING:  Colors.YELLOW,
    logging.ERROR:    Colors.RED,
    logging.CRITICAL: Colors.RED + Colors.BOLD,
}

LEVEL_NAMES = {
    logging.DEBUG:    'DEBUG',
    logging.INFO:     'INFO',
    logging.WARNING:  'WARN',
    logging.ERROR:    'ERROR',
    logging.CRITICAL: 'FATAL',
}

LEVEL_SYMBOLS = {
    logging.DEBUG:    '',
    logging.INFO:     '',
    logging.WARNING:  '',
    logging.ERROR:    '',
    logging.CRITICAL: '',
}


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    def format(self, record):
        # 时间戳（灰色）
        ts = time.strftime('%H:%M:%S', time.localtime(record.created))
        ts_str = f'{Colors.GRAY}{ts}{Colors.RESET}'

        # 级别标签
        color = LEVEL_COLORS.get(record.levelno, Colors.RESET)
        symbol = LEVEL_SYMBOLS.get(record.levelno, '')
        level_name = LEVEL_NAMES.get(record.levelno, record.levelname)
        level_str = f'{color}{level_name:5s}{Colors.RESET}'

        # 模块名
        module_str = f'{Colors.DIM}{record.name}{Colors.RESET}'

        # 消息内容（根据级别着色）
        msg_color = Colors.GREEN if record.levelno <= logging.INFO else color
        msg = f'{msg_color}{record.getMessage()}{Colors.RESET}'

        return f'{ts_str} {level_str} {module_str} │ {msg}'


class ColoredWerkzeugFormatter(logging.Formatter):
    """werkzeug 请求日志格式化器"""

    def format(self, record):
        ts = time.strftime('%H:%M:%S', time.localtime(record.created))
        msg = record.getMessage()

        # 解析 HTTP 状态码来着色
        import re
        status_match = re.search(r'"\s+(\d{3})\s', msg)
        if status_match:
            code = int(status_match.group(1))
            if code < 300:
                color = Colors.GREEN
            elif code < 400:
                color = Colors.CYAN
            elif code < 500:
                color = Colors.YELLOW
            else:
                color = Colors.RED
            # 给状态码着色
            msg = msg.replace(f' {code} ', f' {color}{code}{Colors.RESET} ')

        return f'{Colors.GRAY}{ts}{Colors.RESET} {Colors.DIM}HTTP{Colors.RESET} │ {msg}'


# 创建 handler
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(ColoredFormatter())
_stderr_handler.setLevel(logging.DEBUG)

# werkzeug handler
_werkzeug_handler = logging.StreamHandler(sys.stderr)
_werkzeug_handler.setFormatter(ColoredWerkzeugFormatter())
_werkzeug_handler.setLevel(logging.DEBUG)

# 配置 root logger
logging.basicConfig(level=logging.INFO, handlers=[_stderr_handler], force=True)
logging.getLogger().handlers = [_stderr_handler]

# 配置 werkzeug
_wz = logging.getLogger('werkzeug')
_wz.setLevel(logging.INFO)
_wz.propagate = False
_wz.handlers = [_werkzeug_handler]

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ====================================
# 事件去重缓存（基于消息内容）
# ====================================
import threading
from collections import OrderedDict


class MessageDeduplicator:
    """基于消息内容（规范化镜像名）的短时间窗口去重器"""
    def __init__(self, ttl_seconds=5):
        self._cache = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def is_duplicate(self, image_name):
        """同一规范化镜像名在 TTL 内再次出现视为重复"""
        if not image_name:
            return False
        now = time.time()
        with self._lock:
            if image_name in self._cache and now - self._cache[image_name] < self._ttl:
                return True
            self._cache[image_name] = now
            return False


_message_dedup = MessageDeduplicator(ttl_seconds=5)

# 从环境变量读取配置
WECOM_TOKEN = os.environ.get('WECOM_TOKEN', '')
WECOM_ENCODING_AES_KEY = os.environ.get('WECOM_ENCODING_AES_KEY', '')
WECOM_CORP_ID = os.environ.get('WECOM_CORP_ID', '')
WECOM_AGENT_ID = os.environ.get('WECOM_AGENT_ID', '')
WECOM_SECRET = os.environ.get('WECOM_SECRET', '')
WECOM_API_BASE = os.environ.get('WECOM_API_BASE', 'https://qyapi.weixin.qq.com')  # 企业微信 API 地址
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')  # 格式: owner/repo
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')  # Webhook 验证密钥

# 验证必需的环境变量
required_vars = [WECOM_TOKEN, WECOM_ENCODING_AES_KEY, WECOM_CORP_ID, WECOM_AGENT_ID, WECOM_SECRET, GITHUB_TOKEN, GITHUB_REPO, WEBHOOK_SECRET]
if not all(required_vars):
    logger.error("缺少必需的环境变量！")
    logger.error(f"WECOM_TOKEN: {'已设置' if WECOM_TOKEN else '未设置'}")
    logger.error(f"WECOM_ENCODING_AES_KEY: {'已设置' if WECOM_ENCODING_AES_KEY else '未设置'}")
    logger.error(f"WECOM_CORP_ID: {'已设置' if WECOM_CORP_ID else '未设置'}")
    logger.error(f"WECOM_AGENT_ID: {'已设置' if WECOM_AGENT_ID else '未设置'}")
    logger.error(f"WECOM_SECRET: {'已设置' if WECOM_SECRET else '未设置'}")
    logger.error(f"GITHUB_TOKEN: {'已设置' if GITHUB_TOKEN else '未设置'}")
    logger.error(f"GITHUB_REPO: {'已设置' if GITHUB_REPO else '未设置'}")
    logger.error(f"WEBHOOK_SECRET: {'已设置' if WEBHOOK_SECRET else '未设置'}")

# 初始化消息加解密类
wxcpt = WXBizMsgCrypt(WECOM_TOKEN, WECOM_ENCODING_AES_KEY, WECOM_CORP_ID)

# Access Token 缓存
access_token_cache = {
    'token': None,
    'expires_at': 0
}


def get_access_token():
    """获取企业微信 Access Token"""
    try:
        # 检查缓存
        if access_token_cache['token'] and time.time() < access_token_cache['expires_at']:
            return access_token_cache['token']
        
        # 获取新 token
        url = f"{WECOM_API_BASE}/cgi-bin/gettoken"
        params = {
            'corpid': WECOM_CORP_ID,
            'corpsecret': WECOM_SECRET
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('errcode') == 0:
            token = data.get('access_token')
            expires_in = data.get('expires_in', 7200)
            
            # 缓存 token（提前 5 分钟过期）
            access_token_cache['token'] = token
            access_token_cache['expires_at'] = time.time() + expires_in - 300
            
            logger.info("成功获取 Access Token")
            return token
        else:
            logger.error(f"获取 Access Token 失败: {data.get('errmsg')}")
            return None
            
    except Exception as e:
        logger.error(f"获取 Access Token 异常: {str(e)}")
        return None


def send_wecom_message(user_id, content):
    """发送企业微信消息"""
    try:
        access_token = get_access_token()
        if not access_token:
            logger.error("无法获取 Access Token，消息发送失败")
            return False
        
        url = f"{WECOM_API_BASE}/cgi-bin/message/send?access_token={access_token}"
        
        data = {
            "touser": user_id,
            "msgtype": "text",
            "agentid": int(WECOM_AGENT_ID),
            "text": {
                "content": content
            },
            "safe": 0
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get('errcode') == 0:
            logger.info(f"成功发送企业微信消息给用户: {user_id}")
            return True
        else:
            logger.error(f"发送企业微信消息失败: {result.get('errmsg')}")
            return False
            
    except Exception as e:
        logger.error(f"发送企业微信消息异常: {str(e)}")
        return False


def verify_signature(signature, timestamp, nonce, echo_str):
    """验证企业微信签名"""
    try:
        ret, reply_echo_str = wxcpt.VerifyURL(signature, timestamp, nonce, echo_str)
        if ret == 0:
            logger.info("URL 验证成功")
            return reply_echo_str.decode('utf-8')
        else:
            logger.error(f"URL 验证失败，错误码: {ret}")
            return None
    except Exception as e:
        logger.error(f"验证签名异常: {str(e)}")
        return None


def decrypt_message(msg_signature, timestamp, nonce, post_data):
    """解密企业微信消息"""
    try:
        ret, xml_content = wxcpt.DecryptMsg(post_data, msg_signature, timestamp, nonce)
        if ret == 0:
            logger.info("消息解密成功")
            return xml_content.decode('utf-8')
        else:
            logger.error(f"消息解密失败，错误码: {ret}")
            return None
    except Exception as e:
        logger.error(f"解密消息异常: {str(e)}")
        return None


def parse_message(xml_content):
    """解析 XML 消息"""
    try:
        msg_dict = xmltodict.parse(xml_content)
        return msg_dict.get('xml', {})
    except Exception as e:
        logger.error(f"解析消息异常: {str(e)}")
        return None


def create_github_issue(image_name, user_id=None):
    """在 GitHub 创建 Issue，并发送企业微信通知"""
    try:
        # 清理镜像名称，去除空格
        image_name = image_name.strip()
        
        # 验证镜像名称格式
        if not image_name:
            logger.error("镜像名称为空")
            if user_id:
                send_wecom_message(user_id, "镜像同步失败：镜像名称为空")
            return False
        
        logger.info(f"准备创建 GitHub Issue: {image_name}")
        
        # GitHub API 地址
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
        
        # 请求头
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json"
        }
        
        # Issue 数据（将用户ID保存到body中，用于后续通知）
        issue_data = {
            "title": image_name,
            "labels": ["sync image"],
            "body": (
                f"来自企业微信的镜像同步请求\n\n"
                f"镜像名称: `{image_name}`\n"
                f"提交时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"---\n"
                f"<!-- wecom_user_id: {user_id} -->"
            )
        }
        
        # 发送请求
        response = requests.post(api_url, headers=headers, json=issue_data, timeout=10)
        
        if response.status_code == 201:
            issue_data = response.json()
            issue_url = issue_data.get('html_url', '')
            issue_number = issue_data.get('number', '')
            logger.info(f"Issue 创建成功: {issue_url}")
            
            # 发送企业微信通知
            if user_id:
                notification = (f"镜像同步任务已创建\n\n"
                             f"镜像名称: {image_name}\n"
                             f"Issue 编号: #{issue_number}\n"
                             f"状态: 等待同步\n\n"
                             f"查看详情: {issue_url}")
                send_wecom_message(user_id, notification)
            
            return True
        else:
            logger.error(f"Issue 创建失败: {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            
            # 发送失败通知
            if user_id:
                send_wecom_message(user_id, f"镜像同步失败\n\n镜像名称: {image_name}\n原因: GitHub Issue 创建失败")
            
            return False
            
    except Exception as e:
        logger.error(f"创建 Issue 异常: {str(e)}")
        
        # 发送异常通知
        if user_id:
            send_wecom_message(user_id, f"镜像同步失败\n\n镜像名称: {image_name}\n原因: 系统异常")
        
        return False


def validate_image_name(content):
    """
    验证并规范化镜像名称。

    返回: (image_name, error_message, hint_text)
      - 成功: ("docker.io/library/nginx:latest", None, "自动补仓库: docker.io")
      - 失败: (None, "错误提示", None)
    """
    content = content.strip()

    if not content:
        return None, "镜像名称不能为空\n\n正确格式: <命名空间>/<镜像名>:<标签>\n示例:\n  library/nginx:latest\n  jxxghp/moviepilot-v2:latest\n  docker.io/library/nginx:latest", None

    # 去除协议前缀
    content = content.split('://')[-1]

    # 保存原始输入
    user_input = content

    # 分离镜像名和标签
    tag = 'latest'
    if ':' in content:
        parts = content.rsplit(':', 1)
        if len(parts) == 2 and parts[1]:
            content = parts[0]
            tag = parts[1]

    # 验证标签格式
    import re
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$', tag):
        return None, f"标签格式无效: {tag}\n\n标签仅允许字母、数字、下划线、点、连字符，最多128字符", None

    # 拆分路径
    path_parts = content.split('/')

    # 验证每个路径片段
    for part in path_parts:
        if not part:
            return None, f"镜像路径格式无效: 路径中存在空的片段\n\n输入: {content}", None
        if not re.match(r'^[a-z0-9][a-z0-9_.-]*$', part):
            return None, f"路径片段格式无效: \"{part}\"\n\n镜像路径仅允许小写字母、数字、分隔符(_.-)", None

    # 检查是否有命名空间 + 镜像名
    if len(path_parts) == 1:
        return None, (f"缺少命名空间\n\n"
                     f"输入了 \"{content}\"，只有镜像名，缺少命名空间\n\n"
                     f"正确格式: <命名空间>/<镜像名>:<标签>\n"
                     f"例如: library/{path_parts[0]}:latest"), None
    elif len(path_parts) == 2:
        known_registries = ['docker.io', 'gcr.io', 'quay.io', 'k8s.gcr.io',
                            'ghcr.io', 'registry.k8s.io', 'mcr.microsoft.com',
                            'nvcr.io', 'public.ecr.aws']
        if path_parts[0] in known_registries:
            return None, (f"缺少镜像名\n\n"
                         f"输入了 \"{content}\"，注册表 + 命名空间已填，缺少镜像名\n\n"
                         f"注册表: {path_parts[0]}\n"
                         f"命名空间: {path_parts[1]}\n\n"
                         f"正确格式: {content}/<镜像名>:<标签>\n"
                         f"例如: {content}/nginx:latest"), None
        # namespace/image 格式，自动补充 docker.io/
        content = f"docker.io/{content}"

    image_name = f"{content}:{tag}"

    # 生成补全提示
    user_parts = user_input.split('/')
    has_registry = '.' in user_parts[0] if user_parts else False
    miss_registry = not has_registry
    miss_tag = ':' not in user_input

    if miss_registry and miss_tag:
        hint_text = "由于你没有指定仓库名和标签将使用默认的仓库docker.io和标签latest"
    elif miss_registry:
        hint_text = f"由于你没有指定仓库名将使用默认的仓库docker.io,如: docker.io/{user_input}"
    elif miss_tag:
        hint_text = f"由于你没有指定标签将使用默认的标签latest,如: {user_input}:latest"
    else:
        hint_text = ""

    return image_name, None, hint_text


def get_user_id_from_issue(issue_number):
    """从 Issue body 中提取用户 ID"""
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            issue_data = response.json()
            body = issue_data.get('body', '')
            
            # 从 body 中提取用户 ID
            import re
            match = re.search(r'<!-- wecom_user_id: (\S+) -->', body)
            if match:
                user_id = match.group(1)
                logger.info(f"从 Issue #{issue_number} 提取到用户 ID: {user_id}")
                return user_id
            else:
                logger.warning(f"Issue #{issue_number} 中未找到用户 ID")
                return None
        else:
            logger.error(f"获取 Issue 失败: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"提取用户 ID 异常: {str(e)}")
        return None


@app.route('/wecom/callback', methods=['GET', 'POST'])
def wecom_callback():
    """企业微信回调接口"""
    try:
        if request.method == 'GET':
            # URL 验证
            msg_signature = request.args.get('msg_signature', '')
            timestamp = request.args.get('timestamp', '')
            nonce = request.args.get('nonce', '')
            echostr = request.args.get('echostr', '')
            
            logger.info(f"收到 URL 验证请求: timestamp={timestamp}, nonce={nonce}")
            
            reply_echostr = verify_signature(msg_signature, timestamp, nonce, echostr)
            if reply_echostr:
                return reply_echostr
            else:
                return "验证失败", 403
        
        elif request.method == 'POST':
            # 接收消息
            msg_signature = request.args.get('msg_signature', '')
            timestamp = request.args.get('timestamp', '')
            nonce = request.args.get('nonce', '')
            
            logger.info(f"收到消息推送: timestamp={timestamp}, nonce={nonce}")
            
            # 解密消息
            post_data = request.data
            xml_content = decrypt_message(msg_signature, timestamp, nonce, post_data)
            
            if not xml_content:
                return "解密失败", 403
            
            # 解析消息
            msg = parse_message(xml_content)
            if not msg:
                return "解析失败", 400
            
            logger.info(f"消息内容: {json.dumps(msg, ensure_ascii=False, indent=2)}")
            
            # 获取消息类型和内容
            msg_type = msg.get('MsgType', '')
            
            if msg_type == 'text':
                # 文本消息
                content = msg.get('Content', '')
                from_user = msg.get('FromUserName', '')
                
                logger.info(f"收到文本消息 from {from_user}: {content}")
                
                # 验证镜像名称
                image_name, error_msg, hint = validate_image_name(content)
                
                if error_msg:
                    # 格式验证失败，回复错误提示
                    logger.warning(f"镜像名称验证失败: {error_msg}")
                    reply = f"镜像名称格式错误\n\n{error_msg}"
                    send_wecom_message(from_user, reply)
                    return "success"
                
                # 消息去重（5秒窗口内相同镜像名只处理一次）
                if _message_dedup.is_duplicate(image_name):
                    logger.info(f"跳过重复消息: image_name={image_name}")
                    return "success"
                
                # 创建 GitHub Issue 并发送企业微信通知
                success = create_github_issue(image_name, user_id=from_user)
                
                if success:
                    logger.info(f"成功处理镜像同步请求: {image_name}")
                else:
                    logger.error(f"处理镜像同步请求失败: {image_name}")
                
                return "success"
            
            elif msg_type == 'event':
                # 事件消息
                event = msg.get('Event', '')
                logger.info(f"收到事件: {event}")
                return "success"
            
            else:
                logger.warning(f"不支持的消息类型: {msg_type}")
                return "success"
        
    except Exception as e:
        logger.error(f"处理回调异常: {str(e)}", exc_info=True)
        return "服务器错误", 500


@app.route('/api/notify', methods=['POST'])
def notify_status():
    """
    接收 GitHub Actions 的状态通知并转发到企业微信
    请求格式：
    {
        "secret": "webhook_secret",
        "issue_number": 123,
        "status": "syncing|success|failure",
        "image_name": "docker.io/library/nginx:latest",
        "target_image": "swr.cn-east-3.myhuaweicloud.com/ui_beam-images/nginx:latest",
        "error_message": "错误信息（可选）",
        "logs_url": "日志URL（可选）"
    }
    """
    try:
        # 验证 secret
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        
        secret = data.get('secret', '')
        if secret != WEBHOOK_SECRET:
            logger.warning("无效的 webhook secret")
            return jsonify({"error": "Invalid secret"}), 403
        
        issue_number = data.get('issue_number')
        status = data.get('status')
        image_name = data.get('image_name', '')
        target_image = data.get('target_image', '')
        error_message = data.get('error_message', '')
        logs_url = data.get('logs_url', '')
        
        if not issue_number or not status:
            return jsonify({"error": "Missing required fields"}), 400
        
        # 从 Issue 中获取用户 ID
        user_id = get_user_id_from_issue(issue_number)
        if not user_id:
            logger.warning(f"无法获取 Issue #{issue_number} 的用户 ID，跳过通知（可能是非企业微信创建的 Issue）")
            return jsonify({"success": True, "message": "Skipped: No user ID found"}), 200
        
        # 根据状态发送不同的通知
        if status == 'syncing':
            # 同步中
            message = (f"镜像正在同步中\n\n"
                     f"镜像: {image_name}\n"
                     f"Issue: #{issue_number}\n"
                     f"进度: 正在同步...")
        
        elif status == 'success':
            # 同步成功
            message = (f"镜像同步成功\n\n"
                     f"镜像: {image_name}\n"
                     f"Issue: #{issue_number}\n\n"
                     f"快捷命令：\n"
                     f"docker pull {target_image}\n\n"
                     f"查看详情: https://github.com/{GITHUB_REPO}/issues/{issue_number}")
        
        elif status == 'failure':
            # 同步失败
            message = (f"镜像同步失败\n\n"
                     f"镜像: {image_name}\n"
                     f"Issue: #{issue_number}\n\n"
                     f"失败原因: {error_message or '未知错误'}\n\n")
            
            if logs_url:
                message += f"查看日志: {logs_url}"
        
        else:
            return jsonify({"error": "Invalid status"}), 400
        
        # 发送企业微信通知
        success = send_wecom_message(user_id, message)
        
        if success:
            logger.info(f"成功发送状态通知: {status} for Issue #{issue_number}")
            return jsonify({"success": True, "message": "Notification sent"}), 200
        else:
            logger.error(f"发送状态通知失败: {status} for Issue #{issue_number}")
            return jsonify({"success": False, "message": "Failed to send notification"}), 500
    
    except Exception as e:
        logger.error(f"处理通知请求异常: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "service": "webhook-wecom",
        "timestamp": time.time()
    })


@app.route('/', methods=['GET'])
def index():
    """首页"""
    return jsonify({
        "service": "企业微信消息接收服务器",
        "description": "接收企业微信应用消息，自动在 GitHub 创建镜像同步 Issues",
        "endpoints": {
            "/wecom/callback": "企业微信回调接口（GET: URL验证, POST: 消息接收）",
            "/health": "健康检查接口"
        },
        "status": "running"
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"服务器启动在端口 {port}")
    logger.info(f"GitHub 仓库: {GITHUB_REPO}")
    app.run(host='0.0.0.0', port=port, debug=False)

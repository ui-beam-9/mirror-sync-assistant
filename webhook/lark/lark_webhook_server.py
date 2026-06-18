#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lark（国际版飞书）消息接收服务器
接收 Lark 应用消息，自动在 GitHub 创建镜像同步 Issues
"""

import os
import sys
import hashlib
import json
import time
import base64
import logging
import platform
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

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

from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
import lark_oapi as lark

# 加载 .env 文件
load_dotenv()
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageResponse,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ====================================
# 事件去重缓存（基于 event_id）
# 防止 Lark 短时间内重复推送同一消息
# ====================================
import threading
from collections import OrderedDict

class EventDeduplicator:
    """基于 event_id 的去重器，LRU 淘汰"""
    def __init__(self, max_size=1000, ttl_seconds=60):
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def is_duplicate(self, event_id):
        """返回 True 表示重复事件，False 表示新事件"""
        if not event_id:
            return False
        now = time.time()
        with self._lock:
            # 清理过期条目
            expired = [eid for eid, ts in self._cache.items() if now - ts > self._ttl]
            for eid in expired:
                del self._cache[eid]
            # 检查是否重复
            if event_id in self._cache:
                return True
            # 记录新事件
            self._cache[event_id] = now
            # LRU 淘汰
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
            return False


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


_event_dedup = EventDeduplicator()
_message_dedup = MessageDeduplicator(ttl_seconds=5)

# ====================================
# 从环境变量读取配置
# ====================================

# Lark 应用配置
LARK_APP_ID = os.environ.get('LARK_APP_ID', '')
LARK_APP_SECRET = os.environ.get('LARK_APP_SECRET', '')
LARK_VERIFICATION_TOKEN = os.environ.get('LARK_VERIFICATION_TOKEN', '')
LARK_ENCRYPT_KEY = os.environ.get('LARK_ENCRYPT_KEY', '')

# Lark API 域名（国际版使用 open.larksuite.com，中国版使用 open.feishu.cn）
LARK_API_DOMAIN = os.environ.get('LARK_API_DOMAIN', 'https://open.larksuite.com')

# GitHub 配置
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')  # 格式: owner/repo

# Webhook 验证密钥（用于 GitHub Actions 调用通知接口时验证身份）
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# 验证环境变量
required_vars = {
    'LARK_APP_ID': LARK_APP_ID,
    'LARK_APP_SECRET': LARK_APP_SECRET,
    'LARK_VERIFICATION_TOKEN': LARK_VERIFICATION_TOKEN,
}

optional_vars = {
    'LARK_ENCRYPT_KEY': LARK_ENCRYPT_KEY,
    'GITHUB_TOKEN': GITHUB_TOKEN,
    'GITHUB_REPO': GITHUB_REPO,
    'WEBHOOK_SECRET': WEBHOOK_SECRET,
}

missing_vars = [k for k, v in required_vars.items() if not v]
if missing_vars:
    logger.error(f"缺少必需的 Lark 环境变量: {', '.join(missing_vars)}")
    for k, v in required_vars.items():
        logger.error(f"   {k}: {'已设置' if v else '未设置'}")
    logger.error("请创建 .env 文件并填入以上配置，参考 .env.example")

# 打印可选变量状态
github_ready = bool(GITHUB_TOKEN and GITHUB_REPO)
if not github_ready:
    logger.warning("GitHub 配置未设置，将跳过 Issue 创建功能")
    logger.warning("   消息事件只回复确认，不会创建 GitHub Issue")

logger.info("Lark 配置状态:")
logger.info(f"   APP_ID: {'已设置' if LARK_APP_ID else '未设置'}")
logger.info(f"   APP_SECRET: {'已设置' if LARK_APP_SECRET else '未设置'}")
logger.info(f"   VERIFICATION_TOKEN: {'已设置' if LARK_VERIFICATION_TOKEN else '未设置'}")
logger.info(f"   ENCRYPT_KEY: {'已设置' if LARK_ENCRYPT_KEY else '未设置'}")
logger.info(f"   GitHub: {'已配置' if github_ready else '未配置（跳过）'}")

# ====================================
# Lark 客户端初始化
# ====================================

# 初始化 Lark Client（国际版域名）
lark_client = lark.Client.builder() \
    .app_id(LARK_APP_ID) \
    .app_secret(LARK_APP_SECRET) \
    .domain(LARK_API_DOMAIN) \
    .log_level(lark.LogLevel.INFO) \
    .build()


def get_tenant_access_token():
    """获取 Lark tenant_access_token（SDK 自动管理，此处为备用方法）"""
    try:
        url = f"{LARK_API_DOMAIN}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": LARK_APP_ID,
            "app_secret": LARK_APP_SECRET
        }
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        if data.get('code') == 0:
            token = data.get('tenant_access_token', '')
            logger.info("成功获取 Lark Tenant Access Token")
            return token
        else:
            logger.error(f"获取 Tenant Access Token 失败: {data.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"获取 Tenant Access Token 异常: {str(e)}")
        return None


def send_lark_message(open_id, content):
    """通过 Lark API 发送消息给用户"""
    try:
        access_token = get_tenant_access_token()
        if not access_token:
            logger.error("无法获取 Access Token，消息发送失败")
            return False

        url = f"{LARK_API_DOMAIN}/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "receive_id": open_id,
            "msg_type": "text",
            "content": json.dumps({"text": content})
        }

        response = requests.post(
            url,
            headers=headers,
            params={"receive_id_type": "open_id"},
            json=payload,
            timeout=10
        )
        data = response.json()

        if data.get('code') == 0:
            logger.info(f"成功发送 Lark 消息给用户: {open_id}")
            return True
        else:
            logger.error(f"发送 Lark 消息失败: code={data.get('code')}, msg={data.get('msg')}")
            return False

    except Exception as e:
        logger.error(f"发送 Lark 消息异常: {str(e)}")
        return False


def verify_lark_request(headers, body):
    """验证 Lark 请求签名"""
    timestamp = headers.get('X-Lark-Request-Timestamp', '')
    nonce = headers.get('X-Lark-Request-Nonce', '')
    signature = headers.get('X-Lark-Signature', '')

    logger.info(f"签名验证: timestamp={timestamp}, nonce={nonce}, signature={signature[:20] if signature else 'MISSING'}...")
    logger.info(f"签名验证: body长度={len(body)}, encrypt_key长度={len(LARK_ENCRYPT_KEY)}")

    if not timestamp or not nonce or not signature:
        logger.warning("缺少 Lark 签名头")
        return False

    # 计算签名: timestamp + nonce + encrypt_key + body 的 SHA256
    raw = f"{timestamp}{nonce}{LARK_ENCRYPT_KEY}{body}"
    expected = hashlib.sha256(raw.encode('utf-8')).hexdigest()

    if signature == expected:
        logger.info("签名验证通过")
        return True
    else:
        logger.warning(f"签名验证失败: expected={expected}, got={signature}")
        return False


def decrypt_lark_body(encrypted_body):
    """
    解密 Lark 加密的事件体

    加密原理（Lark 官方文档）：
    1. 使用 SHA256 对 Encrypt Key 进行哈希，得到 AES-256 密钥
    2. 使用 PKCS7 填充事件内容
    3. 生成 16 字节随机 IV
    4. 使用 AES-256-CBC 加密
    5. 最终密文 = base64(iv + encrypted_data)

    返回解密后的 JSON 字符串，失败返回 None
    """
    try:
        if not LARK_ENCRYPT_KEY:
            logger.error("未配置 LARK_ENCRYPT_KEY，无法解密")
            return None

        # 1. SHA256(Encrypt Key) → 256-bit key
        key = hashlib.sha256(LARK_ENCRYPT_KEY.encode('utf-8')).digest()

        # 2. Base64 解码得到 iv(16 bytes) + encrypted_data
        ciphertext = base64.b64decode(encrypted_body)

        if len(ciphertext) < 16:
            logger.error(f"密文长度异常: {len(ciphertext)} bytes")
            return None

        iv = ciphertext[:16]
        encrypted_data = ciphertext[16:]

        # 3. AES-256-CBC 解密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # 4. 去除 PKCS7 填充
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_data) + unpadder.finalize()

        result = plaintext.decode('utf-8')
        logger.info("Lark 事件体解密成功")
        return result

    except Exception as e:
        logger.error(f"解密 Lark 事件体失败: {str(e)}")
        return None


def create_github_issue(image_name, lark_user_id=None):
    """在 GitHub 创建 Issue，并发送 Lark 通知"""
    try:
        # 清理镜像名称，去除空格
        image_name = image_name.strip()

        # 验证镜像名称格式
        if not image_name:
            logger.error("镜像名称为空")
            if lark_user_id:
                send_lark_message(lark_user_id, "镜像同步失败：镜像名称为空")
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

        # Issue 数据（将 Lark 用户 ID 保存到 body 中，用于后续通知）
        issue_data = {
            "title": image_name,
            "labels": ["sync image"],
            "body": (
                f"来自 Lark 的镜像同步请求\n\n"
                f"镜像名称: `{image_name}`\n"
                f"提交时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"---\n"
                f"<!-- lark_user_id: {lark_user_id} -->"
            )
        }

        # 发送请求
        response = requests.post(api_url, headers=headers, json=issue_data, timeout=10)

        if response.status_code == 201:
            issue_data = response.json()
            issue_url = issue_data.get('html_url', '')
            issue_number = issue_data.get('number', '')
            logger.info(f"Issue 创建成功: {issue_url}")

            # 发送 Lark 通知
            if lark_user_id:
                notification = (
                    f"镜像同步任务已创建\n\n"
                    f"镜像名称: {image_name}\n"
                    f"Issue 编号: #{issue_number}\n"
                    f"状态: 等待同步\n\n"
                    f"查看详情: {issue_url}"
                )
                send_lark_message(lark_user_id, notification)

            return True
        else:
            logger.error(f"Issue 创建失败: {response.status_code}")
            logger.error(f"响应内容: {response.text}")

            # 发送失败通知
            if lark_user_id:
                send_lark_message(
                    lark_user_id,
                    f"镜像同步失败\n\n镜像名称: {image_name}\n原因: GitHub Issue 创建失败"
                )

            return False

    except Exception as e:
        logger.error(f"创建 Issue 异常: {str(e)}")

        # 发送异常通知
        if lark_user_id:
            send_lark_message(
                lark_user_id,
                f"镜像同步失败\n\n镜像名称: {image_name}\n原因: 系统异常"
            )

        return False


def validate_image_name(content):
    """
    验证并规范化镜像名称。

    返回: (image_name, error_message, hint_text)
      - 成功: ("docker.io/library/nginx:latest", None, "自动补仓库: docker.io")
      - 失败: (None, "错误提示", None)
    """
    # 处理 Lark 消息内容（可能是 JSON 格式的文本）
    content = content.strip()

    # 如果是 JSON 格式的文本消息，提取 text 字段
    try:
        msg_obj = json.loads(content)
        if isinstance(msg_obj, dict) and 'text' in msg_obj:
            content = msg_obj['text'].strip()
    except (json.JSONDecodeError, TypeError):
        pass

    if not content:
        return None, "镜像名称不能为空\n\n正确格式: <命名空间>/<镜像名>:<标签>\n示例:\n  library/nginx:latest\n  jxxghp/moviepilot-v2:latest\n  docker.io/library/nginx:latest", None

    # 去除协议前缀（如果有人误加了 https://docker.io/xxx 之类）
    content = content.split('://')[-1]

    # 保存协议去除后的原始输入（用于判断是否缺仓库、缺标签）
    user_input = content

    # 分离镜像名和标签（docker 镜像标签允许的字符: [a-zA-Z0-9_.-]）
    # 格式: [registry/][namespace/]image[:tag] 或 [namespace/]image[:tag]
    tag = 'latest'
    if ':' in content:
        parts = content.rsplit(':', 1)
        if len(parts) == 2 and parts[1]:
            content = parts[0]
            tag = parts[1]

    # 验证标签格式（仅允许 a-zA-Z0-9_.-）
    import re
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$', tag):
        return None, f"标签格式无效: {tag}\n\n标签仅允许字母、数字、下划线、点、连字符，最多128字符", None

    # 拆分路径
    path_parts = content.split('/')

    # 验证每个路径片段
    for part in path_parts:
        if not part:
            return None, f"镜像路径格式无效: 路径中存在空的片段\n\n输入: {content}", None
        # 仓库名/命名空间/镜像名允许小写字母、数字、分隔符(_.-)
        if not re.match(r'^[a-z0-9][a-z0-9_.-]*$', part):
            return None, f"路径片段格式无效: \"{part}\"\n\n镜像路径仅允许小写字母、数字、分隔符(_.-)", None

    # 检查是否有命名空间 + 镜像名
    # 必须至少有 namespace/image 格式（至少一级斜杠）
    if len(path_parts) == 1:
        # 只有镜像名，没有命名空间 → 拒绝
        return None, (f"缺少命名空间\n\n"
                     f"输入了 \"{content}\"，只有镜像名，缺少命名空间\n\n"
                     f"正确格式: <命名空间>/<镜像名>:<标签>\n"
                     f"例如: library/{path_parts[0]}:latest"), None
    elif len(path_parts) == 2:
        # namespace/image 格式，判断第一部分是否为已知 registry
        known_registries = ['docker.io', 'gcr.io', 'quay.io', 'k8s.gcr.io',
                            'ghcr.io', 'registry.k8s.io', 'mcr.microsoft.com',
                            'nvcr.io', 'public.ecr.aws']
        if path_parts[0] in known_registries:
            # 这是 registry/namespace 格式，自动补充 library/ 吗？
            # 不，这种是 registry/namespace/image 中的 registry+namespace
            # 如果只有两级且第一部分是 registry，说明缺少镜像名
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
    hints = []
    # 仓库补全判断：用户输入里没带 registry（不含 . 或只有一级路径）
    user_parts = user_input.split('/')
    has_registry = '.' in user_parts[0] if user_parts else False
    miss_registry = not has_registry
    miss_tag = ':' not in user_input

    if miss_registry and miss_tag:
        # 同时缺仓库和标签 → 合并为一条
        hint_text = "由于你没有指定仓库名和标签将使用默认的仓库docker.io和标签latest"
    elif miss_registry:
        hint_text = f"由于你没有指定仓库名将使用默认的仓库docker.io,如: docker.io/{user_input}"
    elif miss_tag:
        hint_text = f"由于你没有指定标签将使用默认的标签latest,如: {user_input}:latest"
    else:
        hint_text = ""

    return image_name, None, hint_text


def get_user_id_from_issue(issue_number):
    """从 Issue body 中提取 Lark 用户 ID"""
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

            # 从 body 中提取 Lark 用户 ID
            import re
            match = re.search(r'<!-- lark_user_id: (\S+) -->', body)
            if match:
                user_id = match.group(1)
                logger.info(f"从 Issue #{issue_number} 提取到 Lark 用户 ID: {user_id}")
                return user_id
            else:
                logger.warning(f"Issue #{issue_number} 中未找到 Lark 用户 ID")
                return None
        else:
            logger.error(f"获取 Issue 失败: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"提取用户 ID 异常: {str(e)}")
        return None


# ====================================
# Flask 路由
# ====================================

@app.route('/lark/callback', methods=['GET', 'POST'])
def lark_callback():
    """Lark 事件回调接口"""
    try:
        if request.method == 'POST':
            raw_body = request.get_data(as_text=True)
            # 强制刷新确保日志立即输出
            sys.stderr.flush()
            logger.info(f">>> POST /lark/callback, body={raw_body[:200]}...")
            sys.stderr.flush()

            # 打印所有请求头用于调试
            for h, v in request.headers.items():
                logger.info(f"  Header: {h}={v}")

            # 1. 检查是否为加密请求体
            try:
                body_json = json.loads(raw_body)
            except json.JSONDecodeError:
                logger.error("无法解析请求体 JSON")
                return jsonify({"code": 1, "msg": "invalid json"}), 400

            encrypt_str = body_json.get('encrypt', '')

            if encrypt_str:
                # --- 加密模式 ---
                if not LARK_ENCRYPT_KEY:
                    logger.error("收到加密请求但未配置 LARK_ENCRYPT_KEY")
                    return jsonify({"code": 1, "msg": "encrypt key not configured"}), 500

                # 解密
                decrypted_body = decrypt_lark_body(encrypt_str)
                if decrypted_body is None:
                    logger.error("解密失败")
                    return jsonify({"code": 1, "msg": "decrypt failed"}), 500

                logger.info(f"解密后数据: {decrypted_body[:300]}")

                try:
                    event_data = json.loads(decrypted_body)
                except json.JSONDecodeError:
                    logger.error("解密后的数据不是有效 JSON")
                    return jsonify({"code": 1, "msg": "invalid decrypted json"}), 400

            else:
                # --- 明文模式 ---
                event_data = body_json

            # 2. URL 验证：检查 challenge（URL验证阶段不验证签名）
            challenge = event_data.get('challenge', '')
            token = event_data.get('token', '')
            event_type = event_data.get('type', '')

            if challenge or event_type == 'url_verification':
                # 验证 Verification Token（如果配置了）
                if LARK_VERIFICATION_TOKEN and token and token != LARK_VERIFICATION_TOKEN:
                    logger.warning(f"Verification Token 不匹配")
                    return jsonify({"code": 1, "msg": "invalid token"}), 403

                logger.info(f"URL 验证成功，返回 challenge: {challenge[:20] if challenge else 'N/A'}...")
                return jsonify({"challenge": challenge})

            # 3. 事件回调阶段验证签名
            if LARK_ENCRYPT_KEY:
                if not verify_lark_request(request.headers, raw_body):
                    logger.warning("Lark 请求签名验证失败")
                    return jsonify({"code": 1, "msg": "signature verification failed"}), 403

            # 4. 处理事件回调
            # 兼容两种格式：
            #   旧版: {"type":"event_callback", "event":{...}}
            #   新版 (schema 2.0): {"schema":"2.0", "header":{"event_type":"im.message.receive_v1",...}, "event":{...}}
            schema = event_data.get('schema', '')
            header = event_data.get('header', {})
            event = event_data.get('event', {})

            # 判断是否为消息接收事件
            is_message_event = False
            open_id = ''
            message_content = ''

            if schema == '2.0' and header.get('event_type') == 'im.message.receive_v1':
                # 新版 schema 2.0 格式
                is_message_event = True
                event_msg = event.get('message', {})
                msg_type = event_msg.get('message_type', '')
                open_id = event.get('sender', {}).get('sender_id', {}).get('open_id', '')
                message_content = event_msg.get('content', '')
                logger.info(f"收到 Lark 事件 (schema 2.0): event_type={header.get('event_type')}, msg_type={msg_type}")

                if msg_type != 'text':
                    logger.info(f"收到非文本消息: {msg_type}")
                    return jsonify({"code": 0})

            elif event_type == 'event_callback':
                # 旧版格式
                is_message_event = True
                # 旧版格式中 msg_type 可能在 event 顶层
                msg_type = event.get('msg_type', event.get('message', {}).get('message_type', ''))
                open_id = event.get('open_id', event.get('sender', {}).get('sender_id', {}).get('open_id', ''))
                message_content = event.get('text', event.get('message', {}).get('content', ''))
                logger.info(f"收到 Lark 事件 (旧版): msg_type={msg_type}")

                if msg_type != 'text':
                    logger.info(f"收到非文本消息: {msg_type}")
                    return jsonify({"code": 0})

            if is_message_event and message_content:
                # 事件去重检查（基于 event_id）
                event_id = header.get('event_id') or event.get('event_id', '')
                if _event_dedup.is_duplicate(event_id):
                    logger.info(f"跳过重复事件: event_id={event_id}")
                    return jsonify({"code": 0})

                text_content = message_content.strip()
                logger.info(f"收到 Lark 文本消息 from {open_id}: {text_content}")

                # 验证镜像名称（先验证拿到规范化名称）
                image_name, error_msg, hint = validate_image_name(text_content)

                if error_msg:
                    # 格式验证失败，回复错误提示
                    logger.warning(f"镜像名称验证失败: {error_msg}")
                    reply = f"镜像名称格式错误\n\n{error_msg}"
                    send_lark_message(open_id, reply)
                    return jsonify({"code": 0})

                # 消息内容去重（基于规范化后的镜像名，5秒窗口内相同镜像名只处理一次）
                if _message_dedup.is_duplicate(image_name):
                    logger.info(f"跳过重复消息: image_name={image_name}")
                    return jsonify({"code": 0})

                if github_ready:
                    # 创建 GitHub Issue 并发送 Lark 通知
                    success = create_github_issue(image_name, lark_user_id=open_id)
                    if success:
                        logger.info(f"成功处理镜像同步请求: {image_name}")
                    else:
                        logger.error(f"处理镜像同步请求失败: {image_name}")
                else:
                    # 没有 GitHub 配置，直接回复确认
                    reply = (
                        f"收到镜像同步请求\n\n"
                        f"镜像名称: {image_name}"
                    )
                    if hint:
                        reply += f"\n\n{hint}"
                    reply += f"\n状态: 已接收（GitHub 未配置，跳过创建 Issue）"
                    send_lark_message(open_id, reply)
                    logger.info(f"已回复确认消息: {image_name}")

                return jsonify({"code": 0})

            logger.info(f"收到非事件回调: type={event_type}, schema={schema}")
            return jsonify({"code": 0})

        else:
            # GET 请求
            return jsonify({
                "service": "Lark Webhook Server",
                "status": "running"
            })

    except Exception as e:
        logger.error(f"处理回调异常: {str(e)}", exc_info=True)
        return jsonify({"code": 1, "msg": "internal error"}), 500


@app.route('/api/cli-sync', methods=['POST'])
def cli_sync():
    """
    接收 lark-cli 监听器转发的镜像同步请求
    请求格式：
    {
        "image_name": "nginx:latest",
        "user_open_id": "ou_xxx"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        image_name_raw = data.get('image_name', '').strip()
        user_open_id = data.get('user_open_id', '')

        if not image_name_raw:
            return jsonify({"error": "Missing image_name"}), 400

        # 验证镜像名称
        image_name, error_msg, hint = validate_image_name(image_name_raw)
        if error_msg:
            logger.warning(f"CLI 同步请求 - 镜像名称验证失败: {error_msg}")
            if user_open_id:
                send_lark_message(user_open_id, f"镜像名称格式错误\n\n{error_msg}")
            return jsonify({"error": error_msg}), 400

        logger.info(f"CLI 同步请求: {image_name} (用户: {user_open_id})")

        if not github_ready:
            # 没有 GitHub 配置，直接回复确认
            if user_open_id:
                send_lark_message(user_open_id, f"收到镜像同步请求\n\n镜像名称: {image_name}\n状态: 已接收（GitHub 未配置）")
            return jsonify({"success": True, "message": "Received (GitHub not configured)"}), 200

        # 创建 GitHub Issue
        success = create_github_issue(image_name, lark_user_id=user_open_id)

        if success:
            return jsonify({"success": True, "message": "Issue created"}), 200
        else:
            return jsonify({"success": False, "message": "Failed to create issue"}), 500

    except Exception as e:
        logger.error(f"CLI 同步异常: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/notify', methods=['POST'])
def notify_status():
    """
    接收 GitHub Actions 的状态通知并转发到 Lark
    请求格式（与现有企业微信服务器协议一致）：
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

        # 从 Issue 中获取 Lark 用户 ID
        user_id = get_user_id_from_issue(issue_number)
        if not user_id:
            logger.warning(f"无法获取 Issue #{issue_number} 的 Lark 用户 ID，跳过通知（可能是非 Lark 创建的 Issue）")
            return jsonify({"success": True, "message": "Skipped: No Lark user ID found"}), 200

        # 根据状态发送不同的通知
        if status == 'syncing':
            # 同步中
            message = (
                f"镜像正在同步中\n\n"
                f"镜像: {image_name}\n"
                f"Issue: #{issue_number}\n"
                f"进度: 正在同步..."
            )

        elif status == 'success':
            # 同步成功
            message = (
                f"镜像同步成功\n\n"
                f"镜像: {image_name}\n"
                f"Issue: #{issue_number}\n\n"
                f"快捷命令：\n"
                f"docker pull {target_image}\n\n"
                f"查看详情: https://github.com/{GITHUB_REPO}/issues/{issue_number}"
            )

        elif status == 'failure':
            # 同步失败
            message = (
                f"镜像同步失败\n\n"
                f"镜像: {image_name}\n"
                f"Issue: #{issue_number}\n\n"
                f"失败原因: {error_message or '未知错误'}\n\n"
            )

            if logs_url:
                message += f"查看日志: {logs_url}"

        else:
            return jsonify({"error": "Invalid status"}), 400

        # 发送 Lark 通知
        success = send_lark_message(user_id, message)

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
        "service": "webhook-lark",
        "timestamp": time.time()
    })


@app.route('/', methods=['GET'])
def index():
    """首页"""
    return jsonify({
        "service": "Lark 消息接收服务器",
        "description": "接收 Lark 应用消息，自动在 GitHub 创建镜像同步 Issues",
        "endpoints": {
            "/lark/callback": "Lark 事件回调接口（POST: 消息接收 + URL验证）",
            "/api/notify": "GitHub Actions 状态通知接口（POST）",
            "/health": "健康检查接口（GET）"
        },
        "status": "running"
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    logger.info(f"Lark Webhook 服务器启动在端口 {port}")
    logger.info(f"GitHub 仓库: {GITHUB_REPO}")
    logger.info(f"Lark API 域名: {LARK_API_DOMAIN}")
    app.run(host='0.0.0.0', port=port, debug=False)

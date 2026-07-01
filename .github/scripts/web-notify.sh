#!/usr/bin/env bash
# 网页端同步通知脚本
#
# 用途：在 GitHub Actions 中调用后端 /api/notify 接口，
#       给通过网页端 SyncPage 提交同步任务的用户发送 PushPlus 微信通知或邮件通知。
#
# 触发条件：Issue body 中含有 <!-- web_sync_request --> 标记（由 web/backend/src/api/sync.js 写入）。
# 通知方式：Issue body 中的 <!-- notify_method: wechat|email --> 注释决定。
# 邮箱地址：Issue body 中的 <!-- notify_email: xxx@xxx.com --> 注释提供。
#
# 用法：
#   bash .github/scripts/web-notify.sh <status> <issue_number> <origin_image> [target_image] [error_message] [logs_url]
#
# 参数：
#   status         syncing | success | failure
#   issue_number   GitHub Issue 编号
#   origin_image   源镜像名
#   target_image   目标镜像名（success 时必填）
#   error_message  错误信息（failure 时必填）
#   logs_url       日志链接（failure 时必填）
#
# 依赖环境变量：
#   BACKEND_API_URL  后端 API 公网地址（如 https://api.ui-beam.com/swr-sync-image/api）
#   GH_TOKEN         GitHub Token（用于读取 Issue body）

set -u

STATUS="${1:-}"
ISSUE_NUMBER="${2:-}"
ORIGIN_IMAGE="${3:-}"
TARGET_IMAGE="${4:-}"
ERROR_MESSAGE="${5:-}"
LOGS_URL="${6:-}"

echo "─── 网页端通知 ($STATUS) ───"
echo "  Issue: #$ISSUE_NUMBER"
echo "  镜像: $ORIGIN_IMAGE"

# 1. 校验后端 URL 是否配置
if [ -z "${BACKEND_API_URL:-}" ]; then
  echo "⚠ BACKEND_API_URL 未配置，跳过网页端通知"
  exit 0
fi

if [ -z "$ISSUE_NUMBER" ]; then
  echo "⚠ 缺少 issue_number 参数"
  exit 0
fi

# 2. 读取 Issue body（含 labels）
if ! command -v gh >/dev/null 2>&1; then
  echo "⚠ 未找到 gh CLI，跳过"
  exit 0
fi

ISSUE_JSON=$(gh issue view "$ISSUE_NUMBER" --json body 2>/dev/null) || {
  echo "⚠ 读取 Issue #$ISSUE_NUMBER 失败，跳过"
  exit 0
}
ISSUE_BODY=$(echo "$ISSUE_JSON" | jq -r '.body // ""')

# 3. 判断是否为网页端同步请求
if ! echo "$ISSUE_BODY" | grep -q "<!-- web_sync_request -->"; then
  echo "→ 非网页端同步请求（无 web_sync_request 标记），跳过"
  exit 0
fi

# 4. 解析通知方式与邮箱
#    注释格式: <!-- notify_method: wechat -->  /  <!-- notify_email: xxx@x.com -->
NOTIFY_METHOD=$(echo "$ISSUE_BODY" | sed -n 's/.*<!-- notify_method: \([^ ]*\) -->.*/\1/p' | head -n1)
NOTIFY_EMAIL=$(echo "$ISSUE_BODY" | sed -n 's/.*<!-- notify_email: \([^ ]*\) -->.*/\1/p' | head -n1)

if [ -z "$NOTIFY_METHOD" ] || [ "$NOTIFY_METHOD" = "none" ]; then
  echo "→ 用户选择不接收通知，跳过"
  exit 0
fi

if [ "$NOTIFY_METHOD" != "wechat" ] && [ "$NOTIFY_METHOD" != "email" ]; then
  echo "⚠ 未知通知方式: $NOTIFY_METHOD，跳过"
  exit 0
fi

if [ "$NOTIFY_METHOD" = "email" ] && [ -z "$NOTIFY_EMAIL" ]; then
  echo "⚠ 邮箱通知但未提供邮箱地址，跳过"
  exit 0
fi

echo "  通知方式: $NOTIFY_METHOD"
[ -n "$NOTIFY_EMAIL" ] && echo "  邮箱: $NOTIFY_EMAIL"

# 5. 根据 status 拼接 title / content
ISSUE_URL="https://github.com/${GITHUB_REPOSITORY:-}/issues/$ISSUE_NUMBER"

case "$STATUS" in
  syncing)
    TITLE="镜像同步中: ${ORIGIN_IMAGE}"
    CONTENT="<h3>镜像同步中</h3>"
    CONTENT="$CONTENT<p><b>镜像:</b> ${ORIGIN_IMAGE}</p>"
    CONTENT="$CONTENT<p><b>Issue:</b> #${ISSUE_NUMBER}</p>"
    CONTENT="$CONTENT<p>正在同步，请稍候...</p>"
    CONTENT="$CONTENT<p><a href=\"$ISSUE_URL\">查看 Issue</a></p>"
    ;;
  success)
    TITLE="镜像同步成功: ${ORIGIN_IMAGE}"
    CONTENT="<h3>镜像同步成功</h3>"
    CONTENT="$CONTENT<p><b>源镜像:</b> ${ORIGIN_IMAGE}</p>"
    CONTENT="$CONTENT<p><b>目标镜像:</b> ${TARGET_IMAGE}</p>"
    CONTENT="$CONTENT<p><b>Issue:</b> #${ISSUE_NUMBER}</p>"
    CONTENT="$CONTENT<h4>快捷命令</h4>"
    CONTENT="$CONTENT<pre>docker pull ${TARGET_IMAGE}\ndocker tag ${TARGET_IMAGE} ${ORIGIN_IMAGE}</pre>"
    CONTENT="$CONTENT<p><a href=\"$ISSUE_URL\">查看 Issue</a></p>"
    ;;
  failure)
    TITLE="镜像同步失败: ${ORIGIN_IMAGE}"
    CONTENT="<h3>镜像同步失败</h3>"
    CONTENT="$CONTENT<p><b>镜像:</b> ${ORIGIN_IMAGE}</p>"
    CONTENT="$CONTENT<p><b>Issue:</b> #${ISSUE_NUMBER}</p>"
    CONTENT="$CONTENT<p><b>失败原因:</b> ${ERROR_MESSAGE:-未知错误}</p>"
    if [ -n "$LOGS_URL" ]; then
      CONTENT="$CONTENT<p><a href=\"$LOGS_URL\">查看详细日志</a></p>"
    fi
    ;;
  *)
    echo "⚠ 未知 status: $STATUS"
    exit 0
    ;;
esac

# 6. 构造请求体并调用后端 /api/notify
#    后端接口 body: { method, title, content, email? }
if [ "$NOTIFY_METHOD" = "email" ]; then
  PAYLOAD=$(jq -n \
    --arg m "$NOTIFY_METHOD" \
    --arg t "$TITLE" \
    --arg c "$CONTENT" \
    --arg e "$NOTIFY_EMAIL" \
    '{method:$m, title:$t, content:$c, email:$e}')
else
  PAYLOAD=$(jq -n \
    --arg m "$NOTIFY_METHOD" \
    --arg t "$TITLE" \
    --arg c "$CONTENT" \
    '{method:$m, title:$t, content:$c}')
fi

NOTIFY_URL="${BACKEND_API_URL%/}/notify"
echo "  调用: POST $NOTIFY_URL"

# 发送请求，失败不阻断 workflow
RESPONSE=$(curl -sS -X POST "$NOTIFY_URL" \
  -H "Content-Type: application/json" \
  --max-time 30 \
  -d "$PAYLOAD" 2>&1) || true

echo "  响应: $RESPONSE"
echo "─── 网页端通知结束 ───"

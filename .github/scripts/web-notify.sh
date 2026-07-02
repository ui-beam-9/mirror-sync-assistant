#!/usr/bin/env bash
# 网页端同步通知脚本
#
# 用途：在 GitHub Actions 中调用后端 /api/notify 接口，
#       给通过网页端 SyncPage 提交同步任务的用户发送邮件通知。
#
# 触发条件：Issue body 中含有 <!-- web_sync_request --> 标记（由 web/backend/src/api/sync.js 写入）。
# 通知方式：Issue body 中的 <!-- notify_method: email --> 注释决定。
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

# 2. 读取 Issue body
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
#    注释格式: <!-- notify_method: email -->  /  <!-- notify_email: xxx@x.com -->
NOTIFY_METHOD=$(echo "$ISSUE_BODY" | sed -n 's/.*<!-- notify_method: \([^ ]*\) -->.*/\1/p' | head -n1)
NOTIFY_EMAIL=$(echo "$ISSUE_BODY" | sed -n 's/.*<!-- notify_email: \([^ ]*\) -->.*/\1/p' | head -n1)

if [ -z "$NOTIFY_METHOD" ] || [ "$NOTIFY_METHOD" = "none" ]; then
  echo "→ 用户选择不接收通知，跳过"
  exit 0
fi

if [ "$NOTIFY_METHOD" != "email" ]; then
  echo "→ 通知方式非邮箱（$NOTIFY_METHOD），跳过"
  exit 0
fi

if [ -z "$NOTIFY_EMAIL" ]; then
  echo "⚠ 邮箱通知但未提供邮箱地址，跳过"
  exit 0
fi

echo "  通知方式: 邮箱"
echo "  邮箱: $NOTIFY_EMAIL"

# 5. 根据 status 拼接 title / content
ISSUE_URL="https://github.com/${GITHUB_REPOSITORY:-}/issues/$ISSUE_NUMBER"

# 邮件通用样式（内联 CSS，兼容各邮件客户端）
STYLE="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#333;line-height:1.6;"
HEADER_BG_SUCCESS="background:#52c41a;border-radius:8px 8px 0 0;padding:20px 24px;"
HEADER_BG_FAIL="background:#ff4d4f;border-radius:8px 8px 0 0;padding:20px 24px;"
HEADER_BG_SYNC="background:#1890ff;border-radius:8px 8px 0 0;padding:20px 24px;"
HEADER_TITLE="color:#fff;font-size:20px;font-weight:600;margin:0;"
BODY="padding:24px;background:#f9fafb;border-radius:0 0 8px 8px;"
INFO_ROW="padding:8px 0;border-bottom:1px solid #e8e8e8;"
INFO_LABEL="display:inline-block;width:80px;color:#999;font-size:13px;"
INFO_VALUE="color:#333;font-weight:500;word-break:break-all;"
CMD_BOX="background:#1e1e1e;color:#d4d4d4;border-radius:6px;padding:16px;margin:12px 0;font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:13px;line-height:1.8;white-space:pre-wrap;word-break:break-all;"
LINK_BTN="display:inline-block;background:#1890ff;color:#fff;text-decoration:none;padding:8px 20px;border-radius:4px;font-size:14px;margin-top:12px;"

case "$STATUS" in
  syncing)
    TITLE="镜像同步中: ${ORIGIN_IMAGE}"
    CONTENT="<div style=\"$STYLE\">"
    CONTENT="$CONTENT<div style=\"$HEADER_BG_SYNC\"><h2 style=\"$HEADER_TITLE\">镜像同步中</h2></div>"
    CONTENT="$CONTENT<div style=\"$BODY\">"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">镜像</span><span style=\"$INFO_VALUE\">${ORIGIN_IMAGE}</span></div>"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">Issue</span><span style=\"$INFO_VALUE\">#${ISSUE_NUMBER}</span></div>"
    CONTENT="$CONTENT<p style=\"color:#666;margin:16px 0;\">正在同步镜像，请耐心等待...</p>"
    CONTENT="$CONTENT<a href=\"$ISSUE_URL\" style=\"$LINK_BTN\">查看 Issue</a>"
    CONTENT="$CONTENT</div></div>"
    ;;
  success)
    TITLE="镜像同步成功: ${ORIGIN_IMAGE}"
    # 目标镜像长度超过 60 字符时用小字号 + 省略号 + title 悬浮
    TARGET_LEN=${#TARGET_IMAGE}
    if [ "$TARGET_LEN" -gt 60 ]; then
      TARGET_STYLE="color:#333;font-weight:500;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:440px;display:inline-block;vertical-align:middle;cursor:text;user-select:all;"
      TARGET_HTML="<span title=\"${TARGET_IMAGE}\" style=\"${TARGET_STYLE}\">${TARGET_IMAGE}</span>"
    else
      TARGET_STYLE="color:#333;font-weight:500;font-size:15px;"
      TARGET_HTML="<span style=\"${TARGET_STYLE}\">${TARGET_IMAGE}</span>"
    fi
    CONTENT="<div style=\"$STYLE\">"
    CONTENT="$CONTENT<div style=\"$HEADER_BG_SUCCESS\"><h2 style=\"$HEADER_TITLE\">镜像同步成功</h2></div>"
    CONTENT="$CONTENT<div style=\"$BODY\">"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">源镜像</span><span style=\"$INFO_VALUE\">${ORIGIN_IMAGE}</span></div>"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">目标镜像</span>${TARGET_HTML}</div>"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">Issue</span><span style=\"$INFO_VALUE\">#${ISSUE_NUMBER}</span></div>"
    CONTENT="$CONTENT<h4 style=\"color:#333;margin:20px 0 8px;\">快捷命令</h4>"
    CONTENT="$CONTENT<div style=\"$CMD_BOX\">docker pull ${TARGET_IMAGE}<br>docker tag ${TARGET_IMAGE} ${ORIGIN_IMAGE}</div>"
    CONTENT="$CONTENT<a href=\"$ISSUE_URL\" style=\"$LINK_BTN\">查看 Issue</a>"
    CONTENT="$CONTENT</div></div>"
    ;;
  failure)
    TITLE="镜像同步失败: ${ORIGIN_IMAGE}"
    # 直接使用真实错误信息，转义 HTML 特殊字符
    FAIL_REASON_HTML=$(echo "${ERROR_MESSAGE:-未知错误}" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')
    CONTENT="<div style=\"$STYLE\">"
    CONTENT="$CONTENT<div style=\"$HEADER_BG_FAIL\"><h2 style=\"$HEADER_TITLE\">镜像同步失败</h2></div>"
    CONTENT="$CONTENT<div style=\"$BODY\">"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">镜像</span><span style=\"$INFO_VALUE\">${ORIGIN_IMAGE}</span></div>"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">Issue</span><span style=\"$INFO_VALUE\">#${ISSUE_NUMBER}</span></div>"
    CONTENT="$CONTENT<div style=\"$INFO_ROW\"><span style=\"$INFO_LABEL\">失败原因</span><span style=\"$INFO_VALUE\">${FAIL_REASON_HTML}</span></div>"
    if [ -n "$LOGS_URL" ]; then
      CONTENT="$CONTENT<a href=\"$LOGS_URL\" style=\"$LINK_BTN\">查看详细日志</a>"
    fi
    CONTENT="$CONTENT<a href=\"$ISSUE_URL\" style=\"$LINK_BTN\">查看 Issue</a>"
    CONTENT="$CONTENT</div></div>"
    ;;
  *)
    echo "⚠ 未知 status: $STATUS"
    exit 0
    ;;
esac

# 6. 构造请求体并调用后端 /api/notify
#    后端接口 body: { method, title, content, email }
PAYLOAD=$(jq -n \
  --arg m "$NOTIFY_METHOD" \
  --arg t "$TITLE" \
  --arg c "$CONTENT" \
  --arg e "$NOTIFY_EMAIL" \
  '{method:$m, title:$t, content:$c, email:$e}')

NOTIFY_URL="${BACKEND_API_URL%/}/notify"
echo "  调用: POST $NOTIFY_URL"

# 发送请求，失败不阻断 workflow
RESPONSE=$(curl -sS -X POST "$NOTIFY_URL" \
  -H "Content-Type: application/json" \
  --max-time 30 \
  -d "$PAYLOAD" 2>&1) || true

echo "  响应: $RESPONSE"
echo "─── 网页端通知结束 ───"

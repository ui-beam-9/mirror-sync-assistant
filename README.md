
# 镜像同步助手（Mirror Sync Assistant）

🚀 搬运国外 Docker 镜像到国内仓库（华为云），解决 Docker Hub、GCR、Quay 等访问困难的问题

[![Docker](https://img.shields.io/badge/Docker-Hub-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub-Actions-2088FF?style=flat&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Huawei Cloud](https://img.shields.io/badge/Huawei-Cloud-FF0000?style=flat&logo=huawei&logoColor=white)](https://www.huaweicloud.com/)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)

---

## 📖 项目简介

本项目通过 GitHub Actions 自动将 Docker 镜像同步到华为云 SWR（Software Repository for Container），解决国内访问 Docker Hub、GCR、Quay 等国外镜像仓库速度慢或无法访问的问题。

### ✨ 主要特性

- ✅ **自动化同步**：通过 Issue 触发，全自动同步流程
- ✅ **企业微信集成**：通过企业微信应用发送镜像名称，自动创建同步任务并接收实时通知
- ✅ **Lark 集成**：通过 Lark（国际版飞书）应用发送镜像名称，自动创建同步任务并接收实时通知
- ✅ **自动构建镜像**：自动构建企业微信/Lark 服务器 Docker 镜像并推送到 SWR
- ✅ **官方 SDK**：使用华为云官方 Python SDK，稳定可靠
- ✅ **灵活配置**：支持域名去除、区域选择等多种配置选项
- ✅ **状态验证**：自动设置镜像为公开并验证状态
- ✅ **详细日志**：完整的同步日志和错误提示
- ✅ **多源支持**：支持 Docker Hub、GCR、Quay 等多个镜像源

---

## 🚀 快速开始

1. 访问 [镜像同步 Issue 模板](../../issues/new?assignees=&labels=sync+image&projects=&template=sync-image.yml)
2. 填写要同步的镜像名称（如：`docker.io/library/nginx:latest`）
3. 提交 Issue，GitHub Actions 会自动开始同步
4. 同步完成后，Issue 会自动关闭并显示同步结果

> 💡 同步后的镜像拉取命令会自动显示在 Issue 中。也支持通过 [企业微信](#-通过企业微信同步) 或 [Lark](#-通过-lark-同步) 发送消息触发同步。

### 查询已同步镜像

访问 [已同步镜像查询](https://msa.ui-beam.com) 查看已经同步过的镜像列表。

---

## 💬 通过企业微信同步

通过企业微信应用发送镜像名称，自动创建同步任务并接收实时通知。

**服务器代码位置**：`webhook/wecom` 文件夹

### 步骤一：创建企业微信应用

1. 登录 [企业微信管理后台](https://work.weixin.qq.com/wework_admin/frame)
2. 进入 **应用管理** → **创建应用**
3. 填写应用名称（如：**镜像同步助手**）、上传图标
4. 创建完成后，记录以下信息（后续部署时填入 `.env`）：
   - **Corp ID**（企业 ID）→ 对应 `.env` 的 `WECOM_CORP_ID`
   - **AgentId**（应用 ID）→ 对应 `.env` 的 `WECOM_AGENT_ID`
   - **Secret**（应用密钥）→ 对应 `.env` 的 `WECOM_SECRET`
5. 进入应用的 **接收消息** → 点击 **设置 API 接收**
6. 先自定义 Token 和 EncodingAESKey（稍后部署时填入 `.env`）：
   - **Token**：自定义字符串，至少 32 位 → 对应 `.env` 的 `WECOM_TOKEN`
   - **EncodingAESKey**：随机生成 43 位字符 → 对应 `.env` 的 `WECOM_ENCODING_AES_KEY`
7. **暂时不要填写 URL**（等服务器部署完成后再回来配置）

> ⚠️ **关键**：先创建应用获取参数，再部署服务器。服务器部署完成后，回到这里填写回调 URL 完成验证。

### 步骤二：部署 Webhook 服务器

#### 🚀 一键部署（推荐）

运行部署脚本，选择「企业微信」即可：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ui-beam-9/docker-image-mirror/main/quick-deploy.sh)
```

> 💡 **提示**：如果国际版无法访问，可使用国内代理：将 `raw.githubusercontent.com` 替换为 `ghproxy.net/https://raw.githubusercontent.com`

脚本功能：
- ✅ 选择安装企业微信或 Lark 服务器
- ✅ 自动检测 Docker 和 Docker Compose
- ✅ 智能检测运行中的容器，提供管理选项
- ✅ 支持自定义安装目录（默认 `/opt/wecom-webhook`）
- ✅ 两种部署方式可选：Docker 镜像部署 或 服务器直接部署

> 📄 脚本源码：[quick-deploy.sh](./quick-deploy.sh)

<details>
<summary>💡 容器管理功能</summary>

如果检测到已有运行中的 Webhook 服务器，脚本会自动进入管理模式，提供以下选项：

**1️⃣ 更新镜像** — 拉取最新版本镜像，自动重启服务，保留现有配置

**2️⃣ 重新安装** — 可选择备份现有配置（自动备份为 `.env.backup.时间戳`），删除现有部署，重新进行全新安装

**3️⃣ 停止并删除** — 停止运行中的服务，可选择是否删除部署目录

</details>

#### 🔧 手动部署

**方式一：Docker 镜像部署（推荐）**

无需下载项目代码，只需下载配置文件：

```bash
# 1. 创建部署目录
mkdir webhook && cd webhook/wecom

# 2. 下载配置文件
curl -O https://raw.githubusercontent.com/ui-beam-9/mirror-sync-assistant/main/webhook/wecom/.env.example
curl -O https://raw.githubusercontent.com/ui-beam-9/mirror-sync-assistant/main/webhook/wecom/docker-compose.yml
mv .env.example .env

# 3. 编辑 .env 文件，填入步骤一获取的参数
nano .env

# 4. 启动服务（会自动拉取预构建镜像）
docker-compose up -d

# 5. 查看日志
docker-compose logs -f
```

**方式二：服务器直接部署（自定义代码）**

适合需要修改代码的场景：

```bash
# 1. 克隆项目
git clone https://github.com/ui-beam-9/mirror-sync-assistant.git
cd mirror-sync-assistant/webhook/wecom

# 2. 配置环境变量
cp .env.example .env
nano .env  # 填入步骤一获取的参数

# 3. 修改 docker-compose.yml 使用本地构建
nano docker-compose.yml
# 注释掉: image: swr.cn-east-3.myhuaweicloud.com/ui_beam-images/wecom-webhook-server:latest
# 取消注释: # build: .

# 4. 启动服务
docker-compose up -d

# 5. 查看日志
docker-compose logs -f
```

### 步骤三：配置环境变量

部署时编辑 `.env` 文件，填入步骤一获取的参数：

```bash
cd wecom-webhook
nano .env
```

```bash
# 企业微信应用配置（来自步骤一）
WECOM_CORP_ID=your_corp_id_here           # 企业 ID（企业微信管理后台 → 我的企业）
WECOM_AGENT_ID=1000002                    # 应用 ID（应用详情 → AgentId）
WECOM_SECRET=your_app_secret_here         # 应用密钥（应用详情 → Secret）
WECOM_TOKEN=your_random_token             # 接收消息 Token（步骤一中自定义的）
WECOM_ENCODING_AES_KEY=your_aes_key       # 加解密密钥（步骤一中生成的 43 位）
WECOM_API_BASE=https://qyapi.weixin.qq.com  # 企业微信 API 地址（动态IP需用固定IP服务器反代）

# GitHub 配置
GITHUB_TOKEN=ghp_xxxxx                    # GitHub Personal Access Token
GITHUB_REPO=owner/repo                    # 仓库名称（格式：owner/repo）

# Webhook 配置
WEBHOOK_SECRET=your_webhook_secret        # Webhook 验证密钥（需与 GitHub Secrets 中配置一致）
```

| 配置项 | 说明 | 获取方式 |
|--------|------|---------|
| `WECOM_CORP_ID` | 企业 ID | 企业微信管理后台 → 我的企业 → 企业信息 |
| `WECOM_AGENT_ID` | 应用 ID | 应用详情页面 → AgentId |
| `WECOM_SECRET` | 应用密钥 | 应用详情页面 → Secret（点击查看） |
| `WECOM_TOKEN` | 接收消息 Token | 自定义字符串，至少 32 位 |
| `WECOM_ENCODING_AES_KEY` | 加解密密钥 | 随机生成，43 位字符 |
| `WECOM_API_BASE` | 企业微信 API 地址 | 默认：`https://qyapi.weixin.qq.com` |
| `GITHUB_TOKEN` | GitHub Token | [GitHub Settings](https://github.com/settings/tokens)，需要 `repo` 权限 |
| `GITHUB_REPO` | 仓库名称 | 格式：`owner/repo` |
| `WEBHOOK_SECRET` | Webhook 验证密钥 | 随机生成，至少 32 位 |

<details>
<summary>💡 企业微信 API 反代配置（视情况而定）</summary>

企业微信有**企业可信 IP** 配置，只有在可信 IP 列表中的服务器才能调用企业微信 API。

| 服务器 IP 类型 | 是否需要反代 | 说明 |
|--------------|------------|------|
| 🔄 动态公网 IP | ✅ **需要** | IP 会变化，需要固定公网 IP 服务器做反代 |
| 📍 固定公网 IP | ❌ **不需要** | 直接将服务器 IP 添加到可信 IP 列表 |
| 🏠 内网 IP / NAT | ✅ **需要** | 无固定公网 IP，需要固定公网 IP 服务器做反代 |

**Nginx 反代配置：**

```nginx
location ^~ / {
    proxy_pass https://qyapi.weixin.qq.com;
    proxy_set_header Host qyapi.weixin.qq.com;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header REMOTE-HOST $remote_addr;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    add_header X-Cache $upstream_cache_status;
    add_header Cache-Control no-cache;
    proxy_ssl_server_name off;
    proxy_ssl_name $proxy_host;
    add_header Strict-Transport-Security "max-age=31536000";
}
```

</details>

> ⚠️ **部署完成后**，回到企业微信管理后台 → 应用 → 接收消息 → 设置 API 接收，填写回调 URL：`https://your-domain.com/wecom/callback`，点击保存完成验证。

### 步骤四：使用步骤

1. 在企业微信中打开 **镜像同步助手** 应用
2. 直接发送镜像名称，例如：
   ```
   docker.io/library/nginx:latest
   ```
3. 服务器自动创建 GitHub Issue 并触发同步
4. 收到实时状态通知：

   **① 任务创建**
   ```
   ✅ 镜像同步任务已创建

   镜像: docker.io/library/nginx:latest
   Issue: #123
   状态: 等待同步

   查看详情: https://github.com/...
   ```

   **② 同步中**
   ```
   🔄 镜像正在同步中

   镜像: docker.io/library/nginx:latest
   Issue: #123
   进度: 正在同步...
   ```

   **③ 同步成功**
   ```
   ✅ 镜像同步成功

   镜像: docker.io/library/nginx:latest
   Issue: #123

   📦 快捷命令：
   docker pull swr.cn-east-3.myhuaweicloud.com/ui_beam-images/nginx:latest

   查看详情: https://github.com/...
   ```

   **④ 同步失败**（如有）
   ```
   ❌ 镜像同步失败

   镜像: docker.io/library/nginx:latest
   Issue: #123

   失败原因: 镜像不存在或网络超时

   查看日志: https://github.com/.../actions/runs/...
   ```

---

## 💬 通过 Lark 同步

通过 Lark（国际版飞书）应用发送镜像名称，自动创建同步任务并接收实时通知。

**服务器代码位置**：`webhook/lark` 文件夹

### 步骤一：创建 Lark 应用

1. 登录 [Lark 开放平台](https://open.larksuite.com/)
2. 点击 **创建企业自建应用**
3. 填写应用名称（如：**镜像同步助手**）、上传图标，点击 **确定**
4. 应用创建完成后进入详情页，记录以下信息（后续部署时填入 `.env`）：
   - **App ID** → 对应 `.env` 的 `LARK_APP_ID`
   - **App Secret** → 对应 `.env` 的 `LARK_APP_SECRET`

5. **开启机器人能力**
   
   在左侧菜单找到 **机器人**（或应用详情页 → **添加能力** → **机器人**），点击启用。启用后可以看到「机器人配置」区域。

6. **配置事件与回调**

   进入应用的 **添加事件与回调** 页面（或左侧菜单 **事件与回调**），这里有三个 Tab：

   **① 加密策略 Tab**
   
   点击 **加密策略** 标签，记录以下信息：
   - **Encrypt Key** → 对应 `.env` 的 `LARK_ENCRYPT_KEY`
   - **Verification Token** → 对应 `.env` 的 `LARK_VERIFICATION_TOKEN`

   > 这两个值可以自定义生成，也可以使用平台默认值。请妥善保存。

   **② 事件配置 Tab**

   - 订阅方式选择 **将事件发送至 开发者服务器**（不要选长链接方式）
   - 点击右侧 **添加事件** 按钮，搜索并添加：**接收消息 (`im.message.receive_v1`)**
   - 所需权限会自动关联（如果提示缺少权限，按提示去权限管理中开通即可）

   **③ 回调配置 Tab**

   - **暂时不填写请求地址 URL**（等服务器部署完成后再回来填写）
   - 部署完成后在此处填写：`https://your-domain.com/lark/callback`，点击保存完成验证

7. **配置权限（⚠️ 关键步骤）**

   进入 **权限管理** 页面，确认已开通以下权限：
   - `im:message` — 获取与发送单聊、群组消息
   - `im:message:send_as_bot` — 以应用身份发送消息
   - `im:message.p2p_msg:readonly` — 读取用户发给机器人的单聊消息
   - `im:message.group_msg:readonly` — 读取群聊中机器人被 @ 的消息（如需群聊支持）
   
   > ⚠️ **重要提醒**：在步骤 6 中添加 `im.message.receive_v1` 事件后，所需权限列表中会显示相关权限项，但这些权限**默认未开通**！必须逐个点击每个权限项右侧的 **「开通权限」** 按钮，确认状态变为「已开通」后才能正常接收消息。如果跳过此步骤，Lark 将不会向你的服务器推送任何消息事件。

8. 发布应用版本

   完成以上配置后，点击 **发布应用**（或创建版本并提交审核）。审核通过后用户才能使用该机器人。

> ⚠️ **关键顺序**：先获取 App ID / Secret / Encrypt Key / Verification Token 等参数，部署好服务器后，再回到 **回调配置** 填写请求地址 URL 完成验证。

### 步骤二：部署 Webhook 服务器

#### 🚀 一键部署（推荐）

运行部署脚本，选择「Lark」即可：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ui-beam-9/docker-image-mirror/main/quick-deploy.sh)
```

> 💡 **提示**：如果国际版无法访问，可使用国内代理：将 `raw.githubusercontent.com` 替换为 `ghproxy.net/https://raw.githubusercontent.com`

脚本功能：
- ✅ 选择安装企业微信或 Lark 服务器
- ✅ 自动检测 Docker 和 Docker Compose
- ✅ 智能检测运行中的容器，提供管理选项（更新/重新安装/停止删除）
- ✅ 支持自定义安装目录（默认 `/opt/lark-webhook`）
- ✅ 两种部署方式可选：Docker 镜像部署 或 服务器直接部署

> 📄 脚本源码：[quick-deploy.sh](./quick-deploy.sh)

<details>
<summary>💡 容器管理功能</summary>

如果检测到已有运行中的 Webhook 服务器，脚本会自动进入管理模式，提供以下选项：

**1️⃣ 更新镜像** — 拉取最新版本镜像，自动重启服务，保留现有配置

**2️⃣ 重新安装** — 可选择备份现有配置，删除现有部署，重新进行全新安装

**3️⃣ 停止并删除** — 停止运行中的服务，可选择是否删除部署目录

</details>

#### 🔧 手动部署

**方式一：Docker 镜像部署（推荐）**

```bash
# 1. 创建部署目录
mkdir webhook/lark && cd webhook/lark 

# 2. 下载配置文件
curl -O https://raw.githubusercontent.com/ui-beam-9/mirror-sync-assistant/main/webhook/lark/.env.example
curl -O https://raw.githubusercontent.com/ui-beam-9/mirror-sync-assistant/main/webhook/lark/docker-compose.yml
mv .env.example .env

# 3. 编辑 .env 文件，填入步骤一获取的参数
nano .env

# 4. 启动服务
docker-compose up -d

# 5. 查看日志
docker-compose logs -f
```

**方式二：服务器直接部署（自定义代码）**

```bash
# 1. 克隆项目
git clone https://github.com/ui-beam-9/mirror-sync-assistant.git
cd mirror-sync-assistant/webhook/lark

# 2. 配置环境变量
cp .env.example .env
nano .env  # 填入步骤一获取的参数

# 3. 修改 docker-compose.yml 使用本地构建
nano docker-compose.yml
# 注释掉: image: swr.cn-east-3.myhuaweicloud.com/ui_beam-images/lark-webhook-server:latest
# 取消注释: # build: .

# 4. 启动服务
docker-compose up -d
```

### 步骤三：配置环境变量

部署时编辑 `.env` 文件，填入步骤一获取的参数：

```bash
cd lark-webhook
nano .env
```

```bash
# Lark 应用配置（来自步骤一）
LARK_APP_ID=cli_xxxxxxxxxxxxx                # App ID（应用详情 → 凭证与基础信息）
LARK_APP_SECRET=your_app_secret_here          # App Secret（应用详情 → 凭证与基础信息）
LARK_VERIFICATION_TOKEN=your_token_here       # Verification Token（事件订阅页面）
LARK_ENCRYPT_KEY=your_encrypt_key_here        # Encrypt Key（事件订阅页面）
LARK_API_DOMAIN=https://open.larksuite.com    # Lark API 域名（国际版）

# GitHub 配置
GITHUB_TOKEN=ghp_xxxxx                        # GitHub Personal Access Token
GITHUB_REPO=owner/repo                        # 仓库名称（格式：owner/repo）

# Webhook 配置
WEBHOOK_SECRET=your_webhook_secret            # Webhook 验证密钥
PORT=8081                                     # 监听端口（默认 8081）
```

| 配置项 | 说明 | 获取方式 |
|--------|------|---------|
| `LARK_APP_ID` | 应用 ID | Lark 开放平台 → 应用详情 → 凭证与基础信息 |
| `LARK_APP_SECRET` | 应用密钥 | Lark 开放平台 → 应用详情 → 凭证与基础信息 |
| `LARK_VERIFICATION_TOKEN` | 验证 Token | Lark 开放平台 → 应用详情 → **事件与回调** → **加密策略** Tab |
| `LARK_ENCRYPT_KEY` | 加密密钥 | Lark 开放平台 → 应用详情 → **事件与回调** → **加密策略** Tab |
| `LARK_API_DOMAIN` | API 域名 | 国际版 Lark：`https://open.larksuite.com`<br>中国版飞书：`https://open.feishu.cn` |
| `GITHUB_TOKEN` | GitHub Token | [GitHub Settings](https://github.com/settings/tokens)，需要 `repo` 权限 |
| `GITHUB_REPO` | 仓库名称 | 格式：`owner/repo` |
| `WEBHOOK_SECRET` | Webhook 验证密钥 | 随机生成，至少 32 位<br>**⚠️ 需要同步配置到 GitHub Secrets 中** |
| `PORT` | 监听端口 | 默认 `8081`（与企业微信服务器 `8080` 区分） |

> ⚠️ **部署完成后**，回到 Lark 开放平台 → 应用详情 → **事件与回调** → **回调配置** Tab，填写请求地址 URL：`https://your-domain.com/lark/callback`，点击保存完成验证。

### 步骤四：使用步骤

1. 在 Lark 中搜索并打开 **镜像同步助手** 应用
2. 直接发送镜像名称，例如：
   ```
   docker.io/library/nginx:latest
   ```
3. 服务器自动创建 GitHub Issue 并触发同步
4. 收到实时状态通知：

   **① 任务创建**
   ```
   ✅ 镜像同步任务已创建

   镜像: docker.io/library/nginx:latest
   Issue: #123
   状态: 等待同步

   查看详情: https://github.com/...
   ```

   **② 同步中**
   ```
   🔄 镜像正在同步中

   镜像: docker.io/library/nginx:latest
   Issue: #123
   进度: 正在同步...
   ```

   **③ 同步成功**
   ```
   ✅ 镜像同步成功

   镜像: docker.io/library/nginx:latest
   Issue: #123

   📦 快捷命令：
   docker pull swr.cn-east-3.myhuaweicloud.com/ui_beam-images/nginx:latest

   查看详情: https://github.com/...
   ```

   **④ 同步失败**（如有）
   ```
   ❌ 镜像同步失败

   镜像: docker.io/library/nginx:latest
   Issue: #123

   失败原因: 镜像不存在或网络超时

   查看日志: https://github.com/.../actions/runs/...
   ```

---

## ⚙️ 配置说明

### 必需的 GitHub Secrets

在 `Settings` → `Secrets and variables` → `Actions` 中配置以下 Secrets：

#### 1. 华为云访问凭证

| Secret 名称 | 说明 | 获取方式 |
|------------|------|---------|
| `HUAWEI_CLOUD_ACCESS_KEY` | 华为云 Access Key (AK) | [华为云访问凭证](https://console.huaweicloud.com/iam#/mine/accessKey) |
| `HUAWEI_CLOUD_SECRET_KEY` | 华为云 Secret Key (SK) | [华为云访问凭证](https://console.huaweicloud.com/iam#/mine/accessKey) |

#### 2. 华为云 SWR 配置

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `HUAWEI_SWR_REGION` | 华为云 SWR 区域代码 | `cn-east-3` |
| `HUAWEI_SWR_NAMESPACE` | 华为云 SWR 组织名称 | `your-organization` |

**⚠️ 注意**：
- `HUAWEI_SWR_REGION` 只需填写区域代码（如 `cn-east-3`），不要填写完整域名
- 组织名称需要在 [华为云 SWR 控制台](https://console.huaweicloud.com/swr/?region=cn-east-3#/swr/dashboard) 预先创建
- 该链接默认打开华东-上海一区域，如需切换区域，请在页面顶部自行选择

#### 3. Docker 登录凭证

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `HUAWEI_SWR_DOCKER_USERNAME` | 华为云 SWR Docker 登录用户名 | `cn-east-3@YOUR_AK` |
| `HUAWEI_SWR_DOCKER_PASSWORD` | 华为云 SWR Docker 登录密码 | `从 SWR 控制台获取` |

**获取 Docker 登录密码**：
1. 登录 [华为云 SWR 控制台](https://console.huaweicloud.com/swr/?region=cn-east-3#/swr/dashboard)
2. 总览 → 右上角登录指令
3. 查看并复制登录密码，建议使用长期有效登录指令

#### 4. 企业微信通知配置（使用企业微信通知时必需）

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `WECOM_WEBHOOK_URL` | 企业微信 Webhook 服务器地址 | `https://your-webhook-server.com` |
| `WEBHOOK_SECRET` | Webhook 验证密钥 | 与 `.env` 中的 `WEBHOOK_SECRET` 相同 |

**配置说明**：
- `WECOM_WEBHOOK_URL` 是你部署的企业微信 webhook 服务器的公网地址（不包含路径）
- `WEBHOOK_SECRET` 用于验证 GitHub Actions 调用的合法性，必须与 webhook 服务器的 `.env` 中配置的值一致
- 该配置用于实现多状态通知功能（同步中、同步成功、同步失败）

#### 5. Lark 通知配置（使用 Lark 通知时必需）

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `LARK_WEBHOOK_URL` | Lark Webhook 服务器地址 | `https://your-lark-server.com` |

**配置说明**：
- `LARK_WEBHOOK_URL` 是你部署的 Lark webhook 服务器的公网地址（不包含路径）
- Lark 服务器默认监听 `8081` 端口，与企业微信服务器 `8080` 端口区分
- **`WEBHOOK_SECRET` 复用已有的 Secret**（Lark 服务器 `.env` 中的 `WEBHOOK_SECRET` 应与 GitHub Secrets 中的 `WEBHOOK_SECRET` 保持一致）

### 可选的 GitHub Secrets

#### 5. 镜像域名去除选项

| Secret 名称 | 可选值 | 默认值 | 说明 |
|------------|--------|--------|------|
| `REMOVE_SOURCE_DOMAIN` | `true` / `false` | `false` | 是否去除源镜像的域名部分 |

---

## 🔧 域名去除配置详解

### 什么是域名去除？

控制在同步镜像时，是否保留源镜像的域名部分。

### 效果对比

#### 场景 1：`REMOVE_SOURCE_DOMAIN = true` （推荐）

去除域名，路径更简洁：

| 源镜像 | 同步后的 SWR 路径 |
|--------|------------------|
| `docker.io/library/busybox:latest` | `swr.cn-east-3.myhuaweicloud.com/namespace/library/busybox:latest` |
| `gcr.io/google-containers/pause:3.1` | `swr.cn-east-3.myhuaweicloud.com/namespace/google-containers/pause:3.1` |
| `quay.io/prometheus/node-exporter:v1.0.0` | `swr.cn-east-3.myhuaweicloud.com/namespace/prometheus/node-exporter:v1.0.0` |

**优点**：
- ✅ 路径简洁，易于使用
- ✅ 节省 SWR 存储空间
- ✅ 符合镜像加速服务习惯

#### 场景 2：`REMOVE_SOURCE_DOMAIN = false` 或不设置

保留完整路径：

| 源镜像 | 同步后的 SWR 路径 |
|--------|------------------|
| `docker.io/library/busybox:latest` | `swr.cn-east-3.myhuaweicloud.com/namespace/docker.io/library/busybox:latest` |
| `gcr.io/google-containers/pause:3.1` | `swr.cn-east-3.myhuaweicloud.com/namespace/gcr.io/google-containers/pause:3.1` |

**优点**：
- ✅ 保留完整源信息
- ✅ 便于追溯镜像来源
- ✅ 可区分不同源的同名镜像

### 推荐配置

大多数情况下推荐设置 `REMOVE_SOURCE_DOMAIN = true`：
- 路径更简洁
- 节省存储空间
- 使用更方便

---

华为云容器镜像服务（SWR）支持以下区域，按地理位置分类：

### 🌏 亚太（13 个区域）

**中国**：
| 区域代码 | 区域名称 | 镜像仓库地址 |
|---------|---------|-------------|
| `cn-north-4` | 华北-北京四 | `swr.cn-north-4.myhuaweicloud.com` |
| `cn-north-9` | 华北-乌兰察布一 | `swr.cn-north-9.myhuaweicloud.com` |
| `cn-north-12` | 华北三 | `swr.cn-north-12.myhuaweicloud.com` |
| `cn-east-3` | 华东-上海一 | `swr.cn-east-3.myhuaweicloud.com` |
| `cn-east-4` | 华东二 | `swr.cn-east-4.myhuaweicloud.com` |
| `cn-east-5` | 华东-青岛 | `swr.cn-east-5.myhuaweicloud.com` |
| `cn-south-1` | 华南-广州 | `swr.cn-south-1.myhuaweicloud.com` |
| `cn-south-4` | 华南-广州-友好用户环境 | `swr.cn-south-4.myhuaweicloud.com` |
| `cn-southwest-2` | 西南-贵阳一 | `swr.cn-southwest-2.myhuaweicloud.com` |
| `ap-southeast-1` | 中国-香港 | `swr.ap-southeast-1.myhuaweicloud.com` |

**其他亚太地区**：
| 区域代码 | 区域名称 | 镜像仓库地址 |
|---------|---------|-------------|
| `ap-southeast-2` | 亚太-曼谷 | `swr.ap-southeast-2.myhuaweicloud.com` |
| `ap-southeast-3` | 亚太-新加坡 | `swr.ap-southeast-3.myhuaweicloud.com` |
| `ap-southeast-4` | 亚太-雅加达 | `swr.ap-southeast-4.myhuaweicloud.com` |

### 🕌 中东（1 个区域）

| 区域代码 | 区域名称 | 镜像仓库地址 |
|---------|---------|-------------|
| `me-east-1` | 中东-利雅得 | `swr.me-east-1.myhuaweicloud.com` |

### 🌍 非洲（2 个区域）

| 区域代码 | 区域名称 | 镜像仓库地址 |
|---------|---------|-------------|
| `af-south-1` | 非洲-约翰内斯堡 | `swr.af-south-1.myhuaweicloud.com` |
| `af-north-1` | 非洲-开罗 | `swr.af-north-1.myhuaweicloud.com` |

### 🇹🇷 土耳其（1 个区域）

| 区域代码 | 区域名称 | 镜像仓库地址 |
|---------|---------|-------------|
| `tr-west-1` | 土耳其-伊斯坦布尔 | `swr.tr-west-1.myhuaweicloud.com` |

### 🌎 拉美（3 个区域）

| 区域代码 | 区域名称 | 镜像仓库地址 |
|---------|---------|-------------|
| `la-north-2` | 拉美-墨西哥城二 | `swr.la-north-2.myhuaweicloud.com` |
| `sa-brazil-1` | 拉美-圣保罗一 | `swr.sa-brazil-1.myhuaweicloud.com` |
| `la-south-2` | 拉美-圣地亚哥 | `swr.la-south-2.myhuaweicloud.com` |

---

## 🔄 同步流程

```
提交 Issue
    ↓
验证镜像名称格式
    ↓
登录华为云 SWR
    ↓
使用 Skopeo 同步镜像
    ↓
设置镜像仓库为公开
    ↓
验证仓库公开状态
    ↓
更新 Issue 并关闭
```

---

## 💡 使用示例

### 同步 Docker Hub 镜像

在 Issue 中填写：
```
docker.io/library/nginx:latest
```

同步后可通过以下方式拉取（假设 `REMOVE_SOURCE_DOMAIN = true`）：
```bash
docker pull swr.cn-east-3.myhuaweicloud.com/your-namespace/library/nginx:latest
```

### 同步 Google Container Registry 镜像

在 Issue 中填写：
```
gcr.io/google-containers/pause:3.9
```

同步后拉取：
```bash
docker pull swr.cn-east-3.myhuaweicloud.com/your-namespace/google-containers/pause:3.9
```

### 同步 Quay.io 镜像

在 Issue 中填写：
```
quay.io/prometheus/node-exporter:v1.7.0
```

同步后拉取：
```bash
docker pull swr.cn-east-3.myhuaweicloud.com/your-namespace/prometheus/node-exporter:v1.7.0
```

---

## 🛠️ 技术架构

### 核心组件

- **GitHub Actions**: 自动化工作流引擎
- **Webhook 服务器**：接收消息并自动创建 GitHub Issues
  - **企业微信 Webhook**：接收企业微信消息
  - **Lark Webhook**：接收 Lark（国际版飞书）消息
- **Skopeo**: 镜像复制工具，无需本地存储
- **华为云 Python SDK**: 官方 SDK，用于设置和验证镜像权限
- **华为云 SWR**: 目标镜像仓库

### 工作流程

```
┌──────────────────────────┐
│   用户在企业微信/Lark      │
│   发送镜像名称消息         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   Webhook 服务器          │
│  （你的服务器，公网地址）  │
│  - 接收并解密消息         │
│  - 提取镜像名称           │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    调用 GitHub API       │
│    创建 Issue            │
└────────────┬─────────────┘
             │
       ┌─────┴─────┐
       │           │
       ▼           ▼
┌─────────────┐  ┌──────────────────────┐
│GitHub Actions│  │  调用消息平台 API     │
│  自动同步    │  │  发送通知消息         │
│             │  └──────────┬───────────┘
│  - 登录 SWR │             │
│  - 同步镜像 │             ▼
│  - 设为公开 │  ┌──────────────────────┐
└──────┬──────┘  │   用户收到通知消息    │
       │         │                      │
       ▼         │  ✅ 镜像同步任务已创建 │
┌─────────────┐  │  镜像: nginx:latest  │
│  华为云 SWR  │  │  Issue: #123         │
│  存储镜像    │  │  状态: 等待同步       │
└─────────────┘  └──────────────────────┘
```

**说明**：
- **Webhook 服务器**：需要部署在有公网访问的服务器上，支持企业微信（端口 8080）和 Lark（端口 8081）
- **消息通知**：Issue 创建后立即发送，用户实时收到反馈

### 依赖包

项目自动安装以下 Python 依赖：
- `huaweicloudsdkcore`: 华为云 SDK 核心库
- `huaweicloudsdkswr`: 华为云容器镜像服务 SDK

### GitHub Actions 工作流

项目包含两个自动化工作流：

#### 1. 镜像同步工作流（`target-image-sync.yml`）
- **触发条件**: 创建带有 `sync image` 标签的 Issue
- **功能**:
  - 使用 Skopeo 同步 Docker 镜像到华为云 SWR
  - 自动设置镜像仓库为公开
  - 验证镜像仓库状态
  - 同步完成后自动关闭 Issue

#### 2. Docker 镜像构建工作流（`build-docker-image.yml`）
- **触发条件**: 
  - 推送代码到 `main`/`master` 分支（`wecom-webhook/` 或 `lark-webhook/` 目录有变化）
  - 每天北京时间 0:00 和 12:00 定时构建
  - 手动触发
- **功能**:
  - 自动构建企业微信服务器 Docker 镜像（`wecom-webhook-server`）
  - 自动构建 Lark 服务器 Docker 镜像（`lark-webhook-server`）
  - 仅在有变更时构建对应镜像（通过 paths-filter 智能检测）
  - 推送镜像到华为云 SWR（`latest` 标签）
  - 自动设置镜像仓库为公开
  - 使用 GitHub Actions 缓存加速构建

**使用预构建镜像**：
```bash
# 企业微信服务器
docker pull swr.cn-east-3.myhuaweicloud.com/ui_beam-images/wecom-webhook-server:latest

# Lark 服务器
docker pull swr.cn-east-3.myhuaweicloud.com/ui_beam-images/lark-webhook-server:latest
```

### 技术优势

1. **安全可靠**: 使用华为云官方 SDK，减少安全风险
2. **稳定高效**: Skopeo 直接复制，无需本地存储
3. **完善日志**: 详细的执行日志和错误提示
4. **易于维护**: 代码结构清晰，注释完整
5. **灵活扩展**: 支持多种配置选项

---

## 📝 配置步骤

### 第一步：创建华为云 SWR 组织

1. 登录 [华为云 SWR 控制台](https://console.huaweicloud.com/swr/?region=cn-east-3#/swr/dashboard)
   - 该链接默认打开华东-上海一区域，如需修改，请在页面顶部切换区域
2. 点击左侧菜单 **组织管理**
3. 点击 **创建组织**，输入组织名称并创建

### 第二步：获取访问凭证

1. 访问 [华为云访问凭证](https://console.huaweicloud.com/iam#/mine/accessKey)
2. 创建或查看 Access Key (AK) 和 Secret Key (SK)
3. 在 [SWR 控制台](https://console.huaweicloud.com/swr/?region=cn-east-3#/swr/dashboard) 获取 Docker 登录密码

### 第三步：配置 GitHub Secrets

1. 进入你的 GitHub 仓库
2. 点击 `Settings` → `Secrets and variables` → `Actions`
3. 点击 `New repository secret`
4. 依次添加所有必需的 Secrets

### 第四步：测试同步

1. 创建测试 Issue，填写镜像名称（如：`alpine:latest`）
2. 提交 Issue，观察 Actions 执行日志
3. 验证镜像是否成功同步到 SWR

---

## ⚠️ 注意事项

1. **AK/SK 安全**: 请妥善保管访问密钥，不要提交到代码仓库
2. **区域一致性**: 确保所有配置中的区域代码保持一致
3. **组织名称**: 必须在 [华为云 SWR 控制台](https://console.huaweicloud.com/swr/?region=cn-east-3#/swr/dashboard) 预先创建组织
4. **权限要求**: AK/SK 需要有 SWR 的读写权限
5. **配额限制**: 注意华为云 SWR 的存储配额和流量限制
6. **镜像大小**: 大镜像同步需要更长时间，请耐心等待

---

## 🔍 故障排查

### Issue 同步失败

1. 检查 Actions 执行日志，查看具体错误信息
2. 确认所有 Secrets 配置正确
3. 验证镜像名称格式是否正确
4. 确认华为云账户状态和 SWR 配额

### 镜像无法拉取

1. 确认镜像已成功同步到 SWR
2. 检查仓库是否设置为公开
3. 验证拉取命令中的域名和路径是否正确

### 仓库设置公开失败

1. 检查 AK/SK 是否有 SWR 权限
2. 确认组织名称是否存在
3. 查看 Python 脚本执行日志

### 企业微信消息接收问题

1. 检查 Webhook 服务器是否正常运行：`curl http://localhost:8080/health`
2. 确认企业微信应用配置是否正确（`WECOM_CORP_ID`, `WECOM_AGENT_ID`, `WECOM_SECRET`）
3. 检查企业微信 API 反代是否可用
4. 查看服务器日志：`cd wecom-webhook && docker-compose logs -f`
5. 验证 Access Token 获取是否成功
6. 确认 GitHub Token 权限正确

### Lark 消息接收问题

1. 检查 Lark 服务器是否正常运行：`curl http://localhost:8081/health`
2. 确认 Lark 应用配置是否正确（`LARK_APP_ID`, `LARK_APP_SECRET`）
3. 验证事件订阅 URL 是否可公网访问
4. 检查 Verification Token 和 Encrypt Key 是否正确
5. 查看服务器日志：`cd lark-webhook && docker-compose logs -f`
6. **检查权限是否已开通**：进入 Lark 开放平台 → 应用详情 → **权限管理**，确认 `im.message.receive_v1` 事件所需的每个权限项右侧都显示「已开通」。添加事件后权限**不会自动开通**，必须逐个手动点击「开通权限」按钮
7. **确认应用已发布**：进入 Lark 开放平台 → 应用详情 → **版本管理与发布**，确认已创建版本并发布（审核通过后生效）
8. 确认 GitHub Token 权限正确

---

## 📚 相关资源

### 官方文档
- [华为云 SWR 官方文档](https://support.huaweicloud.com/swr/index.html)
- [华为云 Python SDK](https://github.com/huaweicloud/huaweicloud-sdk-python-v3)
- [企业微信开发文档](https://developer.work.weixin.qq.com/document/)
- [Skopeo 官方文档](https://github.com/containers/skopeo)
- [GitHub Actions 文档](https://docs.github.com/en/actions)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

项目基于 [docker-registry-mirrors](https://github.com/kubesre/docker-registry-mirrors) 修改。

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

</div>

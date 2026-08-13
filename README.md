# 小伴：可评测的长期记忆陪伴 Agent

本仓库是一个支持语音交互的陪伴型 Agent 本地原型。
<img width="2286" height="1442" alt="0d50de58-0ee0-46d2-889e-285ca4ec46f1" src="https://github.com/user-attachments/assets/112f435b-3250-490e-9e75-a44386841bcc" />


当前代码库主要拆分为两个服务：

* `HDZB_ASR`：音频网关服务。负责接收上传音频，使用 FunASR 进行语音识别，可选执行说话人识别，并将识别出的文本转发给 AI 服务。
* `HDZB_agent`：AI Agent 服务。负责陪伴式对话、天气查询、系统意图识别、简单记忆管理以及家庭成员信息管理。

项目预期发展为具备两种主要交互模式的陪伴型 Agent：

* 儿童模式：安全故事、学习陪伴、情绪安抚，以及由家长配置的使用边界。
* 老人模式：温暖陪伴、提醒事项、天气查询、家庭联系人支持，以及简单的设备控制。

## 当前本地架构

```text
音频文件 / 设备麦克风
        |
        v
HDZB_ASR，端口 8015
  - 上传音频
  - ASR 语音转文字
  - 说话人识别
  - 转发给 Agent
        |
        v
HDZB_agent，端口 8017
  - LLM 对话
  - Function Calling 工具调用
  - 天气查询
  - 意图识别
  - 内存中的会话 / 用户画像数据
```

## 评测与执行轨迹分析

现在每次 `/agent/chat` 请求的返回结果中都会包含 `metadata.trace_id`。

可以通过以下接口查看最近的执行记录：

```text
GET /agent/traces
```

每条执行轨迹包含：

* Agent 选择了哪些工具
* 工具调用参数
* 工具调用结果
* 最终生成的回复
* 端到端执行延迟

借助这些结构化执行信息，可以把实际运行过程中出现的失败案例整理成带标签的评测样本，用于后续定位问题和优化 Agent。

`evaluation/` 目录中包含 `CompanionBench`，这是一个透明的 JSONL 格式评测基准，目前主要用于评估：

* 工具选择能力
* 长期记忆召回能力
* 记忆冲突与更新能力
* 安全性

可以直接对已经保存的 Agent 输出进行评分，不会在评分过程中额外进行隐藏的模型调用：

```bash
python evaluation/run_eval.py \
  --dataset evaluation/datasets/companion_bench.jsonl \
  --results evaluation/datasets/example_results.jsonl
```

生成的评测报告会保存到：

```text
evaluation/reports/latest.json
```

在比较不同模型、Prompt 策略或记忆策略时，建议分别保存每次实验的输出，再统一使用该评分器进行评测，以保证实验结果可复现。

## 本地环境配置

项目默认使用名为 `caremate` 的独立 Conda 环境。

最快的纯文本 Agent 环境配置方式为：

```bash
./scripts/setup_local.sh
```

该脚本会：

* 创建或复用 `caremate` Conda 环境
* 安装 Agent 所需依赖
* 如果 `HDZB_agent/.env` 不存在，则基于 `.env.example` 自动创建
* 不会覆盖已经存在的本地 `.env` 配置
* 不会将项目依赖安装到 Conda 的 `base` 环境中

启动服务之前，需要打开：

```text
HDZB_agent/.env
```

并将其中的两个占位 API Key 替换为自己的真实配置。

如果希望使用其他 Conda 环境名称，可以在执行脚本前设置 `CONDA_ENV_NAME`：

```bash
CONDA_ENV_NAME=my-agent ./scripts/setup_local.sh
CONDA_ENV_NAME=my-agent ./scripts/start_agent.sh
```

如果还需要安装可选的、依赖较重的语音识别环境：

```bash
./scripts/setup_local.sh --with-asr
```

在 macOS 上，ASR 安装流程还会在同一个 Conda 环境中安装 FFmpeg。FunASR 和 TorchCodec 在解码上传音频时需要使用相关的 `libav*` 动态库。

也可以手动创建 Conda 环境：

```bash
conda create -n caremate python=3.11
conda activate caremate
```

安装 Agent 服务依赖：

```bash
pip install -r HDZB_agent/requirements.txt
```

安装 ASR 服务依赖：

```bash
pip install -r HDZB_ASR/requirements.txt
```

复制环境变量文件并填写自己的 API Key。

ASR 网关读取项目根目录下的 `.env`，Agent 服务优先读取 `HDZB_agent/.env`，如果不存在则回退到根目录 `.env`。

请勿将这两个文件提交到 Git 仓库。

```bash
cp .env.example .env
cp .env.example HDZB_agent/.env
```

## 本地运行

建议首先只启动文本 Agent：

```bash
./scripts/start_agent.sh
```

启动后打开：

```text
http://127.0.0.1:8017/docs
```

即可查看 Agent 的 FastAPI 接口文档。

ASR 音频网关属于可选功能。在使用 `--with-asr` 完成环境安装后，可以打开第二个终端执行：

```bash
./scripts/start_asr.sh
```

Agent 服务自身还提供了一个本地聊天网页：

```text
http://127.0.0.1:8017/app/
```

该网页会直接调用已经验证过的文本 Agent API。

当 Agent 识别到 `SET_ALARM` 意图时，会将提醒信息持久化到 SQLite 数据库中。网页端会持续轮询已经到期的提醒，并在页面保持打开时显示浏览器通知。

需要注意的是，目前实现的是**本地网页提醒**，并不是操作系统后台闹钟。因此网页关闭后，浏览器不会像系统闹钟一样在后台持续执行提醒。

网页还支持用户主动授权浏览器地理位置。

点击：

```text
使用当前位置
```

并授予权限后，浏览器会把经纬度发送给本地 Agent。

Agent 使用高德地图逆地理编码获取当前城市和区县，并将其保存到当前会话中。之后 Agent 就可以根据保存的位置回答：

* 当前天气怎么样
* 今天是否适合出门
* 本地天气相关问题

位置信息只存储在本地 SQLite 数据库中。

### 手动启动 Agent 服务

```bash
cd HDZB_agent
uvicorn main_agent:app --host "${SERVER_HOST:-0.0.0.0}" --port "${SERVER_PORT:-8017}" --reload
```

### 手动启动 ASR 网关

在另一个终端中执行：

```bash
cd HDZB_ASR
uvicorn main:app --host "${ASR_SERVER_HOST:-0.0.0.0}" --port "${ASR_SERVER_PORT:-8015}" --reload
```

### API 文档地址

Agent API：

```text
http://localhost:8017/docs
```

ASR 网关 API：

```text
http://localhost:8015/docs
```

## 本地请求示例

### 直接进行 Agent 文本对话

```bash
curl -X POST "http://localhost:8017/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好，今天天气怎么样？","session_id":"local-device-001","agent_type":"companion","mode":"elder"}'
```

### 设置设备默认陪伴模式

```bash
curl -X PUT "http://localhost:8017/agent/devices/local-device-001/mode" \
  -H "Content-Type: application/json" \
  -d '{"mode":"child"}'
```

### 设置面向硬件的设备配置

```bash
curl -X PUT "http://localhost:8017/agent/devices/local-device-001/config" \
  -H "Content-Type: application/json" \
  -d '{"volume":55,"light_profile":"soft","wake_method":"tap_head","usage_start":"08:00","usage_end":"21:30","content_policy":"需要家长知情后再处理定位和联系人信息"}'
```

当前陪伴模式的解析优先级如下：

1. 聊天请求中显式传入的 `mode`
2. `/agent/devices/{device_id}/mode` 中保存的设备默认模式
3. 如果以上都没有，则默认使用 `elder`

最终确定的模式以及设备配置也会被注入 Agent 的 System Prompt。

因此，儿童模式和老人模式可以共享相同的 Agent 核心能力，同时拥有不同的：

* 回复风格
* 交互策略
* 安全约束
* 内容边界

### 通过 ASR 网关进行语音对话

```bash
curl -X POST "http://localhost:8015/agent/chat" \
  -F "file=@HDZB_ASR/@user1@1.m4a"
```

当前 ASR 网关会从类似下面的文件名中临时提取设备 ID 或 Session ID：

```text
@user1@1.m4a
```

后续面向真实硬件设备时，应该使用正式的设备注册机制和 Token 身份认证替代这种临时方案。



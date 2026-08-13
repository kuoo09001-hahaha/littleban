# 小伴：可评测的长期记忆陪伴 Agent

This repository is a local prototype for a voice-enabled companion Agent. Its
core focus is now **Agent evaluation and optimisation**: reproducible tool-use,
long-term-memory, and safety evaluation, plus structured execution traces for
error analysis. Hardware and voice integrations are optional extensions rather
than the product's primary story.

The current codebase is split into two services:

- `HDZB_ASR`: audio gateway service. It receives uploaded audio, runs FunASR speech recognition, optionally identifies the speaker, and forwards recognized text to an AI service.
- `HDZB_agent`: AI Agent service. It handles companion chat, weather lookup, system-intent recognition, simple memory, and family-member information.

The intended product direction is a companion Agent with two interaction modes:

- Child mode: safe storytelling, learning, emotional comfort, and parent-configured boundaries.
- Elder mode: warm companionship, reminders, weather, family contact support, and simple device commands.

## Current Local Architecture

```text
Audio file / device microphone
        |
        v
HDZB_ASR on port 8015
  - upload audio
  - ASR transcription
  - speaker recognition
  - gateway to Agent
        |
        v
HDZB_agent on port 8017
  - LLM chat
  - function calling tools
  - weather
  - intent detection
  - in-memory conversation/profile data
```

## Evaluation and trace analysis

Every `/agent/chat` response now returns `metadata.trace_id`. Inspect recent
executions at `GET /agent/traces`; a trace includes the selected tools, tool
arguments, tool results, final response and end-to-end latency. This makes it
possible to turn production failures into labelled evaluation examples.

`evaluation/` contains `CompanionBench`, a transparent JSONL benchmark for
tool selection, memory recall/conflict updates and safety. Score saved Agent
outputs without performing hidden model calls:

```bash
python evaluation/run_eval.py \
  --dataset evaluation/datasets/companion_bench.jsonl \
  --results evaluation/datasets/example_results.jsonl
```

The generated report is written to `evaluation/reports/latest.json`. When
comparing models or prompt/memory strategies, save each run's output separately
and use this same scorer.

## Local Setup

This project uses a dedicated Conda environment named `caremate` by default.
The fastest way to prepare a text-only Agent environment is:

```bash
./scripts/setup_local.sh
```

The script creates (or reuses) the `caremate` Conda environment, installs the
Agent dependencies and creates
`HDZB_agent/.env` from `.env.example` only if it does not already exist. Open
that file and replace the two placeholder keys before starting the service.
It does not install project packages into Conda's `base` environment.

To use another name, set `CONDA_ENV_NAME` before running either script:

```bash
CONDA_ENV_NAME=my-agent ./scripts/setup_local.sh
CONDA_ENV_NAME=my-agent ./scripts/start_agent.sh
```

To also install the optional, heavier speech-recognition dependencies:

```bash
./scripts/setup_local.sh --with-asr
```

On macOS, the ASR setup also installs FFmpeg into the same Conda environment;
FunASR/TorchCodec needs its `libav*` libraries when decoding uploaded audio.

Manual Conda setup is also supported:

```bash
conda create -n caremate python=3.11
conda activate caremate
```

Install the Agent service dependencies:

```bash
pip install -r HDZB_agent/requirements.txt
```

Install the ASR service dependencies:

```bash
pip install -r HDZB_ASR/requirements.txt
```

Copy environment variables and fill in your API keys. The ASR gateway reads the top-level `.env`; the Agent service reads `HDZB_agent/.env` (and falls back to the top-level `.env`). Never commit either file.

```bash
cp .env.example .env
cp .env.example HDZB_agent/.env
```

## Run Locally

Start only the text Agent first:

```bash
./scripts/start_agent.sh
```

Then open `http://127.0.0.1:8017/docs`. The ASR gateway is optional; after
installing with `--with-asr`, start it in a second terminal with:

```bash
./scripts/start_asr.sh
```

The local chat dashboard is served by the Agent itself:

- `http://127.0.0.1:8017/app/`

It talks directly to the validated text Agent API. When the Agent identifies
a `SET_ALARM` intent, it persists a reminder in SQLite; the dashboard polls
for due reminders and shows a browser notification while the page is open.
This is a local web reminder, not an operating-system background alarm.

The dashboard also supports opt-in browser geolocation. After clicking
“使用当前位置” and granting permission, the browser sends coordinates to the
local Agent, which uses Amap reverse geocoding to save the city/district for
that session. The Agent can then use this saved location for weather and
“是否适合出门” questions. Location is only stored in the local SQLite database.

Manual commands:

Start the Agent service:

```bash
cd HDZB_agent
uvicorn main_agent:app --host "${SERVER_HOST:-0.0.0.0}" --port "${SERVER_PORT:-8017}" --reload
```

Start the ASR gateway service in another terminal:

```bash
cd HDZB_ASR
uvicorn main:app --host "${ASR_SERVER_HOST:-0.0.0.0}" --port "${ASR_SERVER_PORT:-8015}" --reload
```

Open the service docs:

- Agent API: `http://localhost:8017/docs`
- ASR gateway API: `http://localhost:8015/docs`

## Example Local Requests

Direct Agent text chat:

```bash
curl -X POST "http://localhost:8017/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好，今天天气怎么样？","session_id":"local-device-001","agent_type":"companion","mode":"elder"}'
```

Set a device's default companion mode:

```bash
curl -X PUT "http://localhost:8017/agent/devices/local-device-001/mode" \
  -H "Content-Type: application/json" \
  -d '{"mode":"child"}'
```

Set hardware-facing device configuration:

```bash
curl -X PUT "http://localhost:8017/agent/devices/local-device-001/config" \
  -H "Content-Type: application/json" \
  -d '{"volume":55,"light_profile":"soft","wake_method":"tap_head","usage_start":"08:00","usage_end":"21:30","content_policy":"需要家长知情后再处理定位和联系人信息"}'
```

Mode resolution currently follows this order:

1. `mode` in the chat request.
2. Device default mode from `/agent/devices/{device_id}/mode`.
3. `elder` as the compatibility default.

The resolved mode and device configuration are also passed into the Agent system prompt, so child and elder mode now have different response style and safety guidance while still sharing the same core capabilities.

ASR gateway audio chat:

```bash
curl -X POST "http://localhost:8015/agent/chat" \
  -F "file=@HDZB_ASR/@user1@1.m4a"
```

The current ASR gateway extracts a temporary device/session id from filenames such as `@user1@1.m4a`. A later hardware-oriented version should replace this with device registration and token-based authentication.

## Known Technical Debt

- Conversation history and request traces are currently in-process and are lost after restart; structured family-member profiles persist in SQLite.
- Device mode, device configuration, and family-member profiles are stored in SQLite through `SQLITE_DB_PATH`; conversation memory is still in process memory.
- The Agent uses custom function-calling orchestration while some tool classes still inherit from LangChain `BaseTool`. This should be made consistent.
- `main_agent.py` and `companion_agent.py` are too large and should be split into API, service, tool, prompt, and memory modules.
- The ASR gateway still includes legacy companion-service routes on port `8016`.
- TTS is not implemented yet, so the current cloud flow returns text rather than playable speech.

## Recommended Optimization Order

1. Local project hygiene: README, `.env.example`, `.gitignore`, dependency cleanup.
2. Configuration cleanup: remove hard-coded paths and service URLs.
3. API split: move request schemas and routers out of large entry files.
4. Mode system: child and elder mode are represented as domain profiles, wired into the Agent system prompt, and device default mode is persisted in SQLite.
5. Profile persistence: family-member profiles are persisted in SQLite.
6. Device configuration: volume, light profile, wake method, usage window, and content policy are persisted in SQLite and injected into the Agent prompt. Next step is hardware response metadata.
5. Memory persistence: add SQLite for structured profiles and Chroma for semantic memory.
6. TTS and hardware response protocol: return text, audio URL, light actions, vibration actions, and metadata.
7. Family web/admin panel: bind device, set mode, configure contacts, reminders, and usage rules.
8. Tests: add pytest coverage for intent parsing, memory/profile services, tools, and API routes.

# Local Optimization Plan

This plan focuses on improving the project as a local prototype before cloud deployment or hardware integration.

## Stage 0: Project Hygiene

- Add a top-level README that explains the two-service architecture.
- Add `.env.example` so required API keys and ports are visible.
- Add `.gitignore` for Python caches, local secrets, runtime data, and test audio.
- Keep existing audio/document samples in place for now, but prevent new generated files from being tracked later.

## Stage 1: Dependency and Configuration Cleanup

- Normalize `HDZB_agent/requirements.txt`.
- Normalize `HDZB_ASR/requirements.txt`.
- Move hard-coded service URLs and local save paths into settings. The ASR gateway now reads `ASR_SERVER_HOST`, `ASR_SERVER_PORT`, `COMPANION_SERVICE_URL`, `AGENT_SERVICE_URL`, and `SAVE_FILE_DIR` from the environment.
- Keep current ports during local development:
  - ASR gateway: `8015`
  - legacy companion service: `8016`
  - Agent service: `8017`

## Stage 2: API Structure Cleanup

- Split `HDZB_agent/main_agent.py` into routers and schemas. Request/response schemas now live in `HDZB_agent/schemas/agent.py`.
- Weather and personal-info endpoints now live in `HDZB_agent/api/weather.py` and `HDZB_agent/api/personal_info.py`.
- Session management endpoints now live in `HDZB_agent/api/sessions.py`.
- Memory endpoints now live in `HDZB_agent/api/memory.py`.
- Status, debug, metrics, and root endpoints now live in `HDZB_agent/api/status.py`.
- Keep API behavior unchanged while moving code.
- Preserve existing endpoint paths so current tests and manual curl commands still work.

## Stage 3: Agent Core Cleanup

- Split the large `CompanionAgent` into focused services:
  - LLM client
  - Tool executor
  - Intent service
  - Prompt builder
  - Profile service
  - Memory service
- Fix multi-tool `tool_call_id` handling.

## Stage 4: Hardware-Oriented Product Model

- Add `device_id`, `family_id`, `mode`, and `session_id` as first-class concepts. `mode` is now accepted on `AgentRequest`, device default mode is available through `/agent/devices/{device_id}/mode`, device hardware-facing config is available through `/agent/devices/{device_id}/config`, and mode resolution is request > device > default elder.
- Introduce child and elder mode profiles. Initial profiles now live in `HDZB_agent/domain/modes.py` and are passed into the Agent system prompt.
- Define structured device actions for light, vibration, volume, and errors. Volume, light profile, wake method, usage window, and content policy are now persisted and injected into prompts; response action metadata remains to be implemented.

## Stage 5: Persistence and Tests

- Add SQLite for device, family, profile, contact, and reminder data. Device mode persistence is now implemented with `device_modes`; family-member profile persistence is implemented with `family_members`; device configuration persistence is implemented with `device_configs`.
- Connect Chroma-based semantic memory to the Agent flow.
- Add pytest tests for the stable service layer.

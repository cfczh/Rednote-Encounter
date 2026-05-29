# Project Structure

This project is a M5Stack CoreS3 social-agent prototype. The current root keeps the runnable entry points visible, while docs, media, and original source packages are grouped separately.

## Root Entry Points

- `RUNBOOK.md`: flashing and bridge run instructions.
- `pc_ble_agent_bridge.py`: PC-side BLE scanner, LLM caller, and GATT writer.
- `run_bridge.ps1`: starts the PC bridge.
- `flash_xiao_hong.ps1`: compiles/uploads the Xiao Hong firmware slot.
- `flash_zhang_zong.ps1`: compiles/uploads the Zhang Zong firmware slot.
- `list_ports.ps1`: lists serial ports.
- `read_serial.ps1`: reads serial output for quick diagnostics.

## Main Code

- `cores3_encounter/`: Arduino/M5Stack CoreS3 firmware.
- `xiao_hong/xiao_hong/`: Xiao Hong persona/skill files.
- `zhang_zong_skill/`: Zhang Zong persona/skill files.
- `zhang/zhang-agent/`: standalone Zhang agent service code.

## Supporting Folders

- `docs/`: project notes and prompts for implementation work.
- `media/`: demo videos and visual reference media.
- `archives/source_packages/`: original zip/source packages kept for reference.
- `archives/misc/`: non-source leftovers kept out of the root.
- `archives/generated_cache/`: generated Python cache files moved out of the root.
- `build/`: generated Arduino build artifacts.

## Current Next Work

The next implementation task should preserve the existing BLE and bridge chain, then add a clear hardware action state machine, bridge cooldown/call rules, normal UTF-8 prompts, and a stable SD-card resource contract for UI/animation assets.

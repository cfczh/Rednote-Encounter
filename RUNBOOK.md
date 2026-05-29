# M5Stack Social Agent Runbook

## 1. Find Ports

Connect one M5 at a time and run:

```powershell
.\list_ports.ps1
```

Note the `COM` port.

## 2. Flash Xiao Hong

```powershell
.\flash_xiao_hong.ps1 COM5
```

Replace `COM5` with the port shown on your machine.

## 3. Flash Zhang Zong

```powershell
.\flash_zhang_zong.ps1 COM6
```

Replace `COM6` with the second M5 port.

## 4. Start the PC Bridge

```powershell
.\run_bridge.ps1
```

Keep this terminal open. When both M5 devices are nearby, the bridge scans their BLE broadcasts, calls the configured DeepSeek-compatible API, and writes short replies back to the M5 screens.

## Notes

- Xiao Hong is compiled with `LOCAL_PERSONA_SLOT=0`.
- Zhang Zong is compiled with `LOCAL_PERSONA_SLOT=1`.
- API settings are read from `zhang/zhang-agent/.env`.
- If Chinese text shows as boxes on the M5 screen, the BLE and model parts can still be working; the next fix is adding a Chinese font to the M5 display layer.

param(
  [string]$XiaoHongPort = "",
  [string]$ZhangZongPort = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:XIAO_HONG_SERIAL_PORT = if ($XiaoHongPort) { $XiaoHongPort } else { "COM3" }
$env:ZHANG_ZONG_SERIAL_PORT = if ($ZhangZongPort) { $ZhangZongPort } else { "COM7" }

Start-Process "$Root\dashboard.html"
python .\pc_ble_agent_bridge.py

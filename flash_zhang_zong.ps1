param(
  [Parameter(Mandatory = $true)]
  [string]$Port
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ArduinoCli = "C:\Program Files\Arduino CLI\arduino-cli.exe"
$Sketch = Join-Path $Root "cores3_encounter"
$BuildPath = Join-Path $env:TEMP "rednote_m5_build_zhang_zong"

& $ArduinoCli compile `
  --fqbn m5stack:esp32:m5stack_cores3 `
  --build-property "compiler.cpp.extra_flags=-DLOCAL_PERSONA_SLOT=1" `
  --build-path $BuildPath `
  --upload `
  --port $Port `
  $Sketch

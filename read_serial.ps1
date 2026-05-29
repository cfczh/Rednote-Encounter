param(
  [string]$Port = "COM7",
  [int]$Seconds = 8
)

$ErrorActionPreference = "Stop"
$serial = [System.IO.Ports.SerialPort]::new($Port, 115200)
$serial.ReadTimeout = 1000
$serial.Open()
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) {
  try {
    Write-Output $serial.ReadLine()
  } catch {
  }
}
$serial.Close()

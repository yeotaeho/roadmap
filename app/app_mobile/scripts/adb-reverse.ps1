<#
.SYNOPSIS
  연결된 모든 안드로이드 디바이스(에뮬레이터 포함)에 adb reverse 를 일괄 적용합니다.

.DESCRIPTION
  실기기/에뮬레이터 모두 폰의 localhost:<Port> → PC 의 localhost:<Port> 로 포워딩하여
  Flutter 앱이 동일한 baseUrl 로 PC 백엔드를 호출할 수 있게 합니다.

.PARAMETER Port
  포워딩할 포트 (기본 8000). 여러 개 지정 가능.

.PARAMETER Device
  특정 디바이스 시리얼만 지정 (생략 시 전체).

.EXAMPLE
  .\scripts\adb-reverse.ps1
  .\scripts\adb-reverse.ps1 -Port 8000,8080
  .\scripts\adb-reverse.ps1 -Device emulator-5554
#>

[CmdletBinding()]
param(
  [int[]]$Port = @(8000),
  [string]$Device = ''
)

$ErrorActionPreference = 'Stop'

function Get-ConnectedDevices {
  $raw = & adb devices 2>$null
  if (-not $raw) { return @() }
  return $raw |
    Select-Object -Skip 1 |
    Where-Object { $_ -match '\bdevice\b' -and $_ -notmatch 'offline' } |
    ForEach-Object { ($_ -split '\s+')[0] } |
    Where-Object { $_ }
}

$devices = if ($Device) { @($Device) } else { Get-ConnectedDevices }

if (-not $devices -or $devices.Count -eq 0) {
  Write-Warning '연결된 adb 디바이스가 없습니다. (adb devices 결과 비어있음)'
  exit 1
}

foreach ($d in $devices) {
  foreach ($p in $Port) {
    Write-Host "[adb-reverse] $d  tcp:$p -> tcp:$p" -ForegroundColor Cyan
    & adb -s $d reverse "tcp:$p" "tcp:$p" | Out-Null
  }
  Write-Host "[adb-reverse] $d  list:" -ForegroundColor DarkGray
  & adb -s $d reverse --list
}

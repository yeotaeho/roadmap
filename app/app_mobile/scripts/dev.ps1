<#
.SYNOPSIS
  adb reverse 적용 후 flutter run 을 실행합니다 (dart_defines/local.env 자동 주입).

.PARAMETER Device
  실행할 디바이스 시리얼. 생략 시:
    - 디바이스 1개면 자동 선택
    - 2개 이상이면 사용자에게 선택지 표시

.PARAMETER Port
  adb reverse 포트 (기본 8000). 여러 개 가능.

.PARAMETER EnvFile
  Flutter dart-define-from-file 경로 (기본 dart_defines/local.env)

.PARAMETER Release
  release 모드로 실행.

.PARAMETER Args
  flutter run 에 그대로 넘길 추가 인자.

.EXAMPLE
  .\scripts\dev.ps1
  .\scripts\dev.ps1 -Device emulator-5554
  .\scripts\dev.ps1 -Release
  .\scripts\dev.ps1 -- --verbose
#>

[CmdletBinding()]
param(
  [string]$Device = '',
  [int[]]$Port = @(8000),
  [string]$EnvFile = 'dart_defines/local.env',
  [switch]$Release,
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$ExtraArgs
)

$ErrorActionPreference = 'Stop'
$repoMobile = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoMobile

if (-not (Test-Path $EnvFile)) {
  Write-Warning "$EnvFile 가 없습니다. dart_defines/example.env 를 복사해 만들어주세요."
}

function Get-ConnectedDevices {
  $raw = & adb devices 2>$null
  if (-not $raw) { return @() }
  return $raw |
    Select-Object -Skip 1 |
    Where-Object { $_ -match '\bdevice\b' -and $_ -notmatch 'offline' } |
    ForEach-Object { ($_ -split '\s+')[0] } |
    Where-Object { $_ }
}

$devices = Get-ConnectedDevices
if (-not $devices -or $devices.Count -eq 0) {
  throw '연결된 adb 디바이스가 없습니다. USB 디버깅 또는 에뮬레이터를 먼저 켜주세요.'
}

if (-not $Device) {
  if ($devices.Count -eq 1) {
    $Device = $devices[0]
  } else {
    Write-Host '연결된 디바이스:' -ForegroundColor Cyan
    for ($i = 0; $i -lt $devices.Count; $i++) {
      Write-Host "  [$i] $($devices[$i])"
    }
    $idx = Read-Host '실행할 디바이스 번호'
    if ($idx -notmatch '^\d+$' -or [int]$idx -ge $devices.Count) {
      throw "잘못된 선택: $idx"
    }
    $Device = $devices[[int]$idx]
  }
}

Write-Host "==> 디바이스: $Device" -ForegroundColor Green
& (Join-Path $PSScriptRoot 'adb-reverse.ps1') -Device $Device -Port $Port

$flutterArgs = @('run', '-d', $Device, "--dart-define-from-file=$EnvFile")
if ($Release) { $flutterArgs += '--release' }
if ($ExtraArgs) { $flutterArgs += $ExtraArgs }

Write-Host "==> flutter $($flutterArgs -join ' ')" -ForegroundColor Green
& flutter @flutterArgs

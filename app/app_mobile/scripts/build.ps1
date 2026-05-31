<#
.SYNOPSIS
  dart_defines/local.env 를 주입해 Flutter APK/AAB/iOS 빌드를 실행합니다.

.EXAMPLE
  .\scripts\build.ps1
  .\scripts\build.ps1 -Target appbundle -Release
  .\scripts\build.ps1 -EnvFile dart_defines/local.env
#>

[CmdletBinding()]
param(
  [ValidateSet('apk', 'appbundle', 'ios', 'ipa')]
  [string]$Target = 'apk',
  [string]$EnvFile = 'dart_defines/local.env',
  [switch]$Release
)

$ErrorActionPreference = 'Stop'
$repoMobile = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoMobile

if (-not (Test-Path $EnvFile)) {
  Write-Warning "$EnvFile 가 없습니다. dart_defines/example.env 를 복사해 local.env 를 만드세요."
  exit 1
}

$flutterArgs = @('build', $Target, "--dart-define-from-file=$EnvFile")
if ($Release) { $flutterArgs += '--release' }

Write-Host "==> flutter $($flutterArgs -join ' ')" -ForegroundColor Green
& flutter @flutterArgs

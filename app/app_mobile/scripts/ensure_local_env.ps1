# local.env 가 없으면 example.env 를 복사 (최초 1회)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$local = Join-Path $root 'dart_defines/local.env'
$example = Join-Path $root 'dart_defines/example.env'

if (-not (Test-Path $local)) {
  if (-not (Test-Path $example)) {
    throw "dart_defines/example.env 가 없습니다."
  }
  Copy-Item $example $local
  Write-Host "dart_defines/local.env 생성됨 — example.env 를 복사했습니다. 값을 채워주세요." -ForegroundColor Yellow
}

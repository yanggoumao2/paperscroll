<#
  Build the PaperScroll Android APK (Windows).

  The APK is a thin shell: it loads the interface from your PaperScroll server, so later UI updates
  need no reinstall. Pass the address your phone uses to reach the server, e.g. the PC's Tailscale IP.

    .\build-apk.ps1 -Server http://100.x.y.z:8766

  JDK 21 and the Android SDK are taken from JAVA_HOME / ANDROID_HOME, or from ..\toolchain
  (created by .\scripts\setup-android.ps1). Output: ..\dist\PaperScroll.apk (debug-signed) and a copy in
  ..\web\download\ so the phone can download it from the server.
#>
param([string]$Server = $env:PAPERSCROLL_SERVER)
$ErrorActionPreference = 'Stop'
if (-not $Server) { throw 'Pass the server address the phone will use, e.g. -Server http://100.x.y.z:8766' }
$Server = $Server.TrimEnd('/')
$R = Split-Path $PSScriptRoot -Parent; $T = Join-Path $R 'toolchain'
if (Test-Path "$T\jdk21") { $env:JAVA_HOME = "$T\jdk21" }              # the portable toolchain wins: Gradle needs JDK 21
if (Test-Path "$T\android-sdk") { $env:ANDROID_HOME = "$T\android-sdk" }
if (-not $env:JAVA_HOME -or -not $env:ANDROID_HOME) { throw 'JDK 21 / Android SDK not found: set JAVA_HOME and ANDROID_HOME, or run .\scripts\setup-android.ps1' }
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME; $env:Path = "$env:JAVA_HOME\bin;$env:Path"
if (Test-Path "$T\gradle-home") { $env:GRADLE_USER_HOME = "$T\gradle-home" }

Set-Location $PSScriptRoot
if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE) { throw 'npm ci failed' } }
if (Test-Path www) { Remove-Item www -Recurse -Force }
Copy-Item "$R\web" www -Recurse
if (Test-Path www\download) { Remove-Item www\download -Recurse -Force }   # never bundle the APK into itself
"sdk.dir=$($env:ANDROID_HOME -replace '\\','\\')" | Set-Content android\local.properties -Encoding ASCII
npx cap sync android
if ($LASTEXITCODE) { throw 'cap sync failed' }
node scripts/set-server.mjs $Server
if ($LASTEXITCODE) { throw 'set-server failed' }
Set-Location android
.\gradlew.bat assembleDebug --no-daemon --console=plain
if ($LASTEXITCODE) { throw 'gradle failed' }
New-Item -ItemType Directory "$R\dist" -Force | Out-Null
Copy-Item app\build\outputs\apk\debug\app-debug.apk "$R\dist\PaperScroll.apk" -Force
New-Item -ItemType Directory "$R\web\download" -Force | Out-Null
Copy-Item "$R\dist\PaperScroll.apk" "$R\web\download\PaperScroll.apk" -Force
Get-Item "$R\dist\PaperScroll.apk" | Select-Object Name, Length, LastWriteTime
"BUILD_OK  (server: $Server)"

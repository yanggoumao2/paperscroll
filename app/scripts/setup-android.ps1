# Portable JDK 21 + Android SDK for building the APK on Windows. Installs into <repo>\toolchain only (git-ignored).
$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'
$T = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'toolchain'; New-Item -ItemType Directory $T -Force | Out-Null
if (-not (Test-Path "$T\jdk21\bin\java.exe")) {
  Invoke-WebRequest 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse' -OutFile "$T\jdk.zip"
  Expand-Archive "$T\jdk.zip" "$T\jdk-tmp" -Force
  Move-Item (Get-ChildItem "$T\jdk-tmp" | Select -First 1).FullName "$T\jdk21"
  Remove-Item "$T\jdk.zip","$T\jdk-tmp" -Recurse -Force
}
$env:JAVA_HOME = "$T\jdk21"; $env:Path = "$T\jdk21\bin;$env:Path"
if (-not (Test-Path "$T\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat")) {
  Invoke-WebRequest 'https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip' -OutFile "$T\clt.zip"
  Expand-Archive "$T\clt.zip" "$T\clt-tmp" -Force
  New-Item -ItemType Directory "$T\android-sdk\cmdline-tools" -Force | Out-Null
  Move-Item "$T\clt-tmp\cmdline-tools" "$T\android-sdk\cmdline-tools\latest"
  Remove-Item "$T\clt.zip","$T\clt-tmp" -Recurse -Force
}
$sdkm = "$T\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat"
$yes = ("y`n" * 20)
$yes | & $sdkm --sdk_root="$T\android-sdk" --licenses | Out-Null
& $sdkm --sdk_root="$T\android-sdk" "platform-tools" "platforms;android-35" "build-tools;35.0.0" | Select -Last 3
"ANDROID_SETUP_DONE"

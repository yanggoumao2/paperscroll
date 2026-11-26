# Phone-size screenshots of the sandbox server (dev/sandbox_server.py, port 8799) with headless Edge.
# Use -path "__frame" (412x892 iframe; the plain page gets resized at capture time). Each load shows the next paper.
param([int]$n = 4, [string]$size = "504,960", [string]$tag = "m", [string]$path = "")
$E = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$O = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "data\shots"; New-Item -ItemType Directory $O -Force | Out-Null
for ($i = 1; $i -le $n; $i++) {
  & $E --headless=new --disable-gpu --hide-scrollbars "--user-data-dir=$O\edge-$tag$i" "--window-size=$size" --force-device-scale-factor=1 --virtual-time-budget=40000 "--screenshot=$O\$tag$i.png" "http://127.0.0.1:8799/$path" 2>&1 | Out-Null
  "$tag$i " + (Test-Path "$O\$tag$i.png")
}

# Render icon.html masters (1024px) with headless Edge; resizing into Android resources is done by make-res.py.
$E = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"; $D = $PSScriptRoot
foreach ($m in "full", "fg", "splash") {
  $u = ([Uri]"$D\icon.html").AbsoluteUri + "?m=$m"
  & $E --headless=new --disable-gpu --hide-scrollbars "--user-data-dir=$D\edge" --window-size=1024,1024 --force-device-scale-factor=1 `
      --default-background-color=00000000 --allow-file-access-from-files --virtual-time-budget=5000 "--screenshot=$D\master-$m.png" $u 2>&1 | Out-Null
  "$m " + (Test-Path "$D\master-$m.png")
}

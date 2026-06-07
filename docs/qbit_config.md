## Preliminary Qbittorrent client configuration
This setup example assumes qbit is installed on a Windows PC; MAF and ABS dockers are hosted on another linux pc on the same LAN; All pc's and phones are connected via Tailscale 

### Qbit Settings:  

- Settings > Downloads:
  - Torrent content layout = `Create subfolder`
  - Default Save Path = `C:\Users\username\Desktop\Audiobooks`
  - Incomplete Path = `C:\Users\username\Desktop\Audiobooks\temp`
  - Automatically Add Torrents from > Add:
    - `C:\Users\username\Downloads`
  - Run External Program
    - Check ✅ 'Run on Torrent Finished'
    - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\scripts\abs-scan.ps1" "%L" "%N"`

### Audiobookshelf Automation on Complete

-  Create and save the Qbit-Audiobookshelf helper script `abs-scan.ps1`.  
-  This script location needs to be updated in the Run External Program command, set above.  

```powershell
param(
  [string]$Category = "",
  [string]$TorrentName = ""
)

$ABS      = "http://audiobookshelf_ip:13378"
$LIB_ID   = "5d333333-3333-3333-3333-33333333318d"      # <-- your library id
$API_KEY  = "eyJhbG...uVVxw"          # <-- your ABS API key

# Debounce: prevent scan spam if multiple torrents finish close together
$LockFile = "$env:ProgramData\abs-scan.lock"
$CooldownSeconds = 60

try {
  if (Test-Path $LockFile) {
    $age = (Get-Date) - (Get-Item $LockFile).LastWriteTime
    if ($age.TotalSeconds -lt $CooldownSeconds) { exit 0 }
  }
  New-Item -ItemType File -Force -Path $LockFile | Out-Null

  Invoke-RestMethod -Method Post `
    -Uri "$ABS/api/libraries/$LIB_ID/scan" `
    -Headers @{ Authorization = "Bearer $API_KEY" } `
    -TimeoutSec 30 | Out-Null
} catch {
  # optional: write to a log for debugging
  $log = "$env:ProgramData\abs-scan.log"
  "$(Get-Date -Format o) scan failed: $($_.Exception.Message) cat='$Category' name='$TorrentName'" |
    Out-File -Append -Encoding utf8 $log
}
```

### WebUI
- Settings > WebUI:
  - Check ✅ `Web User Interface`
  - Authentication:
    - Set `Username` & `Password`
    - Check ✅ `Bypass Authentication for Clients on Local Host`

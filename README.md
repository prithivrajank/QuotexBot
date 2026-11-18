# QuotexBot

Signals-only Quotex Python bot source archive supplied by the repository owner.

## Download / reconstruct the original ZIP on Windows

The GitHub Contents API accepts text files, so the original ZIP is stored losslessly as Base64 text segments under `uploads/`. Run the following in PowerShell to reconstruct the original `QuotexPythonBot-updated.zip`:

```powershell
$parts = @(
  "001", "002", "003", "004", "005",
  "006a.001", "006a.002", "006a.003", "006b",
  "006c.001", "006c.002", "006c.003a", "006c.003b"
)

$base = "https://raw.githubusercontent.com/prithivrajank/QuotexBot/main/uploads/QuotexPythonBot-updated.zip.b64."
$segments = foreach ($part in $parts) {
  (Invoke-WebRequest -Uri ($base + $part) -UseBasicParsing).Content.Trim()
}

$base64 = $segments -join ""
[IO.File]::WriteAllBytes(
  "QuotexPythonBot-updated.zip",
  [Convert]::FromBase64String($base64)
)
```

Then extract the ZIP using File Explorer or:

```powershell
Expand-Archive -Path .\QuotexPythonBot-updated.zip -DestinationPath .\QuotexPythonBot
```

## Security

Do not commit real SSIDs, session cookies, passwords, Telegram bot tokens, API keys, or other credentials. Review the supplied authentication/session integration and configure secrets locally; do not publish personal session values.

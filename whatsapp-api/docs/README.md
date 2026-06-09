# Dokumentasi Cepat Baileys API

Dokumentasi ringkas untuk `Baileys-API`, backend WhatsApp yang digunakan oleh `WhatsApp-Telegram-Bridge`.

## Start Server

```powershell
cd Baileys-API
npm start
```

Server default:

```text
http://localhost:3000
```

## Connect WhatsApp

```powershell
npm start
```

Jika session belum ada atau invalid, pilih metode login dari terminal:

```text
1) Scan QR Code
2) Pairing Code with phone number
```

Pilih QR untuk scan barcode. Pilih pairing code untuk login dengan nomor.

Masukkan `pairingCode` di WhatsApp:

```text
WhatsApp > Linked devices > Link a device > Link with phone number instead
```

## Ambil JID Grup WhatsApp

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/groups" -Method Get
```

Format:

```text
Nama Grup => 120xxxxxxxxxxxx@g.us
```

Gunakan nilai `120xxxxxxxxxxxx@g.us` sebagai `jid` di `WhatsApp-Telegram-Bridge/config/config.py`.

## Kirim Pesan Test

```powershell
$body = @{
  jid = "120363408099585884@g.us"
  message = @{
    text = "Test dari Baileys API"
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Uri "http://127.0.0.1:3000/send-message" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"
```

## Reset Session

Reset WhatsApp:

```powershell
cd ..\WhatsApp-Telegram-Bridge
.\venv\Scripts\python.exe scripts\reset_sessions.py --whatsapp --force
```

Reset Telegram:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --telegram --force
```

Reset semua:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --all --force
```

## Troubleshooting

- `401 Not connected`: panggil `/connect`, lalu scan QR jika perlu.
- `/groups` gagal: WhatsApp belum connected atau server belum jalan.
- Pesan tidak masuk grup: pastikan JID berakhiran `@g.us` dan akun WhatsApp adalah anggota grup.
- Pesan dobel: pastikan hanya satu proses bridge Python berjalan.

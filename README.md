# WhatsApp Telegram Bridge

Bridge Python untuk meneruskan pesan dari satu atau beberapa chat Telegram ke WhatsApp melalui server lokal `Baileys-API`.

## Ringkasan

Project ini berjalan sebagai listener Telegram. Setiap pesan baru dari Telegram source yang dikonfigurasi akan diproses, lalu dikirim ke WhatsApp API:

```text
POST http://localhost:3000/send-message
```

Alur sistem:

```text
Telegram chat/group/channel
        -> main.py
        -> media_handler.py
        -> whatsapp_sender.py
        -> Baileys-API
        -> WhatsApp user/group
```

## Fitur

- Forward pesan Telegram ke WhatsApp secara real-time.
- Mendukung banyak source Telegram sekaligus.
- Target WhatsApp bisa nomor personal atau grup.
- Mendukung teks, foto, audio, dan video.
- Media Telegram tersimpan rapi di `downloads/telegram_media`.
- Retry otomatis jika WhatsApp API sempat belum connected.
- Utility reset session untuk ganti akun Telegram atau nomor WhatsApp.
- Admin bot Telegram untuk login Telegram bridge, pairing WhatsApp, list grup, set source/target, dan logout session.
- Logging ke terminal dan `logs/bridge.log`.

## Struktur Folder

```text
WhatsApp-Telegram-Bridge/
  config/
    config.py                 Konfigurasi utama
  downloads/
    telegram_media/           Folder media Telegram yang di-download
  logs/
    bridge.log                Log runtime bridge
  scripts/
    list_telegram_chats.py    Cek daftar chat Telegram
    reset_sessions.py         Reset session Telegram/WhatsApp
  main.py                     Listener Telegram
  media_handler.py            Handler teks/media Telegram
  whatsapp_sender.py          Sender ke Baileys-API
  requirements.txt            Dependency Python
```

## Dependency

```text
telethon==1.27.0
requests==2.31.0
loguru==0.7.2
```

Kegunaan:

- `telethon`: login Telegram, listen pesan, download media.
- `requests`: HTTP request ke WhatsApp API.
- `loguru`: logging.

## Setup Awal

Install dependency Python:

```powershell
cd WhatsApp-Telegram-Bridge
cd ..\telegram-bridge
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
```

Jika tidak memakai virtual environment:

```powershell
pip install -r requirements.txt
```

## Mendapatkan Telegram API ID dan API Hash

1. Buka `https://my.telegram.org`.
2. Login dengan nomor Telegram.
3. Masuk ke menu `API development tools`.
4. Buat aplikasi baru.
5. Ambil nilai `api_id` dan `api_hash`.
6. Masukkan ke `config/config.py`.

Contoh:

```python
api_id = "12345678"
api_hash = "your_api_hash"
```

## Mendapatkan Telegram Chat ID

Cara paling rapi adalah memakai script bawaan:

```powershell
cd WhatsApp-Telegram-Bridge
.\venv\Scripts\python.exe scripts\list_telegram_chats.py
```

Output akan menampilkan tipe chat, ID, dan nama:

```text
TYPE       ID                 NAME
group      -1001991717357     IDLIX
user       8612321231         NOVLI R01 BOT
```

Ambil nilai `ID`, lalu masukkan ke `telegram_chats`.

Alternatif:

- Forward pesan ke bot seperti `@userinfobot` untuk user ID.
- Untuk group/channel, script `list_telegram_chats.py` lebih akurat karena ID Telegram group/channel sering memakai prefix `-100`.

## Mendapatkan WhatsApp JID

Jalankan `Baileys-API`, connect WhatsApp, lalu ambil daftar grup:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/groups" -Method Get
```

Contoh hasil:

```text
Testing TG2WA => 120363408099585884@g.us
```

Gunakan ID `120363408099585884@g.us` sebagai `jid`.

Format JID:

```text
Nomor personal : 628xxxxxxxxxx@s.whatsapp.net
Grup WhatsApp  : 120xxxxxxxxxxxx@g.us
```

Catatan:

- Untuk grup, akun WhatsApp yang login di `Baileys-API` harus menjadi anggota grup.
- Jika pesan tidak terlihat, cek lagi apakah `jid` mengarah ke nomor personal atau grup yang benar.

## Konfigurasi

Edit:

```text
config/config.py
```

Contoh konfigurasi multi-source Telegram ke satu grup WhatsApp:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

api_id = "YOUR_TELEGRAM_API_ID"
api_hash = "YOUR_TELEGRAM_API_HASH"

telegram_chats = [
    -1001991717357,
    860210821,
]

telegram_chat = telegram_chats

jid = "120363408099585884@g.us"
whatsapp_api_url = "http://localhost:3000/send-message"
media_path = str(BASE_DIR / "downloads" / "telegram_media")
```

## Menjalankan

1. Jalankan `Baileys-API`.
2. Connect WhatsApp dengan QR atau pairing code.
3. Jalankan bridge.

Command bridge:

```powershell
cd WhatsApp-Telegram-Bridge
.\venv\Scripts\python.exe main.py
```

Log sukses startup:

```text
Telegram client connected
Telegram source resolved
Waiting for new messages
```

Log sukses forward:

```text
Telegram message received
Sending message to WhatsApp API
WhatsApp API response: status_code=200
Message forwarded to WhatsApp
```

## Reset Session

Gunakan jika ingin mengganti akun Telegram atau nomor WhatsApp.

Pastikan bridge dan `Baileys-API` dimatikan dulu.

Dry-run, hanya menampilkan target hapus:

```powershell
cd WhatsApp-Telegram-Bridge
.\venv\Scripts\python.exe scripts\reset_sessions.py --all
```

Reset Telegram saja:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --telegram --force
```

Reset WhatsApp saja:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --whatsapp --force
```

Reset Telegram dan WhatsApp:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --all --force
```

Setelah reset:

1. Jalankan ulang `Baileys-API`.
2. Panggil `/connect`.
3. Scan QR WhatsApp baru jika diminta.
4. Jalankan bridge.
5. Login Telegram ulang jika Telethon meminta kode.

## Bersih-Bersih File

File yang aman dihapus saat tidak dibutuhkan:

```text
__pycache__/
*.pyc
downloads/telegram_media/*
logs/bridge.log
```

File yang jangan dihapus kecuali ingin reset login:

```text
Test Session.session
Test Session.session-journal
../Baileys-API/auth_info/
```

## Troubleshooting

### WhatsApp API response 401

Artinya WhatsApp API belum connected.

Solusi:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect" -Method Post
```

Jika QR muncul di terminal `Baileys-API`, scan QR tersebut.

### Status 200 tapi pesan tidak terlihat

Cek:

- `jid` sudah benar.
- Untuk grup, JID harus berakhiran `@g.us`.
- Akun WhatsApp yang login adalah anggota grup.
- Tidak ada instance bridge lama yang masih berjalan.

### Pesan terkirim dobel

Pastikan hanya satu proses bridge berjalan.

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*WhatsApp-Telegram-Bridge*" -and $_.CommandLine -like "*main.py*" } |
  Select-Object ProcessId,CommandLine
```

### Tidak tahu source Telegram yang aktif

Lihat log startup:

```powershell
Get-Content logs\bridge.log -Tail 40
```

Cari baris:

```text
Telegram source resolved
```

## File Sensitif

Jangan upload file/folder ini ke repository publik:

```text
config/config.py
*.session
*.session-journal
../Baileys-API/auth_info/
logs/
downloads/
```

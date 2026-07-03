# telegram-bridge

`telegram-bridge` adalah service Python yang membaca pesan baru dari Telegram lalu meneruskannya ke WhatsApp melalui service `../whatsapp-api`.

Service ini tidak terhubung langsung ke WhatsApp. Semua pengiriman WhatsApp dilakukan dengan HTTP request ke:

```text
POST http://localhost:3000/send-message
```

## Alur Kerja

```text
Telegram source
  -> main.py
  -> media_handler.py
  -> whatsapp_sender.py
  -> ../whatsapp-api
  -> WhatsApp target
```

Penjelasan file utama:

- `main.py`: membuat `TelegramClient`, login Telegram, resolve source chat, register event `NewMessage`, dan menjalankan listener.
- `media_handler.py`: mengubah pesan Telegram menjadi payload yang kompatibel dengan Baileys, termasuk download foto/audio/video.
- `whatsapp_sender.py`: mengirim payload ke WhatsApp API, memanggil `/connect` ketika API mengembalikan `401`, lalu retry pengiriman.
- `config/config.py`: konfigurasi aktif untuk credential Telegram, source chat, target WhatsApp, endpoint API, dan folder media.

## Fitur

- Listen pesan Telegram secara real-time.
- Source Telegram bisa satu ID atau list beberapa ID.
- Mendukung Telegram user, group, megagroup, dan channel yang dapat diakses akun Telegram.
- Forward teks, foto, audio, dan video.
- Caption foto/video tetap dikirim jika ada.
- Media diunduh ke folder `media_path`.
- Logging ke terminal dan `logs/bridge.log`.
- Utility daftar chat Telegram.
- Utility reset session Telegram dan WhatsApp.

## Teknologi dan Library

Dependency ada di `requirements.txt`:

```text
telethon==1.27.0
requests==2.31.0
loguru==0.7.2
```

Fungsi dependency:

- `telethon`: Telegram client, auth session, event listener, entity resolver, dan download media.
- `requests`: HTTP client untuk `POST /send-message` dan `POST /connect`.
- `loguru`: logger terminal dan file dengan rotasi `5 MB` dan retensi `7 days`.

## Struktur Folder

```text
telegram-bridge/
  README.md
  Dockerfile
  requirements.txt
  main.py
  media_handler.py
  whatsapp_sender.py
  config/
    config.py                 Konfigurasi aktif, jangan dipublikasi
    config_example.py         Template konfigurasi
  scripts/
    list_telegram_chats.py    Menampilkan ID chat Telegram
    reset_sessions.py         Reset session Telegram/WhatsApp
  downloads/
    telegram_media/           Lokasi default hasil download media
  logs/
    bridge.log                Log runtime
  tmp/
    telegram_chats.txt        Output utility daftar chat
  *.session                   Session login Telegram dari Telethon
```

Folder `downloads`, `logs`, `tmp`, `__pycache__`, dan file `*.session` adalah artefak runtime.

## Prasyarat

- Python 3.10 atau lebih baru direkomendasikan.
- `whatsapp-api` berjalan di `http://localhost:3000`.
- `api_id` dan `api_hash` Telegram dari `https://my.telegram.org`.
- JID WhatsApp target, misalnya `628xxxxxxxxxx@s.whatsapp.net` atau `120xxxxxxxxxxxx@g.us`.

## Instalasi

Dari root workspace:

```powershell
cd telegram-bridge
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
```

Jika tidak memakai virtual environment:

```powershell
pip install -r requirements.txt
```

## Konfigurasi

Salin template jika `config/config.py` belum tersedia:

```powershell
Copy-Item config\config_example.py config\config.py
```

Isi `config/config.py`:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

api_id = "YOUR_TELEGRAM_API_ID"
api_hash = "YOUR_TELEGRAM_API_HASH"

telegram_chat = [
    -1001234567890,
    123456789,
]

jid = "120xxxxxxxxxxxx@g.us"
whatsapp_api_url = "http://localhost:3000/send-message"
media_path = str(BASE_DIR / "downloads" / "telegram_media")
```

Catatan konfigurasi:

- `api_id` dan `api_hash` wajib diisi.
- `telegram_chat` dapat berupa satu ID/string atau list ID/string.
- Group/channel Telegram biasanya memakai ID dengan prefix `-100`.
- `jid` wajib diisi dengan target WhatsApp.
- `whatsapp_api_url` wajib ada karena diimpor oleh `main.py` dan `whatsapp_sender.py`.
- `media_path` wajib menunjuk folder yang dapat ditulis oleh proses Python.

## Mendapatkan Telegram API ID dan API Hash

1. Buka `https://my.telegram.org`.
2. Login dengan nomor Telegram.
3. Buka `API development tools`.
4. Buat aplikasi baru.
5. Salin `api_id` dan `api_hash` ke `config/config.py`.

## Mendapatkan Telegram Chat ID

Jalankan:

```powershell
cd telegram-bridge
.\venv\Scripts\python.exe scripts\list_telegram_chats.py
```

Output contoh:

```text
TYPE       ID                 NAME
group      -1001991717357     Nama Grup
user       8612321231         Nama User
channel    -1001234567890     Nama Channel
```

Hasil juga disimpan ke:

```text
tmp/telegram_chats.txt
```

Gunakan nilai `ID` pada `telegram_chat`.

## Mendapatkan WhatsApp JID

Pastikan `whatsapp-api` sudah connected, lalu jalankan:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/groups" -Method Get
```

Format JID:

```text
Nomor personal : 628xxxxxxxxxx@s.whatsapp.net
Grup WhatsApp  : 120xxxxxxxxxxxx@g.us
```

Untuk grup, akun WhatsApp yang login di `whatsapp-api` harus menjadi anggota grup tersebut.

## Menjalankan

Urutan manual yang disarankan:

```powershell
cd ..\whatsapp-api
npm start
```

Di terminal lain:

```powershell
cd ..\telegram-bridge
.\venv\Scripts\python.exe main.py
```

Saat pertama kali login Telegram, Telethon akan meminta nomor telepon, kode login, dan password 2FA jika akun menggunakannya. Session disimpan sebagai file `Test Session.session`.

Log startup yang sehat biasanya berisi:

```text
Telegram client connected
Telegram source resolved
Waiting for new messages
```

## Payload yang Dikirim ke WhatsApp API

Teks:

```json
{
  "jid": "120xxxxxxxxxxxx@g.us",
  "message": {
    "text": "Isi pesan Telegram"
  }
}
```

Foto:

```json
{
  "jid": "120xxxxxxxxxxxx@g.us",
  "message": {
    "image": {
      "url": "downloads/telegram_media/photo.jpg"
    },
    "caption": "Caption"
  }
}
```

Audio dan video juga dikirim memakai format `audio.url` atau `video.url` sesuai format Baileys.

## Reset Session

Dry-run:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --all
```

Reset Telegram:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --telegram --force
```

Reset WhatsApp:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --whatsapp --force
```

Reset semua:

```powershell
.\venv\Scripts\python.exe scripts\reset_sessions.py --all --force
```

Script hanya menghapus target di dalam workspace:

- Telegram: `telegram-bridge/*.session` dan `telegram-bridge/*.session-journal`.
- WhatsApp: `whatsapp-api/auth_info`.

## Troubleshooting

### ImportError atau variabel config tidak ditemukan

Pastikan `config/config.py` berisi semua variabel ini:

```python
api_id = ""
api_hash = ""
telegram_chat = ""
jid = ""
whatsapp_api_url = "http://localhost:3000/send-message"
media_path = "downloads/telegram_media"
```

### WhatsApp API response 401

Artinya `whatsapp-api` belum connected. Jalankan:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect" -Method Post
```

Lalu scan QR dari terminal `whatsapp-api`.

### Status 200 tetapi pesan tidak terlihat

Cek:

- `jid` sudah benar.
- JID grup berakhiran `@g.us`.
- Akun WhatsApp yang login adalah anggota grup.
- Hanya ada satu proses `main.py` yang berjalan.

### Pesan terkirim dobel

Cari proses bridge yang masih aktif:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*telegram-bridge*" -and $_.CommandLine -like "*main.py*" } |
  Select-Object ProcessId,CommandLine
```

### Source Telegram gagal resolve

Jalankan ulang:

```powershell
.\venv\Scripts\python.exe scripts\list_telegram_chats.py
```

Gunakan ID numerik dari output, terutama untuk group/channel.

## File Sensitif

Jangan upload:

```text
config/config.py
*.session
*.session-journal
downloads/
logs/
tmp/
venv/
```

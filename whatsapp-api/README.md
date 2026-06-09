# Baileys API

REST API dan WebSocket server untuk mengirim pesan WhatsApp menggunakan library Baileys. Di workspace ini, `Baileys-API` dipakai sebagai backend WhatsApp untuk `WhatsApp-Telegram-Bridge`.

## Ringkasan

Server berjalan di:

```text
http://localhost:3000
```

Bridge Python mengirim payload ke:

```text
POST /send-message
```

Alur integrasi:

```text
WhatsApp-Telegram-Bridge
        -> Baileys-API
        -> WhatsApp Web session
        -> WhatsApp user/group
```

## Fitur

- Login WhatsApp dengan QR code.
- Session tersimpan di `auth_info/`.
- Kirim pesan ke nomor personal atau grup WhatsApp.
- Ambil daftar grup WhatsApp.
- Queue pengiriman pesan dengan jeda.
- Rate limit request HTTP.
- WebSocket event untuk status koneksi, QR, dan event pesan WhatsApp.

## Dependency Utama

- `@whiskeysockets/baileys`: koneksi WhatsApp Web.
- `express`: REST API server.
- `socket.io`: WebSocket server.
- `qrcode-terminal`: tampilkan QR di terminal.
- `express-rate-limit`: rate limit request.
- `p-queue`: antrean pengiriman pesan.
- `typescript`, `tsx`, `tsc-alias`: TypeScript build/dev tools.

## Struktur Folder

```text
Baileys-API/
  auth_info/              Session WhatsApp lokal
  dist/                   Hasil build
  docs/                   Dokumentasi tambahan
  src/
    controllers/          Handler request
    routes/               Routing endpoint
    services/             Logic message dan group
    listeners/            Listener event WhatsApp
    utils/                Helper response/parser
    server.ts             Express + Socket.IO server
    whatsappClient.ts     Koneksi Baileys
  package.json
  tsconfig.json
```

## Setup

Install dependency:

```powershell
cd Baileys-API
npm install
```

Build:

```powershell
npm run build
```

Start server:

```powershell
npm start
```

Development mode:

```powershell
npm run dev
```

## Login WhatsApp

Jalankan:

```powershell
npm start
```

Jika session belum ada atau session lama invalid, terminal akan menampilkan pilihan:

```text
1) Scan QR Code
2) Pairing Code with phone number
```

Pilih `1` untuk QR. Pilih `2` untuk pairing code dengan nomor WhatsApp.

Jika berhasil, session tersimpan di:

```text
auth_info/
```

### Login WhatsApp Dengan Nomor Pairing Code

Saat memilih opsi `2`, terminal akan meminta nomor dan menampilkan `pairingCode`. Masukkan kode tersebut di aplikasi WhatsApp:

```text
WhatsApp > Linked devices > Link a device > Link with phone number instead
```

Catatan:

- Ini bukan OTP SMS.
- Nomor harus memakai format negara, contoh `6281234567890`.
- Kode punya batas waktu, jadi segera masukkan ke WhatsApp.

## Mendapatkan WhatsApp Group JID

Pastikan WhatsApp sudah connected, lalu jalankan:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/groups" -Method Get
```

Contoh hasil:

```text
Testing TG2WA => 120363408099585884@g.us
```

Gunakan ID tersebut sebagai `jid` di bridge:

```python
jid = "120363408099585884@g.us"
```

Format JID:

```text
Nomor personal : 628xxxxxxxxxx@s.whatsapp.net
Grup WhatsApp  : 120xxxxxxxxxxxx@g.us
```

## Endpoint Penting

Connect:

```text
POST /connect
POST /api/v2/auth/login
```

Logout:

```text
DELETE /logout
POST /api/v2/auth/logout
```

Kirim pesan:

```text
POST /send-message
POST /api/v2/message/send
```

List grup:

```text
GET /groups
GET /api/v2/group/min
GET /api/v2/group
```

## Contoh Kirim Pesan

```powershell
$body = @{
  jid = "120363408099585884@g.us"
  message = @{
    text = "Halo dari Baileys API"
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Uri "http://127.0.0.1:3000/send-message" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"
```

## Integrasi Dengan Telegram Bridge

Di `WhatsApp-Telegram-Bridge/config/config.py`:

```python
whatsapp_api_url = "http://localhost:3000/send-message"
jid = "120363408099585884@g.us"
```

## Reset Session WhatsApp

Gunakan jika ingin mengganti nomor WhatsApp.

Hapus session:

```powershell
cd ..\WhatsApp-Telegram-Bridge
.\venv\Scripts\python.exe scripts\reset_sessions.py --whatsapp --force
```

Setelah reset:

1. Jalankan `npm start` dari `Baileys-API`.
2. Pilih QR atau pairing code dari terminal.

## Troubleshooting

### 401 Not connected

WhatsApp belum connected.

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect" -Method Post
```

### `/groups` gagal

Biasanya WhatsApp belum connected atau server belum jalan.

### Pesan sukses tapi tidak terlihat

Cek:

- `jid` benar.
- Untuk grup, JID berakhiran `@g.us`.
- Akun WhatsApp yang login adalah anggota grup.
- Tidak ada bridge lama yang masih mengirim ke target berbeda.

## File Sensitif

Jangan upload ke repository publik:

```text
auth_info/
node_modules/
.env
```

## License

MIT

# Dokumentasi `whatsapp-api`

Folder ini berisi dokumentasi tambahan untuk service `whatsapp-api`. Dokumentasi utama ada di `../README.md`; file di folder ini dipakai sebagai referensi cepat saat integrasi atau debugging.

## Isi Folder

```text
docs/
  README.md              Ringkasan dokumentasi folder docs
  guide.md               Panduan penggunaan API yang lebih panjang
  addressing-modes.md    Penjelasan format alamat/JID
  troubleshooting.md     Catatan masalah umum
  legacy_readme.md       README lama sebagai arsip referensi
```

## Service yang Didokumentasikan

`whatsapp-api` adalah server Node.js/TypeScript berbasis Express, Socket.IO, dan Baileys. Fungsinya:

- Menyambungkan akun WhatsApp Web.
- Menyediakan endpoint login/logout.
- Mengirim pesan WhatsApp melalui REST API.
- Mengambil daftar grup WhatsApp.
- Menyediakan event realtime via Socket.IO.

## Quick Start

Dari folder `whatsapp-api`:

```powershell
npm install
npm run build
npm start
```

Server default:

```text
http://localhost:3000
```

Login QR:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect" -Method Post
```

Login pairing code:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect?phoneNumber=6281234567890" -Method Post
```

## Endpoint Ringkas

```text
POST   /connect
DELETE /logout
POST   /send-message
GET    /groups
POST   /api/v2/auth/login
POST   /api/v2/auth/logout
POST   /api/v2/message/send
GET    /api/v2/group
GET    /api/v2/group/min
GET    /api/v2/group/name/:name
GET    /api/v2/group/name/:name/min
GET    /api/v2/group/id/:id
GET    /api/v2/group/id/:id/min
```

## Contoh Kirim Pesan

```powershell
$body = @{
  jid = "120xxxxxxxxxxxx@g.us"
  message = @{
    text = "Test dari whatsapp-api"
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Uri "http://127.0.0.1:3000/send-message" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"
```

## Format JID

```text
Nomor personal : 628xxxxxxxxxx@s.whatsapp.net
Grup WhatsApp  : 120xxxxxxxxxxxx@g.us
```

Untuk integrasi dengan `telegram-bridge`, nilai JID dimasukkan ke:

```text
../telegram-bridge/config/config.py
```

## Troubleshooting Cepat

- `401 Not connected`: panggil `POST /connect`, lalu scan QR atau gunakan pairing code.
- `/groups` mengembalikan `403`: WhatsApp belum connected.
- Pesan tidak masuk grup: pastikan JID berakhiran `@g.us` dan akun WhatsApp adalah anggota grup.
- Pairing code gagal: hapus `auth_info/` jika session lama rusak, lalu coba login ulang.
- Pesan dari bridge gagal: pastikan `telegram-bridge/config/config.py` memakai `whatsapp_api_url = "http://localhost:3000/send-message"` untuk mode lokal.

## File Referensi

Baca dokumen berikut untuk detail tambahan:

- `guide.md`: panduan lengkap penggunaan REST API.
- `addressing-modes.md`: detail format target pesan.
- `troubleshooting.md`: investigasi masalah koneksi dan pengiriman.

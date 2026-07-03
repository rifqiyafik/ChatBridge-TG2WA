# whatsapp-api

`whatsapp-api` adalah REST API dan WebSocket server untuk WhatsApp Web. Service ini menggunakan Baileys sebagai client WhatsApp dan dipakai oleh `../telegram-bridge` untuk mengirim pesan ke nomor personal atau grup WhatsApp.

Server default:

```text
http://localhost:3000
```

Endpoint yang dipakai bridge:

```text
POST /send-message
```

## Alur Kerja

```text
HTTP client / telegram-bridge
  -> Express route
  -> controller
  -> service
  -> Baileys socket
  -> WhatsApp Web
```

## Fitur

- Login WhatsApp dengan QR code.
- Login WhatsApp dengan pairing code berbasis nomor telepon.
- Simpan session WhatsApp di `auth_info/`.
- Kirim pesan ke satu JID atau banyak JID sekaligus.
- Batasi maksimal 50 penerima per request.
- Batasi teks sederhana maksimal 5000 karakter.
- Queue pengiriman pesan dengan concurrency `1` dan delay `2 detik`.
- Rate limit HTTP `60 request/menit/IP`.
- Ambil daftar grup WhatsApp.
- Endpoint legacy pendek dan endpoint versi `/api/v2`.
- Socket.IO untuk event koneksi, QR, dan pesan WhatsApp.

## Teknologi dan Library

Runtime:

- Node.js dengan module type `module`.
- TypeScript sebagai bahasa source.
- Express 5 untuk REST API.
- Socket.IO untuk komunikasi event realtime.
- Baileys `@whiskeysockets/baileys` untuk koneksi WhatsApp Web.

Dependency utama:

- `@whiskeysockets/baileys`: socket WhatsApp, auth state, fetch versi WA Web, QR/pairing, dan `sendMessage`.
- `@hapi/boom`: normalisasi error disconnect Baileys.
- `express`: routing dan middleware REST API.
- `express-rate-limit`: pembatas request per IP.
- `socket.io`: WebSocket server.
- `p-queue`: antrean pengiriman pesan.
- `qrcode-terminal`: render QR code di terminal.
- `qrcode`: utilitas QR tambahan.
- `pino`: logger yang digunakan ekosistem Baileys.
- `chalk`: styling output terminal.
- `tsx`: menjalankan TypeScript saat development.
- `typescript` dan `tsc-alias`: compile source ke `dist/` dan resolve path alias.

## Struktur Folder

```text
whatsapp-api/
  README.md
  package.json
  package-lock.json
  tsconfig.json
  Dockerfile
  src/
    index.ts                    Entrypoint aplikasi
    server.ts                   Setup Express, HTTP server, Socket.IO, routes
    initWhatsApp.ts             Inisialisasi koneksi WhatsApp saat startup
    whatsappClient.ts           Baileys socket, auth state, reconnect, logout
    socket.ts                   Setup Socket.IO event bridge
    constants/
      whatsappEvents.ts         Nama event Baileys dan app
    controllers/
      auth.controller.ts        Login/logout WhatsApp
      message.controller.ts     Validasi dan kirim pesan
      group.controller.ts       Endpoint daftar/cari grup
    routes/
      auth.routes.ts            /api/v2/auth
      message.routes.ts         /api/v2/message
      group.routes.ts           /api/v2/group
    services/
      message.service.ts        Queue dan call sock.sendMessage
      group.service.ts          Ambil dan filter metadata grup
    listeners/
      messageListener.ts        Listener event pesan WhatsApp
    utils/
      response.ts               Format response JSON
      messageParser.ts          Parser event/message WhatsApp
      getNumber.ts              Helper nomor/JID
      debug.ts                  Helper debug
    types/
      index.ts                  Type shared
  dist/                         Output build JavaScript
  docs/                         Dokumentasi tambahan
  examples/                     Contoh client
  auth_info/                    Session WhatsApp, dibuat saat login
  node_modules/                 Dependency lokal
```

## Script NPM

```json
{
  "start": "node dist/index.js",
  "dev": "tsx watch src/index.ts",
  "build": "tsc && tsc-alias --resolve-full-paths --resolve-full-extension .js",
  "testbuild": "tsc --noEmit"
}
```

Fungsi:

- `npm run dev`: development mode, watch file TypeScript.
- `npm run build`: compile ke `dist/`.
- `npm start`: menjalankan output build.
- `npm run testbuild`: type-check tanpa menulis file build.

## Instalasi

```powershell
cd whatsapp-api
npm install
npm run build
npm start
```

Development mode:

```powershell
npm run dev
```

Port default `3000`. Bisa diubah dengan environment variable `PORT`:

```powershell
$env:PORT = "3001"
npm start
```

## Login WhatsApp

### QR Code

Jalankan server, lalu panggil:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect" -Method Post
```

Scan QR yang muncul di terminal melalui:

```text
WhatsApp > Linked devices > Link a device
```

### Pairing Code

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect?phoneNumber=6281234567890" -Method Post
```

Masukkan pairing code di aplikasi WhatsApp:

```text
WhatsApp > Linked devices > Link a device > Link with phone number instead
```

Catatan:

- `phoneNumber` memakai format negara, contoh `6281234567890`.
- Pairing code bukan OTP SMS.
- Session tersimpan di `auth_info/`.

## Endpoint

### Auth

```text
POST   /connect
DELETE /logout
POST   /api/v2/auth/login
POST   /api/v2/auth/logout
```

`/connect` dan `/api/v2/auth/login` menerima optional `phoneNumber` dari query atau body untuk pairing code.

Logout default menghapus cache session:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/logout" -Method Delete
```

Logout tanpa hapus session:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/logout?deleteSession=false" -Method Delete
```

### Message

```text
POST /send-message
POST /api/v2/message/send
```

Body:

```json
{
  "jid": "120xxxxxxxxxxxx@g.us",
  "message": {
    "text": "Halo dari whatsapp-api"
  }
}
```

Bulk JID:

```json
{
  "jid": [
    "628xxxxxxxxxx@s.whatsapp.net",
    "120xxxxxxxxxxxx@g.us"
  ],
  "message": {
    "text": "Pesan broadcast terbatas"
  }
}
```

Batasan dari controller/service:

- `jid` dan `message` wajib ada.
- Array `jid` maksimal 50 penerima.
- `message.text` maksimal 5000 karakter.
- Queue internal maksimal 30 item menunggu.
- Jika WhatsApp belum connected, response `401`.

### Group

```text
GET /groups
GET /api/v2/group
GET /api/v2/group/min
GET /api/v2/group/name/:name
GET /api/v2/group/name/:name/min
GET /api/v2/group/id/:id
GET /api/v2/group/id/:id/min
```

Gunakan `/groups` atau `/api/v2/group/min` untuk mengambil daftar JID grup secara ringkas.

## Contoh Test Kirim Pesan

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

## Integrasi Dengan `telegram-bridge`

Di `../telegram-bridge/config/config.py`:

```python
whatsapp_api_url = "http://localhost:3000/send-message"
jid = "120xxxxxxxxxxxx@g.us"
```

Jika dijalankan di Docker Compose dalam network yang sama, endpoint internal biasanya perlu mengarah ke nama service:

```python
whatsapp_api_url = "http://baileys-api:3000/send-message"
```

## Docker

Dari root workspace:

```powershell
docker compose up --build
```

Dockerfile menjalankan build TypeScript lalu menjalankan `dist/index.js`. Folder `auth_info/` sebaiknya di-mount sebagai volume agar session tidak hilang saat container dibuat ulang.

## Troubleshooting

### `401 Not connected`

WhatsApp belum connected atau session invalid. Panggil:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/connect" -Method Post
```

### `/groups` mengembalikan 403

WhatsApp belum connected. Login ulang dengan QR atau pairing code.

### Pesan sukses tapi tidak terlihat

Cek:

- JID benar.
- JID grup berakhiran `@g.us`.
- Akun WhatsApp yang login adalah anggota grup target.
- Bridge tidak mengirim ke target lain dari konfigurasi lama.

### Pairing code gagal

Cek:

- Nomor memakai format negara tanpa tanda `+`.
- Session lama di `auth_info/` tidak rusak.
- Jika perlu, hapus `auth_info/` lalu login ulang.

## File Sensitif

Jangan upload:

```text
auth_info/
node_modules/
.env
dist/ jika ingin repo source-only
```

## License

MIT

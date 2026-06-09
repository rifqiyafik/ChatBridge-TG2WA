import {
  default as makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  WASocket,
  fetchLatestBaileysVersion,
  Browsers,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import qrcode from "qrcode-terminal";
import fs from "fs";
import { EventEmitter } from "events";
import { intializeMessageListener } from "@/listeners/messageListener";
import {
  APP_EVENT_CONNECTED,
  APP_EVENT_DISCONNECTED,
  APP_EVENT_QR_CODE,
  BAILEYS_EVENT_CONNECTION_UPDATE,
  BAILEYS_EVENT_CREDS_UPDATE,
  BAILEYS_MESSAGE_EVENTS,
} from "@/constants/whatsappEvents";

export const waEmitter = new EventEmitter();


let sock : WASocket | null = null;
let connectPromise : Promise<void> | null = null;
let _isConnected = false;
let currentQR : string | null = null;
let currentPairingCode : string | null = null;
let pairingPhone: string | null = null;

function isConnected(): boolean {
  return !!sock && _isConnected;
}

function getQR(): string | null {
  return currentQR;
}

function getPairingCode(): string | null {
  return currentPairingCode;
}

function getSock(): WASocket | null {
  return sock;
}

function normalizePhoneNumber(phoneNumber: string): string {
  return phoneNumber.replace(/\D/g, "");
}

function connectToWA(phoneNumber?: string): Promise<void> {
  // If already connected and ready, return immediately
  if (isConnected()) return Promise.resolve();

  if (phoneNumber) {
    pairingPhone = normalizePhoneNumber(phoneNumber);
  }

  // If a connection is currently in progress, return the existing promise
  if (connectPromise) return connectPromise;

  connectPromise = new Promise<void>(async (resolve, reject) => {
    try {
      const { state, saveCreds } = await useMultiFileAuthState("auth_info");
      const { version } = await fetchLatestBaileysVersion();

      // Clear creds.me temporarily if not registered to prevent validateConnection from sending a login node
      if (state.creds && !state.creds.registered && state.creds.me) {
        console.log("Session not registered yet. Temporarily clearing creds.me for registration/pairing handshake...");
        delete (state.creds as any).me;
      }

      sock = makeWASocket({
        version,
        auth: state,
        browser: Browsers.windows("Chrome"),
        markOnlineOnConnect: false,
        syncFullHistory: false,
        connectTimeoutMs: 60_000,
      });

      // Initialize the message listener immediately so events aren't missed
      intializeMessageListener(sock);

      sock.ev.on(BAILEYS_EVENT_CREDS_UPDATE, saveCreds);

      sock.ev.on(BAILEYS_EVENT_CONNECTION_UPDATE, (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
          currentQR = qr;
          if (!pairingPhone) {
            qrcode.generate(qr, { small: true });
          }
          waEmitter.emit(APP_EVENT_QR_CODE, qr);
        }

        if (connection === "open") {
          console.log("✅ WhatsApp connection opened");
          !!currentQR && (currentQR = null); // Clear QR code once connected if it exists
          !!currentPairingCode && (currentPairingCode = null);
          pairingPhone = null;
          _isConnected = true;
          waEmitter.emit(APP_EVENT_CONNECTED);
          resolve();
        }

        if (connection === "close") {
          _isConnected = false;
          connectPromise = null; // Clear the pending connection promise
          !!currentQR && (currentQR = null); // Clear QR code on disconnect if it exists
          !!currentPairingCode && (currentPairingCode = null);
          const disconnectError = new Boom(lastDisconnect?.error, {
            statusCode: (lastDisconnect?.error as Boom | undefined)?.output?.statusCode,
          });
          waEmitter.emit(APP_EVENT_DISCONNECTED, lastDisconnect);

          if (sock) {
            sock.ev.removeAllListeners(BAILEYS_EVENT_CONNECTION_UPDATE);
            sock.ev.removeAllListeners(BAILEYS_EVENT_CREDS_UPDATE);
            for (const eventName of BAILEYS_MESSAGE_EVENTS) {
              sock.ev.removeAllListeners(eventName);
            }
          }
          sock = null;

          // Reject if it failed before ever opening (Promises ignore multiple settle calls)
          reject(disconnectError);

          // Handle reconnection
          reconnectToWA(disconnectError);
        }
      });
    } catch (err) {
      connectPromise = null;
      reject(err);
    }
  });

  return connectPromise;
}

function reconnectToWA(disconnect: Boom) {
  if (isConnected()) {
    console.log("Already connected to WhatsApp.");
    return;
  }

  if (disconnect) {
    console.log("Previous connection closed. Reason:", disconnect.message);
    waEmitter.emit("disconnectReason", disconnect.message);

    const shouldReconnect =
      disconnect?.output?.statusCode !== DisconnectReason.loggedOut;

    if (shouldReconnect) {
      if (pairingPhone) {
        console.log("Pairing code is active. Reconnecting to wait for phone linking after 3 seconds...");
        setTimeout(() => {
          connectToWA().catch((err) =>
            console.error("Reconnection during pairing failed:", err.message),
          );
        }, 3000);
        return;
      }

      console.log("Attempting to reconnect...");
      // Wrap the promise to catch silent errors inside reconnection
      connectToWA().catch((err) =>
        console.error("Reconnection completely failed:", err.message),
      );
    } else {
      if (pairingPhone) {
        console.log("Logged out or invalid pairing code request. Resetting pairing phone state.");
        pairingPhone = null;
      }
      console.log("Logged out. Not reconnecting.");
    }
  }
}

async function requestPairingCodeForPhone(phoneNumber: string): Promise<string> {
  const normalizedPhoneNumber = normalizePhoneNumber(phoneNumber);

  if (!normalizedPhoneNumber) {
    throw new Error("phoneNumber is required");
  }

  if (isConnected()) {
    throw new Error("Already connected to WhatsApp");
  }

  let lastError: unknown;

  for (let attempt = 0; attempt < 5; attempt++) {
    if (!sock && !connectPromise) {
      connectToWA(normalizedPhoneNumber).catch((err) => {
        console.error("Connection failed:", err);
      });
    }

    for (let waitAttempt = 0; waitAttempt < 20; waitAttempt++) {
      if (sock) break;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    if (!sock) continue;

    try {
      await sock.waitForSocketOpen();
      console.log("Waiting 2 seconds for Noise handshake to complete...");
      await new Promise((resolve) => setTimeout(resolve, 2000));
      currentPairingCode = await sock.requestPairingCode(normalizedPhoneNumber);
      console.log(`WhatsApp pairing code for ${normalizedPhoneNumber}: ${currentPairingCode}`);
      return currentPairingCode;
    } catch (error) {
      lastError = error;
      console.error("Pairing code request failed:", error);

      if (!isConnected()) {
        sock = null;
        connectPromise = null;
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  pairingPhone = null;

  if (lastError instanceof Error) {
    throw lastError;
  }

  throw new Error("WhatsApp socket was not ready for pairing code request");
}

async function logout(deleteSessionCache = true): Promise<void> {
  const currentSock = getSock();
  if (!currentSock) {
    console.log("No active connection to log out from.");
    return;
  }
  try {
    await currentSock.logout();
    console.log("✅ Logged out successfully.");
    // Optional: Delete session folder to clear any residual data
    if (deleteSessionCache && fs.existsSync("auth_info")) {
      fs.rmSync("auth_info", { recursive: true, force: true });
      console.log("🗑️ Session files deleted.");
    }

    sock = null; // Clear socket reference
    pairingPhone = null;
    !!currentQR && (currentQR = null);
    !!currentPairingCode && (currentPairingCode = null);
     // Clear QR code
  } catch (error) {
    console.error("❌ Logout failed:", error);
  }
}

export {
  connectToWA,
  isConnected,
  getSock,
  getQR,
  getPairingCode,
  requestPairingCodeForPhone,
  logout,
};

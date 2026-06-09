import fs from "fs";
import path from "path";
import readline from "readline/promises";
import { spawnSync } from "child_process";
import { stdin as input, stdout as output } from "process";
import {
  connectToWA,
  isConnected,
  requestPairingCodeForPhone,
  waEmitter,
} from "./whatsappClient";

const SESSION_DIR = path.resolve("auth_info");
const SESSION_FILE = path.resolve("auth_info", "creds.json");
const PAIRING_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes
const INVALID_SESSION_CODES = new Set([401, 403, 419]);

function copyToClipboard(value: string): boolean {
  if (process.platform !== "win32") return false;
  try {
    const result = spawnSync("clip.exe", {
      input: value,
      encoding: "utf8",
    });
    return result.status === 0;
  } catch {
    return false;
  }
}

async function waitForConnection(timeoutMs: number): Promise<void> {
  if (isConnected()) return;

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      waEmitter.off("connected", onConnected);
      reject(new Error(`Timed out waiting for WhatsApp connection.`));
    }, timeoutMs);

    const onConnected = () => {
      clearTimeout(timeout);
      resolve();
    };

    waEmitter.once("connected", onConnected);
  });
}

function normalizePhoneNumber(value: string): string {
  return value.replace(/\D/g, "");
}

function getStatusCode(error: unknown): number | undefined {
  if (!error || typeof error !== "object") return undefined;

  const maybeBoom = error as {
    output?: {
      statusCode?: number;
    };
  };

  return maybeBoom.output?.statusCode;
}

function clearWhatsAppSession(): void {
  if (fs.existsSync(SESSION_DIR)) {
    fs.rmSync(SESSION_DIR, { recursive: true, force: true });
    console.log(`Deleted invalid WhatsApp session: ${SESSION_DIR}`);
  }
}

async function connectExistingSession(): Promise<boolean> {
  if (!fs.existsSync(SESSION_FILE)) return false;

  try {
    const credsRaw = fs.readFileSync(SESSION_FILE, "utf-8");
    const creds = JSON.parse(credsRaw);
    if (!creds || !creds.registered) {
      console.log("Found incomplete/unregistered WhatsApp session. Cleaning up...");
      clearWhatsAppSession();
      return false;
    }
  } catch (err) {
    console.error("Failed to read existing session credentials:", err);
    clearWhatsAppSession();
    return false;
  }

  console.log("Found existing WhatsApp session. Connecting...");

  try {
    await connectToWA();
    console.log("Existing WhatsApp session connected.");
    return true;
  } catch (error) {
    const statusCode = getStatusCode(error);
    console.error("Existing WhatsApp session failed:", error);

    if (statusCode && INVALID_SESSION_CODES.has(statusCode)) {
      console.log(`Session is invalid or logged out. statusCode=${statusCode}`);
      clearWhatsAppSession();
      return false;
    }

    throw error;
  }
}

async function connectWithQr(): Promise<void> {
  console.log("");
  console.log("Initializing QR code generation. Please wait...");
  console.log("Scan the QR code in WhatsApp > Linked devices > Link a device.");
  await connectToWA();
  console.log("WhatsApp linked successfully with QR code.");
}

async function connectWithPairingCode(rl: readline.Interface): Promise<void> {
  console.log("");
  const rawPhoneNumber = await rl.question(
    "Enter WhatsApp phone number with country code, example 6281234567890: "
  );
  const phoneNumber = normalizePhoneNumber(rawPhoneNumber);
  if (!phoneNumber) {
    throw new Error("Phone number is required.");
  }

  console.log("");
  console.log("Before requesting the code, open WhatsApp on your phone:");
  console.log("Linked devices > Link a device > Link with phone number instead");
  console.log("Keep that input screen open.");
  await rl.question("Press Enter here only when WhatsApp is ready for the pairing code...");
  console.log("");

  console.log("Requesting WhatsApp pairing code...");
  const pairingCode = await requestPairingCodeForPhone(phoneNumber);

  console.log("");
  console.log(`Phone number : ${phoneNumber}`);
  console.log(`Pairing code : ${pairingCode}`);
  if (copyToClipboard(pairingCode)) {
    console.log("Pairing code copied to clipboard.");
  }
  console.log("");
  console.log("Enter the pairing code in WhatsApp. Do not request another code while this one is active.");
  console.log("Waiting for WhatsApp to finish linking...");

  await waitForConnection(PAIRING_TIMEOUT_MS);
  console.log("WhatsApp linked successfully with pairing code.");
}

async function promptLoginMethod(): Promise<void> {
  if (!process.stdin.isTTY) {
    console.log("Non-interactive terminal detected. Defaulting to QR code scan...");
    await connectWithQr();
    return;
  }

  const rl = readline.createInterface({ input, output });

  try {
    while (true) {
      console.log("");
      console.log("No valid WhatsApp session found.");
      console.log("Select a WhatsApp linking method:");
      console.log("1) Scan QR Code");
      console.log("2) Pairing Code with phone number");
      const choice = (await rl.question("Choice (1 or 2): ")).trim();

      if (choice === "1") {
        await connectWithQr();
        return;
      }

      if (choice === "2") {
        await connectWithPairingCode(rl);
        return;
      }

      console.log("Invalid choice. Please type 1 or 2.");
    }
  } finally {
    rl.close();
  }
}

export async function initWhatsApp(): Promise<void> {
  if (await connectExistingSession()) {
    return;
  }

  try {
    await promptLoginMethod();
  } catch (error) {
    console.error("WhatsApp initialization failed:", error);
  }
}

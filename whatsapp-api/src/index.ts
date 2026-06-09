import { startServer } from "@/server";
import { initWhatsApp } from "@/initWhatsApp";

async function main() {
  await startServer();
  await initWhatsApp();
}

void main();

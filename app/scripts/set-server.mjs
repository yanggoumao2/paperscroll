// Point the synced Android project at the user's PaperScroll server (called by build-apk.*).
// Edits only generated files: android/app/src/main/assets/{capacitor.config.json, public/offline.html}.
import { readFileSync, writeFileSync } from "node:fs";
const server = (process.argv[2] || "").replace(/\/$/, "");
if (!/^https?:\/\/[^\s/]+$/.test(server)) { console.error("server must look like http://host:port"); process.exit(1); }
const assets = new URL("../android/app/src/main/assets/", import.meta.url);
const cfgPath = new URL("capacitor.config.json", assets);
const cfg = JSON.parse(readFileSync(cfgPath, "utf8"));
cfg.server = { ...(cfg.server || {}), url: server };
writeFileSync(cfgPath, JSON.stringify(cfg, null, 2));
const offPath = new URL("public/offline.html", assets);
writeFileSync(offPath, readFileSync(offPath, "utf8").replaceAll("__PAPERSCROLL_SERVER__", server));
console.log("server.url =", server);

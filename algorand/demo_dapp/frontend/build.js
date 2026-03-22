const fs = require("fs");
const path = require("path");

const src = path.join(__dirname, "public", "index.html");
const distDir = path.join(__dirname, "dist");
const dest = path.join(distDir, "index.html");

if (!fs.existsSync(src)) {
  console.error("Missing public/index.html");
  process.exit(1);
}

fs.mkdirSync(distDir, { recursive: true });
fs.copyFileSync(src, dest);
console.log("Build complete:", dest);

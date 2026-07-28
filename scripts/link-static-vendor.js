/**
 * Crea collegamenti static/vendor/* -> node_modules (senza "@" negli URL).
 * Necessario per Chrome/iOS WebKit e per Windows (junction).
 */
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const vendorDir = path.join(root, "static", "vendor");

const links = [
  ["tabler", path.join("node_modules", "@tabler", "core", "dist")],
  ["tabler-icons", path.join("node_modules", "@tabler", "icons-webfont", "dist")],
  ["alpinejs", path.join("node_modules", "alpinejs", "dist")],
  ["htmx", path.join("node_modules", "htmx.org", "dist")],
  ["sqljs", path.join("node_modules", "sql.js", "dist")],
  ["fullcalendar", path.join("node_modules", "fullcalendar")],
  ["fullcalendar-core", path.join("node_modules", "@fullcalendar", "core")],
];

fs.mkdirSync(vendorDir, { recursive: true });

for (const [name, targetRel] of links) {
  const linkPath = path.join(vendorDir, name);
  const targetPath = path.join(root, targetRel);

  if (!fs.existsSync(targetPath)) {
    console.warn("skip (missing):", targetRel);
    continue;
  }

  try {
    const st = fs.lstatSync(linkPath);
    if (st.isSymbolicLink() || st.isDirectory()) {
      fs.rmSync(linkPath, { recursive: true, force: true });
    }
  } catch (_) {
    /* missing */
  }

  const type = process.platform === "win32" ? "junction" : "dir";
  fs.symlinkSync(targetPath, linkPath, type);
  console.log("linked", path.relative(root, linkPath), "->", targetRel);
}

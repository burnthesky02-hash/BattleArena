// Obfuscates (or, failing that, minifies) every .js file and every inline <script> in .html files under a folder, in place.
// Usage: node js_protect.js <folder>      Exit code 3 = neither javascript-obfuscator nor esbuild is installed.
const fs = require("fs"), path = require("path"), vm = require("vm");
let Obf = null, esb = null;
try { Obf = require("javascript-obfuscator"); } catch (e) {}
if (!Obf) { try { esb = require("esbuild"); } catch (e) {} }
if (!Obf && !esb) { console.log("no javascript-obfuscator or esbuild available"); process.exit(3); }

// Conservative settings: top-level names stay (pages call each other's globals and inline onclick handlers), object keys stay.
const OPTS = {
  compact: true, simplify: true, renameGlobals: false, renameProperties: false, transformObjectKeys: false,
  identifierNamesGenerator: "hexadecimal", stringArray: true, stringArrayThreshold: 0.75, stringArrayEncoding: ["base64"],
  stringArrayRotate: true, stringArrayShuffle: true, stringArrayWrappersCount: 1, splitStrings: false,
  controlFlowFlattening: false, deadCodeInjection: false, selfDefending: false, debugProtection: false,
  disableConsoleOutput: false, unicodeEscapeSequence: false, numbersToExpressions: false, target: "browser",
};

function syntaxOk(code) { try { new vm.Script(code); return true; } catch (e) { return false; } }
function protect(code) {
  let out = null;
  try { out = Obf ? Obf.obfuscate(code, OPTS).getObfuscatedCode() : esb.transformSync(code, { minify: true, target: "es2019" }).code; } catch (e) { return code; }
  return syntaxOk(out) ? out : code;                 // never ship something that does not parse
}

let nFiles = 0, nInline = 0;
function walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) { walk(p); continue; }
    if (p.endsWith(".js")) { fs.writeFileSync(p, protect(fs.readFileSync(p, "utf8"))); nFiles++; }
    else if (p.endsWith(".html")) {
      const html = fs.readFileSync(p, "utf8");
      const out = html.replace(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/gi, (m, attrs, body) => {
        attrs = attrs || "";
        if (/\ssrc\s*=/i.test(attrs) || /type\s*=\s*["'](?!text\/javascript|module)/i.test(attrs) || !body.trim()) return m;
        nInline++;
        return "<script" + attrs + ">" + protect(body).replace(/<\/script/gi, "<\\/script") + "</script>";
      });
      fs.writeFileSync(p, out);
    }
  }
}
walk(process.argv[2]);
console.log((Obf ? "obfuscated " : "minified ") + nFiles + " js files and " + nInline + " inline scripts");

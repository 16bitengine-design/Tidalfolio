// node lego3d/render_test.js OUTDIR  : renders a few test frames with headless Chromium (software WebGL, no graphics card needed)
const { chromium } = require("playwright"); const path = require("path"); const http = require("http"); const fs = require("fs");
const dir = __dirname, out = process.argv[2] || "/tmp/lego-out"; fs.mkdirSync(out, { recursive: true });
const srv = http.createServer((q, r) => { const f = path.join(dir, decodeURIComponent(q.url.split("?")[0])); fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { "Content-Type": f.endsWith(".js") ? "text/javascript" : "text/html" }); r.end(d); } }); }).listen(0);
const FIGS = [
 { skin: 0xf6c700, torso: 0xf2a20c, legs: 0x1c3f94, bib: 0x1c3f94, hat: "straw", hatColor: 0xe2c35a, hatColor2: 0xc0392b, mood: "shocked", action: "talk" },
 { skin: 0x7fd1b9, torso: 0xffffff, legs: 0x3a3a3a, apron: 0xf2564f, hat: "chef", mood: "happy", action: "cheer" },
 { skin: 0xf6c700, torso: 0x1f9e9a, legs: 0x2b2b3a, tie: 0xd62839, hair: 0x555555, mood: "sad", action: "stand" },
 { skin: 0xf3a0c0, torso: 0x7b3fb5, legs: 0x5b2b88, hat: "crown", mood: "angry", action: "wave" },
];
(async () => {
  const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const W = +process.env.W || 540, H = +process.env.H || 960;
  const p = await b.newPage({ viewport: { width: W, height: H } });
  p.on("console", m => console.log("page:", m.text())); p.on("pageerror", e => console.log("pageerror:", e.message));
  await p.goto(`http://localhost:${srv.address().port}/scene.html?w=${W}&h=${H}`); await p.waitForFunction("window.ready === true", null, { timeout: 60000 });
  const ROOMS = [{ floor: 0x4caf50, wall: 0x3b6fd6, sky: 0xbfe6ff }, { floor: 0xd9b36c, wall: 0xe8765b, sky: 0xffd9a0 }, { floor: 0x9aa3ad, wall: 0x2f4858, sky: 0x1a2a52 }, { floor: 0x7bc47f, wall: 0x8e5bd0, sky: 0xffc2e0 }];
  for (let i = 0; i < FIGS.length; i++) {
    await p.evaluate(([f, r]) => window.setup({ bg: r.sky, room: r, fig: f }), [FIGS[i], ROOMS[i]]);
    const t0 = Date.now(); await p.evaluate("window.frame(2.0)"); await p.screenshot({ path: `${out}/f${i}.png` });
    console.log(`frame ${i}: ${Date.now() - t0} ms`);
  }
  await b.close(); srv.close();
})();

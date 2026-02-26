from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Dataset Segmentation Tool")

ROOT_DIR = Path(__file__).resolve().parent
DATASET_DIR = ROOT_DIR / "dataset_frames"
VALID_SPLITS: tuple[str, ...] = ("train", "val")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class SaveLabelRequest(BaseModel):
    split: Literal["train", "val"]
    image_name: str
    png_data_url: str


@app.on_event("startup")
def ensure_labels_dirs() -> None:
    for split in VALID_SPLITS:
        (DATASET_DIR / split / "labels").mkdir(parents=True, exist_ok=True)


def split_dir(split: str) -> Path:
    if split not in VALID_SPLITS:
        raise HTTPException(status_code=400, detail="split must be train or val")
    return DATASET_DIR / split


def list_images(split: str) -> list[str]:
    sdir = split_dir(split)
    if not sdir.exists():
        return []
    files = [
        p.name
        for p in sdir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(files)


def safe_image_path(split: str, image_name: str) -> Path:
    if Path(image_name).name != image_name:
        raise HTTPException(status_code=400, detail="invalid image name")
    path = split_dir(split) / image_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="image not found")
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="unsupported image extension")
    return path


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.get("/api/images")
def api_images(split: Literal["train", "val"]) -> dict:
    images = list_images(split)
    return {"split": split, "images": images, "count": len(images)}


@app.get("/api/frame")
def api_frame(split: Literal["train", "val"], image_name: str) -> FileResponse:
    image_path = safe_image_path(split, image_name)
    return FileResponse(image_path)


@app.post("/api/save-label")
def api_save_label(payload: SaveLabelRequest) -> dict:
    image_path = safe_image_path(payload.split, payload.image_name)

    prefix = "data:image/png;base64,"
    if not payload.png_data_url.startswith(prefix):
        raise HTTPException(status_code=400, detail="png_data_url must be data:image/png;base64,...")

    try:
        raw = base64.b64decode(payload.png_data_url[len(prefix) :], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid png base64") from exc

    labels_dir = split_dir(payload.split) / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    out_path = labels_dir / f"{image_path.stem}.png"
    out_path.write_bytes(raw)

    return {"saved": True, "path": str(out_path.relative_to(ROOT_DIR))}


HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Segmentation Tool</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --line: #334155;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #22d3ee;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, #1e293b 0%, #0b1020 60%, #020617 100%);
      color: var(--text);
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: rgba(2, 6, 23, 0.85);
    }
    .bar label, .bar .group {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 6px 8px;
      background: #0b1220;
      color: var(--muted);
      font-size: 13px;
    }
    input, select, button {
      background: #0f172a;
      color: var(--text);
      border: 1px solid #475569;
      border-radius: 6px;
      padding: 6px;
    }
    button { cursor: pointer; }
    button:hover { border-color: var(--accent); }
    .hint {
      margin-left: auto;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .workspace {
      padding: 12px;
      overflow: auto;
      display: grid;
      place-items: center;
    }
    #canvasWrap {
      position: relative;
      width: fit-content;
      height: fit-content;
      border: 1px solid var(--line);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55);
      background: #000;
    }
    #canvasWrap canvas {
      display: block;
      max-width: 94vw;
      max-height: 82vh;
    }
    #drawCanvas {
      position: absolute;
      left: 0;
      top: 0;
    }
    #gridCanvas {
      position: absolute;
      left: 0;
      top: 0;
      pointer-events: none;
    }
  </style>
</head>
<body>
  <div class="bar">
    <label>Сплит
      <select id="split">
        <option value="train">train</option>
        <option value="val">val</option>
      </select>
    </label>
    <button id="reloadBtn">Обновить список</button>
    <label>Кадр
      <select id="imageSelect"></select>
    </label>
    <button id="prevBtn">Назад</button>
    <button id="nextBtn">Вперед</button>

    <label>Инструмент
      <select id="tool">
        <option value="path">Путь (жёлтый маркер)</option>
        <option value="unknown">Не видно (белый маркер)</option>
        <option value="wall">Стена (чёрная перегородка)</option>
        <option value="drone">Дрон (красная точка)</option>
        <option value="orange">Апельсин (оранжевая точка)</option>
      </select>
    </label>

    <label>Размер маркера <input id="brushSize" type="number" min="1" max="300" value="18" /></label>
    <label>Размер дрона <input id="droneSize" type="number" min="1" max="200" value="10" /></label>
    <label>Размер апельсина <input id="orangeSize" type="number" min="1" max="200" value="10" /></label>
    <label>Прозрачность маски <input id="alpha" type="range" min="0.1" max="1" step="0.05" value="0.45" /></label>

    <button id="resetBtn">Сброс (всё не видно)</button>
    <button id="saveBtn">Сохранить PNG в labels</button>
    <span id="status" class="hint">Готово</span>
  </div>

  <div class="workspace">
    <div id="canvasWrap">
      <canvas id="imageCanvas" width="960" height="640"></canvas>
      <canvas id="drawCanvas" width="960" height="640"></canvas>
      <canvas id="gridCanvas" width="960" height="640"></canvas>
    </div>
  </div>

  <script>
    const splitEl = document.getElementById("split");
    const imageSelectEl = document.getElementById("imageSelect");
    const toolEl = document.getElementById("tool");
    const brushSizeEl = document.getElementById("brushSize");
    const droneSizeEl = document.getElementById("droneSize");
    const orangeSizeEl = document.getElementById("orangeSize");
    const alphaEl = document.getElementById("alpha");
    const statusEl = document.getElementById("status");

    const reloadBtn = document.getElementById("reloadBtn");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const resetBtn = document.getElementById("resetBtn");
    const saveBtn = document.getElementById("saveBtn");

    const imageCanvas = document.getElementById("imageCanvas");
    const drawCanvas = document.getElementById("drawCanvas");
    const gridCanvas = document.getElementById("gridCanvas");

    const imageCtx = imageCanvas.getContext("2d");
    const drawCtx = drawCanvas.getContext("2d");
    const gridCtx = gridCanvas.getContext("2d");

    const img = new Image();

    const state = {
      split: "train",
      images: [],
      currentIndex: -1,
      wallV: [[false, false], [false, false], [false, false]],
      wallH: [[false, false, false], [false, false, false]],
      isDrawing: false,
      lastX: 0,
      lastY: 0
    };

    function setStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.style.color = isError ? "#fca5a5" : "#94a3b8";
    }

    function currentImageName() {
      if (state.currentIndex < 0 || state.currentIndex >= state.images.length) return null;
      return state.images[state.currentIndex];
    }

    function resetWallState() {
      state.wallV = [[false, false], [false, false], [false, false]];
      state.wallH = [[false, false, false], [false, false, false]];
    }

    function fillUnknownAll() {
      drawCtx.save();
      drawCtx.globalCompositeOperation = "source-over";
      drawCtx.fillStyle = "#ffffff";
      drawCtx.fillRect(0, 0, drawCanvas.width, drawCanvas.height);
      drawCtx.restore();
      redrawGridOverlay();
    }

    function setCanvasSize(w, h) {
      [imageCanvas, drawCanvas, gridCanvas].forEach((c) => {
        c.width = w;
        c.height = h;
      });
      redrawGridOverlay();
      applyAlpha();
    }

    function applyAlpha() {
      drawCanvas.style.opacity = String(Number(alphaEl.value) || 0.45);
    }

    function redrawGridOverlay() {
      const w = gridCanvas.width;
      const h = gridCanvas.height;
      const cellW = w / 3;
      const cellH = h / 3;

      gridCtx.clearRect(0, 0, w, h);
      gridCtx.strokeStyle = "#00e5ff";
      gridCtx.lineWidth = 2;
      gridCtx.strokeRect(0, 0, w, h);

      gridCtx.strokeStyle = "rgba(34,211,238,0.95)";
      gridCtx.lineWidth = 1;
      for (let i = 1; i < 3; i++) {
        gridCtx.beginPath();
        gridCtx.moveTo(i * cellW, 0);
        gridCtx.lineTo(i * cellW, h);
        gridCtx.stroke();

        gridCtx.beginPath();
        gridCtx.moveTo(0, i * cellH);
        gridCtx.lineTo(w, i * cellH);
        gridCtx.stroke();
      }

      gridCtx.strokeStyle = "#000000";
      gridCtx.lineWidth = Math.max(4, Math.min(cellW, cellH) * 0.08);
      for (let r = 0; r < 3; r++) {
        for (let b = 0; b < 2; b++) {
          if (!state.wallV[r][b]) continue;
          const x = (b + 1) * cellW;
          const y1 = r * cellH;
          const y2 = (r + 1) * cellH;
          gridCtx.beginPath();
          gridCtx.moveTo(x, y1);
          gridCtx.lineTo(x, y2);
          gridCtx.stroke();
        }
      }
      for (let a = 0; a < 2; a++) {
        for (let c = 0; c < 3; c++) {
          if (!state.wallH[a][c]) continue;
          const y = (a + 1) * cellH;
          const x1 = c * cellW;
          const x2 = (c + 1) * cellW;
          gridCtx.beginPath();
          gridCtx.moveTo(x1, y);
          gridCtx.lineTo(x2, y);
          gridCtx.stroke();
        }
      }
    }

    function drawWallsOnContext(ctx, w, h) {
      const cellW = w / 3;
      const cellH = h / 3;
      ctx.save();
      ctx.strokeStyle = "#000000";
      ctx.lineWidth = Math.max(4, Math.min(cellW, cellH) * 0.08);
      ctx.lineCap = "round";
      for (let r = 0; r < 3; r++) {
        for (let b = 0; b < 2; b++) {
          if (!state.wallV[r][b]) continue;
          const x = (b + 1) * cellW;
          const y1 = r * cellH;
          const y2 = (r + 1) * cellH;
          ctx.beginPath();
          ctx.moveTo(x, y1);
          ctx.lineTo(x, y2);
          ctx.stroke();
        }
      }
      for (let a = 0; a < 2; a++) {
        for (let c = 0; c < 3; c++) {
          if (!state.wallH[a][c]) continue;
          const y = (a + 1) * cellH;
          const x1 = c * cellW;
          const x2 = (c + 1) * cellW;
          ctx.beginPath();
          ctx.moveTo(x1, y);
          ctx.lineTo(x2, y);
          ctx.stroke();
        }
      }
      ctx.restore();
    }

    function drawPoint(x, y, color, radius) {
      drawCtx.save();
      drawCtx.fillStyle = color;
      drawCtx.beginPath();
      drawCtx.arc(x, y, radius, 0, Math.PI * 2);
      drawCtx.fill();
      drawCtx.restore();
    }

    function markerColor(tool) {
      if (tool === "path") return "#ffff00";
      if (tool === "unknown") return "#ffffff";
      return null;
    }

    function drawBrush(x0, y0, x1, y1) {
      const color = markerColor(toolEl.value);
      if (!color) return;
      const size = Math.max(1, Number(brushSizeEl.value) || 1);
      drawCtx.save();
      drawCtx.strokeStyle = color;
      drawCtx.lineWidth = size;
      drawCtx.lineCap = "round";
      drawCtx.lineJoin = "round";
      drawCtx.beginPath();
      drawCtx.moveTo(x0, y0);
      drawCtx.lineTo(x1, y1);
      drawCtx.stroke();
      drawCtx.restore();
    }

    function canvasPoint(e, canvas) {
      const rect = canvas.getBoundingClientRect();
      const sx = canvas.width / rect.width;
      const sy = canvas.height / rect.height;
      return {
        x: (e.clientX - rect.left) * sx,
        y: (e.clientY - rect.top) * sy
      };
    }

    function toggleClosestWall(x, y) {
      const w = drawCanvas.width;
      const h = drawCanvas.height;
      const cellW = w / 3;
      const cellH = h / 3;
      const threshold = Math.max(8, Math.min(cellW, cellH) * 0.12);
      let best = null;

      for (let r = 0; r < 3; r++) {
        for (let b = 0; b < 2; b++) {
          const lx = (b + 1) * cellW;
          const y1 = r * cellH;
          const y2 = (r + 1) * cellH;
          if (y < y1 || y > y2) continue;
          const dist = Math.abs(x - lx);
          if (dist <= threshold && (!best || dist < best.dist)) {
            best = { type: "v", r, b, dist };
          }
        }
      }

      for (let a = 0; a < 2; a++) {
        for (let c = 0; c < 3; c++) {
          const ly = (a + 1) * cellH;
          const x1 = c * cellW;
          const x2 = (c + 1) * cellW;
          if (x < x1 || x > x2) continue;
          const dist = Math.abs(y - ly);
          if (dist <= threshold && (!best || dist < best.dist)) {
            best = { type: "h", a, c, dist };
          }
        }
      }

      if (!best) return false;
      if (best.type === "v") state.wallV[best.r][best.b] = !state.wallV[best.r][best.b];
      else state.wallH[best.a][best.c] = !state.wallH[best.a][best.c];
      return true;
    }

    drawCanvas.addEventListener("pointerdown", (e) => {
      const p = canvasPoint(e, drawCanvas);
      const tool = toolEl.value;

      if (tool === "wall") {
        if (toggleClosestWall(p.x, p.y)) {
          redrawGridOverlay();
        }
        return;
      }

      if (tool === "drone") {
        drawPoint(p.x, p.y, "#ff0000", Math.max(1, Number(droneSizeEl.value) || 10));
        return;
      }

      if (tool === "orange") {
        drawPoint(p.x, p.y, "#ff8c00", Math.max(1, Number(orangeSizeEl.value) || 10));
        return;
      }

      state.isDrawing = true;
      state.lastX = p.x;
      state.lastY = p.y;
      drawBrush(p.x, p.y, p.x, p.y);
    });

    drawCanvas.addEventListener("pointermove", (e) => {
      if (!state.isDrawing) return;
      const p = canvasPoint(e, drawCanvas);
      drawBrush(state.lastX, state.lastY, p.x, p.y);
      state.lastX = p.x;
      state.lastY = p.y;
    });

    function stopDrawing() {
      state.isDrawing = false;
    }

    drawCanvas.addEventListener("pointerup", stopDrawing);
    drawCanvas.addEventListener("pointercancel", stopDrawing);
    drawCanvas.addEventListener("pointerleave", stopDrawing);

    async function loadImageList() {
      const split = splitEl.value;
      state.split = split;
      const r = await fetch(`/api/images?split=${encodeURIComponent(split)}`);
      if (!r.ok) throw new Error(`Не удалось получить список (${r.status})`);
      const data = await r.json();
      state.images = data.images || [];

      imageSelectEl.innerHTML = "";
      for (const name of state.images) {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        imageSelectEl.appendChild(opt);
      }

      if (state.images.length === 0) {
        state.currentIndex = -1;
        setStatus(`Нет изображений в dataset_frames/${split}`, true);
        imageCtx.clearRect(0, 0, imageCanvas.width, imageCanvas.height);
        drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
        redrawGridOverlay();
        return;
      }

      state.currentIndex = 0;
      imageSelectEl.selectedIndex = 0;
      await loadCurrentImage();
    }

    async function loadCurrentImage() {
      const name = currentImageName();
      if (!name) return;

      const url = `/api/frame?split=${encodeURIComponent(state.split)}&image_name=${encodeURIComponent(name)}`;
      await new Promise((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("Не удалось загрузить изображение"));
        img.src = url;
      });

      setCanvasSize(img.width, img.height);
      imageCtx.clearRect(0, 0, imageCanvas.width, imageCanvas.height);
      imageCtx.drawImage(img, 0, 0, imageCanvas.width, imageCanvas.height);

      resetWallState();
      fillUnknownAll();
      setStatus(`Открыт ${state.split}/${name}`);
    }

    async function saveMask() {
      const name = currentImageName();
      if (!name) {
        setStatus("Нет выбранного изображения", true);
        return;
      }

      const out = document.createElement("canvas");
      out.width = drawCanvas.width;
      out.height = drawCanvas.height;
      const outCtx = out.getContext("2d");
      outCtx.drawImage(drawCanvas, 0, 0);
      drawWallsOnContext(outCtx, out.width, out.height);
      const png = out.toDataURL("image/png");
      const body = {
        split: state.split,
        image_name: name,
        png_data_url: png
      };

      const r = await fetch("/api/save-label", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });

      if (!r.ok) {
        const errText = await r.text();
        throw new Error(errText || `Ошибка сохранения (${r.status})`);
      }
      const data = await r.json();
      setStatus(`Сохранено: ${data.path}`);
    }

    splitEl.addEventListener("change", async () => {
      try {
        await loadImageList();
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    reloadBtn.addEventListener("click", async () => {
      try {
        await loadImageList();
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    imageSelectEl.addEventListener("change", async () => {
      state.currentIndex = imageSelectEl.selectedIndex;
      try {
        await loadCurrentImage();
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    prevBtn.addEventListener("click", async () => {
      if (state.images.length === 0) return;
      state.currentIndex = (state.currentIndex - 1 + state.images.length) % state.images.length;
      imageSelectEl.selectedIndex = state.currentIndex;
      try {
        await loadCurrentImage();
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    nextBtn.addEventListener("click", async () => {
      if (state.images.length === 0) return;
      state.currentIndex = (state.currentIndex + 1) % state.images.length;
      imageSelectEl.selectedIndex = state.currentIndex;
      try {
        await loadCurrentImage();
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    resetBtn.addEventListener("click", () => {
      resetWallState();
      fillUnknownAll();
      setStatus("Маска сброшена: везде класс 'не видно'");
    });

    saveBtn.addEventListener("click", async () => {
      try {
        await saveMask();
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    alphaEl.addEventListener("input", applyAlpha);

    applyAlpha();
    loadImageList().catch((err) => {
      setStatus(String(err), true);
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

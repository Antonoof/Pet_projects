import json
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="Image Gallery")

app.mount("/static", StaticFiles(directory="images"), name="static")
IMAGES_DIR = Path("images")
image_cache = None


def get_images():
    global image_cache
    if image_cache is None:
        if not IMAGES_DIR.exists():
            image_cache = []
        else:
            image_cache = sorted(
                [
                    f.name
                    for f in IMAGES_DIR.iterdir()
                    if f.is_file()
                    and f.suffix.lower()
                    in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]
                ]
            )
    return image_cache


def generate_gallery_html(images: list, current_index: int = 0):
    if not images:
        return """<!DOCTYPE html><html><body><h1 style="text-align: center; margin-top: 50px;">No images found</h1></body></html>"""

    current_image = images[current_index]

    start_idx = max(0, current_index - 5)
    end_idx = min(len(images), current_index + 6)
    visible_thumbnails = images[start_idx:end_idx]

    thumbnails_html = ""
    for j, img in enumerate(visible_thumbnails):
        img_index = start_idx + j
        is_active = "active" if img_index == current_index else ""
        thumbnails_html += f'<img class="thumbnail {is_active}" src="/static/{img}" onclick="navigate({img_index})" loading="lazy" data-index="{img_index}">'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Gallery - {current_image}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, sans-serif;
            margin: 0;
            padding: 0;
            background: #0d1117;
            color: white;
            height: 100vh;
            overflow: hidden;
        }}
        .gallery-container {{
            display: flex;
            height: 100vh;
            align-items: center;
            justify-content: center;
        }}
        .image-wrapper {{
            position: relative;
            max-width: 90vw;
            max-height: 90vh;
        }}
        .main-image {{
            max-width: 100%;
            max-height: 80vh;
            object-fit: contain;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            cursor: zoom-in;
        }}
        .main-image.zoomed {{
            cursor: zoom-out;
            transform: scale(1.5);
            transition: transform 0.3s ease;
        }}
        .image-info {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.85);
            padding: 12px 20px;
            border-radius: 16px;
            text-align: right;
            font-size: 14px;
            z-index: 100;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            max-width: 300px;
        }}
        .image-counter {{
            font-weight: 600;
            font-size: 15px;
            color: #58a6ff;
            margin-bottom: 4px;
        }}
        .image-name {{
            font-size: 13px;
            opacity: 0.9;
        }}
        .thumbnails {{
            position: fixed;
            bottom: 25px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 12px;
            max-width: 80vw;
            overflow-x: auto;
            padding: 15px;
            background: rgba(0,0,0,0.4);
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }}
        .thumbnail {{
            width: 65px;
            height: 65px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            opacity: 0.7;
            transition: all 0.3s ease;
        }}
        .thumbnail:hover {{
            opacity: 0.9;
            transform: scale(1.08);
        }}
        .thumbnail.active {{
            opacity: 1;
            border: 2px solid #58a6ff;
            transform: scale(1.1);
        }}
        .loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            background: rgba(0,0,0,0.9);
            padding: 20px 30px;
            border-radius: 15px;
            display: none;
        }}
        .zoom-hint {{
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            padding: 8px 16px;
            border-radius: 12px;
            font-size: 12px;
            opacity: 0.8;
            z-index: 100;
        }}
    </style>
</head>
<body>
    <div class="image-info" id="imageInfo">
        <div class="image-counter">{current_index + 1} / {len(images)}</div>
        <div class="image-name">{current_image}</div>
    </div>

    <div class="gallery-container">
        <div class="image-wrapper">
            <img 
                id="mainImage" 
                class="main-image" 
                src="/static/{current_image}" 
                alt="{current_image}"
                onload="hideLoading()"
                onclick="toggleZoom()"
            >
            <div id="loading" class="loading">Загрузка...</div>
        </div>
    </div>

    <div class="thumbnails" id="thumbnailsContainer">
        {thumbnails_html}
    </div>

    <div class="zoom-hint" id="zoomHint">
        Кликните на изображение для увеличения • ← → для навигации
    </div>

    <script>
        const totalImages = {len(images)};
        const allImages = {json.dumps(images)};
        let currentIndex = {current_index};
        let isZoomed = false;

        function navigate(index) {{
            if (index < 0) index = 0;
            if (index >= totalImages) index = totalImages - 1;
            if (index === currentIndex) return;
            
            currentIndex = index;
            document.getElementById('loading').style.display = 'block';
            document.getElementById('mainImage').style.opacity = '0.3';
            
            window.history.pushState({{index: index}}, '', '/view/' + index);
            loadImage(index);
            updateThumbnails(index);
        }}
        
        function loadImage(index) {{
            const imageName = allImages[index];
            const newImage = new Image();
            
            newImage.onload = function() {{
                document.getElementById('mainImage').src = this.src;
                document.getElementById('mainImage').alt = imageName;
                
                const infoElement = document.getElementById('imageInfo');
                infoElement.innerHTML = `
                    <div class="image-counter">${{index + 1}} / ${{totalImages}}</div>
                    <div class="image-name">${{imageName}}</div>
                `;
                
                hideLoading();
            }};
            
            newImage.onerror = function() {{
                hideLoading();
                alert('Ошибка загрузки: ' + imageName);
            }};
            
            newImage.src = '/static/' + imageName;
        }}
        
        function updateThumbnails(currentIndex) {{
            const startIdx = Math.max(0, currentIndex - 5);
            const endIdx = Math.min(totalImages, currentIndex + 6);
            const visibleImages = allImages.slice(startIdx, endIdx);
            
            let thumbnailsHtml = '';
            for (let i = 0; i < visibleImages.length; i++) {{
                const imgIndex = startIdx + i;
                const isActive = imgIndex === currentIndex ? 'active' : '';
                thumbnailsHtml += `
                    <img class="thumbnail ${{isActive}}" 
                         src="/static/${{visibleImages[i]}}" 
                         onclick="navigate(${{imgIndex}})" 
                         loading="lazy">
                `;
            }}
            
            document.getElementById('thumbnailsContainer').innerHTML = thumbnailsHtml;
        }}
        
        function hideLoading() {{
            document.getElementById('loading').style.display = 'none';
            document.getElementById('mainImage').style.opacity = '1';
        }}
        
        function toggleZoom() {{
            const image = document.getElementById('mainImage');
            isZoomed = !isZoomed;
            
            if (isZoomed) {{
                image.classList.add('zoomed');
            }} else {{
                image.classList.remove('zoomed');
            }}
        }}
        
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowLeft') navigate(currentIndex - 1);
            else if (e.key === 'ArrowRight') navigate(currentIndex + 1);
            else if (e.key === 'Escape') {{
                if (isZoomed) toggleZoom();
                else window.location.href = '/';
            }}
        }});
        
        window.addEventListener('popstate', function(e) {{
            if (e.state && e.state.index !== undefined) {{
                navigate(e.state.index);
            }}
        }});
        
        let touchStartX = 0;
        document.addEventListener('touchstart', e => {{
            touchStartX = e.changedTouches[0].screenX;
        }});
        
        document.addEventListener('touchend', e => {{
            const touchEndX = e.changedTouches[0].screenX;
            const diff = touchEndX - touchStartX;
            
            if (Math.abs(diff) > 50) {{
                if (diff > 0) navigate(currentIndex - 1);
                else navigate(currentIndex + 1);
            }}
        }});
        
        setTimeout(() => {{
            document.getElementById('zoomHint').style.opacity = '0';
        }}, 3000);
    </script>
</body>
</html>"""

    return html


@app.get("/", response_class=HTMLResponse)
async def gallery_home():
    images = get_images()
    return generate_gallery_html(images, 0)


@app.get("/view/{image_index:int}", response_class=HTMLResponse)
async def view_image(image_index: int):
    images = get_images()

    if not images:
        return HTMLResponse(
            """<div style="text-align: center; margin-top: 100px;"><h1>No images found</h1></div>"""
        )

    if image_index < 0:
        image_index = 0
    if image_index >= len(images):
        image_index = len(images) - 1

    return generate_gallery_html(images, image_index)


@app.get("/api/images")
async def api_list_images():
    images = get_images()
    return {"images": images, "count": len(images)}


@app.get("/api/image/{image_index:int}")
async def api_get_image_info(image_index: int):
    images = get_images()

    if not images or image_index < 0 or image_index >= len(images):
        raise HTTPException(status_code=404, detail="Image not found")

    image_name = images[image_index]
    image_path = IMAGES_DIR / image_name

    return {
        "index": image_index,
        "name": image_name,
        "url": f"/static/{image_name}",
        "size": image_path.stat().st_size if image_path.exists() else 0,
    }

if __name__ == "__main__":
    uvicorn.run("visualizeImages:app", host="0.0.0.0", port=8000, reload=True)

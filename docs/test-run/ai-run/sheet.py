"""Contact sheet of every draft reel: 3 frames each, with the clip, source, score and hook. Usage: sheet.py reelbot.db out.jpg"""
import sqlite3, subprocess, sys, io
from PIL import Image, ImageDraw, ImageFont
db, out = sys.argv[1], sys.argv[2]

c = sqlite3.connect(db); c.row_factory = sqlite3.Row
rows = c.execute("select r.id, c.filename, r.on_screen_text, r.source, r.virality_score, r.video_path from reels r join clips c on c.id=r.clip_id where r.status='draft' order by c.created_at, r.created_at").fetchall()
TW, TH, COLS = 180, 320, 3
font = ImageFont.load_default(15)
per_row = 2  # reels per sheet row
cell_w = TW * COLS + 10
sheet = Image.new("RGB", (cell_w * per_row, ((len(rows) + 1) // per_row) * (TH + 44)), "white")
for n, r in enumerate(rows):
    x0, y0 = (n % per_row) * cell_w, (n // per_row) * (TH + 44)
    for i, t in enumerate((0.7, 3.5, 6.8)):
        jpg = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", r["video_path"], "-frames:v", "1", "-vf", f"scale={TW}:{TH}", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True).stdout
        if jpg:
            sheet.paste(Image.open(io.BytesIO(jpg)), (x0 + i * TW, y0 + 40))
    d = ImageDraw.Draw(sheet)
    d.text((x0 + 2, y0 + 2), f"{r['filename']} · {r['source']} · {r['virality_score']}", fill="black", font=font)
    d.text((x0 + 2, y0 + 20), f"“{r['on_screen_text']}”", fill="black", font=font)
sheet.save(out, quality=85)
print(len(rows), "reels")

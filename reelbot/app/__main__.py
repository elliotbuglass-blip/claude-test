import os

import uvicorn

uvicorn.run("reelbot.app.web:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

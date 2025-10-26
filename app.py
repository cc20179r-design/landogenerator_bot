import os
import json
import base64
import requests
from flask import Flask, request, abort

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")            # isi di Render Secret
FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")# isi di Render Secret (opsional)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_this_secret")  # endpoint secret

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable required")

# simple in-memory store for selected model per chat (not persistent)
chat_model = {}

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/sendMessage", data=data)

def send_photo_by_url(chat_id, photo_url, caption=None):
    data = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        data["caption"] = caption
    requests.post(f"{TELEGRAM_API}/sendPhoto", data=data)

@app.route("/", methods=["GET"])
def home():
    return "Gy Telegram AI Bot (Render) - alive"

@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return "", 400

    # Message
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]

        # start command
        if "text" in msg and msg["text"].startswith("/start"):
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🎨 Nano Banana", "callback_data": "model:nano"}],
                    [{"text": "⚡ Kling Pro", "callback_data": "model:kling"}]
                ]
            }
            send_message(chat_id, "Halo Gy! Pilih model AI untuk generate gambar:", reply_markup=keyboard)
            return "", 200

        # plain text = treat as prompt
        if "text" in msg:
            prompt = msg["text"].strip()
            model = chat_model.get(chat_id, "nano")  # default nano
            send_message(chat_id, f"Generate gambar dengan model <b>{model}</b>. Sedang diproses... Mohon tunggu.")
            # call image generation
            try:
                image_url = generate_image_with_freepik(prompt, model)
                if image_url:
                    send_photo_by_url(chat_id, image_url, caption=f"Model: {model}\nPrompt: {prompt}")
                else:
                    send_message(chat_id, "Maaf, gagal membuat gambar (no image URL).")
            except Exception as e:
                send_message(chat_id, f"Error saat generate: {str(e)}")
            return "", 200

    # Callback query (button)
    if "callback_query" in update:
        cb = update["callback_query"]
        data = cb.get("data", "")
        chat_id = cb["message"]["chat"]["id"]
        # set model if callback like "model:nano"
        if data.startswith("model:"):
            model_key = data.split(":",1)[1]
            chat_model[chat_id] = model_key
            # answerCallbackQuery
            callback_id = cb["id"]
            requests.post(f"{TELEGRAM_API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": f"Model diset ke {model_key}"})
            send_message(chat_id, f"Kamu memilih model: {model_key}\nKirim prompt (deskripsi gambar) sekarang.")
            return "", 200

    return "", 200

def generate_image_with_freepik(prompt: str, model: str) -> str:
    """
    Contoh panggilan ke API Freepik. Ganti endpoint/payload sesuai docs Freepik.
    Kembalikan URL gambar (image_url) atau raise exception.
    """
    if not FREEPIK_API_KEY:
        # jika belum punya Freepik, sementara return placeholder image
        # Ganti ini nanti dengan panggilan API sesungguhnya.
        return "https://via.placeholder.com/1024x1024.png?text=Demo+Image"

    # contoh endpoint (BAYANGAN) — GANTI dengan endpoint resmi Freepik
    endpoint = "https://api.freepik.com/v1/generate-image"

    payload = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1
    }
    headers = {
        "Authorization": f"Bearer {FREEPIK_API_KEY}",
        "Content-Type": "application/json"
    }

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Freepik API error: {resp.status_code} {resp.text}")

    data = resp.json()

    if isinstance(data, dict) and "image_url" in data:
        return data["image_url"]

    # fallback
    raise RuntimeError("Format response Freepik tidak dikenali. Perlu sesuaikan parsing.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

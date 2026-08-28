import os
import requests
import gspread
from flask import Flask, request, jsonify

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secure_verify_token")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "923023099306")
SHEET_NAME = os.environ.get("SHEET_NAME", "RestaurantMenu")

user_sessions = {}

def get_menu_from_sheet():
    try:
        gc = gspread.service_account(filename='/etc/secrets/credentials.json')
        sh = gc.open(SHEET_NAME)
        worksheet = sh.get_worksheet(0)
        records = worksheet.get_all_records()
        if records:
            return records
    except Exception as e:
        print("Google Sheet Error:", e)
    
    # Fallback default menu agar sheet load na ho paye
    return [
        {"Name": "Chicken Biryani", "Price": 450},
        {"Name": "Special Zinger Burger", "Price": 380},
        {"Name": "Large Family Pizza", "Price": 1500},
        {"Name": "Cold Drink (1.5L)", "Price": 200}
    ]

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

def send_whatsapp_message(recipient, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    try:
        if (
            data
            and data.get("object") == "whatsapp_business_account"
            and data.get("entry")
            and data["entry"][0].get("changes")
            and data["entry"][0]["changes"][0].get("value")
            and data["entry"][0]["changes"][0]["value"].get("messages")
        ):
            msg_obj = data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender_phone = msg_obj["from"]
            msg_body = msg_obj.get("text", {}).get("body", "").strip().lower()

            if sender_phone not in user_sessions:
                user_sessions[sender_phone] = {
                    "step": "menu",
                    "cart": [],
                    "total": 0,
                    "name": "",
                    "address": ""
                }

            user = user_sessions[sender_phone]
            step = user["step"]

            menu_items = get_menu_from_sheet()

            if step == "menu" or "menu" in msg_body or "hi" in msg_body or "hello" in msg_body:
                user["step"] = "ordering"
                menu_text = "🌟 *Welcome to Royal Spice Restaurant!* 🌟\n\nYeh raha hamara live menu:\n"
                for idx, item in enumerate(menu_items, 1):
                    name = item.get("Name", "Item")
                    price = item.get("Price", 0)
                    menu_text += f"{idx}️⃣ *{name}* - Rs. {price}\n"
                
                menu_text += "\nAapko kya order karna hai? Item ka naam ya number likh kar bhejein!"
                send_whatsapp_message(sender_phone, menu_text)

            elif step == "ordering":
                if "done" in msg_body or "checkout" in msg_body:
                    if not user["cart"]:
                        send_whatsapp_message(sender_phone, "Aapne abhi tak kuch select nahi kiya! Pehle menu se item chunein.")
                        return jsonify({"status": "success"}), 200
                    
                    user["step"] = "get_name"
                    send_whatsapp_message(sender_phone, "Zabardast! 🛒 Aapka bill tayar hai.\nAb apna *Pura Naam* likh kar bhejein:")
                    return jsonify({"status": "success"}), 200

                matched_item = None
                for idx, item in enumerate(menu_items, 1):
                    name = str(item.get("Name", "")).lower()
                    if str(idx) in msg_body or name in msg_body:
                        matched_item = item
                        break

                if matched_item:
                    item_name = matched_item.get("Name")
                    item_price = int(matched_item.get("Price", 0))
                    user["cart"].append(item_name)
                    user["total"] += item_price

                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                    response_text = (
                        f"✅ *{item_name}* cart mein shamil ho gaya!\n\n"
                        f"🛒 *Aapka Cart:*\n{cart_summary}\n\n"
                        f"💰 *Total Bill:* Rs. {user['total']}\n\n"
                        f"Kya aap kuch aur add karwana chahte hain? (Mazeed item ka naam likhein ya order khatam karne ke liye *'Done'* likhein)"
                    )
                    send_whatsapp_message(sender_phone, response_text)
                else:
                    send_whatsapp_message(sender_phone, "Bhai samajh nahi aaya! Baraye meharbani menu se sahi item number likhein ya *'Done'* likhein.")

            elif step == "get_name":
                user["name"] = msg_body.title()
                user["step"] = "get_address"
                send_whatsapp_message(sender_phone, f"Shukriya {user['name']}! 😊\nAb apna *Delivery Address* type kar ke bhej dein.")

            elif step == "get_address":
                user["address"] = msg_body.title()
                cart_summary = ", ".join(user["cart"])
                
                confirmation_msg = "🎉 *Order Confirmed!* 🎉\n\nAapka order successfully book ho gaya hai aur restaurant owner ko bhej diya gaya hai!"
                send_whatsapp_message(sender_phone, confirmation_msg)

                owner_msg = (
                    f"🚨 *Naya Order Aaya Hai!* 🚨\n\n"
                    f"👤 *Customer Name:* {user['name']}\n"
                    f"📱 *Phone:* {sender_phone}\n"
                    f"🛒 *Items:* {cart_summary}\n"
                    f"💰 *Total Bill:* Rs. {user['total']}\n"
                    f"📍 *Address:* {user['address']}"
                )
                send_whatsapp_message(OWNER_PHONE, owner_msg)

                user_sessions[sender_phone] = {"step": "menu", "cart": [], "total": 0, "name": "", "address": ""}

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
                    

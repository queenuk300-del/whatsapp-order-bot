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
    
    return [
        {"Name": "Chicken Biryani", "Price": 450},
        {"Name": "Special Zinger Burger", "Price": 380},
        {"Name": "Large Family Pizza", "Price": 1500},
        {"Name": "Cold Drink", "Price": 200}
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
                    "address": "",
                    "temp_item": None
                }

            user = user_sessions[sender_phone]
            step = user["step"]
            menu_items = get_menu_from_sheet()

            # 1. Menu & Greeting Handler
            if step == "menu" or "menu" in msg_body or "hi" in msg_body or "hello" in msg_body:
                user["step"] = "ordering"
                menu_text = "🌟 *Welcome to Royal Spice Restaurant!* 🌟\n\nYeh raha hamara shandaar live menu:\n"
                for idx, item in enumerate(menu_items, 1):
                    name = item.get("Name", "Item")
                    price = item.get("Price", 0)
                    menu_text += f"{idx}️⃣ *{name}* - Rs. {price}\n"
                
                menu_text += "\nAapko kya order karna hai? Item ka naam ya number likh kar bhejein!"
                send_whatsapp_message(sender_phone, menu_text)

            # 2. Smart Ordering & Sub-options Handler
            elif step == "ordering":
                if "done" in msg_body or "checkout" in msg_body:
                    if not user["cart"]:
                        send_whatsapp_message(sender_phone, "Aapne abhi tak kuch select nahi kiya! Pehle menu se item chunein.")
                        return jsonify({"status": "success"}), 200
                    
                    user["step"] = "get_name"
                    send_whatsapp_message(sender_phone, "Zabardast! 🛒 Aapka bill tayar hai.\nAb apna *Pura Naam* likh kar bhejein:")
                    return jsonify({"status": "success"}), 200

                # Smart Detection for Cold Drink / Beverages
                if "drink" in msg_body or "cold drink" in msg_body or "pepsi" in msg_body or "coke" in msg_body or "cola" in msg_body:
                    user["step"] = "choose_drink_size"
                    send_whatsapp_message(sender_phone, "🥤 Aapko konsi cold drink chahiye?\n1️⃣ 500ml (Rs. 100)\n2️⃣ 1 Litre (Rs. 150)\n3️⃣ 1.5 Litre (Rs. 200)\n\nNumber likh kar bhejein:")
                    return jsonify({"status": "success"}), 200

                # Smart Detection for Pizza (Toppings / Add-ons)
                if "pizza" in msg_body:
                    user["temp_item"] = {"Name": "Large Family Pizza", "Price": 1500}
                    user["step"] = "pizza_topping"
                    send_whatsapp_message(sender_phone, "🍕 Great choice! Kya aap pizza ke sath extra toppings karwana chahte hain?\n\n1️⃣ Extra Cheese (+Rs. 100)\n2️⃣ Extra Chicken (+Rs. 150)\n3️⃣ Dono (Cheese + Chicken) (+Rs. 250)\n4️⃣ Nahi, Normal hi theek hai\n\nNumber likh kar bhejein:")
                    return jsonify({"status": "success"}), 200

                # Standard Item Matching from Sheet
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
                    # Strict Error Handling for gibberish/wrong names
                    send_whatsapp_message(sender_phone, "Bhai samajh nahi aaya! Baraye meharbani menu se sahi item number likhein ya *'Done'* likhein.")

            # 3. Drink Size Sub-options Handler
            elif step == "choose_drink_size":
                drink_name, drink_price = "", 0
                if "1" in msg_body or "500" in msg_body:
                    drink_name, drink_price = "Cold Drink (500ml)", 100
                elif "2" in msg_body or "1" in msg_body:
                    drink_name, drink_price = "Cold Drink (1 Litre)", 150
                elif "3" in msg_body or "1.5" in msg_body:
                    drink_name, drink_price = "Cold Drink (1.5 Litre)", 200
                else:
                    send_whatsapp_message(sender_phone, "Ghalat option! Baraye meharbani 1, 2 ya 3 mein se koi number chunein:")
                    return jsonify({"status": "success"}), 200

                user["cart"].append(drink_name)
                user["total"] += drink_price
                user["step"] = "ordering"

                cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                send_whatsapp_message(sender_phone, f"✅ *{drink_name}* add ho gaya!\n\n🛒 *Cart:* \n{cart_summary}\n\n💰 *Total:* Rs. {user['total']}\n\nMazeed kuch chahye toh likhein warna *'Done'* likhein.")

            # 4. Pizza Toppings Add-on Handler
            elif step == "pizza_topping":
                pizza_item = user["temp_item"]
                extra_name, extra_price = "", 0

                if "1" in msg_body or "cheese" in msg_body:
                    extra_name, extra_price = " + Extra Cheese", 100
                elif "2" in msg_body or "chicken" in msg_body:
                    extra_name, extra_price = " + Extra Chicken", 150
                elif "3" in msg_body or "dono" in msg_body:
                    extra_name, extra_price = " + Extra Cheese & Chicken", 250
                elif "4" in msg_body or "nahi" in msg_body or "normal" in msg_body:
                    extra_name, extra_price = "", 0
                else:
                    send_whatsapp_message(sender_phone, "Sahi option select karein (1, 2, 3 ya 4):")
                    return jsonify({"status": "success"}), 200

                final_pizza_name = pizza_item["Name"] + extra_name
                final_pizza_price = int(pizza_item["Price"]) + extra_price

                user["cart"].append(final_pizza_name)
                user["total"] += final_pizza_price
                user["step"] = "ordering"
                user["temp_item"] = None

                cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                send_whatsapp_message(sender_phone, f"🍕 *{final_pizza_name}* add ho gaya!\n\n🛒 *Cart:* \n{cart_summary}\n\n💰 *Total:* Rs. {user['total']}\n\nMazeed kuch add karwana hai? (Item likhein ya *'Done'* likhein)")

            # 5. Customer Name Collection
            elif step == "get_name":
                user["name"] = msg_body.title()
                user["step"] = "get_address"
                send_whatsapp_message(sender_phone, f"Shukriya {user['name']}! 😊\nAb apna *Delivery Address* type kar ke bhej dein (ya location share kar dein).")

            # 6. Address Collection & Owner Notification
            elif step == "get_address":
                user["address"] = msg_body.title()
                cart_summary = ", ".join(user["cart"])
                
                confirmation_msg = "🎉 *Order Confirmed!* 🎉\n\nAapka order successfully book ho gaya hai aur kitchen ko bhej diya gaya hai! Jald khana pohnch jaye ga."
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

                user_sessions[sender_phone] = {"step": "menu", "cart": [], "total": 0, "name": "", "address": "", "temp_item": None}

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
        

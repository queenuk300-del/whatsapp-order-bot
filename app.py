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
    
    # Comprehensive Fast Food Menu Fallback
    return [
        {"Name": "Zinger Burger", "Price": 380},
        {"Name": "Beef Burger", "Price": 450},
        {"Name": "Club Sandwich", "Price": 350},
        {"Name": "Regular Pizza (Small)", "Price": 800},
        {"Name": "Large Family Pizza", "Price": 1500},
        {"Name": "French Fries (Masala)", "Price": 200},
        {"Name": "Chicken Garlic Mayo Roll", "Price": 250},
        {"Name": "Cold Drink (500ml)", "Price": 100},
        {"Name": "Cold Drink (1.5 Litre)", "Price": 200}
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
                    "temp_item": None,
                    "pending_matches": []
                }

            user = user_sessions[sender_phone]
            step = user["step"]
            menu_items = get_menu_from_sheet()

            # Global Reset / Menu Request
            if "menu" in msg_body or "hi" in msg_body or "hello" in msg_body or "start" in msg_body:
                user["step"] = "ordering"
                user["pending_matches"] = []
                menu_text = "🌟 *Welcome to Royal Spice Fast Food!* 🌟\n\nYeh raha hamara complete menu:\n"
                for idx, item in enumerate(menu_items, 1):
                    name = item.get("Name", "Item")
                    price = item.get("Price", 0)
                    menu_text += f"{idx}️⃣ *{name}* - Rs. {price}\n"
                
                menu_text += "\nAapko kya order karna hai? Item ka naam ya number likh kar bhejein!"
                send_whatsapp_message(sender_phone, menu_text)
                return jsonify({"status": "success"}), 200

            # Checkout Trigger
            if "done" in msg_body or "checkout" in msg_body or "order complete" in msg_body:
                if not user["cart"]:
                    send_whatsapp_message(sender_phone, "Aapne abhi tak kuch select nahi kiya! Pehle menu se item chunein.")
                    return jsonify({"status": "success"}), 200
                
                user["step"] = "get_name"
                send_whatsapp_message(sender_phone, "Zabardast! 🛒 Aapka bill tayar hai.\nAb apna *Pura Naam* likh kar bhejein:")
                return jsonify({"status": "success"}), 200

            # Handling multi-match selection if user was asked to pick from filtered options
            if step == "select_from_matches":
                matches = user["pending_matches"]
                if msg_body.isdigit() and 1 <= int(msg_body) <= len(matches):
                    selected = matches[int(msg_body) - 1]
                    user["pending_matches"] = []
                    
                    # Check if selected item needs custom options (like Pizza or Drink)
                    item_name = selected.get("Name")
                    item_price = int(selected.get("Price", 0))

                    if "pizza" in item_name.lower():
                        user["temp_item"] = selected
                        user["step"] = "pizza_topping"
                        send_whatsapp_message(sender_phone, f"🍕 *{item_name}* select kiya hai! Kya aap extra toppings chahte hain?\n\n1️⃣ Extra Cheese (+Rs. 100)\n2️⃣ Extra Chicken (+Rs. 150)\n3️⃣ Dono (Cheese + Chicken) (+Rs. 250)\n4️⃣ Nahi, Normal hi theek hai\n\nNumber likh kar bhejein:")
                        return jsonify({"status": "success"}), 200
                    elif "drink" in item_name.lower():
                        # Add directly or let normal flow handle
                        pass

                    user["cart"].append(item_name)
                    user["total"] += item_price
                    user["step"] = "ordering"

                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                    send_whatsapp_message(sender_phone, f"✅ *{item_name}* cart mein shamil ho gaya!\n\n🛒 *Cart:*\n{cart_summary}\n\n💰 *Total Bill:* Rs. {user['total']}\n\nMazeed kuch add karwana hai? (Item likhein ya *'Done'* likhein)")
                    return jsonify({"status": "success"}), 200
                else:
                    send_whatsapp_message(sender_phone, "Baraye meharbani di gayi list mein se sahi number select karein:")
                    return jsonify({"status": "success"}), 200

            # Step: Pizza Toppings (Smart override if user types something else)
            if step == "pizza_topping":
                if msg_body in ["1", "2", "3", "4"]:
                    pizza_item = user["temp_item"]
                    extra_name, extra_price = "", 0
                    if msg_body == "1":
                        extra_name, extra_price = " + Extra Cheese", 100
                    elif msg_body == "2":
                        extra_name, extra_price = " + Extra Chicken", 150
                    elif msg_body == "3":
                        extra_name, extra_price = " + Extra Cheese & Chicken", 250
                    
                    final_name = pizza_item["Name"] + extra_name
                    final_price = int(pizza_item["Price"]) + extra_price

                    user["cart"].append(final_name)
                    user["total"] += final_price
                    user["step"] = "ordering"
                    user["temp_item"] = None

                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                    send_whatsapp_message(sender_phone, f"🍕 *{final_name}* add ho gaya!\n\n🛒 *Cart:*\n{cart_summary}\n\n💰 *Total:* Rs. {user['total']}\n\nMazeed kuch add karna hai? (Item likhein ya *'Done'* likhein)")
                    return jsonify({"status": "success"}), 200
                else:
                    # If user typed an item name instead of 1-4, fall through to normal search below so it doesn't trap them!
                    user["step"] = "ordering"

            # Main Smart Ordering & Keyword / Single-Word Matcher
            if step == "ordering" or step == "pizza_topping":
                # Check for direct number index
                matched_item = None
                if msg_body.isdigit():
                    idx = int(msg_body)
                    if 1 <= idx <= len(menu_items):
                        matched_item = menu_items[idx - 1]
                
                # If not by number, search by keyword/single word across all menu items
                if not matched_item:
                    found_matches = []
                    for item in menu_items:
                        name_lower = str(item.get("Name", "")).lower()
                        # Check if any word in user query matches item name
                        if msg_body in name_lower or any(word in name_lower for word in msg_body.split()):
                            found_matches.append(item)

                    if len(found_matches) == 1:
                        matched_item = found_matches[0]
                    elif len(found_matches) > 1:
                        # Multiple matches found! Ask user to specify
                        user["pending_matches"] = found_matches
                        user["step"] = "select_from_matches"
                        match_text = f"🔍 '*{msg_body}*' se miltay jultay yeh options hain, batayein konsa chahiye:\n"
                        for idx, m in enumerate(found_matches, 1):
                            match_text += f"{idx}️⃣ {m.get('Name')} - Rs. {m.get('Price')}\n"
                        match_text += "\nNumber likh kar bhejein:"
                        send_whatsapp_message(sender_phone, match_text)
                        return jsonify({"status": "success"}), 200

                if matched_item:
                    item_name = matched_item.get("Name")
                    item_price = int(matched_item.get("Price", 0))

                    # Special trigger for Pizza customization
                    if "pizza" in item_name.lower():
                        user["temp_item"] = matched_item
                        user["step"] = "pizza_topping"
                        send_whatsapp_message(sender_phone, f"🍕 *{item_name}* select kiya hai! Kya aap extra toppings chahte hain?\n\n1️⃣ Extra Cheese (+Rs. 100)\n2️⃣ Extra Chicken (+Rs. 150)\n3️⃣ Dono (Cheese + Chicken) (+Rs. 250)\n4️⃣ Nahi, Normal hi theek hai\n\nNumber likh kar bhejein:")
                        return jsonify({"status": "success"}), 200

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
                    # Strict Error Handling when item is completely unknown
                    send_whatsapp_message(sender_phone, "Bhai samajh nahi aaya! Baraye meharbani menu se sahi item number likhein ya *'Done'* likhein.")

            # Step: Get Customer Name
            elif step == "get_name":
                user["name"] = msg_body.title()
                user["step"] = "get_address"
                send_whatsapp_message(sender_phone, f"Shukriya {user['name']}! 😊\nAb apna *Delivery Address* type kar ke bhej dein (ya location share kar dein).")

            # Step: Get Address & Instant Owner Alert
            elif step == "get_address":
                user["address"] = msg_body.title()
                cart_summary = ", ".join(user["cart"])
                
                # Customer Confirmation
                confirmation_msg = "🎉 *Order Confirmed!* 🎉\n\nAapka order successfully book ho gaya hai aur restaurant manager ko foran bhej diya gaya hai! Jald khana dispatch ho jaye ga."
                send_whatsapp_message(sender_phone, confirmation_msg)

                # Instant Manager/Owner Priority Alert
                owner_alert = (
                    f"🚨 *URGENT: Naya Order Restaurant Par Aaya Hai!* 🚨\n\n"
                    f"👤 *Customer Name:* {user['name']}\n"
                    f"📱 *Phone Number:* {sender_phone}\n"
                    f"🛒 *Ordered Items:* {cart_summary}\n"
                    f"💰 *Total Bill:* Rs. {user['total']}\n"
                    f"📍 *Delivery Address:* {user['address']}\n\n"
                    f"⚡ *Kitchen ko foran tayari ka hukm dein!*"
                )
                send_whatsapp_message(OWNER_PHONE, owner_alert)

                # Reset Session for new order
                user_sessions[sender_phone] = {"step": "menu", "cart": [], "total": 0, "name": "", "address": "", "temp_item": None, "pending_matches": []}

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
                

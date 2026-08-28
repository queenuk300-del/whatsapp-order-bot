import os
import requests
import gspread
from flask import Flask, request, jsonify

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secure_verify_token")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "923046763002")
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
    
    # Almaida Fried Comprehensive Menu Fallback
    return [
        {"Name": "Zinger Deal (4 Burgers + 4 Drinks)", "Price": 950, "Image": "https://images.unsplash.com/photo-1561758033-d89a9ad46330"},
        {"Name": "Rice Deal (Mandi/Broast Rice)", "Price": 250, "Image": "https://images.unsplash.com/photo-1516714435131-44d6b64dc6a2"},
        {"Name": "Panini Deal (Grilled/Mushroom)", "Price": 180, "Image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af"},
        {"Name": "Nawabi Burger", "Price": 350, "Image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd"},
        {"Name": "Zinger Burger", "Price": 380, "Image": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90"},
        {"Name": "Tower Burger", "Price": 480, "Image": "https://images.unsplash.com/photo-1550547660-d9450f859349"},
        {"Name": "Club Sandwich", "Price": 350, "Image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af"},
        {"Name": "Large Family Pizza", "Price": 1500, "Image": "https://images.unsplash.com/photo-1513104890138-7c749659a591"},
        {"Name": "French Fries (Masala/Large)", "Price": 200, "Image": "https://images.unsplash.com/photo-1576107232684-1279f3908591"},
        {"Name": "Chicken Garlic Mayo Roll", "Price": 250, "Image": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46"},
        {"Name": "Cold Drink (1.5 Litre)", "Price": 200, "Image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97"}
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

def send_whatsapp_image(recipient, image_url, caption):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
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
                    "cart_raw": [],
                    "total": 0,
                    "name": "",
                    "address": "",
                    "pending_matches": []
                }

            user = user_sessions[sender_phone]
            step = user["step"]
            menu_items = get_menu_from_sheet()

            # 1. Strict Name Step Handler
            if step == "get_name":
                user["name"] = msg_body.title()
                user["step"] = "get_address"
                send_whatsapp_message(sender_phone, f"Bohat shukriya {user['name']} ji! ❤️\nAb apna pyara sa *Delivery Address* type kar ke bhej dein (ya apni *Live Location* share kar dein).")
                return jsonify({"status": "success"}), 200

            # 2. Strict Address Step Handler
            if step == "get_address":
                user["address"] = msg_body.title()
                cart_summary = ", ".join(user["cart"])
                
                confirmation_msg = (
                    f"🎉 *Order Confirmed!* 🎉\n\n"
                    f"Aapka order successfully book ho gaya hai aur kitchen mein chef ko bhej diya gaya hai! 👨‍🍳\n"
                    f"⏱️ *Estimated Delivery Time:* 35 to 45 minutes.\n"
                    f"Garam garam khana jald aapke darwaze par hoga. Enjoy! 🍔✨"
                )
                send_whatsapp_message(sender_phone, confirmation_msg)
                user["step"] = "completed"

                owner_alert = (
                    f"🚨 *URGENT: Almaida Fried Par Naya Order Aaya Hai!* 🚨\n\n"
                    f"👤 *Customer Name:* {user['name']}\n"
                    f"📱 *Phone Number:* {sender_phone}\n"
                    f"🛒 *Ordered Items:* {cart_summary}\n"
                    f"💰 *Total Bill:* Rs. {user['total']}\n"
                    f"📍 *Delivery Address/Location:* {user['address']}\n\n"
                    f"⚡ *Kitchen ko foran tayari ka hukm dein!*"
                )
                send_whatsapp_message(OWNER_PHONE, owner_alert)
                return jsonify({"status": "success"}), 200

            # 3. Post-Order Completed Chat Handler
            if step == "completed":
                if any(w in msg_body for w in ["menu", "hi", "hello", "start", "order", "deal"]):
                    user_sessions[sender_phone] = {"step": "ordering", "cart": [], "cart_raw": [], "total": 0, "name": "", "address": "", "pending_matches": []}
                    step = "ordering"
                else:
                    send_whatsapp_message(sender_phone, "😊 Aapka bohat shukriya! Enjoy your meal! 🍔✨ Agar mazeed kuch order krna ho toh *'Menu'* likh kar bata sakte hain.")
                    return jsonify({"status": "success"}), 200

            # 4. Global Commands (Cart, Clear, Modify)
            if msg_body in ["clear", "reset", "cancel", "cancel order"]:
                user_sessions[sender_phone] = {"step": "ordering", "cart": [], "cart_raw": [], "total": 0, "name": "", "address": "", "pending_matches": []}
                send_whatsapp_message(sender_phone, "🗑️ Aapka cart clear kar diya gaya hai. Naya order shuru karne ke liye koi item name ya number likhein.")
                return jsonify({"status": "success"}), 200

            if msg_body == "cart":
                if not user["cart"]:
                    send_whatsapp_message(sender_phone, "🛒 Aapka cart abhi khali hai!")
                else:
                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                    send_whatsapp_message(sender_phone, f"🛒 *Aapka Current Cart:*\n{cart_summary}\n\n💰 *Total Bill:* Rs. {user['total']}\n\nItem remove karne ke liye *'Remove [item name]'* likhein, ya order mukammal karne ke liye *'Done'* likhein.")
                return jsonify({"status": "success"}), 200

            if "remove" in msg_body or "delete" in msg_body:
                item_to_remove = msg_body.replace("remove", "").replace("delete", "").strip()
                removed_any = False
                new_cart = []
                new_raw = []
                new_total = 0
                
                for item_str, price in user["cart_raw"]:
                    if item_to_remove in item_str.lower():
                        removed_any = True
                    else:
                        new_cart.append(item_str)
                        new_raw.append((item_str, price))
                        new_total += price
                
                if removed_any:
                    user["cart"] = new_cart
                    user["cart_raw"] = new_raw
                    user["total"] = new_total
                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]]) if user["cart"] else "Khali"
                    send_whatsapp_message(sender_phone, f"🗑️ Item remove ho gaya!\n\n🛒 *Updated Cart:*\n{cart_summary}\n\n💰 *Total Bill:* Rs. {user['total']}")
                else:
                    send_whatsapp_message(sender_phone, "⚠️ Aisa koi item aapke cart mein nahi mila. Sahi naam likh kar try karein.")
                return jsonify({"status": "success"}), 200

            # 5. Welcome & Menu Handler (Clean numbering for 10, 11 to avoid keycap split)
            if msg_body in ["menu", "hi", "hello", "start", "assalam o alaikum", "salam"]:
                user["step"] = "ordering"
                user["pending_matches"] = []
                menu_text = "🍔 *Welcome to Almaida Fried!* 🍟\n_Maza Kuch Khas Hai_ ✨\n\nYeh raha hamara lazeez menu:\n"
                for idx, item in enumerate(menu_items, 1):
                    name = item.get("Name", "Item")
                    price = item.get("Price", 0)
                    if idx <= 9:
                        # Keycap digits for 1-9
                        num_icon = f"{idx}\u20e3"
                    else:
                        num_icon = f"{idx}."
                    menu_text += f"{num_icon} *{name}* - Rs. {price}\n"
                
                menu_text += "\nAapko kya order karna hai? Item ka naam ya number likh kar bhejein! ❤️"
                send_whatsapp_image(sender_phone, "https://images.unsplash.com/photo-1504674900247-0877df9cc836", menu_text)
                return jsonify({"status": "success"}), 200

            # 6. Checkout / Done Trigger
            if msg_body in ["done", "checkout", "finish", "ok done"]:
                if not user["cart"]:
                    send_whatsapp_message(sender_phone, "Aapne abhi tak kuch select nahi kiya! Pehle menu se pyari si cheez chunein. 😊")
                    return jsonify({"status": "success"}), 200
                
                if step != "upsell_offered":
                    user["step"] = "upsell_offered"
                    send_whatsapp_message(sender_phone, "🍟 *Ek choti si recommendation:* Kya iske sath Mazedar Masala Fries ya thandi Cold Drink add karwana chahenge, ya itna kafi hai?\n\n(Mazeed item likhein, ya *'No'* / *'Final'* likhein)")
                    return jsonify({"status": "success"}), 200

            if step == "upsell_offered":
                if msg_body in ["no", "final", "nahi", "itna kafi", "nah", "nope"]:
                    user["step"] = "get_name"
                    send_whatsapp_message(sender_phone, "Zabardast! 🛒 Aapka lazeez bill tayar hai.\nAb apna *Pura Naam* pyare se andaz mein likh kar bhejein:")
                    return jsonify({"status": "success"}), 200

            # 7. Multi-match Selection Handler
            if step == "select_from_matches":
                matches = user["pending_matches"]
                if msg_body.isdigit() and 1 <= int(msg_body) <= len(matches):
                    selected = matches[int(msg_body) - 1]
                    user["pending_matches"] = []
                    item_name = selected.get("Name")
                    item_price = int(selected.get("Price", 0))
                    item_img = selected.get("Image", "")

                    user["cart"].append(item_name)
                    user["cart_raw"].append((item_name, item_price))
                    user["total"] += item_price
                    user["step"] = "ordering"

                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                    response_text = (
                        f"✅ *{item_name}* aapke cart mein shamil ho gaya! 🎉\n\n"
                        f"🛒 *Aapka Cart:*\n{cart_summary}\n\n"
                        f"💰 *Total Bill:* Rs. {user['total']}\n\n"
                        f"Kuch aur khane ka dil hai? Item ka naam likhein ya *'Done'* likhein."
                    )
                    if item_img:
                        send_whatsapp_image(sender_phone, item_img, response_text)
                    else:
                        send_whatsapp_message(sender_phone, response_text)
                    return jsonify({"status": "success"}), 200
                else:
                    send_whatsapp_message(sender_phone, "Baraye meharbani di gayi list mein se sahi number select karein:")
                    return jsonify({"status": "success"}), 200

            # 8. Robust Quantity & Item Matcher (Direct Number or Keyword)
            if step == "ordering" or step == "upsell_offered":
                # Parse quantity if provided (e.g., "2 zinger" or "3 8" etc.)
                qty = 1
                clean_query = msg_body
                query_words = msg_body.split()
                
                if len(query_words) >= 2 and query_words[0].isdigit() and query_words[1].isdigit():
                    # Handle case like "1 0" or similar, or quantity prefix
                    pass

                if query_words and query_words[0].isdigit():
                    potential_qty = int(query_words[0])
                    # If the first number is within menu range (1 to len(menu)), treat it as item selection number rather than qty unless specified
                    # But wait, to make it foolproof: if user writes "2", it could mean item #2 or quantity 2.
                    # Standard convention: if single digit number matches menu index 1..len(menu), treat as item number.
                    if 1 <= potential_qty <= len(menu_items) and len(query_words) == 1:
                        matched_item = menu_items[potential_qty - 1]
                        qty = 1
                    else:
                        qty = potential_qty
                        clean_query = " ".join(query_words[1:])
                else:
                    clean_query = msg_body

                matched_item = None
                
                # Check if clean_query is a direct number
                if clean_query.isdigit():
                    idx = int(clean_query)
                    if 1 <= idx <= len(menu_items):
                        matched_item = menu_items[idx - 1]
                
                # If not by number, search flexibly by keyword across menu items
                if not matched_item and clean_query:
                    found_matches = []
                    for item in menu_items:
                        name_lower = str(item.get("Name", "")).lower()
                        # Flexible matching: check if query words appear in item name
                        query_tokens = clean_query.split()
                        if all(token in name_lower for token in query_tokens):
                            found_matches.append(item)

                    if len(found_matches) == 1:
                        matched_item = found_matches[0]
                    elif len(found_matches) > 1:
                        user["pending_matches"] = found_matches
                        user["step"] = "select_from_matches"
                        match_text = f"🔍 '*{clean_query}*' se miltay jultay yeh lazeez options hain, batayein konsa pasand hai:\n"
                        for idx, m in enumerate(found_matches, 1):
                            match_text += f"{idx}️⃣ {m.get('Name')} - Rs. {m.get('Price')}\n"
                        match_text += "\nNumber select kar ke bhejein:"
                        send_whatsapp_message(sender_phone, match_text)
                        return jsonify({"status": "success"}), 200

                if matched_item:
                    item_name = matched_item.get("Name")
                    unit_price = int(matched_item.get("Price", 0))
                    item_price = unit_price * qty
                    display_name = f"{qty}x {item_name}" if qty > 1 else item_name
                    item_img = matched_item.get("Image", "")

                    user["cart"].append(display_name)
                    user["cart_raw"].append((display_name, item_price))
                    user["total"] += item_price
                    user["step"] = "ordering"

                    cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
                    response_text = (
                        f"😋 *{display_name}* add ho gaya!\n\n"
                        f"🛒 *Aapka Cart:*\n{cart_summary}\n\n"
                        f"💰 *Total Bill:* Rs. {user['total']}\n\n"
                        f"Mazeed kuch add karwana hai? (Item ka naam/number likhein, ya *'Done'* likhein)"
                    )
                    
                    if item_img:
                        send_whatsapp_image(sender_phone, item_img, response_text)
                    else:
                        send_whatsapp_message(sender_phone, response_text)
                else:
                    if msg_body in ["no", "ni", "nahi", "wrong order", "ok", "thanks"]:
                        send_whatsapp_message(sender_phone, "Theek hai ji! Agar order mukammal karna hai toh *'Done'* likhein, ya cart dekhne ke liye *'Cart'* likhein.")
                    else:
                        send_whatsapp_message(sender_phone, "Bhai jaan yeh item samajh nahi aaya! Baraye meharbani menu se sahi item name ya number (jaise 5, 8, 10) likhein.")

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
                        

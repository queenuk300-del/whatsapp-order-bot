import os
import re
import requests
import gspread
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# --- Configurations ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secure_verify_token")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "923046763002")
SHEET_NAME = os.environ.get("SHEET_NAME", "RestaurantMenu")

# OpenRouter API Setup
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

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
        {"Name": "Zinger Deal (4 Burgers + 4 Drinks)", "Price": 950, "Image": "https://images.unsplash.com/photo-1561758033-d89a9ad46330"},
        {"Name": "Couple Deal (2 Zinger + 2 Drinks)", "Price": 550, "Image": "https://images.unsplash.com/photo-1550547660-d9450f859349"},
        {"Name": "Family Pizza Deal (1 Large Pizza + 1.5L Drink)", "Price": 1600, "Image": "https://images.unsplash.com/photo-1513104890138-7c749659a591"},
        {"Name": "Zinger Burger", "Price": 380, "Image": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90"},
        {"Name": "Mighty Zinger Burger", "Price": 550, "Image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd"},
        {"Name": "Tower Burger", "Price": 480, "Image": "https://images.unsplash.com/photo-1550547660-d9450f859349"},
        {"Name": "Nawabi Burger", "Price": 350, "Image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd"},
        {"Name": "Patty Burger (Chicken/Beef)", "Price": 300, "Image": "https://images.unsplash.com/photo-1550547660-d9450f859349"},
        {"Name": "Small Pizza", "Price": 500, "Image": "https://images.unsplash.com/photo-1590947132387-155cc02f3212"},
        {"Name": "Medium Pizza", "Price": 900, "Image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38"},
        {"Name": "Large Family Pizza", "Price": 1500, "Image": "https://images.unsplash.com/photo-1513104890138-7c749659a591"},
        {"Name": "Crown Crust Pizza (Large)", "Price": 1800, "Image": "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3"},
        {"Name": "Chicken Broast (Quarter)", "Price": 450, "Image": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec"},
        {"Name": "Crispy Fried Chicken (2 Pcs)", "Price": 350, "Image": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec"},
        {"Name": "Hot Wings (10 Pcs)", "Price": 400, "Image": "https://images.unsplash.com/photo-1569691899455-88464f6d3ab1"},
        {"Name": "Chicken Nuggets (10 Pcs)", "Price": 350, "Image": "https://images.unsplash.com/photo-1562967914-608f82629710"},
        {"Name": "Chicken Shawarma", "Price": 150, "Image": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46"},
        {"Name": "Zinger Roll", "Price": 250, "Image": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46"},
        {"Name": "Chicken Garlic Mayo Roll", "Price": 250, "Image": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46"},
        {"Name": "Panini Deal (Grilled/Mushroom)", "Price": 180, "Image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af"},
        {"Name": "Club Sandwich", "Price": 350, "Image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af"},
        {"Name": "Rice Deal (Mandi/Broast Rice)", "Price": 250, "Image": "https://images.unsplash.com/photo-1516714435131-44d6b64dc6a2"},
        {"Name": "French Fries (Regular)", "Price": 150, "Image": "https://images.unsplash.com/photo-1576107232684-1279f3908591"},
        {"Name": "French Fries (Masala/Large)", "Price": 200, "Image": "https://images.unsplash.com/photo-1576107232684-1279f3908591"},
        {"Name": "Loaded Cheese & Mayo Fries", "Price": 350, "Image": "https://images.unsplash.com/photo-1576107232684-1279f3908591"},
        {"Name": "Oreo Shake", "Price": 250, "Image": "https://images.unsplash.com/photo-1572490122747-3968b75cc699"},
        {"Name": "Chocolate Shake", "Price": 250, "Image": "https://images.unsplash.com/photo-1572490122747-3968b75cc699"},
        {"Name": "Cold Drink (Regular/Can)", "Price": 100, "Image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97"},
        {"Name": "Cold Drink (1.5 Litre)", "Price": 200, "Image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97"}
    ]

def get_system_instruction():
    menu_items = get_menu_from_sheet()
    menu_text = ""
    for idx, item in enumerate(menu_items, 1):
        menu_text += f"• {item.get('Name')} - Rs. {item.get('Price')} (System Image Tag: [IMAGE: {item.get('Name')}])\n"

    return f"""Aap 'Almaida Fried' ke ek nihayat enthusiastic, friendly, aur smart AI order-taker hain. Hamesha Roman Urdu mein chat karein.

# Aapka Menu:
{menu_text}

# Aapke Rules:
1. **Mazy Wali Guftagu:** Khane ko bht mazedar andaz mein describe karein (jaise "garma garam crispy Zinger", "cheesy juicy pizza", "thandi thar cold drink") taa ke customer ke munh mein pani aa jaye. Emojis ka khul kar istemaal karein! 🍔🍕🍟
2. **Tasweerein Bhejna (VERY IMPORTANT):** Jab bhi aap kisi item ko suggest karein, ya customer menu mangy, toh apne message mein us item ka Image Tag lazmi lagayein. Example: Agar Zinger Burger ki baat ho rahi hai toh apne text ke andar `[IMAGE: Zinger Burger]` likhein. System khud is tag ko tasweer mein badal dega.
3. **Full Customer Control:** Agar customer bole "1 Zinger minus kar do", "Order change karna hai", ya "Mera poora order cancel kar do", toh foran politely confirm karein, cart update karein, aur naye hisaab (total) ki details dein.
4. **Smart Upselling:** Customer ki pasand dekh kar lightly upsell karein (Maslan: "Sir, crispy Zinger ke sath masaledar fries aur thandi drink lagwa dun?").
5. **Order Completion:** Jab customer bole "Bas itna hi" ya "Done", toh us se uska "Mukammal Naam" aur "Delivery Address" mangein.
6. **Strict Boundary (No Irrelevant Chat):** Aapka maqsad SIRF Almaida Fried ke orders lena hai. Agar koi customer siyasat, mazhab, fuzool baten, ya aisi cheez par baat kare jo restaurant se related nahi, toh sirf narmi se kahein: "Maaf kijiye, main Almaida Fried ka AI order-taker hoon. Main sirf menu aur orders ke hawalay se madad kar sakta hoon. Kya main aapko menu dikha dun?"
7. **Final Alert Format:** JAB customer apna Naam aur Address dono de de, toh aapko apna aakhri jawab STRICTLY is format mein dena hai:

||ORDER_DONE||
Name: [Customer Ka Naam]
Address: [Customer Ka Address]
Items: [Final Ordered Items ki List]
Total: [Final Amount in Rs]
Instructions: [Agar koi special instructions hon, warna N/A]
"""

def create_ai_session():
    return [{"role": "system", "content": get_system_instruction()}]

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

def send_whatsapp_image(recipient, image_url, caption=""):
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
            msg_body = msg_obj.get("text", {}).get("body", "").strip()
            msg_lower = msg_body.lower()

            if msg_lower == "reset system":
                user_sessions[sender_phone] = create_ai_session()
                send_whatsapp_message(sender_phone, "🔄 System has been manually reset.")
                return jsonify({"status": "success"}), 200

            if sender_phone not in user_sessions:
                user_sessions[sender_phone] = create_ai_session()

            if msg_lower in ["clear", "reset", "cancel", "cancel order"]:
                user_sessions[sender_phone] = create_ai_session()
                send_whatsapp_message(sender_phone, "🗑️ Aapka order cancel kar diya gaya hai. Naya order shuru karne ke liye 'Hi' ya 'Menu' likhein.")
                return jsonify({"status": "success"}), 200

            try:
                # Add user message to history
                user_sessions[sender_phone].append({"role": "user", "content": msg_body})

                # Call OpenRouter API with universal free router
                response = client.chat.completions.create(
                    model="openrouter/free",
                    messages=user_sessions[sender_phone]
                )
                
                ai_reply = response.choices[0].message.content
                
                # Save AI response to history
                user_sessions[sender_phone].append({"role": "assistant", "content": ai_reply})

                # Image Tag Interceptor
                image_tags = re.findall(r'\[IMAGE:\s*(.*?)\]', ai_reply, re.IGNORECASE)
                clean_text = re.sub(r'\[IMAGE:\s*.*?\]', '', ai_reply, flags=re.IGNORECASE).strip()

                images_to_send = []
                menu_items = get_menu_from_sheet()
                for tag in image_tags:
                    for item in menu_items:
                        if tag.lower().strip() in str(item.get("Name", "")).lower():
                            if item.get("Image"):
                                images_to_send.append(item["Image"])
                            break

                if "||ORDER_DONE||" in clean_text:
                    order_details = clean_text.replace("||ORDER_DONE||", "").strip()
                    owner_alert = f"🚨 *URGENT: Almaida Fried Par Naya AI Order Aaya Hai!* 🚨\n\n📱 *Customer Number:* {sender_phone}\n\n{order_details}\n\n⚡ *Kitchen ko foran tayari ka hukm dein!*"
                    send_whatsapp_message(OWNER_PHONE, owner_alert)
                    
                    customer_msg = "🎉 *Order Confirmed!* 🎉\n\nAapka order successfully book ho gaya hai aur kitchen mein chef ko bhej diya gaya hai! 👨‍🍳\n⏱️ *Estimated Delivery Time:* 35 to 45 minutes.\n\nGaram garam khana jald aapke darwaze par hoga. Shukriya! 🍔✨"
                    send_whatsapp_message(sender_phone, customer_msg)
                    user_sessions[sender_phone] = create_ai_session()
                else:
                    if images_to_send:
                        send_whatsapp_image(sender_phone, images_to_send[0], clean_text)
                        for img in images_to_send[1:]:
                            send_whatsapp_image(sender_phone, img, "")
                    else:
                        send_whatsapp_message(sender_phone, clean_text)

            except Exception as ai_error:
                print("AI System Error:", ai_error)
                send_whatsapp_message(sender_phone, "⚠️ Maaf kijiye, abhi system busy hai. Ek choti si line likh kar dobara bhej dein.")

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

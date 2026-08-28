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
        menu_text += f"- {item.get('Name')} : Rs. {item.get('Price')} [IMAGE: {item.get('Name')}]\n"

    return f"""Aap 'Almaida Fried' ke smart aur friendly order-taker hain. Roman Urdu mein baat karein.

# Menu & Images:
{menu_text}

# Strict Rules:
1. **Mukhtasir aur Pyari Guftagu:** Messages bohat chhotay, khubsurat aur friendly hon. Lambi baatein ya kahaniyan bilkul nahi karni.
2. **No Stars/Bold:** Text mein kahin bhi asterisks (*) ya stars ka istemaal hargiz na karein. Bilkul clean text likhein.
3. **No Talking About Pictures:** Kabhi yeh mat kahein ke "main tasweer lagwa raha hoon" ya "yeh lo tasweer". Aap ne sirf message ke andar item ka exact tag [IMAGE: Item Name] likhna hai, system khud tasweer bhej dega.
4. **Mazy Wali Lines:** Khane ka zikr karte waqt mukhtasir mazy wali line aur emojis dein taa ke bhook barhe (jaise: "Garma garam crispy zinger! 🍔").
5. **Full Control & Upselling:** Customer ki marzi par order change/cancel karein. Halki si upselling karein (jaise sath cold drink ya fries ka kehna).
6. **Order Completion:** Jab customer order finalize kar dey, toh us ka "Mukammal Naam" aur "Delivery Address" mangein.
7. **Strict Boundary:** Fuzool ya restaurant ke ilawa baaton ka jawab na dein.
8. **Final Format:** JAB customer Naam aur Address de de, toh sirf yeh format dein:

||ORDER_DONE||
Name: [Customer Name]
Address: [Customer Address]
Items: [Final Items]
Total: [Total Amount]
Instructions: [N/A or Notes]
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
                send_whatsapp_message(sender_phone, "🗑️ Aapka order cancel kar diya gaya hai. Naya order shuru karne ke liye 'Hi' likhein.")
                return jsonify({"status": "success"}), 200

            try:
                user_sessions[sender_phone].append({"role": "user", "content": msg_body})

                response = client.chat.completions.create(
                    model="openrouter/free",
                    messages=user_sessions[sender_phone]
                )
                
                ai_reply = response.choices[0].message.content
                user_sessions[sender_phone].append({"role": "assistant", "content": ai_reply})

                # Clean stars if AI accidentally puts them
                ai_reply = ai_reply.replace("*", "")

                # Corrected Regex handling
                image_tags = re.findall(r'\[IMAGE:\s*(.*?)\]', ai_reply, flags=re.IGNORECASE)
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
                    owner_alert = f"🚨 URGENT: Almaida Fried Par Naya AI Order Aaya Hai! 🚨\n\n📱 Customer Number: {sender_phone}\n\n{order_details}\n\n⚡ Kitchen ko foran tayari ka hukm dein!"
                    send_whatsapp_message(OWNER_PHONE, owner_alert)
                    
                    customer_msg = "🎉 Order Confirmed! 🎉\n\nAapka order successfully book ho gaya hai aur kitchen mein chef ko bhej diya gaya hai! 👨‍🍳\n⏱️ Estimated Delivery Time: 35 to 45 minutes.\n\nGaram garam khana jald aapke darwaze par hoga. Shukriya! 🍔✨"
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
                        

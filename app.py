import os
import requests
import gspread
import google.generativeai as genai
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Configurations ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secure_verify_token")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "923046763002")
SHEET_NAME = os.environ.get("SHEET_NAME", "RestaurantMenu")

# Gemini API Key Setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

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
        {"Name": "Zinger Deal (4 Burgers + 4 Drinks)", "Price": 950},
        {"Name": "Rice Deal (Mandi/Broast Rice)", "Price": 250},
        {"Name": "Panini Deal (Grilled/Mushroom)", "Price": 180},
        {"Name": "Nawabi Burger", "Price": 350},
        {"Name": "Zinger Burger", "Price": 380},
        {"Name": "Tower Burger", "Price": 480},
        {"Name": "Club Sandwich", "Price": 350},
        {"Name": "Large Family Pizza", "Price": 1500},
        {"Name": "French Fries (Masala/Large)", "Price": 200},
        {"Name": "Chicken Garlic Mayo Roll", "Price": 250},
        {"Name": "Cold Drink (1.5 Litre)", "Price": 200}
    ]

def create_ai_session():
    menu_items = get_menu_from_sheet()
    menu_text = ""
    for idx, item in enumerate(menu_items, 1):
        menu_text += f"{idx}. {item.get('Name')} - Rs. {item.get('Price')}\n"

    system_instruction = f"""Aap 'Almaida Fried' ke ek nihayat polite, friendly aur smart AI order-taker hain. Aapko hamesha Roman Urdu mein baat karni hai.

# Aapka Menu:
{menu_text}

# Aapke Rules:
1. Hamesha khush akhlaqi se pesh aana hai jese ek professional salesman karta hai.
2. Sirf isi menu mein se order lena hai.
3. Agar customer ajeeb spelling likhe (jaise "Piza", "peeza", "Pizaa hai?"), toh khud samajh jayen ke wo "Large Family Pizza" maang raha hai aur usi ke mutabiq jawab dein. Puchen "Jee bilkul Large Family Pizza 1500 Rs ka hai, kitne lagwa dun?".
4. Jese hi customer apna main order bataye, toh softly upsell karein (Maslan: "Zabardast choice! Sir kya iske sath mein thandi cold drink ya masala fries add kar dun?").
5. Jab customer bole ke "Bas itna hi" ya "Done", toh us se uska "Mukammal Naam" aur "Delivery Address" mangein.
6. JAB customer apna Naam aur Address dono de de, toh aapko apna aakhri jawab STRICTLY is format mein dena hai (taa ke system isay parh kar owner ko Whatsapp alert bhej sakay). Is format ke ilawa us message mein koi aam baat nahi karni:

||ORDER_DONE||
Name: [Customer Ka Naam]
Address: [Customer Ka Address]
Items: [Item 1, Item 2...]
Total: [Total Amount in Rs]
Instructions: [Agar koi special instructions hon, warna N/A]
"""
    
    # Updated to latest working model
    model = genai.GenerativeModel(
        model_name="gemini-3.6-flash",
        system_instruction=system_instruction
    )
    return model.start_chat(history=[])
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
            msg_body = msg_obj.get("text", {}).get("body", "").strip()
            msg_lower = msg_body.lower()

            if sender_phone not in user_sessions:
                user_sessions[sender_phone] = create_ai_session()
            
            chat = user_sessions[sender_phone]

            if msg_lower in ["clear", "reset", "cancel", "cancel order"]:
                user_sessions[sender_phone] = create_ai_session()
                send_whatsapp_message(sender_phone, "🗑️ Aapka order cancel kar diya gaya hai. Naya order shuru karne ke liye 'Hi' ya 'Menu' likhein.")
                return jsonify({"status": "success"}), 200

            try:
                # Send user message to AI
                response = chat.send_message(msg_body)
                ai_reply = response.text

                # Check if AI triggered the final order alert
                if "||ORDER_DONE||" in ai_reply:
                    order_details = ai_reply.replace("||ORDER_DONE||", "").strip()
                    
                    # Alert Owner
                    owner_alert = f"🚨 *URGENT: Almaida Fried Par Naya AI Order Aaya Hai!* 🚨\n\n📱 *Customer Number:* {sender_phone}\n\n{order_details}\n\n⚡ *Kitchen ko foran tayari ka hukm dein!*"
                    send_whatsapp_message(OWNER_PHONE, owner_alert)
                    
                    # Alert Customer
                    customer_msg = "🎉 *Order Confirmed!* 🎉\n\nAapka order successfully book ho gaya hai aur kitchen mein chef ko bhej diya gaya hai! 👨‍🍳\n⏱️ *Estimated Delivery Time:* 35 to 45 minutes.\n\nGaram garam khana jald aapke darwaze par hoga. Shukriya! 🍔✨"
                    send_whatsapp_message(sender_phone, customer_msg)
                    
                    # Reset chat for future orders
                    user_sessions[sender_phone] = create_ai_session()
                else:
                    # Send normal AI conversation response
                    send_whatsapp_message(sender_phone, ai_reply)

            except Exception as ai_error:
                print("AI System Error:", ai_error)
                send_whatsapp_message(sender_phone, "⚠️ Maaf kijiye, abhi system busy hai. Ek choti si line likh kar dobara bhej dein.")

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    

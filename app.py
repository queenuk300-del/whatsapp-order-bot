import os
import re
import requests
import gspread
import threading
import time
import random
import string
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# --- Configurations ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secure_verify_token")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "923046763002")
SHEET_NAME = os.environ.get("SHEET_NAME", "SHEET1")

# OpenRouter API Setup
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

user_sessions = {}
processed_message_ids = []

# --- Google Sheets Functions (Data Saving) ---
def get_sheet(tab_name):
    try:
        gc = gspread.service_account(filename='/etc/secrets/credentials.json')
        sh = gc.open(SHEET_NAME)
        return sh.worksheet(tab_name)
    except Exception as e:
        print(f"Sheet Error ({tab_name}):", e)
        return None

def get_menu_from_sheet():
    try:
        worksheet = get_sheet("Sheet1")
        if worksheet:
            records = worksheet.get_all_records()
            if records:
                return records
    except Exception:
        pass
    
    return [
        {"Name": "Zinger Deal (4 Burgers + 4 Drinks)", "Price": 950, "Image": "https://images.unsplash.com/photo-1561758033-d89a9ad46330"},
        {"Name": "Couple Deal (2 Zinger + 2 Drinks)", "Price": 550, "Image": "https://images.unsplash.com/photo-1550547660-d9450f859349"},
        {"Name": "Family Pizza Deal (1 Large Pizza + 1.5L Drink)", "Price": 1600, "Image": "https://images.unsplash.com/photo-1513104890138-7c749659a591"},
        {"Name": "Zinger Burger", "Price": 380, "Image": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90"},
        {"Name": "Mighty Zinger Burger", "Price": 550, "Image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd"},
        {"Name": "Small Pizza", "Price": 500, "Image": "https://images.unsplash.com/photo-1590947132387-155cc02f3212"},
        {"Name": "Large Family Pizza", "Price": 1500, "Image": "https://images.unsplash.com/photo-1513104890138-7c749659a591"},
        {"Name": "Cold Drink (Regular/Can)", "Price": 100, "Image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97"}
    ]

def get_customer_profile(phone):
    worksheet = get_sheet("Customers")
    if worksheet:
        records = worksheet.get_all_records()
        for row in records:
            if str(row.get("Phone")) == str(phone):
                return {"name": row.get("Name"), "address": row.get("Address")}
    return None

def save_customer_profile(phone, name, address):
    worksheet = get_sheet("Customers")
    if worksheet:
        records = worksheet.get_all_records()
        row_idx = None
        for i, row in enumerate(records, start=2):
            if str(row.get("Phone")) == str(phone):
                row_idx = i
                break
        if row_idx:
            worksheet.update_acell(f'B{row_idx}', name)
            worksheet.update_acell(f'C{row_idx}', address)
        else:
            worksheet.append_row([str(phone), name, address])

def save_order_to_sheet(order_id, phone, details, status="active"):
    worksheet = get_sheet("Orders")
    if worksheet:
        current_time = int(time.time())
        worksheet.append_row([order_id, str(phone), current_time, details, status])

def get_recent_order(phone):
    worksheet = get_sheet("Orders")
    if worksheet:
        records = worksheet.get_all_records()
        recent_order = None
        row_idx = None
        for i, row in enumerate(records, start=2):
            if str(row.get("Phone")) == str(phone) and row.get("Status") == "active":
                recent_order = row
                row_idx = i
        
        if recent_order:
            elapsed_time = int(time.time()) - int(recent_order.get("Time", 0))
            if elapsed_time <= 300: # 5 mins
                return {"order_id": recent_order.get("OrderID"), "details": recent_order.get("Details"), "row": row_idx}
    return None

def update_order_status(row_idx, new_status, new_details=None):
    worksheet = get_sheet("Orders")
    if worksheet and row_idx:
        worksheet.update_acell(f'E{row_idx}', new_status)
        if new_details:
             worksheet.update_acell(f'D{row_idx}', new_details)

# --- AI Instructions ---
def get_system_instruction(sender_phone):
    menu_items = get_menu_from_sheet()
    menu_text = ""
    for idx, item in enumerate(menu_items, 1):
        menu_text += f"- {item.get('Name')} : Rs. {item.get('Price')} [IMAGE: {item.get('Name')}]\n"

    memory_context = ""
    cust_profile = get_customer_profile(sender_phone)
    if cust_profile:
        name = cust_profile['name']
        addr = cust_profile['address']
        memory_context += f"\n# CUSTOMER PROFILE:\nName: {name}\nAddress: {addr}\n(Instructions: Customer ko us ke naam se welcome karein aur poochein kya order isi purane address pe bhejna hai.)\n"
    
    recent_order = get_recent_order(sender_phone)
    if recent_order:
        memory_context += f"\n# RECENT ACTIVE ORDER (Within 5 mins):\nOrder ID: {recent_order['order_id']}\nDetails: {recent_order['details']}\n(Instructions: Agar customer is order mein change ya cancel chahe, toh aap handle kar sakte hain.)\n"

    return f"""Aap 'Almaida Fried' ke professional AI Virtual Order Taker hain. Sirf Pakistani Roman Urdu mein mukhtasir baat karte hain.

# Aapka Menu:
{menu_text}
{memory_context}

# STRICT RULES (Lazmi follow karein):
1. **Identity & Language:** Main Almaida Fried ka AI Virtual Order Taker hoon. Hindi alfaz (jaise 'havaal', 'swagat', 'jaani') HARGIZ istemaal na karein. Sirf "Assalam o Alaikum", "Sir/Ma'am" kahein.
2. **Pehla Jawab (Greeting + Menu):** Jab customer pehli baar 'Hi' ya 'Salam' bheje, toh foran ek chhota salam kar ke MUKAMMAL MENU bhej dein.
3. **Short & Professional:** Messages 1-2 lines ke hon. No kahani.
4. **Out-of-Menu & Smart Suggestions:** Agar customer aisi cheez mange jo menu mein NAHI hai, toh politely maazrat karein. AGAR us se milti julti koi cheez menu mein hai, toh foran option dein. Fuzool baaton ka jawab na dein.
5. **No Stars/Bold:** Text mein kahin bhi asterisks (*) HARGIZ na lagayein.
6. **Silent Images:** Tasweer bhejte waqt sirf `[IMAGE: Item Name]` lagayein, text mein tasweer bhejne ka zikr na karein.
7. **FINAL ORDER FORMATS (CRITICAL):**
   Sirf in 3 formats ka use karein. Izafi baatein (Shukriya) in formats mein shamil na karein.

   - NAYA ORDER: (Jab Name/Address dono mil jayen)
     ||ORDER_DONE||
     Name: [Asal Naam]
     Address: [Asal Address]
     Items: [Ordered Items]
     Total: [Total Amount]

   - CANCEL ORDER: (Jab customer 5 min wala order cancel kare)
     ||ORDER_CANCEL||
     OrderID: [Recent Order ID]

   - MODIFY ORDER: (Jab customer 5 min wale order mein tabdeeli kare)
     ||ORDER_MODIFY||
     OrderID: [Recent Order ID]
     Name: [Name]
     Address: [Address]
     Items: [New Modified Items]
     Total: [New Total Amount]
"""

def create_ai_session(sender_phone):
    return [{"role": "system", "content": get_system_instruction(sender_phone)}]

# --- WhatsApp API Functions ---
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

# --- Main Processing Logic ---
def process_ai_response(sender_phone, msg_body):
    try:
        if sender_phone not in user_sessions:
            user_sessions[sender_phone] = create_ai_session(sender_phone)
            
        user_sessions[sender_phone].append({"role": "user", "content": msg_body})

        response = client.chat.completions.create(
            model="openrouter/free",
            messages=user_sessions[sender_phone]
        )
        
        ai_reply = response.choices[0].message.content
        ai_reply = re.sub(r'User Safety:.*?\n|Response Safety:.*?\n?', '', ai_reply, flags=re.IGNORECASE)
        ai_reply = ai_reply.replace("*", "").strip()

        if not ai_reply:
            ai_reply = "Maaf kijiye, main aapki baat samajh nahi paya. Kya main aapko humara menu dikhaun?"

        user_sessions[sender_phone].append({"role": "assistant", "content": ai_reply})

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
            order_details = clean_text.split("||ORDER_DONE||")[1].strip()
            
            name_match = re.search(r"Name:\s*(.*)", order_details)
            addr_match = re.search(r"Address:\s*(.*)", order_details)
            if name_match and addr_match:
                save_customer_profile(sender_phone, name_match.group(1).strip(), addr_match.group(1).strip())

            order_id = "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            save_order_to_sheet(order_id, sender_phone, order_details)
            
            owner_alert = f"🚨 URGENT: Almaida Fried Par Naya AI Order Aaya Hai! 🚨\n\n📱 Customer Number: {sender_phone}\n🧾 Order ID: {order_id}\n\n{order_details}\n\n⚡ Kitchen ko foran tayari ka hukm dein!"
            send_whatsapp_message(OWNER_PHONE, owner_alert)
            
            customer_msg = f"🎉 Order Confirmed! 🎉\n\nAapka order successfully book ho gaya hai aur kitchen mein chef ko bhej diya gaya hai! 👨‍🍳\n🧾 Order ID: {order_id}\n⏱️ Estimated Delivery Time: 35 to 45 minutes.\n\n(Aap aglay 5 minute tak is order mein tabdeeli ya cancellation karwa sakte hain). Shukriya! 🍔✨"
            send_whatsapp_message(sender_phone, customer_msg)
            user_sessions[sender_phone] = create_ai_session(sender_phone)

        elif "||ORDER_CANCEL||" in clean_text:
            order_id_match = re.search(r"OrderID:\s*([A-Za-z0-9\-]+)", clean_text)
            o_id = order_id_match.group(1).strip() if order_id_match else "N/A"
            
            recent_order = get_recent_order(sender_phone)
            if recent_order:
                 update_order_status(recent_order['row'], 'cancelled')

            owner_alert = f"⚠️ ORDER CANCELLED! ⚠️\n\n📱 Customer: {sender_phone}\n🧾 Order ID: {o_id}\n\nCustomer ne order cancel kar diya hai. Kitchen ko rok dein!"
            send_whatsapp_message(OWNER_PHONE, owner_alert)
            
            cust_msg = f"✅ Aapka order (ID: {o_id}) successfully cancel kar diya gaya hai. Jab bhi bhook lagay, Almaida Fried yahan mojood hai!"
            send_whatsapp_message(sender_phone, cust_msg)
            user_sessions[sender_phone] = create_ai_session(sender_phone)

        elif "||ORDER_MODIFY||" in clean_text:
            parts = clean_text.split("||ORDER_MODIFY||")[1].strip()
            order_id_match = re.search(r"OrderID:\s*([A-Za-z0-9\-]+)", parts)
            o_id = order_id_match.group(1).strip() if order_id_match else "N/A"
            
            recent_order = get_recent_order(sender_phone)
            if recent_order:
                 update_order_status(recent_order['row'], 'active', parts)

            owner_alert = f"🔄 ORDER MODIFIED! 🔄\n\n📱 Customer: {sender_phone}\n🧾 Order ID: {o_id}\n\n[NAYI DETAILS]:\n{parts}\n\nPuranay order ki jagah ab yeh naya order tayar karein!"
            send_whatsapp_message(OWNER_PHONE, owner_alert)
            
            cust_msg = f"✅ Aapka order (ID: {o_id}) successfully update kar diya gaya hai! Naya bill aur items note kar liye gaye hain. Shukriya! 🍔✨"
            send_whatsapp_message(sender_phone, cust_msg)
            user_sessions[sender_phone] = create_ai_session(sender_phone)

        else:
            if images_to_send:
                send_whatsapp_image(sender_phone, images_to_send[0], clean_text)
                for img in images_to_send[1:]:
                    send_whatsapp_image(sender_phone, img, "")
            else:
                send_whatsapp_message(sender_phone, clean_text)

    except Exception as ai_error:
        print("AI System Error:", ai_error)
        send_whatsapp_message(sender_phone, "Maaf kijiye ga, system mein thora masla hai. Kya aap apna message dobara bhej sakte hain?")

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
            msg_id = msg_obj.get("id")
            msg_body = msg_obj.get("text", {}).get("body", "").strip()
            msg_lower = msg_body.lower()

            if msg_id in processed_message_ids:
                return jsonify({"status": "success"}), 200
            
            processed_message_ids.append(msg_id)
            if len(processed_message_ids) > 100:
                processed_message_ids.pop(0)

            if msg_lower == "reset system":
                user_sessions[sender_phone] = create_ai_session(sender_phone)
                send_whatsapp_message(sender_phone, "System has been manually reset.")
                return jsonify({"status": "success"}), 200

            if msg_lower in ["clear", "reset", "cancel", "cancel order"]:
                user_sessions[sender_phone] = create_ai_session(sender_phone)
                send_whatsapp_message(sender_phone, "Aapka system refresh kar diya gaya hai. Naya order shuru karne ke liye 'Hi' likhein.")
                return jsonify({"status": "success"}), 200

            thread = threading.Thread(target=process_ai_response, args=(sender_phone, msg_body))
            thread.start()

            return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
                        

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

# --- Google Sheets Functions ---
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
    except Exception as e:
        print("Menu Error:", e)
    
    return [
        {"Name": "Zinger Deal (4 Burgers + 4 Drinks)", "Price": 950, "Image": "https://images.unsplash.com/photo-1561758033-d89a9ad46330"},
        {"Name": "Couple Deal (2 Zinger + 2 Drinks)", "Price": 550, "Image": "https://images.unsplash.com/photo-1550547660-d9450f859349"},
        {"Name": "Family Pizza Deal (1 Large Pizza + 1.5L Drink)", "Price": 1600, "Image": "https://images.unsplash.com/photo-1513104890138-7c749659a591"},
        {"Name": "Zinger Burger", "Price": 380, "Image": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90"},
        {"Name": "Cold Drink (Regular/Can)", "Price": 100, "Image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97"}
    ]

def get_customer_profile(phone):
    try:
        worksheet = get_sheet("Customers")
        if worksheet:
            records = worksheet.get_all_records()
            for row in records:
                if str(row.get("Phone")) == str(phone):
                    return {"name": row.get("Name"), "address": row.get("Address")}
    except Exception:
        pass
    return None

def save_customer_profile(phone, name, address):
    try:
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
    except Exception:
        pass

def save_order_to_sheet(order_id, phone, details, status="active"):
    try:
        worksheet = get_sheet("Orders")
        if worksheet:
            current_time = int(time.time())
            worksheet.append_row([order_id, str(phone), current_time, details, status])
    except Exception:
        pass

def get_recent_order(phone):
    try:
        worksheet = get_sheet("Orders")
        if worksheet:
            records = worksheet.get_all_records()
            recent_order = None
            row_idx = None
            for i, row in enumerate(records, start=2):
                if str(row.get("Phone")) == str(phone) and str(row.get("Status")).lower() == "active":
                    recent_order = row
                    row_idx = i
            
            if recent_order:
                elapsed_time = int(time.time()) - int(recent_order.get("Time", 0))
                if elapsed_time <= 1800: # 30 mins lock
                    return {"order_id": recent_order.get("OrderID"), "details": recent_order.get("Details"), "row": row_idx}
    except Exception:
        pass
    return None

def update_order_status(row_idx, new_status, new_details=None):
    try:
        worksheet = get_sheet("Orders")
        if worksheet and row_idx:
            worksheet.update_acell(f'E{row_idx}', new_status)
            if new_details:
                 worksheet.update_acell(f'D{row_idx}', new_details)
    except Exception:
        pass

# --- VISUAL & SMART AI Instructions ---
def get_system_instruction(sender_phone):
    menu_items = get_menu_from_sheet()
    menu_text = ""
    for idx, item in enumerate(menu_items, 1):
        menu_text += f"- {item.get('Name')} : Rs. {item.get('Price')}\n"

    cust_profile = get_customer_profile(sender_phone)
    profile_text = f"Known Customer: {cust_profile['name']} ({cust_profile['address']})" if cust_profile else "New Customer"
    
    recent_order = get_recent_order(sender_phone)
    if recent_order:
        state_rules = f"""
# ⚠️ CURRENT STATE: ACTIVE ORDER (LOCKED) ⚠️
Customer ka order pehle se ACTIVE hai (Order ID: {recent_order['order_id']}).
Current Items: {recent_order['details']}

# SMART RULES FOR THIS STATE:
1. Naya order HARGIZ nahi lagana. '||ORDER_DONE||' SAKHT MANA HAI.
2. Agar customer kahe "confirm kardo", "ok", ya "jaldi bhejo", toh kaho: "Sir/Ma'am, aapka order already confirm hai aur tayar ho raha hai."
3. Agar customer koi NAYI CHEEZ add karwaye, TOH BINA POOCHE FORAN yeh bhejo:
||ORDER_MODIFY||
OrderID: {recent_order['order_id']}
Items: [Purani aur Nayi dono list]
Total: [New Total]
"""
    else:
        state_rules = """
# ⚠️ CURRENT STATE: NO ACTIVE ORDER ⚠️
# SMART ORDER TAKING PROCESS (FOLLOW STRICTLY):

STEP 1 (Get Items): Customer se order note karo.
STEP 2 (Visual Upsell - VERY IMPORTANT): Agar customer ke order mein 'Cold Drink' ya 'Fries' shamil NAHI hain, toh order final karne se pehle muh mein pani lanay walay andaz mein recommend karo aur SATH HI uski tasweer ka tag lazmi lagao! 
(Misaal: "Sir, garma garam khane ke sath ek chilled thandi Cold Drink add kar dun? [IMAGE: Cold Drink (Regular/Can)]")
STEP 3 (Name & Address - STRICT LOCK): Agar customer apni items final kar le, toh us se Asal Naam aur Delivery Address poocho. (Known customer ho toh address confirm karwa lo).
STEP 4 (Strict Validation): 
- JAB TAK customer ka Asal Naam aur Mukammal Address na mil jaye, aap '||ORDER_DONE||' HARGIZ generate nahi karenge! Chahe wo 'Done' ya 'Confirm' kyun na kahe. Us surat mein kaho: "Sir, order dispatch karne ke liye baraye meharbani apna mukammal naam aur delivery address bata dein."
- Jab Items + Name + Address teeno cheezein mukammal ho jayen, TOH BINA DOBAARA POOCHE FORAN yeh format bhejo:
||ORDER_DONE||
Name: [Asal Naam]
Address: [Asal Address]
Items: [Ordered Items]
Total: [Total Amount]
"""

    return f"""Aap 'Almaida Fried' ke smart, tez, aur sales-driven AI Virtual Order Taker hain. Sirf Pakistani Roman Urdu mein mukhtasir baat karte hain.

# Aapka Menu:
{menu_text}

# Customer Info:
{profile_text}

{state_rules}

# ZERO TOLERANCE RULES (BE SMART, NOT ROBOTIC):
1. Fake ya robotic alfaz (jaise "Arz karta hoon", "Maafi chahta hoon", "Swagat hai") HARGIZ use na karein. Aap ek professional order taker hain.
2. Slang words (Bhai, Jaani, Yaar) use nahi karne. Sirf "Sir" ya "Ma'am".
3. Messages 1-2 lines se lambe na hon.
4. Kisi bhi lafz ke sath asterisks (*) hargiz na lagayen.
5. **PICTURE MARKETING:** Jab bhi aap kisi item (Pizza, Burger, Shakes, Drink) ke baare mein baat karein ya recommend karein, toh uski tasweer bhejne ke liye text mein `[IMAGE: Exact Item Name]` LAZMI likhein taa ke customer ka mood banay!
"""

def create_ai_session(sender_phone):
    return [{"role": "system", "content": get_system_instruction(sender_phone)}]

# --- WhatsApp APIs ---
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

def send_whatsapp_message(recipient, text):
    if not text:
        return
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
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print("WhatsApp Send Exception:", e)

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

# --- Automated Promotion / Broadcast Route ---
@app.route("/send-promo", methods=["GET"])
def send_promotion_broadcast():
    try:
        worksheet = get_sheet("Customers")
        if not worksheet:
            return jsonify({"status": "error", "message": "Customers sheet not found"}), 400
            
        records = worksheet.get_all_records()
        if not records:
            return jsonify({"status": "message", "message": "No customers found for promotion"}), 200

        promo_caption = (
            "🔥 WEEKEND SPECIAL MEGA DEAL! 🔥\n\n"
            "Kya bhook ne kar diya hai bura haal? To intezaar kis baat ka hai!\n"
            "Order karein hamara Special Family Pizza Deal (1 Large Pizza + 1.5L Cold Drink) "
            "sirf Rs. 1600 mein! 🍕🥤\n\n"
            "Garam garam, cheese se bhara hua khana abhi apke darwaze par. "
            "Naya order dene ke liye 'Hi' likhein!"
        )
        promo_image = "https://images.unsplash.com/photo-1513104890138-7c749659a591"

        sent_count = 0
        for row in records:
            phone = row.get("Phone")
            if phone:
                send_whatsapp_image(str(phone), promo_image, promo_caption)
                sent_count += 1
                time.sleep(1)

        return jsonify({"status": "success", "message": f"Promotion successfully sent to {sent_count} customers!"}), 200

    except Exception as e:
        print("Broadcast Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Main Logic ---
def process_ai_response(sender_phone, msg_body):
    try:
        if sender_phone not in user_sessions:
            user_sessions[sender_phone] = create_ai_session(sender_phone)
        else:
            user_sessions[sender_phone][0]['content'] = get_system_instruction(sender_phone)
            
        user_sessions[sender_phone].append({"role": "user", "content": msg_body})

        response = client.chat.completions.create(
            model="openrouter/free",
            messages=user_sessions[sender_phone],
            max_tokens=400
        )
        
        ai_reply = response.choices[0].message.content
        ai_reply = re.sub(r'User Safety:.*?\n|Response Safety:.*?\n?', '', ai_reply, flags=re.IGNORECASE)
        ai_reply = ai_reply.replace("*", "").strip()

        if not ai_reply:
            ai_reply = "Ji Sir, batayein main mazeed kya madad kar sakta hoon?"

        user_sessions[sender_phone].append({"role": "assistant", "content": ai_reply})
        clean_text = ai_reply.strip()

        # --- IMAGE EXTRACTION FIX LOGIC ---
        images_to_send = []
        image_tags = re.findall(r'\[IMAGE:\s*(.*?)\]', clean_text)
        
        if image_tags:
            menu_items = get_menu_from_sheet()
            for tag in image_tags:
                for item in menu_items:
                    if item.get('Name', '').strip().lower() == tag.strip().lower():
                        images_to_send.append(item.get('Image'))
                        break
            
            # Remove the tags from the text so it looks clean to the customer
            clean_text = re.sub(r'\[IMAGE:\s*.*?\]', '', clean_text).strip()
        # ----------------------------------

        if "||ORDER_DONE||" in clean_text:
            if get_recent_order(sender_phone):
                send_whatsapp_message(sender_phone, "Sir, aapka active order pehle hi kitchen mein tayar ho raha hai.")
                return

            order_details = clean_text.split("||ORDER_DONE||")[1].strip()
            name_match = re.search(r"Name:\s*(.*)", order_details)
            addr_match = re.search(r"Address:\s*(.*)", order_details)
            
            if name_match and addr_match:
                save_customer_profile(sender_phone, name_match.group(1).strip(), addr_match.group(1).strip())

            order_id = "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            save_order_to_sheet(order_id, sender_phone, order_details)
            
            owner_alert = f"🚨 URGENT: Almaida Fried Par Naya AI Order Aaya Hai! 🚨\n\n📱 Customer: {sender_phone}\n🧾 Order ID: {order_id}\n\n{order_details}"
            send_whatsapp_message(OWNER_PHONE, owner_alert)
            
            customer_msg = f"🎉 Order Confirmed! 🎉\n🧾 Order ID: {order_id}\n⏱️ Estimated Delivery: 35-45 mins.\n(Aap 30 minute tak order mein mazeed items add ya cancel karwa sakte hain)."
            send_whatsapp_message(sender_phone, customer_msg)
            user_sessions[sender_phone] = create_ai_session(sender_phone)

        elif "||ORDER_MODIFY||" in clean_text:
            recent_order = get_recent_order(sender_phone)
            if recent_order:
                parts = clean_text.split("||ORDER_MODIFY||")[1].strip()
                o_id = recent_order['order_id']
                update_order_status(recent_order['row'], 'active', parts)

                owner_alert = f"🔄 ORDER UPDATE! 🔄\n\n📱 Customer: {sender_phone}\n🧾 Order ID: {o_id}\n\n[NAYI DETAILS / ADDED ITEMS]:\n{parts}"
                send_whatsapp_message(OWNER_PHONE, owner_alert)
                
                cust_msg = f"✅ Aapka order (ID: {o_id}) successfully update kar diya gaya hai! Shukriya."
                send_whatsapp_message(sender_phone, cust_msg)
            else:
                send_whatsapp_message(sender_phone, "Sir, aapka pichla order close ho chuka hai. Naya order likhwaiye.")

        elif "||ORDER_CANCEL||" in clean_text:
            recent_order = get_recent_order(sender_phone)
            if recent_order:
                 update_order_status(recent_order['row'], 'cancelled')
                 o_id = recent_order['order_id']
                 
                 owner_alert = f"⚠️ ORDER CANCELLED! ⚠️\n\n📱 Customer: {sender_phone}\n🧾 Order ID: {o_id}\n\nCustomer ne order cancel kar diya hai. Kitchen ko rok dein!"
                 send_whatsapp_message(OWNER_PHONE, owner_alert)
                 
                 cust_msg = f"✅ Aapka order (ID: {o_id}) cancel kar diya gaya hai. Jab bhi bhook lagay, hum yahan mojood hain!"
                 send_whatsapp_message(sender_phone, cust_msg)
            else:
                 send_whatsapp_message(sender_phone, "Is waqt aapka koi active order nahi hai jise cancel kiya ja sakay.")

        else:
            if images_to_send:
                send_whatsapp_image(sender_phone, images_to_send[0], clean_text)
                for img in images_to_send[1:]:
                    send_whatsapp_image(sender_phone, img, "")
            else:
                send_whatsapp_message(sender_phone, clean_text)

    except Exception as ai_error:
        print("AI System Error:", ai_error)
        send_whatsapp_message(sender_phone, "Ji Sir, process ho raha hai. Thora intezaar kijiye.")

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
                send_whatsapp_message(sender_phone, "System reset ho gaya hai.")
                return jsonify({"status": "success"}), 200

            if msg_lower in ["clear", "reset", "cancel", "cancel order"]:
                user_sessions[sender_phone] = create_ai_session(sender_phone)
                send_whatsapp_message(sender_phone, "System refresh ho gaya hai. Naya order ke liye 'Hi' likhein.")
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
                

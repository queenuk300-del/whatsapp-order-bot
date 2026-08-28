Import os
Import requests
Import gspread
From difflib import get_close_matches
From flask import Flask, request, jsonify
App = Flask(name)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secure_verify_token")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "923046763002")
SHEET_NAME = os.environ.get("SHEET_NAME", "RestaurantMenu")
user_sessions = {}
Def get_menu_from_sheet():
Try:
Gc = gspread.service_account(filename='/etc/secrets/credentials.json')
Sh = gc.open(SHEET_NAME)
Worksheet = sh.get_worksheet(0)
Records = worksheet.get_all_records()
If records:
Return records
Except Exception as e:
Print("Google Sheet Error:", e)
Return [
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
Def verify_webhook():
Mode = request.args.get("hub.mode")
Token = request.args.get("hub.verify_token")
Challenge = request.args.get("hub.challenge")
If mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
Return challenge, 200
Return "Verification failed", 403
Def send_whatsapp_message(recipient, text):
Url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
Headers = {
"Authorization": f"Bearer {WHATSAPP_TOKEN}",
"Content-Type": "application/json",
}
Payload = {
"messaging_product": "whatsapp",
"to": recipient,
"type": "text",
"text": {"body": text}
}
Requests.post(url, headers=headers, json=payload)
Def send_whatsapp_image(recipient, image_url, caption):
Url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
Headers = {
"Authorization": f"Bearer {WHATSAPP_TOKEN}",
"Content-Type": "application/json",
}
Payload = {
"messaging_product": "whatsapp",
"to": recipient,
"type": "image",
"image": {
"link": image_url,
"caption": caption
}
}
Requests.post(url, headers=headers, json=payload)
@app.route("/webhook", methods=["POST"])
Def webhook():
Data = request.get_json()
Try:
If (
Data
And data.get("object") == "whatsapp_business_account"
And data.get("entry")
And data["entry"][0].get("changes")
And data["entry"][0]["changes"][0].get("value")
And data["entry"][0]["changes"][0]["value"].get("messages")
):
Msg_obj = data["entry"][0]["changes"][0]["value"]["messages"][0]
Sender_phone = msg_obj["from"]
Msg_body = msg_obj.get("text", {}).get("body", "").strip().lower()
If sender_phone not in user_sessions:
User_sessions[sender_phone] = {
"step": "menu",
"cart": [],
"cart_raw": [],
"total": 0,
"name": "",
"address": "",
"instructions": "",
"pending_matches": [],
"pending_fuzzy_item": None
}
User = user_sessions[sender_phone]
Step = user["step"]
Menu_items = get_menu_from_sheet()
If step == "get_name":
User["name"] = msg_body.title()
User["step"] = "get_address"
Send_whatsapp_message(sender_phone, f"Bohat shukriya {user['name']} ji! ❤️\nAb apna pyara sa Delivery Address type kar ke bhej dein (ya apni Live Location share kar dein).")
Return jsonify({"status": "success"}), 200
If step == "get_address":
User["address"] = msg_body.title()
Cart_summary = ", ".join(user["cart"])
Special_notes = f"\n📝 Instructions: {user['instructions']}" if user['instructions'] else ""
Confirmation_msg = (
f"🎉 Order Confirmed! 🎉\n\n"
f"Aapka order successfully book ho gaya hai aur kitchen mein chef ko bhej diya gaya hai! 👨‍🍳\n"
f"⏱️ Estimated Delivery Time: 35 to 45 minutes.\n"
f"Garam garam khana jald aapke darwaze par hoga. Enjoy! 🍔✨"
)
Send_whatsapp_message(sender_phone, confirmation_msg)
User["step"] = "completed"
Owner_alert = (
f"🚨 URGENT: Almaida Fried Par Naya Order Aaya Hai! 🚨\n\n"
f"👤 Customer Name: {user['name']}\n"
f"📱 Phone Number: {sender_phone}\n"
f"🛒 Ordered Items: {cart_summary}\n"
f"💰 Total Bill: Rs. {user['total']}\n"
f"📍 Delivery Address/Location: {user['address']}"
f"{special_notes}\n\n"
f"⚡ Kitchen ko foran tayari ka hukm dein!"
)
Send_whatsapp_message(OWNER_PHONE, owner_alert)
Return jsonify({"status": "success"}), 200
If step == "completed":
If any(w in msg_body for w in ["menu", "hi", "hello", "start", "order", "deal", "h", "salam"]):
User_sessions[sender_phone] = {"step": "ordering", "cart": [], "cart_raw": [], "total": 0, "name": "", "address": "", "instructions": "", "pending_matches": [], "pending_fuzzy_item": None}
Step = "ordering"
Else:
Send_whatsapp_message(sender_phone, "😊 Aapka bohat shukriya! Enjoy your meal! 🍔✨ Agar mazeed kuch order krna ho toh 'Menu' likh kar bata sakte hain.")
Return jsonify({"status": "success"}), 200
If msg_body in ["clear", "reset", "cancel", "cancel order"]:
User_sessions[sender_phone] = {"step": "ordering", "cart": [], "cart_raw": [], "total": 0, "name": "", "address": "", "instructions": "", "pending_matches": [], "pending_fuzzy_item": None}
Send_whatsapp_message(sender_phone, "🗑️ Aapka cart clear kar diya gaya hai. Naya order shuru karne ke liye koi item name ya number likhein.")
Return jsonify({"status": "success"}), 200
If msg_body == "cart":
If not user["cart"]:
Send_whatsapp_message(sender_phone, "🛒 Aapka cart abhi khali hai!")
Else:
Cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
Send_whatsapp_message(sender_phone, f"🛒 Aapka Current Cart:\n{cart_summary}\n\n💰 Total Bill: Rs. {user['total']}\n\nItem remove karne ke liye 'Remove [item name]' likhein, ya order mukammal karne ke liye 'Done' likhein.")
Return jsonify({"status": "success"}), 200
If "remove" in msg_body or "delete" in msg_body:
Item_to_remove = msg_body.replace("remove", "").replace("delete", "").strip()
Removed_any = False
New_cart = []
New_raw = []
New_total = 0
For item_str, price in user["cart_raw"]:
If item_to_remove in item_str.lower():
Removed_any = True
Else:
New_cart.append(item_str)
New_raw.append((item_str, price))
New_total += price
If removed_any:
User["cart"] = new_cart
User["cart_raw"] = new_raw
User["total"] = new_total
Cart_summary = "\n".join([f"• {i}" for i in user["cart"]]) if user["cart"] else "Khali"
Send_whatsapp_message(sender_phone, f"🗑️ Item remove ho gaya!\n\n🛒 Updated Cart:\n{cart_summary}\n\n💰 Total Bill: Rs. {user['total']}")
Else:
Send_whatsapp_message(sender_phone, "⚠️ Aisa koi item aapke cart mein nahi mila. Sahi naam likh kar try karein.")
Return jsonify({"status": "success"}), 200
If msg_body in ["h", "a", "b", "menu", "hi", "hello", "start", "assalam o alaikum", "salam"] or len(msg_body) <= 1:
User["step"] = "ordering"
User["pending_matches"] = []
User["pending_fuzzy_item"] = None
Menu_text = "🍔 Welcome to Almaida Fried! 🍟\n_Maza Kuch Khas Hai_ ✨\n\nYeh raha hamara lazeez menu:\n"
For idx, item in enumerate(menu_items, 1):
Name = item.get("Name", "Item")
Price = item.get("Price", 0)
Num_icon = f"{idx}\u20e3" if idx <= 9 else f"{idx}."
Menu_text += f"{num_icon} {name} - Rs. {price}\n"
Menu_text += "\nAapko kya order karna hai? Item ka naam ya number likh kar bhejein! ❤️"
Send_whatsapp_image(sender_phone, "https://images.unsplash.com/photo-1504674900247-0877df9cc836", menu_text)
Return jsonify({"status": "success"}), 200
If user["pending_fuzzy_item"]:
Matched_item = user["pending_fuzzy_item"]
If msg_body in ["yes", "haan", "y", "ji", "han", "ok", "yup"]:
User["pending_fuzzy_item"] = None
Item_name = matched_item.get("Name")
Item_price = int(matched_item.get("Price", 0))
Item_img = matched_item.get("Image", "")
User["cart"].append(item_name)
User["cart_raw"].append((item_name, item_price))
User["total"] += item_price
User["step"] = "ordering"
Cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
Response_text = (
f"😋 {item_name} add ho gaya!\n\n"
f"🛒 Aapka Cart:\n{cart_summary}\n\n"
f"💰 Total Bill: Rs. {user['total']}\n\n"
f"Mazeed kuch add karwana hai? (Item ka naam/number likhein, ya 'Done' likhein)"
)
If item_img:
Send_whatsapp_image(sender_phone, item_img, response_text)
Else:
Send_whatsapp_message(sender_phone, response_text)
Return jsonify({"status": "success"}), 200
Else:
User["pending_fuzzy_item"] = None
Send_whatsapp_message(sender_phone, "Theek hai ji! Baraye meharbani menu se sahi item ka naam ya number likhein.")
Return jsonify({"status": "success"}), 200
If msg_body in ["done", "checkout", "finish", "ok done"]:
If not user["cart"]:
Send_whatsapp_message(sender_phone, "Aapne abhi tak kuch select nahi kiya! Pehle menu se pyari si cheez chunein. 😊")
Return jsonify({"status": "success"}), 200
If step != "upsell_offered":
User["step"] = "upsell_offered"
Cart_text_all = " ".join(user["cart"]).lower()
Has_fries = "fries" in cart_text_all
Has_drink = "drink" in cart_text_all
If has_fries and has_drink:
User["step"] = "get_name"
Send_whatsapp_message(sender_phone, "Zabardast! 🛒 Aapka lazeez bill tayar hai.\nAb apna Pura Naam pyare se andaz mein likh kar bhejein:")
Elif has_fries:
Send_whatsapp_message(sender_phone, "🥤 Ek choti si recommendation: Kya iske sath thandi thandi Cold Drink add karwana chahenge, ya itna kafi hai?\n\n(Mazeed item likhein, ya 'No' / 'Final' likhein)")
Elif has_drink:
Send_whatsapp_message(sender_phone, "🍟 Ek choti si recommendation: Kya iske sath Mazedar Masala Fries add karwana chahenge, ya itna kafi hai?\n\n(Mazeed item likhein, ya 'No' / 'Final' likhein)")
Else:
Send_whatsapp_message(sender_phone, "🍟 Ek choti si recommendation: Kya iske sath Mazedar Masala Fries ya thandi Cold Drink add karwana chahenge, ya itna kafi hai?\n\n(Mazeed item likhein, ya 'No' / 'Final' likhein)")
Return jsonify({"status": "success"}), 200
If step == "upsell_offered":
If msg_body in ["no", "final", "nahi", "itna kafi", "nah", "nope"]:
User["step"] = "get_name"
Send_whatsapp_message(sender_phone, "Zabardast! 🛒 Aapka lazeez bill tayar hai.\nAb apna Pura Naam pyare se andaz mein likh kar bhejein:")
Return jsonify({"status": "success"}), 200
If step == "select_from_matches":
Matches = user["pending_matches"]
If msg_body.isdigit() and 1 <= int(msg_body) <= len(matches):
Selected = matches[int(msg_body) - 1]
User["pending_matches"] = []
Item_name = selected.get("Name")
Item_price = int(selected.get("Price", 0))
Item_img = selected.get("Image", "")
User["cart"].append(item_name)
User["cart_raw"].append((item_name, item_price))
User["total"] += item_price
User["step"] = "ordering"
Cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
Response_text = (
f"✅ {item_name} aapke cart mein shamil ho gaya! 🎉\n\n"
f"🛒 Aapka Cart:\n{cart_summary}\n\n"
f"💰 Total Bill: Rs. {user['total']}\n\n"
f"Kuch aur khane ka dil hai? Item ka naam likhein ya 'Done' likhein."
)
If item_img:
Send_whatsapp_image(sender_phone, item_img, response_text)
Else:
Send_whatsapp_message(sender_phone, response_text)
Return jsonify({"status": "success"}), 200
Else:
Send_whatsapp_message(sender_phone, "Baraye meharbani di gayi list mein se sahi number select karein:")
Return jsonify({"status": "success"}), 200
If step == "ordering" or step == "upsell_offered":
If any(w in msg_body for w in ["masala", "tez", "spicy", "sauce", "extra", "less", "kam"]):
User["instructions"] = (user["instructions"] + " | " + msg_body) if user["instructions"] else msg_body
Send_whatsapp_message(sender_phone, f"✨ Aapki special requirement note kar li gayi hai: '{msg_body}' 👍")
Return jsonify({"status": "success"}), 200
If "have" in msg_body or "available" in msg_body or "milti hai" in msg_body or "hai kya" in msg_body or "kya hai" in msg_body or "do you" in msg_body:
Found_inquiry = []
For item in menu_items:
If any(word in item.get("Name", "").lower() for word in msg_body.split() if len(word) > 2):
Found_inquiry.append(item)
If found_inquiry:
Reply_text = "Jee bilkul! Yeh items available hain:\n"
For fi in found_inquiry:
Reply_text += f"• {fi.get('Name')} - Rs. {fi.get('Price')}\n"
Reply_text += "\nInhe add karne ke liye inka naam ya number likh dein!"
Send_whatsapp_message(sender_phone, reply_text)
Else:
Send_whatsapp_message(sender_phone, "Ji hamare paas upar menu mein diye gaye tamam items fresh available hain. Mazeed details ke liye menu check karein!")
Return jsonify({"status": "success"}), 200
Qty = 1
Query_words = msg_body.split()
If query_words and query_words[0].isdigit():
Potential_qty = int(query_words[0])
If 1 <= potential_qty <= len(menu_items) and len(query_words) == 1:
Matched_item = menu_items[potential_qty - 1]
Qty = 1
Else:
Qty = potential_qty
Clean_query = " ".join(query_words[1:])
Else:
Clean_query = msg_body
Matched_item = None
If clean_query.isdigit():
Idx = int(clean_query)
If 1 <= idx <= len(menu_items):
Matched_item = menu_items[idx - 1]
If not matched_item and clean_query:
Found_matches = []
For item in menu_items:
Name_lower = str(item.get("Name", "")).lower()
Query_tokens = clean_query.split()
If all(token in name_lower for token in query_tokens):
Found_matches.append(item)
If len(found_matches) == 1:
Matched_item = found_matches[0]
Elif len(found_matches) > 1:
User["pending_matches"] = found_matches
User["step"] = "select_from_matches"
Match_text = "🔍 '{}' se miltay jultay yeh lazeez options hain, batayein konsa pasand hai:\n".format(clean_query)
For idx, m in enumerate(found_matches, 1):
Match_text += f"{idx}️⃣ {m.get('Name')} - Rs. {m.get('Price')}\n"
Match_text += "\nNumber select kar ke bhejein:"
Send_whatsapp_message(sender_phone, match_text)
Return jsonify({"status": "success"}), 200
If not matched_item and clean_query:
All_item_names = [str(item.get("Name", "")).lower() for item in menu_items]
Close_names = get_close_matches(clean_query, all_item_names, n=1, cutoff=0.5)
If close_names:
Matched_name = close_names[0]
For item in menu_items:
If str(item.get("Name", "")).lower() == matched_name:
Matched_item = item
Break
If matched_item:
User["pending_fuzzy_item"] = matched_item
Send_whatsapp_message(sender_phone, f"🤔 Kya aapka matlab {matched_item.get('Name')} hai?\n\n(Jawab dein: Yes ya No)")
Return jsonify({"status": "success"}), 200
If matched_item:
Item_name = matched_item.get("Name")
Unit_price = int(matched_item.get("Price", 0))
Item_price = unit_price * qty
Display_name = f"{qty}x {item_name}" if qty > 1 else item_name
Item_img = matched_item.get("Image", "")
User["cart"].append(display_name)
User["cart_raw"].append((display_name, item_price))
User["total"] += item_price
User["step"] = "ordering"
Cart_summary = "\n".join([f"• {i}" for i in user["cart"]])
Response_text = (
f"😋 {display_name} add ho gaya!\n\n"
f"🛒 Aapka Cart:\n{cart_summary}\n\n"
f"💰 Total Bill: Rs. {user['total']}\n\n"
f"Mazeed kuch add karwana hai? (Item ka naam/number likhein, ya 'Done' likhein)"
)
If item_img:
Send_whatsapp_image(sender_phone, item_img, response_text)
Else:
Send_whatsapp_message(sender_phone, response_text)
Else:
Is_completely_absent = True
For item in menu_items:
Item_words = item.get("Name", "").lower().split()
If any(w in clean_query for w in item_words if len(w) > 3):
Is_completely_absent = False
Break
If is_completely_absent and len(clean_query) > 3:
Send_whatsapp_message(sender_phone, f"Maazrat bhaijaan! '{msg_body}' hamare paas available nahi hai. Baraye meharbani menu mein se koi doosra lazeez item chunein! ❤️")
Else:
Cart_summary = "\n".join([f"• {i}" for i in user["cart"]]) if user["cart"] else "Khali"
Polite_msg = (
f"😅 Bhaijaan, samajh nahi aayi! Please menu dekhein aur sahi item name ya number ki selection karein.\n\n"
f"🛒 Aapka Cart Abhi Mehfooz Hai:\n{cart_summary}\n"
f"💰 Total: Rs. {user['total']}\n\n"
f"👇 Hamara Lazeez Menu:\n"
)
For idx, item in enumerate(menu_items, 1):
Name = item.get("Name", "Item")
Price = item.get("Price", 0)
Num_icon = f"{idx}\u20e3" if idx <= 9 else f"{idx}."
Polite_msg += f"{num_icon} {name} - Rs. {price}\n"
Polite_msg += "\nSahi item ka naam ya number likh kar bhejein! ❤️"
Send_whatsapp_message(sender_phone, polite_msg)
Except Exception as e:
Print(f"Error: {e}")
Return jsonify({"status": "success"}), 200
If name == "main":
App.run(host="0.0.0.0", port=10000)

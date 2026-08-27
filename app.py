from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

@app.route('/', methods=['GET'])
def home():
    try:
        sheet = client.open("Restaurant_Menu").sheet1
        menu_data = sheet.get_all_records()
        items_count = len(menu_data)
        return f"Mubarak ho Umair shb ka Bot Google Sheet se connect ho gaya hai! 🎉<br>Total Menu Items: {items_count}"
    
    except Exception as e:
        return f"Bot Live hai, lekin Sheet connect nahi hui. Error: {e}"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        challenge = request.args.get("hub.challenge")
        return str(challenge)
    elif request.method == 'POST':
        print("Naya message aaya hai!")
        return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
    

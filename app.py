from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Mubarak Ho! Hussain Abbas ka WhatsApp Bot Render par Live hai! 🚀"

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
  

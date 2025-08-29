from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes

@app.route('/')
def home():
    return "Hello, this is the backend server!"

@app.route('/api/message')
def get_message():
    message = {"message": "This is a message from the backend."}
    return jsonify(message)

if __name__ == '__main__':
    app.run(debug=True)

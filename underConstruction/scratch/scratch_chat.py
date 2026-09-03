import requests
import sys

url = "http://127.0.0.1:8002/chat/"

def chat(msg, conv_id="guest"):
    payload = {"message": msg, "conversation_id": conv_id}
    headers = {"Content-Type": "application/json"}
    try:
        print(f"Sending: {msg}")
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print("Response:", data["response"])
            print("Conversation ID:", data["conversation_id"])
            return data["conversation_id"]
        else:
            print("Error:", resp.status_code, resp.text)
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    c_id = chat("Do you have any shoes?")
    c_id = chat("I want a payment-related product", c_id)

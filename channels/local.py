import os

def start_local():
    pass

def stop_local():
    pass

def getLastMessage():
    if os.path.exists("chat.txt"):
        with open("chat.txt", "r") as f:
            content = f.read().strip()
            if content:
                return f"User: {content}"
    return ""

def send_message(text):
    with open("chat-response.txt", "w") as f:
        f.write(text)

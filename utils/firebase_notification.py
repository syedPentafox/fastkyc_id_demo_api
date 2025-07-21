import firebase_admin
from firebase_admin import credentials, messaging
import os
from dotenv import load_dotenv
import json

load_dotenv()
service_file = json.loads(os.getenv("GOOGLE_SERVICE_FILE"))
cred = credentials.Certificate(service_file)
firebase_admin.initialize_app(cred)


def send_push_notification(title, msg, registration_token, data=None):
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=msg),
        data=data,
        tokens=registration_token,
    )

    response = messaging.send_multicast(message)
    responses = response.responses

    print("responses", response.responses)

    # Print or log the result of each individual message
    for i, resp in enumerate(responses):
        if resp.success:
            return True
    return False

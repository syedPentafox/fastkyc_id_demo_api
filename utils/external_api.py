import requests
from utils.db_connection import db
import json
import curlify
from utils.metrics import application_json


class APIRequester:
    def __init__(self):
        self.db = db
        self.session = self.db.get_db_session()

    def get_api_details(self, api_name):
        model = self.db.get_model("external_apis")
        return self.session.query(model).filter_by(api_name=api_name).first()

    def make_request(self, api_name, payload, header_payload=None):
        api_details = self.get_api_details(api_name)

        if not api_details:
            raise ValueError(f"No API configuration found for: {api_name}")

        url = api_details.api
        method = api_details.method.upper()
        raw_headers = (
            self.convert_to_dict(api_details.headers) if api_details.headers else {}
        )
        raw_payload = (
            self.convert_to_dict(api_details.payload) if api_details.payload else {}
        )

        # Format the payload using the input payload and the raw payload from the database
        formatted_payload = self._format_data(payload, raw_payload)
        formatted_header = self._format_data(header_payload, raw_headers)

        print("api_details.content_type.lower()", api_details.content_type.lower())
        # Determine content type
        content_type = application_json
        if api_details.content_type.lower() == "form_data":
            content_type = "multipart/form-data"

        # Prepare the request details
        request_kwargs = {"method": method, "url": url, "headers": formatted_header}

        print("Converted payload", formatted_payload)
        print("content_type", content_type)
        if content_type == application_json:
            request_kwargs["json"] = formatted_payload
        else:
            request_kwargs["data"] = formatted_payload

        # Generate and print the curl command
        prepared_request = requests.Request(**request_kwargs).prepare()
        curl_command = curlify.to_curl(prepared_request)
        print(f"Curl command: {curl_command}")

        # Make the actual request
        response = requests.request(**request_kwargs)

        if response.headers.get("Content-Type") == application_json:
            response_data = response.json()
        else:
            response_data = response.text
        if response_data:
            return response_data
        else:
            return {}

    def convert_to_dict(self, data):
        if isinstance(data, dict):
            return json.dumps(data)
        elif isinstance(data, str):
            return json.loads(data)
        else:
            raise ValueError(
                "Invalid data format, must be a dictionary or a JSON string."
            )

    def _format_data(self, payload, format_string):
        print("format_string", format_string, type(format_string))
        print("payload", payload, type(payload))
        if payload:
            for k, v in payload.items():
                format_string = format_string.replace("{" + k + "}", str(v))
                print(
                    "self.convert_to_dict(format_string)",
                    self.convert_to_dict(format_string),
                )
            return self.convert_to_dict(format_string)
        else:
            return self.convert_to_dict(format_string)

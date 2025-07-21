import base64
import io
import logging
import os
import uuid

import boto3
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
docs_url = os.getenv("AMAZON_S3_BASE_URL")
s3_bucket_name = os.getenv("S3_BUCKET_NAME")


def s3_file_upload(file_name, file_message, folder_name):
    """This to Upload the file in s3 bucket"""
    uploaded_file_url = ""
    client = boto3.client("s3")
    logger.info(
        "A file with key %s is being uploaded to bucket %s", file_name, s3_bucket_name
    )
    try:
        upload_response = client.put_object(
            Body=file_message.file.read(),
            Bucket=s3_bucket_name,
            Key=f"{folder_name}/{file_name}",
            ContentType=file_message.content_type,
        )
        logger.info("File upload to S3 response: {}".format(upload_response))
        if upload_response:
            uploaded_file_url = docs_url + f"/{folder_name}/" + file_name
    except Exception as e:
        logger.info("File upload to s3 failed because: {}", format(e))
    return uploaded_file_url


def _get_file_content_type(_file_to_upload):
    """this function only allows the below file types to upload in S3."""
    content_type_map = {
        "pdf": "application/pdf",
        "csv": "text/csv",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xml": "application/xml",
        "json": "application/json",
        "zip": "application/zip",
    }
    if _file_to_upload:
        return content_type_map.get(_file_to_upload.rsplit(".", 1)[1].lower())


def decode_base64_file(data):
    """
    BytesIO is manipulated bytes data in memory.BytesIO classes is most useful in scenarios
    where you need to mimic a normal file.
    """
    decoded_file = base64.b64decode(data)
    return io.BytesIO(decoded_file)


def s3_base64_file_upload(
    _file_prefix, _file_name, _bucket_name, _file_message, previous_file_name=None
):
    """This to Upload the base64 file in s3 bucket"""
    if previous_file_name:
        """file uploaded S3 in the previous file name, It's used to replace the old file"""
        logger.info("file upload with existing file name")
        _file_to_upload = _file_prefix + "/" + previous_file_name
    else:
        logger.info("file upload with a new file name")
        _file_to_upload = _file_prefix + "/{0}___{1}".format(uuid.uuid4(), _file_name)
    _upload_status = False
    _uploaded_file = ""
    client = boto3.client("s3")
    _file_object = decode_base64_file(_file_message)
    logger.info(
        "A file with key %s is being uploaded to bucket %s",
        _file_to_upload,
        _bucket_name,
    )
    try:
        _upload_response = client.put_object(
            Body=_file_object.read(),
            Bucket=_bucket_name,
            Key=_file_to_upload,
            ContentType=_get_file_content_type(_file_to_upload),
        )
        logger.info("File upload to S3 response: {}".format(_upload_response))
        if _upload_response:
            _upload_status = True
            _uploaded_file = docs_url + "/" + _file_to_upload
    except Exception as e:
        logger.info("File upload to s3 failed because: {}", format(e))
    return _upload_status, _uploaded_file

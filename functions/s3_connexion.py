import boto3
import os 

def get_s3():
    return boto3.client(
        "s3",
        endpoint_url="https://minio.lab.sspcloud.fr",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )
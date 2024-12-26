from google.cloud import storage

def test_gcs_access():
    credentials_path = "C:/Users/merlin/Desktop/agrario-backend/google-credentials.json"  # Update with actual path
    bucket_name = "agrario-static"

    try:
        storage_client = storage.Client.from_service_account_json(credentials_path)
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix="tutorials/")

        for blob in blobs:
            print(f"Blob: {blob.name}, Public URL: {blob.public_url}")

    except Exception as e:
        print(f"Error: {e}")

test_gcs_access()

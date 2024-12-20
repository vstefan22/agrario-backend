import base64

# Path to the file containing your JSON content
file_path = "google-credentials.json"  # Make sure this is the correct path

# Read the JSON file content
with open(file_path, "rb") as file:
    file_content = file.read()

# Encode the content to base64
encoded_content = base64.b64encode(file_content).decode("utf-8")

# Print the base64-encoded content
print(encoded_content)

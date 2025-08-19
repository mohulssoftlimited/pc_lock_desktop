import os, json, requests
from cryptography.fernet import Fernet

class TokenManager:
    def __init__(self):
        self.app_data_path = os.path.join(os.getenv('APPDATA'), 'MailBlade')
        os.makedirs(self.app_data_path, exist_ok=True)
        self.key_file = os.path.join(self.app_data_path, 'key.key')
        self.token_file = os.path.join(self.app_data_path, 'tokens.enc')
        self.key = self.get_or_create_key()

    def get_or_create_key(self):
        if not os.path.exists(self.key_file):
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key
        with open(self.key_file, 'rb') as f:
            return f.read()

    def save_tokens(self, tokens):
        fernet = Fernet(self.key)
        encrypted_data = fernet.encrypt(json.dumps(tokens).encode())
        with open(self.token_file, 'wb') as f:
            f.write(encrypted_data)

    def load_tokens(self):
        if not os.path.exists(self.token_file):
            return None
        with open(self.token_file, 'rb') as f:
            encrypted_data = f.read()
        fernet = Fernet(self.key)
        return json.loads(fernet.decrypt(encrypted_data).decode())
    
    def verify_token(self, token):
        """Verify the validity of an access token."""
        try:
            response = requests.post("https://sync.swingtheory.golf/api/token/verify/", data={"token": token})
            print(response)
            print(response.json())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Token verification failed: {e}")
            return None
    
    def refresh_tokens(self, refresh_token):
        try:
            response = requests.post("https://sync.swingtheory.golf/api/token/refresh/", data={"refresh": refresh_token})
            response.raise_for_status()
            return response.json()  # Returns new tokens
        except requests.exceptions.HTTPError:
            return None
    
    def clear_tokens(self):
        """Remove the token file physically."""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print("Token file removed successfully.")
            else:
                print("Token file does not exist.")
        except Exception as e:
            print(f"Failed to remove token file: {e}")
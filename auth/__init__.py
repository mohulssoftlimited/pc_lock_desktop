import os, json
from cryptography.fernet import Fernet

# Utility to encrypt and save tokens
class TokenManager:
    def __init__(self):
        self.app_data_path = os.path.join(os.getenv('APPDATA'), 'MyApp')
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
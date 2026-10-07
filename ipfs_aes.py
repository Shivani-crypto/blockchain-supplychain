import os
import hashlib
import json
import base64
import requests
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

KEY_PATH = os.path.join("keys", "aes_key.bin")
UPLOADS_DIR = os.path.join("uploads", "ipfs_store")

os.makedirs("keys", exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

def generate_or_load_aes_key(key_file=KEY_PATH):
    """Generate a 256-bit AES key if it doesn't exist, or load the existing key."""
    if not os.path.exists(key_file):
        key = get_random_bytes(32) # 256-bit key
        with open(key_file, "wb") as f:
            f.write(key)
        print(f"[AES] Generated new 256-bit AES key at {key_file}")
    else:
        with open(key_file, "rb") as f:
            key = f.read()
        print(f"[AES] Loaded existing AES key from {key_file}")
    return key

def encrypt_data(raw_bytes: bytes, aes_key: bytes) -> dict:
    """Encrypt raw bytes using AES-GCM."""
    cipher = AES.new(aes_key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(raw_bytes)
    return {
        "nonce": base64.b64encode(cipher.nonce).decode('utf-8'),
        "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
        "tag": base64.b64encode(tag).decode('utf-8')
    }

def decrypt_data(encrypted_payload: dict, aes_key: bytes) -> bytes:
    """Decrypt AES-GCM payload."""
    nonce = base64.b64decode(encrypted_payload["nonce"])
    ciphertext = base64.b64decode(encrypted_payload["ciphertext"])
    tag = base64.b64decode(encrypted_payload["tag"])
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)

def get_sha256_hash(raw_bytes: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(raw_bytes).hexdigest()

def upload_to_ipfs_or_pinata(encrypted_payload: dict, filename: str, pinata_api_key: str = "", pinata_secret_key: str = "") -> tuple:
    """
    Upload encrypted payload to Pinata IPFS service if credentials available,
    otherwise fallback to mock local IPFS hash storage.
    Returns (ipfs_hash, sha256_hash).
    """
    json_bytes = json.dumps(encrypted_payload).encode('utf-8')
    sha256_hash = get_sha256_hash(json_bytes)

    if pinata_api_key and pinata_secret_key and pinata_api_key != "YOUR_PINATA_API_KEY":
        try:
            url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
            headers = {
                "pinata_api_key": pinata_api_key,
                "pinata_secret_api_key": pinata_secret_key,
                "Content-Type": "application/json"
            }
            body = {
                "pinataMetadata": {"name": filename},
                "pinataContent": encrypted_payload
            }
            response = requests.post(url, json=body, headers=headers, timeout=10)
            if response.status_code == 200:
                ipfs_hash = response.json().get("IpfsHash")
                print(f"[IPFS/Pinata] Uploaded to Pinata successfully: {ipfs_hash}")
                return ipfs_hash, sha256_hash
        except Exception as e:
            print(f"[IPFS/Pinata Warning] Failed Pinata upload, falling back to local IPFS storage: {e}")

    # Fallback / Local IPFS store simulation
    ipfs_hash = "Qm" + sha256_hash[:44]
    local_path = os.path.join(UPLOADS_DIR, f"{ipfs_hash}.json")
    with open(local_path, "w", encoding='utf-8') as f:
        json.dump(encrypted_payload, f, indent=2)
    print(f"[IPFS Local] Encrypted file stored at {local_path} with IPFS Hash: {ipfs_hash}")
    return ipfs_hash, sha256_hash

def get_from_ipfs(ipfs_hash: str, pinata_gateway_url: str = "") -> dict:
    """Retrieve encrypted payload from IPFS or local storage."""
    local_path = os.path.join(UPLOADS_DIR, f"{ipfs_hash}.json")
    if os.path.exists(local_path):
        with open(local_path, "r", encoding='utf-8') as f:
            return json.load(f)
    
    if pinata_gateway_url and ipfs_hash:
        try:
            res = requests.get(f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}", timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print(f"[IPFS Fetch Error] {e}")

    return {}

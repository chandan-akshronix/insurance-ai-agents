import os
from app_server.utils.config import read_secret, get_config_value

def verify_secrets():
    print("Verifying secrets loading...")
    
    # Test 1: Check if environment variables are loaded (via config.py import)
    openai_key = os.getenv("AZURE_OPENAI_KEY")
    if openai_key and not openai_key.startswith("8qTE"): # Check if it's the actual key (masked check)
        print("✅ AZURE_OPENAI_KEY loaded from env")
    elif openai_key:
         print("✅ AZURE_OPENAI_KEY loaded from env (matches known prefix)")
    else:
        print("❌ AZURE_OPENAI_KEY NOT loaded from env")

    # Test 2: Check read_secret function
    try:
        key_via_func = read_secret("AZURE_OPENAI_KEY")
        if key_via_func:
            print("✅ read_secret('AZURE_OPENAI_KEY') works")
    except Exception as e:
        print(f"❌ read_secret('AZURE_OPENAI_KEY') failed: {e}")

    # Test 3: Check other vars
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if endpoint:
        print(f"✅ AZURE_OPENAI_ENDPOINT loaded: {endpoint}")
    else:
        print("❌ AZURE_OPENAI_ENDPOINT NOT loaded")

if __name__ == "__main__":
    verify_secrets()

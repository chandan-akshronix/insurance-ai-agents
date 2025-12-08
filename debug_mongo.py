from app_server.utils.clients import db
from datetime import datetime

def test_mongo_insert():
    print(f"Testing connection to database: {db.name}")
    try:
        result = db.result.insert_one({
            "test": True,
            "timestamp": datetime.now().isoformat(),
            "message": "Debug insertion"
        })
        print(f"Successfully inserted document with ID: {result.inserted_id}")
        
        # Verify retrieval
        doc = db.result.find_one({"_id": result.inserted_id})
        if doc:
            print(f"Successfully retrieved document: {doc}")
        else:
            print("Failed to retrieve inserted document")
            
    except Exception as e:
        print(f"Error inserting into MongoDB: {e}")

if __name__ == "__main__":
    test_mongo_insert()

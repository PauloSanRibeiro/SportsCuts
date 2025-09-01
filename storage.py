from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage

# Corrected line: Assumes firebaseAccount.json is in the same directory as storage.py
cred_path = Path(__file__).parent / "firebaseAccount.json"

cred = credentials.Certificate(str(cred_path))
firebase_admin.initialize_app(
    cred, {"storageBucket": "takevideosgame.firebasestorage.app"}
)

# Firestore
db = firestore.client()
db.collection("teste").document("doc1").set({"msg": "funcionou!"})

# Storage
bucket = storage.bucket()
blob = bucket.blob("teste.txt")
blob.upload_from_filename("arquivo_local.txt")

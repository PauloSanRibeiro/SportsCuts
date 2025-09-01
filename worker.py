import os
import json
import traceback
from pathlib import Path
from urllib.parse import quote_plus

import google.auth
from google.auth.transport.requests import Request

# Firebase
import firebase_admin
from firebase_admin import credentials, storage
from google.cloud.exceptions import GoogleCloudError

from dotenv import load_dotenv
from supabase import create_client, Client
import supabase

# -------- CONFIGURAÇÃO --------
BASE_DIR = Path(__file__).resolve().parent

cred_path = Path(__file__).parent / "firebaseAccount.json"
cred = credentials.Certificate(str(cred_path))
firebase_admin.initialize_app(
    cred,
    {
        "storageBucket": "takevideosgame.firebasestorage.app"
    },  # cuidado com o domínio, deve ser appspot.com
)

# Use google.auth para manter credenciais atualizadas
credentials, project = google.auth.load_credentials_from_file(str(cred_path))
if credentials.expired and credentials.refresh_token:
    credentials.refresh(Request())

bucket = storage.bucket()


# -------- Supabase Init --------
load_dotenv(BASE_DIR / "configs.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Nome da tabela no Postgres/Supabase
TABLE_NAME = "metadata"

# -------- Paths --------
PENDING_DIR = BASE_DIR / "pending"


def process_file(video_path: Path):
    
    meta_path = video_path.with_suffix(".json")

    if not meta_path.exists():
        print(f"[WARN] Metadados nao encontrados para {video_path.name}")
        return

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

        existing = (
            supabase.table("cutsvideo")
            .select("*")
            .eq("filename", video_path.name)
            .execute()
        )
    if existing.data:
        print(f"{video_path.name} já enviado, ignorando...")
        return

    try:
        print(f"Enviando {video_path.name} ...")

        # Upload Firebase
        try:

            client_name = metadata.get("codpartner")
            court_name = metadata.get("idlocation")

            blob_path = f"{client_name}/{court_name}/{video_path.name}"

            blob = bucket.blob(blob_path)
            print(
                f"Iniciando upload de {video_path.name} para {bucket.name} em {blob_path} ..."
            )

            blob.upload_from_filename(str(video_path.resolve()), timeout=60)
            blob.make_public()  # ou gerar signed_url se preferir
            metadata["urlvideo"] = blob.public_url

            print("Upload Firebase concluído")

        except GoogleCloudError as e:
            print(f"Erro no upload para Firebase: {e}")
            return

        except Exception as e:

            print(f"Erro inesperado no upload: {e}")
            traceback.print_exc()
            return

        # Salva no Supabase
        print("Gravando metadados no Supabase...")
        metadata["status"] = "uploaded"
        metadata["json"] = metadata.copy()
        insert_resp = supabase.table("cutsvideo").insert(metadata).execute()

        if insert_resp.data:
            print("Registro gravado no Supabase")
        else:
            print(f"Erro ao gravar no Supabase: {insert_resp}")

        print(f"Upload concluído: {metadata['urlvideo']}")

        # Apaga local apenas se deu tudo certo
        os.remove(video_path)
        os.remove(meta_path)

    except Exception as e:

        print(f"Erro ao processar {video_path.name}: {e}")
        traceback.print_exc()
        # Atualiza metadata para retomar depois
        metadata["status"] = "error"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    print("Iniciando verificação de arquivos em pending...")

    for video_path in PENDING_DIR.glob("*.mp4"):
        
        print(f"Encontrado: {video_path.name}")

        done_flag = video_path.with_suffix(".done")
        
        if not done_flag.exists():
            print(f"[SKIP] {video_path.name} ainda não está pronto (sem .done)")
            continue

        process_file(video_path)

        # Remove o sinalizador após sucesso
        try:
            os.remove(done_flag)
        except Exception as e:
            print(f"[WARN] Não foi possível remover {done_flag.name}: {e}")
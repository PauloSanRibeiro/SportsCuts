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
from google.oauth2 import service_account

from dotenv import load_dotenv
from supabase import create_client, Client
import supabase

# -------- CONFIGURAÇÃO --------
BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / "configs.env")

firebase_config = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN")
}
for key, value in firebase_config.items():
    if value is None:
        raise ValueError(f"[ERRO] Variável de ambiente ausente: {key}")
    
temp_path = BASE_DIR / "firebase_temp.json"
with open(temp_path, "w") as f:
    json.dump(firebase_config, f)

cred = credentials.Certificate(temp_path)

firebase_admin.initialize_app(
    cred, {"storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")}
)


# Use google.auth para manter credenciais atualizadas
credentials = service_account.Credentials.from_service_account_info(firebase_config)

if credentials.expired and credentials.refresh_token:
    credentials.refresh(Request())

bucket = storage.bucket()

try:
    os.remove(temp_path)
except Exception as e:
    print(f"[WARN] Não foi possível remover {temp_path.name}: {e}")


# -------- Supabase Init --------
urlSupa = os.getenv("SUPABASE_URL")
keySupa = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(urlSupa, keySupa)

# Nome da tabela no Postgres/Supabase
TABLE_NAME = "metadata"


PENDING_DIR = BASE_DIR / "pending"
def process_file(video_path: Path) -> bool:
    meta_path = video_path.with_suffix(".json")

    if not meta_path.exists():
        print(f"[WARN] Metadados não encontrados para {video_path.name}")
        return False

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
        return True  # já está no banco, pode remover o .done

    try:
        print(f"Enviando {video_path.name} ...")

        # Upload Firebase
        try:
            client_name = metadata.get("codpartner")
            court_name = metadata.get("idlocation")
            blob_path = f"{client_name}/{court_name}/{video_path.name}"

            blob = bucket.blob(blob_path)
            print(f"Iniciando upload de {video_path.name} para {bucket.name} em {blob_path} ...")

            blob.upload_from_filename(str(video_path.resolve()), timeout=60)
            blob.make_public()
            metadata["urlvideo"] = blob.public_url

            print("Upload Firebase concluído")

        except GoogleCloudError as e:
            print(f"Erro no upload para Firebase: {e}")
            return False

        except Exception as e:
            print(f"Erro inesperado no upload: {e}")
            traceback.print_exc()
            return False

        # Salva no Supabase
        print("Gravando metadados no Supabase...")
        metadata["status"] = "uploaded"
        metadata["json"] = metadata.copy()
        insert_resp = supabase.table("cutsvideo").insert(metadata).execute()

        if insert_resp.data:
            print("Registro gravado no Supabase")
        else:
            print(f"Erro ao gravar no Supabase: {insert_resp}")
            return False

        print(f"Upload concluído: {metadata['urlvideo']}")

        # Apaga local apenas se deu tudo certo
        os.remove(video_path)
        os.remove(meta_path)

        return True

    except Exception as e:
        print(f"Erro ao processar {video_path.name}: {e}")
        traceback.print_exc()
        metadata["status"] = "error"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return False


if __name__ == "__main__":
    print("Iniciando verificação de arquivos em pending...")

    for video_path in PENDING_DIR.glob("*.mp4"):
        print(f"Encontrado: {video_path.name}")
        done_flag = video_path.with_suffix(".done")

        if not done_flag.exists():
            print(f"[SKIP] {video_path.name} ainda não está pronto (sem .done)")
            continue

        if sucesso := process_file(video_path):
            try:
                os.remove(done_flag)
            except Exception as e:
                print(f"[WARN] Não foi possível remover {done_flag.name}: {e}")
        else:
            print(f"[RETRY] Mantendo {done_flag.name} para reprocessamento futuro")



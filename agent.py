import ctypes
import os
import glob
import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime


from google.auth.transport.requests import Request

# Firebase
from firebase_admin import credentials, storage, firestore
import json
from pathlib import Path
from datetime import datetime
import subprocess

# -------- CONFIGURAÇÃO --------
BASE_DIR = Path(__file__).resolve().parent

# Carrega configuração
with open(BASE_DIR / "config.json", "r") as f:
    cfg = json.load(f)

# Nome da câmera (passado via argumento)
if len(sys.argv) < 2:
    print(" Nenhum nome de câmera informado.")
    sys.exit(1)

camera_location = sys.argv[1]

camera_cfg = next(
    (c for c in cfg["cameras"] if c["cameralocation"] == camera_location), None
)
if not camera_cfg:
    print(f" Camera '{camera_location}' nao encontrada no config.json")
    sys.exit(1)

SEG_PATH = camera_cfg["segment_path"]
FINAL_PATH = camera_cfg["final_path"]
CLIENT = camera_cfg["client"]
OUTPUT_DURATION = cfg["output_duration"]
SEGMENT_TIME = cfg.get("segment_time", 10)

os.makedirs(SEG_PATH, exist_ok=True)
os.makedirs(FINAL_PATH, exist_ok=True)


# -------- FUNÇÕES --------
def buffer_pronto(path, min_files=3, min_size_kb=100):
    arquivos = sorted(glob.glob(os.path.join(path, "*.mp4")), key=os.path.getmtime)
    if len(arquivos) < min_files:
        print(f"[SKIP] Buffer insuficiente: {len(arquivos)} arquivos")
        return False
    for f in arquivos[-min_files:]:
        tamanho_kb = os.path.getsize(f) // 1024
        if tamanho_kb < min_size_kb:
            print(f"[SKIP] Segmento suspeito: {os.path.basename(f)} ({tamanho_kb} KB)")
            return False
    return True

def create_clip():
    # Lista os arquivos recentes
    files = sorted(glob.glob(os.path.join(SEG_PATH, "*.mp4")), key=os.path.getmtime)
    if not files:
        print("Nenhum segmento encontrado.")
        return None

    n_files = (OUTPUT_DURATION // SEGMENT_TIME) + 2
    last_segments = files[-n_files:]

    # Cria arquivo de lista temporário para concat
    concat_list = BASE_DIR / "concat_list.txt"
    with open(concat_list, "w") as f:
        for s in last_segments:
            f.write(f"file '{os.path.abspath(s)}'\n")

    # Nome final do clip
    out_name = os.path.join(
        FINAL_PATH,
        f"{camera_location}_clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
    )

    # Comando FFmpeg: concat + corte direto
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-t",
            str(OUTPUT_DURATION),
            out_name,
        ],
        check=True,
    )
    # Converte para vertical
    clip_path = Path(out_name)
    vertical_path = clip_path.with_name("vertical_" + clip_path.name)
    converter_para_retrato(clip_path, vertical_path)

    # Substitui o original pelo vertical
    os.replace(vertical_path, clip_path)

    try:
        os.remove(concat_list)
    except Exception as e:
        print(f" Não consegui remover temporário: {e}")

    print(f" Clip criado: {out_name}")
    return out_name


def get_duration(video_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


logo_path = BASE_DIR / "template.png"


def aplicar_overlay(video_path, logo_path, output_path):
    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-i",
        str(logo_path),
        "-filter_complex",
        "overlay=5:5",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)

def converter_para_retrato(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-vf", "scale=1080:1920",  # ou crop, ou transpose se quiser girar
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)

def create_metadata(video_path, camera_location):

    video_path = Path(video_path)
    duration = get_duration(video_path)

    metadata = {
        "filename": video_path.name,
        "durationvideo": duration,
        "codpartner": CLIENT,
        "idlocation": camera_location,
        "dtcreated": datetime.now().isoformat(),
    }

    meta_file = video_path.with_suffix(".json")

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


    return meta_file


# -------- MAIN --------
if __name__ == "__main__":
    
    clip = create_clip()

    if clip:
        # Aplica o overlay de patrocínio
        logo_path = BASE_DIR / "favicon.ico"
        overlay_path = Path(clip).with_name("overlay_" + Path(clip).name)
        aplicar_overlay(clip, logo_path, overlay_path)

        # Substitui o vídeo original pelo com overlay
        os.replace(overlay_path, clip)

        meta_file = create_metadata(clip, camera_location)

        # Cria sinalizador .done para o worker saber que está pronto
        done_flag = Path(clip).with_suffix(".done")
        try:
            with open(done_flag, "w") as f:
                f.write("ok")
            print(f"Sinalizador criado: {done_flag.name}")
        except Exception as e:
            print(f"[WARN] Não foi possível criar o .done: {e}")
        print(f" Metadata criada: {meta_file.name}")


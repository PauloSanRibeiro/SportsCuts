import os
import subprocess
import threading
from evdev import InputDevice, categorize, ecodes

# Configurações
agent_path = "/home/paulo/sportscuts/agents/SportsCuts/run_agent.sh"
worker_path = "/home/paulo/sportscuts/agents/SportsCuts/run_worker.sh"
log_dir = "/home/paulo/sportscuts/agents/SportsCuts/logs"

cam1 = "1"
cam2 = "2"

# Funções
def is_agent_running(cam):
    result = subprocess.run(["pgrep", f"agent_{cam}"], stdout=subprocess.PIPE)
    return result.returncode == 0

def start_agent(cam):
    if not is_agent_running(cam):
        log_file = os.path.join(log_dir, f"log_{cam}.txt")
        subprocess.Popen([agent_path, cam], stdout=open(log_file, "w"), stderr=subprocess.STDOUT)

# Escuta botão físico (ex: botão 288)
def listen_joystick():
    try:
        device = InputDevice('/dev/input/event7')  # mapear o botao cat /proc/bus/input/devices
        
        print("Escutando botão físico...")
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:
                if event.code == 288:
                    print("Botão físico → Câmera 1")
                    start_agent(cam1)
    except Exception as e: print(f"Erro ao escutar botao: {e}")

# Escuta tecla do teclado
def listen_keyboard():
    try:
        keyboard_dev = InputDevice('/dev/input/event8')  # mapear o botao cat /proc/bus/input/devices
        print("Escutando tecla 'F7' para Câmera 2...")

        for event in keyboard_dev.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:
                if event.code == ecodes.KEY_F7:
                    print("Tecla F7 → Câmera 2")
                    start_agent(cam2)
    except Exception as e: print(f"Erro ao escutar teclado: {e}")

#  Rodar ambos em paralelo
if __name__ == "__main__":
    threading.Thread(target=listen_joystick, daemon=True).start()
    threading.Thread(target=listen_keyboard, daemon=True).start()
    while True:
        pass
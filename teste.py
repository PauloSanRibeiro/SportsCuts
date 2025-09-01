from evdev import InputDevice, categorize, ecodes

device = InputDevice('/dev/input/event7')  # substitua se necessário

for event in device.read_loop():
    if event.type == ecodes.EV_KEY and event.value == 1:  # pressionado
        print(f"Botão {event.code} pressionado")
        # Aqui você pode disparar o corte, overlay, upload etc.

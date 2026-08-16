#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
from PIL import Image
import io

OUTPUT = "data_splicing_varianti"
JPEG_OUTPUT = "jpeg_converted"
NUM_VARIANTI = 60

def get_pixel_offset(data):
    if data[:2] != b'BM':
        return None
    return int.from_bytes(data[10:14], "little")

def split_bmp(data):
    offset = get_pixel_offset(data)
    if offset is None:
        return None, None
    return data[:offset], data[offset:]

def fix_length(data, length):
    if len(data) >= length:
        return data[:length]
    return data + bytes(length - len(data))

# --- EFFETTI DI SOVRAPPOSIZIONE ---
def mix_bytes(a, b):
    return bytes([(x + y) // 2 for x, y in zip(a, b)])

def xor_bytes(a, b):
    return bytes([x ^ y for x, y in zip(a, b)])

def self_shift_mix(pixels):
    shift = random.randint(50, 5000)
    shifted_pixels = pixels[shift:] + pixels[:shift]
    if random.choice([True, False]):
        return mix_bytes(pixels, shifted_pixels)
    else:
        return xor_bytes(pixels, shifted_pixels)

# --- EFFETTI DI SPLICING (TAGLIO) ---
def mix_fraction(a, b, parts):
    cut = len(a) // parts
    return a[:cut] + b[cut:]

def mix_blocks(a, b, block_size):
    result = bytearray()
    limit = min(len(a), len(b))
    use_a = True
    for i in range(0, limit, block_size):
        if use_a:
            result.extend(a[i:i+block_size])
        else:
            result.extend(b[i:i+block_size])
        use_a = not use_a
    return bytes(result)

def self_shift_splice(pixels):
    shift = random.randint(100, 2000)
    shifted_pixels = pixels[shift:] + pixels[:shift]
    if random.choice([True, False]):
        return mix_fraction(pixels, shifted_pixels, 2)
    else:
        return mix_blocks(pixels, shifted_pixels, random.choice([32, 64, 128]))

# --- NUOVI EFFETTI "FIGHI" ---

# 1. Reverse (Inverti la traccia)
def reverse_effect(pixels):
    return pixels[::-1]

# 2. Delay / Loop (Copia un pezzo e lo ripete più volte)
def delay_loop(pixels):
    seg_size = len(pixels) // random.randint(6, 12) # Prende 1/6 o 1/12 dell'immagine
    segment = pixels[:seg_size]
    # Ripete questo segmento fino a riempire la lunghezza originale
    result = bytearray()
    while len(result) < len(pixels):
        result.extend(segment)
    return bytes(result[:len(pixels)])

# 3. Cross Merge (Mix tra due immagini DIVERSE)
def cross_merge(a, b):
    if random.choice([True, False]):
        return mix_bytes(a, b)
    else:
        return xor_bytes(a, b)

# 4. Cut & Swap (Prende l'inizio di A e lo mette alla fine, o prende un pezzo di B)
def cut_swap(a, b):
    # Prende il primo quarto di A
    quarter = len(a) // 4
    part_a = a[:quarter]
    # Lo toglie dall'inizio e lo sposta alla fine
    rest_a = a[quarter:]
    if random.choice([True, False]):
        # Swap con se stessa
        return rest_a + part_a
    else:
        # Prende un quarto di B e lo mette all'inizio di A
        part_b = b[:quarter]
        return part_b + rest_a

# --- FUNZIONI PER LA CONVERSIONE IN JPEG ---
def convert_all_bmps_to_jpeg():
    if not os.path.exists(JPEG_OUTPUT):
        os.makedirs(JPEG_OUTPUT)
    
    print("\n--- Avvio conversione in JPEG ---")
    for root, dirs, files in os.walk(OUTPUT):
        for file in files:
            if file.lower().endswith('.bmp'):
                src_path = os.path.join(root, file)
                
                # Manteniamo la struttura delle cartelle
                rel_path = os.path.relpath(root, OUTPUT)
                target_dir = os.path.join(JPEG_OUTPUT, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                
                target_filename = os.path.splitext(file)[0] + '.jpg'
                target_path = os.path.join(target_dir, target_filename)
                
                try:
                    with Image.open(src_path) as img:
                        # .convert('RGB') è fondamentale per evitare che i glitch con canale Alpha (RGBA) vengano salvati male in JPEG
                        rgb_img = img.convert('RGB')
                        rgb_img.save(target_path, 'JPEG', quality=95)
                except Exception as e:
                    print(f"  -> Errore convertendo {file}: {e}")
    print("Conversione JPEG completata nella cartella 'jpeg_converted'.")

# --- SCRITTURA DEI FILE TXT (Come replicare con Audacity) ---
def write_audacity_guide(folder_path, category_name, instructions):
    txt_path = os.path.join(folder_path, "come_farlo_con_audacity.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"COME REPLICARE L'EFFETTO '{category_name.upper()}' CON AUDACITY\n")
        f.write("=" * 50 + "\n\n")
        f.write("Per ottenere questi risultati manualmente con Audacity, il procedimento è il seguente:\n")
        f.write("1. Apri Audacity e importa il tuo file immagine selezionando File > Importa > Dati non elaborati (Raw Data).\n")
        f.write("2. Imposta il formato di codifica su 'U-Law' o 'A-Law' (o altri formati che danno il 'databending' migliore).\n")
        f.write("3. Applica i passaggi specifici qui sotto:\n\n")
        f.write(instructions)
        f.write("\n\n---\n")
        f.write("Consiglio finale: Dopo aver lavorato la traccia audio in Audacity, esporta il file come 'WAV' o 'Aiff'.\n")
        f.write("Rinomina l'estensione del file esportato da .wav a .bmp e aprilo con Anteprima per vedere il glitch generato!\n")

# --- PROCESSO PRINCIPALE ---
def process():
    files = [f for f in os.listdir(".") if f.lower().endswith(".bmp")]

    if len(files) < 1:
        print("Servono almeno 1 BMP.")
        return

    os.makedirs(OUTPUT, exist_ok=True)

    images = {}
    print("Caricamento BMP:")
    for f in files:
        with open(f, "rb") as file:
            data = file.read()
        header, pixels = split_bmp(data)
        if header:
            images[f] = {"header": header, "pixels": pixels}
            print("-", f)

    names = list(images.keys())

    print("\nGenero varianti e cartelle...")

    # CARTELLA 1 & 2 (Gia esistenti)
    folder_configs = [
        ("overlay_mix", "Sovrapposizione con copia shiftata"),
        ("splice_pieces", "Tagli e scambi con se stessa o altra BMP"),
        ("reverse_effect", "Traccia invertita al contrario (Reverse)"),
        ("delay_loop", "Eco (Delay) - Un pezzo iniziale ripetuto in loop"),
        ("cross_merge", "Mix di due immagini diverse sovrapposte"),
        ("cut_swap", "Spostamento di grossi blocchi dall'inizio alla fine")
    ]

    for folder_name, description in folder_configs:
        current_path = os.path.join(OUTPUT, folder_name)
        os.makedirs(current_path, exist_ok=True)
        
        # Scriviamo le istruzioni per Audacity
        if folder_name == "overlay_mix":
            guide = "Per replicare questa cartella:\n- Duplica la traccia.\n- Sposta la seconda traccia di alcuni millisecondi (Effetto > Sposta).\n- Seleziona entrambe e fai Mix > Miscela e rendi.\n- (Opzionale) Applica Effetto > Inverti su una traccia prima del mix per ottenere l'effetto XOR."
        elif folder_name == "splice_pieces":
            guide = "Per replicare questa cartella:\n- Duplica la traccia e spostala di un breve tratto.\n- Usa lo strumento Selezione per tagliare un pezzo della seconda traccia.\n- Sposta il pezzo tagliato in un punto diverso della traccia principale (Cut & Paste)."
        elif folder_name == "reverse_effect":
            guide = "Per replicare questa cartella:\n- Dopo l'import Raw Data, seleziona tutta la traccia.\n- Vai su Effetto > Inverti (Reverse).\n- Questo invertirà completamente l'ordine dei byte, creando l'effetto visivo di 'immagine sbrogliata al contrario'."
        elif folder_name == "delay_loop":
            guide = "Per replicare questa cartella:\n- Seleziona una breve porzione all'inizio della traccia (es. un secondo di audio).\n- Premi Ctrl+C per copiarla.\n- Vai su Traccia > Aggiungi nuovo > Traccia mono.\n- Incolla la porzione copiata e premi Ctrl+R (Ripeti) per replicarla decine di volte fino a riempire la durata originale.\n- Mixa le due tracce."
        elif folder_name == "cross_merge":
            guide = "Per replicare questa cartella:\n- Importa DUE diverse immagini come Raw Data in due tracce separate.\n- Portale entrambe alla stessa durata (se sono diverse, usa Effetto > Cambia velocità).\n- Seleziona entrambe le tracce e fai Mix > Miscela e rendi.\n- Questo fonde i byte delle due immagini."
        elif folder_name == "cut_swap":
            guide = "Per replicare questa cartella:\n- Importa il file. Duplica la traccia.\n- Taglia la prima metà della traccia duplicata.\n- Sposta questo pezzo tagliato alla fine della traccia principale (o incollalo all'inizio di una seconda traccia).\n- Mixa le tracce insieme per ottenere lo spostamento di blocchi."
        
        write_audacity_guide(current_path, folder_name, guide)

    # Generazione immagini per ogni cartella
    for i in range(NUM_VARIANTI):
        for folder_name in [f[0] for f in folder_configs]:
            a = random.choice(names)
            img_a = images[a]
            header = img_a["header"]
            pixels = img_a["pixels"]

            if folder_name == "overlay_mix":
                pixels = self_shift_mix(pixels)
            elif folder_name == "splice_pieces":
                if len(names) >= 2 and random.random() > 0.5:
                    b = random.choice([n for n in names if n != a])
                    pixels = mix_fraction(pixels, images[b]["pixels"], random.choice([2, 4, 5, 10]))
                else:
                    pixels = self_shift_splice(pixels)
            elif folder_name == "reverse_effect":
                pixels = reverse_effect(pixels)
            elif folder_name == "delay_loop":
                pixels = delay_loop(pixels)
            elif folder_name == "cross_merge":
                if len(names) >= 2:
                    b = random.choice([n for n in names if n != a])
                    pixels = cross_merge(pixels, images[b]["pixels"])
                else:
                    pixels = cross_merge(pixels, pixels) # Se solo un'immagine, merge con se stessa
            elif folder_name == "cut_swap":
                if len(names) >= 2:
                    b = random.choice([n for n in names if n != a])
                    pixels = cut_swap(pixels, images[b]["pixels"])
                else:
                    pixels = cut_swap(pixels, pixels)

            pixels = fix_length(pixels, len(img_a["pixels"]))
            output = header + pixels
            filename = f"{i:03d}_{a[:-4]}.bmp"
            with open(os.path.join(OUTPUT, folder_name, filename), "wb") as f:
                f.write(output)

    print("\nGenerazione BMP completata.")
    
    # --- CONVERSIONE FINALE IN JPEG ---
    convert_all_bmps_to_jpeg()

if __name__ == "__main__":
    process()
    print("\nTutti i passaggi completati!\n")
    print("Troverai i file BMP in 'data_splicing_varianti'.")
    print("Troverai i JPEG per Indesign in 'jpeg_converted' (stessa struttura).")
    print("In ogni cartella è presente il file 'come_farlo_con_audacity.txt' per la tua tesi.")
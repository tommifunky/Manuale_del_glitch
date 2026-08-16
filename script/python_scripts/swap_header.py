import os
import struct
import io
import random
from PIL import Image

def get_header_offset(data):
    """Legge l'offset dei dati pixel (bfOffBits)."""
    if len(data) < 14: return None
    return struct.unpack('<I', data[10:14])[0]

def fix_header_length(header_bytes, target_length):
    """Taglia o riempie di zeri l'header per avere esattamente la lunghezza target."""
    if len(header_bytes) >= target_length:
        return header_bytes[:target_length]
    else:
        return header_bytes + b'\x00' * (target_length - len(header_bytes))

def fix_data_length(data_bytes, target_length):
    """Taglia o riempie di zeri i dati pixel per avere esattamente la lunghezza target."""
    if len(data_bytes) >= target_length:
        return data_bytes[:target_length]
    else:
        return data_bytes + b'\x00' * (target_length - len(data_bytes))

def save_glitch_file(original_bytes, header, data, output_path):
    """Unisce header e dati mantenendo la lunghezza totale invariata."""
    header_size = len(header)
    total_len = len(original_bytes)
    expected_data_len = total_len - header_size
    final_data = fix_data_length(data, expected_data_len)
    final_bytes = header + final_data
    with open(output_path, 'wb') as f:
        f.write(final_bytes)

def convert_folder_to_jpeg(source_folder, dest_folder):
    """Converte tutti i BMP in una cartella in JPEG, mantenendo la struttura."""
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
    
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.lower().endswith('.bmp'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, source_folder)
                target_dir = os.path.join(dest_folder, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                
                target_file = os.path.splitext(file)[0] + '.jpg'
                target_path = os.path.join(target_dir, target_file)
                
                try:
                    with Image.open(src_path) as img:
                        rgb_img = img.convert('RGB')
                        rgb_img.save(target_path, 'JPEG', quality=95)
                    print(f"  -> Convertito in JPEG: {target_file}")
                except Exception as e:
                    print(f"  -> Errore convertendo {file} in JPEG: {e}")

def process_bmps_in_folder():
    folder_path = os.getcwd()
    bmp_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.bmp')]
    
    if not bmp_files:
        print("Nessun file .bmp trovato.")
        return

    # Cartelle di output
    os.makedirs("01_varianti_base", exist_ok=True)
    os.makedirs("02_header_swap", exist_ok=True)
    os.makedirs("03_data_splicing", exist_ok=True)
    os.makedirs("04_random_mix_sbizzarriti", exist_ok=True)
    os.makedirs("05_original_cross_swap", exist_ok=True)

    # Carichiamo tutti i file originali
    all_originals = {}
    for filename in bmp_files:
        path = os.path.join(folder_path, filename)
        with open(path, 'rb') as f:
            all_originals[filename] = f.read()

    # --- FASE 1: Genera le 4 varianti per ogni BMP ---
    variant_files = {}
    for filename, orig_bytes in all_originals.items():
        base_name = os.path.splitext(filename)[0]
        img = Image.open(os.path.join(folder_path, filename))
        
        header_size = get_header_offset(orig_bytes)
        if header_size is None: continue

        variants = {
            f"{base_name}_orig": orig_bytes,
            f"{base_name}_rotL": img.transpose(Image.ROTATE_90),
            f"{base_name}_rotR": img.transpose(Image.ROTATE_270),
            f"{base_name}_specchio": img.transpose(Image.FLIP_LEFT_RIGHT)
        }

        for name, pil_img in variants.items():
            if isinstance(pil_img, bytes):
                save_bytes = pil_img
            else:
                buffer = io.BytesIO()
                pil_img.save(buffer, format='BMP')
                save_bytes = buffer.getvalue()
            
            out_path = os.path.join("01_varianti_base", f"{name}.bmp")
            with open(out_path, 'wb') as f:
                f.write(save_bytes)
            variant_files[name] = save_bytes
        
        print(f"-> Varianti base per {filename} salvate.")

    variant_names = list(variant_files.keys())

    # --- FASE 2: Header Swap tra le varianti (MIX TOTALE) ---
    for name1 in variant_names:
        data1 = variant_files[name1]
        h_size1 = get_header_offset(data1) or 0
        
        for name2 in variant_names:
            if name1 == name2: continue
            data2 = variant_files[name2]
            h_size2 = get_header_offset(data2) or 0

            header = data1[:h_size1]
            pixels = data2[h_size2:]
            
            out_path = os.path.join("02_header_swap", f"{name1}_header_{name2}_data.bmp")
            save_glitch_file(data1, header, pixels, out_path)
    
    print("-> Header Swap incrociati completati.")

    # --- FASE 2.5: Header Swap SOLO tra immagini originali diverse ---
    original_variants = [n for n in variant_names if n.endswith('_orig')]
    for i in range(len(original_variants)):
        nameA = original_variants[i]
        dataA = variant_files[nameA]
        h_sizeA = get_header_offset(dataA) or 0
        for j in range(i + 1, len(original_variants)):
            nameB = original_variants[j]
            dataB = variant_files[nameB]
            h_sizeB = get_header_offset(dataB) or 0
            
            # Swap 1: Header di A + Dati di B
            headerA = dataA[:h_sizeA]
            pixelsB = dataB[h_sizeB:]
            out_path = os.path.join("05_original_cross_swap", f"{nameA}_header_{nameB}_data.bmp")
            save_glitch_file(dataA, headerA, pixelsB, out_path)
            
            # Swap 2: Header di B + Dati di A
            headerB = dataB[:h_sizeB]
            pixelsA = dataA[h_sizeA:]
            out_path = os.path.join("05_original_cross_swap", f"{nameB}_header_{nameA}_data.bmp")
            save_glitch_file(dataB, headerB, pixelsA, out_path)
    print("-> Header Swap tra Originali puri completati!")

    # --- FASE 3: Data Splicing (50% metà e metà + Alternanza) ---
    for i in range(0, len(variant_names), 2):
        if i+1 >= len(variant_names): break
        
        nameA = variant_names[i]
        nameB = variant_names[i+1]
        
        dataA = variant_files[nameA]
        dataB = variant_files[nameB]
        
        h_sizeA = get_header_offset(dataA) or 0
        h_sizeB = get_header_offset(dataB) or 0
        
        headerA = dataA[:h_sizeA]
        pixelsA = dataA[h_sizeA:]
        pixelsB = dataB[h_sizeB:]
        
        # 3A. 50% di A + 50% di B
        half = len(pixelsA) // 2
        spliced_pixels_50 = pixelsA[:half] + pixelsB[:len(pixelsA)-half]
        out_path = os.path.join("03_data_splicing", f"{nameA}_50_{nameB}.bmp")
        save_glitch_file(dataA, headerA, spliced_pixels_50, out_path)
        
        # 3B. Interleaving 4 byte
        interleaved_pixels = bytearray()
        min_len = min(len(pixelsA), len(pixelsB))
        for x in range(0, min_len, 4):
            interleaved_pixels.extend(pixelsA[x:x+4])
            interleaved_pixels.extend(pixelsB[x:x+4])
        interleaved_pixels.extend(pixelsA[min_len:])
        
        out_path = os.path.join("03_data_splicing", f"{nameA}_interleaved_{nameB}.bmp")
        save_glitch_file(dataA, headerA, bytes(interleaved_pixels), out_path)

    print("-> Data Splicing completato.")

    # --- FASE 4: Mix "Sbizzarrisciti" ---
    for name in variant_names:
        data_orig = variant_files[name]
        h_size_orig = get_header_offset(data_orig) or 0
        
        others = [v for v in variant_names if v != name]
        if len(others) >= 1:
            random_other = random.choice(others)
            data_other = variant_files[random_other]
            h_size_other = get_header_offset(data_other) or 0
            
            header_swap = data_other[:h_size_other]
            pixels_orig = data_orig[h_size_orig:]
            
            out_path = os.path.join("04_random_mix_sbizzarriti", f"{name}_crazy_swap.bmp")
            save_glitch_file(data_orig, header_swap, pixels_orig, out_path)

            corrupted_pixels = bytearray(data_orig[h_size_orig:])
            if len(corrupted_pixels) > 10:
                pos = random.randint(0, len(corrupted_pixels)-1)
                corrupted_pixels[pos] = random.randint(0, 255)
            
            out_path = os.path.join("04_random_mix_sbizzarriti", f"{name}_byte_corruption.bmp")
            save_glitch_file(data_orig, data_orig[:h_size_orig], bytes(corrupted_pixels), out_path)

    print("-> Mix sbizzarriti completati!")

    # --- FASE 5: Conversione di tutti i BMP generati in JPEG ---
    print("\n--- Avvio conversione in JPEG ---")
    source_folders = [
        "01_varianti_base", 
        "02_header_swap", 
        "03_data_splicing", 
        "04_random_mix_sbizzarriti",
        "05_original_cross_swap"
    ]
    
    for folder in source_folders:
        if os.path.exists(folder):
            print(f"Convertendo {folder}...")
            convert_folder_to_jpeg(folder, os.path.join("99_jpeg_converted", folder))

if __name__ == "__main__":
    print("Avvio Multi-Variant Glitch Engine...")
    process_bmps_in_folder()
    print("\nTutti i glitch sono stati generati. Controlla le cartelle:")
    print("1. 01_varianti_base (Le 4 varianti di ogni BMP)")
    print("2. 02_header_swap (Header di una, dati di un'altra - Mix totale)")
    print("3. 03_data_splicing (Metà e metà o alternati)")
    print("4. 04_random_mix_sbizzarriti (Mix imprevedibili e corruzione byte)")
    print("5. 05_original_cross_swap (Header Swap SOLO tra due immagini originali diverse)")
    print("6. 99_jpeg_converted (Contiene tutte le cartelle convertite in JPG)")
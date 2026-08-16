#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Glitcher - Modifica di file BMP
Processa tutti i BMP in una cartella e per ognuno genera una struttura di cartelle
con varianti di glitch per header e pixel.
"""

import os
import sys
import random
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

# ======================================================================
# UTILITY
# ======================================================================

def ensure_dir(path: Path) -> None:
    """Crea la directory se non esiste."""
    path.mkdir(parents=True, exist_ok=True)

def random_byte() -> int:
    return random.randint(0, 255)

def random_bytes(n: int) -> bytes:
    return bytes(random_byte() for _ in range(n))

def clamp(val: int, min_val: int = 0, max_val: int = 255) -> int:
    return max(min_val, min(val, max_val))

def write_readme(folder: Path, file_list: List[Tuple[str, str]], title: str, description: str = "") -> None:
    """Crea un README.txt nella cartella."""
    readme_path = folder / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"{title}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if description:
            f.write("─" * 70 + "\n")
            f.write("DESCRIZIONE\n")
            f.write("─" * 70 + "\n\n")
            f.write(description + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("FILE GENERATI\n")
        f.write("─" * 70 + "\n\n")
        f.write("| # | Nome file | Descrizione |\n")
        f.write("|---|-----------|-------------|\n")
        for idx, (name, desc) in enumerate(file_list, 1):
            f.write(f"| {idx} | {name} | {desc} |\n")
        f.write("\n")
        f.write("─" * 70 + "\n")
        f.write("NOTE\n")
        f.write("─" * 70 + "\n\n")
        f.write("• L'originale è sempre incluso per riferimento.\n")
        f.write("• Se l'immagine non si apre, è normale: fa parte del glitch.\n")

# ======================================================================
# BMP PARSER
# ======================================================================

class BMPParser:
    """Parser per leggere e modificare file BMP."""
    
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        self._parse_header()
    
    def _parse_header(self):
        """Estrae le informazioni dall'header BMP."""
        data = self.data
        if len(data) < 54:
            raise ValueError("File BMP troppo piccolo")
        
        # Signature
        self.signature = data[0:2]
        
        # Offset dei dati dei pixel (byte 10-13)
        self.pixel_offset = (data[10] | (data[11] << 8) | 
                            (data[12] << 16) | (data[13] << 24))
        
        # Larghezza (byte 18-21) - little-endian
        self.width = (data[18] | (data[19] << 8) | 
                     (data[20] << 16) | (data[21] << 24))
        
        # Altezza (byte 22-25) - little-endian
        self.height = (data[22] | (data[23] << 8) | 
                      (data[24] << 16) | (data[25] << 24))
        
        # Profondità colore (byte 28-29)
        self.bpp = data[28] | (data[29] << 8)
        
        # Dimensione del file (byte 2-5)
        self.file_size = (data[2] | (data[3] << 8) | 
                         (data[4] << 16) | (data[5] << 24))
        
        # Dimensione dell'header (byte 14-17)
        self.header_size = (data[14] | (data[15] << 8) | 
                           (data[16] << 16) | (data[17] << 24))
    
    def save(self, path: Path) -> None:
        """Salva i dati modificati."""
        with open(path, 'wb') as f:
            f.write(self.data)
    
    def get_pixel_data(self) -> bytearray:
        """Restituisce i dati dei pixel."""
        return self.data[self.pixel_offset:]
    
    def get_pixel_len(self) -> int:
        """Restituisce la lunghezza dei dati pixel."""
        return len(self.data) - self.pixel_offset
    
    def set_pixel_data(self, new_data: bytes) -> None:
        """Sostituisce i dati dei pixel."""
        self.data = self.data[:self.pixel_offset] + bytearray(new_data)
        self._update_file_size(len(self.data))
    
    def _update_file_size(self, new_size: int) -> None:
        """Aggiorna il campo dimensione del file."""
        self.data[2] = new_size & 0xFF
        self.data[3] = (new_size >> 8) & 0xFF
        self.data[4] = (new_size >> 16) & 0xFF
        self.data[5] = (new_size >> 24) & 0xFF
    
    def set_width(self, width: int) -> None:
        """Modifica la larghezza."""
        self.width = width
        self.data[18] = width & 0xFF
        self.data[19] = (width >> 8) & 0xFF
        self.data[20] = (width >> 16) & 0xFF
        self.data[21] = (width >> 24) & 0xFF
    
    def set_height(self, height: int) -> None:
        """Modifica l'altezza."""
        self.height = height
        self.data[22] = height & 0xFF
        self.data[23] = (height >> 8) & 0xFF
        self.data[24] = (height >> 16) & 0xFF
        self.data[25] = (height >> 24) & 0xFF
    
    def set_pixel_offset(self, offset: int) -> None:
        """Modifica l'offset dei pixel."""
        self.pixel_offset = offset
        self.data[10] = offset & 0xFF
        self.data[11] = (offset >> 8) & 0xFF
        self.data[12] = (offset >> 16) & 0xFF
        self.data[13] = (offset >> 24) & 0xFF
    
    def set_bpp(self, bpp: int) -> None:
        """Modifica la profondità di colore."""
        self.bpp = bpp
        self.data[28] = bpp & 0xFF
        self.data[29] = (bpp >> 8) & 0xFF

# ======================================================================
# BMP GLITCHER
# ======================================================================

class BMPGlitcher:
    def __init__(self, input_path: Path, output_base: Path):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        
        try:
            self.parser = BMPParser(self.data)
        except ValueError as e:
            print(f"⚠️  {input_path.name}: {e}, salto.")
            self.parser = None
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.bmp'):
            filename += '.bmp'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    def get_pixel_counts(self, pixel_len: int) -> List[int]:
        """Genera una lista di conteggi per le modifiche."""
        counts = [1, 10, 100, 1000, 10000, 100000, 500000, 1000000]
        
        # Aggiungi conteggi casuali basati sulla dimensione
        random_counts = []
        for _ in range(5):
            if pixel_len > 100:
                rc = random.randint(10, min(pixel_len // 2, 1000000))
                random_counts.append(rc)
        
        counts.extend(random_counts)
        counts = sorted(set(counts))
        
        # Filtra quelli che superano la dimensione dei pixel
        counts = [c for c in counts if c < pixel_len]
        
        if not counts:
            counts = [1]
        
        return counts
    
    # ------------------------------------------------------------------
    # PIXEL: Sostituzione con valori casuali
    # ------------------------------------------------------------------
    def generate_pixel_modifications(self):
        """Genera varianti con byte modificati a caso."""
        folder = self.output_base / "pixel_modifications"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        pixel_len = self.parser.get_pixel_len()
        if pixel_len == 0:
            print(f"⚠️  Nessun dato pixel in {self.input_path.name}")
            return
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", "Originale")]
        
        counts = self.get_pixel_counts(pixel_len)
        
        for count in counts:
            if count >= pixel_len:
                count = pixel_len - 1
            if count <= 0:
                continue
            
            new_data = bytearray(self.data)
            pixel_start = self.parser.pixel_offset
            
            positions = random.sample(range(pixel_len), count)
            for pos in positions:
                new_data[pixel_start + pos] = random_byte()
            
            fname = f"{self.base_name}_pixel_mod_{count}"
            self.save_image(new_data, folder, fname)
            file_list.append((f"{fname}.bmp", f"Modificati {count} byte a caso nella zona pixel"))
        
        write_readme(folder, file_list, "BMP - Pixel: Sostituzione casuale",
                     "Sono stati modificati byte a caso nella zona dei pixel.\n"
                     "I byte sono stati sostituiti con valori casuali da 00 a FF.\n\n"
                     "La zona dei pixel inizia all'offset indicato nell'header (di solito 54).\n"
                     "Modificare questi byte altera direttamente i colori dell'immagine.")
        print(f"   ✅ pixel_modifications: {len(counts)} versioni")
    
    # ------------------------------------------------------------------
    # PIXEL: Eliminazione byte
    # ------------------------------------------------------------------
    def generate_pixel_deletions(self):
        """Genera varianti con byte eliminati."""
        folder = self.output_base / "pixel_deletions"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        pixel_len = self.parser.get_pixel_len()
        if pixel_len == 0:
            return
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", "Originale")]
        
        counts = self.get_pixel_counts(pixel_len)
        
        for count in counts:
            if count >= pixel_len:
                count = pixel_len - 1
            if count <= 0:
                continue
            
            new_data = bytearray(self.data)
            pixel_start = self.parser.pixel_offset
            
            # Seleziona posizioni da eliminare
            positions = sorted(random.sample(range(pixel_len), count), reverse=True)
            
            # Elimina i byte (dal fondo per non shiftare le posizioni)
            for pos in positions:
                del new_data[pixel_start + pos]
            
            # Aggiorna la dimensione del file
            parser = BMPParser(new_data)
            parser._update_file_size(len(new_data))
            
            fname = f"{self.base_name}_pixel_del_{count}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"Eliminati {count} byte dalla zona pixel"))
        
        write_readme(folder, file_list, "BMP - Pixel: Eliminazione byte",
                     "Sono stati eliminati byte dalla zona dei pixel.\n"
                     "La dimensione del file è stata ridotta di conseguenza.\n\n"
                     "L'eliminazione di byte sposta i pixel successivi, creando distorsioni.\n"
                     "La zona dei pixel inizia all'offset indicato nell'header (di solito 54).")
        print(f"   ✅ pixel_deletions: {len(counts)} versioni")
    
    # ------------------------------------------------------------------
    # PIXEL: Inserimento byte 00
    # ------------------------------------------------------------------
    def generate_pixel_insert_00(self):
        """Genera varianti con byte 00 inseriti."""
        folder = self.output_base / "pixel_insert_00"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        pixel_len = self.parser.get_pixel_len()
        if pixel_len == 0:
            return
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", "Originale")]
        
        counts = self.get_pixel_counts(pixel_len)
        counts = [c for c in counts if c < pixel_len * 2]
        
        for count in counts:
            if count <= 0:
                continue
            
            new_data = bytearray(self.data)
            pixel_start = self.parser.pixel_offset
            
            # Scegli posizioni casuali dove inserire
            positions = sorted(random.sample(range(pixel_len + count), count), reverse=True)
            
            for pos in positions:
                new_data.insert(pixel_start + pos, 0x00)
            
            # Aggiorna la dimensione del file
            parser = BMPParser(new_data)
            parser._update_file_size(len(new_data))
            
            fname = f"{self.base_name}_pixel_ins00_{count}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"Inseriti {count} byte 00 nella zona pixel"))
        
        write_readme(folder, file_list, "BMP - Pixel: Inserimento byte 00",
                     "Sono stati inseriti byte con valore 00 nella zona dei pixel.\n"
                     "La dimensione del file è stata aumentata di conseguenza.\n\n"
                     "L'inserimento di byte sposta i pixel successivi, creando distorsioni.\n"
                     "Il valore 00 in un pixel corrisponde a colore nero.\n"
                     "La zona dei pixel inizia all'offset indicato nell'header (di solito 54).")
        print(f"   ✅ pixel_insert_00: {len(counts)} versioni")
    
    # ------------------------------------------------------------------
    # PIXEL: Inserimento byte FF
    # ------------------------------------------------------------------
    def generate_pixel_insert_FF(self):
        """Genera varianti con byte FF inseriti."""
        folder = self.output_base / "pixel_insert_FF"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        pixel_len = self.parser.get_pixel_len()
        if pixel_len == 0:
            return
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", "Originale")]
        
        counts = self.get_pixel_counts(pixel_len)
        counts = [c for c in counts if c < pixel_len * 2]
        
        for count in counts:
            if count <= 0:
                continue
            
            new_data = bytearray(self.data)
            pixel_start = self.parser.pixel_offset
            
            positions = sorted(random.sample(range(pixel_len + count), count), reverse=True)
            
            for pos in positions:
                new_data.insert(pixel_start + pos, 0xFF)
            
            parser = BMPParser(new_data)
            parser._update_file_size(len(new_data))
            
            fname = f"{self.base_name}_pixel_insFF_{count}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"Inseriti {count} byte FF nella zona pixel"))
        
        write_readme(folder, file_list, "BMP - Pixel: Inserimento byte FF",
                     "Sono stati inseriti byte con valore FF nella zona dei pixel.\n"
                     "La dimensione del file è stata aumentata di conseguenza.\n\n"
                     "L'inserimento di byte sposta i pixel successivi, creando distorsioni.\n"
                     "Il valore FF in un pixel corrisponde a colore bianco.\n"
                     "La zona dei pixel inizia all'offset indicato nell'header (di solito 54).")
        print(f"   ✅ pixel_insert_FF: {len(counts)} versioni")
    
    # ------------------------------------------------------------------
    # HEADER: Mix larghezza + altezza
    # ------------------------------------------------------------------
    def generate_header_mix(self):
        """Genera varianti che modificano larghezza e altezza insieme."""
        folder = self.output_base / "header_mix"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        original_width = self.parser.width
        original_height = self.parser.height
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", f"Originale ({original_width}x{original_height})")]
        
        # Modifiche progressive (mantenendo le proporzioni)
        ratios = [0.10, 0.25, 0.50, 0.75, 1.25, 1.50, 2.00, 3.00, 5.00]
        
        for i, ratio in enumerate(ratios, 1):
            new_w = int(original_width * ratio)
            new_h = int(original_height * ratio)
            
            if new_w < 1:
                new_w = 1
            if new_h < 1:
                new_h = 1
            if new_w > 10000:
                new_w = 10000
            if new_h > 10000:
                new_h = 10000
            
            if new_w == original_width and new_h == original_height:
                continue
            
            new_data = bytearray(self.data)
            parser = BMPParser(new_data)
            parser.set_width(new_w)
            parser.set_height(new_h)
            
            pct = int(ratio * 100)
            fname = f"{self.base_name}_header_mix_{i}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"Dimensione: {original_width}x{original_height} → {new_w}x{new_h} ({pct}%)"))
        
        # 10 combinazioni casuali (larghezza e altezza indipendenti)
        for i in range(10, 20):
            if random.random() < 0.5:
                new_w = random.randint(1, min(original_width * 3, 10000))
            else:
                new_w = random.randint(1, original_width * 5)
            
            if random.random() < 0.5:
                new_h = random.randint(1, min(original_height * 3, 10000))
            else:
                new_h = random.randint(1, original_height * 5)
            
            if new_w < 1:
                new_w = 1
            if new_h < 1:
                new_h = 1
            if new_w > 10000:
                new_w = 10000
            if new_h > 10000:
                new_h = 10000
            
            if new_w == original_width and new_h == original_height:
                continue
            
            new_data = bytearray(self.data)
            parser = BMPParser(new_data)
            parser.set_width(new_w)
            parser.set_height(new_h)
            
            fname = f"{self.base_name}_header_mix_rand_{i-9}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"Dimensione random: {new_w}x{new_h}"))
        
        write_readme(folder, file_list, "BMP - Header: Mix Larghezza e Altezza",
                     f"Sono state generate varianti con diverse combinazioni di larghezza e altezza.\n\n"
                     f"Larghezza originale: {original_width} pixel (byte 18-21 in little-endian)\n"
                     f"Altezza originale: {original_height} pixel (byte 22-25 in little-endian)\n\n"
                     "In HexFiend, questi byte si trovano nell'header BMP (primi 54 byte).\n"
                     "Modificare questi valori altera la forma dell'immagine.")
        print(f"   ✅ header_mix: {len(file_list)-1} versioni")
    
    # ------------------------------------------------------------------
    # HEADER: Offset pixel
    # ------------------------------------------------------------------
    def generate_header_offset(self):
        """Genera varianti che modificano l'offset dei pixel."""
        folder = self.output_base / "header_offset"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        original_offset = self.parser.pixel_offset
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", f"Originale (offset: {original_offset})")]
        
        # Modifiche progressive dell'offset
        offsets = [
            54, 100, 200, 500, 1000, 2000, 5000,
            original_offset + 10, original_offset + 50, original_offset + 100,
            original_offset - 10, original_offset - 50, original_offset - 100,
        ]
        
        # Filtra valori validi (non negativi e diversi dall'originale)
        valid_offsets = sorted(set([o for o in offsets if o >= 54 and o != original_offset]))
        
        for i, new_offset in enumerate(valid_offsets[:15], 1):
            new_data = bytearray(self.data)
            parser = BMPParser(new_data)
            parser.set_pixel_offset(new_offset)
            
            diff = new_offset - original_offset
            sign = "+" if diff > 0 else ""
            
            fname = f"{self.base_name}_header_offset_{i}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"Offset: {original_offset} → {new_offset} ({sign}{diff} byte)"))
        
        write_readme(folder, file_list, "BMP - Header: Modifica Offset Pixel",
                     f"Sono state generate varianti con offset dei pixel diversi.\n\n"
                     f"Offset originale: {original_offset} byte (byte 10-13 in little-endian).\n\n"
                     "L'offset indica dove iniziano i dati dei pixel nel file.\n"
                     "In HexFiend, questo valore si trova ai byte 10-13 dell'header BMP.\n"
                     "Modificarlo fa sì che il computer legga i pixel da un punto diverso,\n"
                     "producendo shift visivi o colori inaspettati.")
        print(f"   ✅ header_offset: {len(valid_offsets)} versioni")
    
    # ------------------------------------------------------------------
    # HEADER: Profondità colore (BPP)
    # ------------------------------------------------------------------
    def generate_header_bpp(self):
        """Genera varianti che modificano la profondità di colore."""
        folder = self.output_base / "header_bpp"
        ensure_dir(folder)
        
        if self.parser is None:
            return
        
        original_bpp = self.parser.bpp
        
        # Copia originale
        shutil.copy2(self.input_path, folder / f"{self.base_name}_original.bmp")
        
        file_list = [(f"{self.base_name}_original.bmp", f"Originale (BPP: {original_bpp})")]
        
        # Tutti i valori BPP possibili (standard + non standard per glitch)
        bpp_values = [
            1, 2, 4, 8, 12, 16, 24, 32,
            48, 64, 96, 128, 255
        ]
        
        for i, new_bpp in enumerate(bpp_values, 1):
            if new_bpp == original_bpp:
                continue
            
            new_data = bytearray(self.data)
            parser = BMPParser(new_data)
            parser.set_bpp(new_bpp)
            
            fname = f"{self.base_name}_header_bpp_{i}"
            parser.save(folder / f"{fname}.bmp")
            file_list.append((f"{fname}.bmp", f"BPP: {original_bpp} → {new_bpp} bit per pixel"))
        
        write_readme(folder, file_list, "BMP - Header: Modifica Profondità Colore",
                     f"Sono state generate varianti con diverse profondità di colore.\n\n"
                     f"BPP originale: {original_bpp} bit per pixel (byte 28-29 in little-endian).\n\n"
                     "Il BPP (Bits Per Pixel) determina quanti bit vengono usati per ogni pixel.\n"
                     "Valori standard: 1, 4, 8, 16, 24, 32.\n"
                     "Valori non standard (come 48, 64, 96, 255) producono glitch estremi.\n"
                     "In HexFiend, questo valore si trova ai byte 28-29 dell'header BMP.")
        print(f"   ✅ header_bpp: {len(bpp_values)} versioni")
    
    # ------------------------------------------------------------------
    # RUN ALL
    # ------------------------------------------------------------------
    def run_all(self):
        if self.parser is None:
            return
        
        print(f"\n📷 Elaborazione di: {self.input_path.name}")
        print(f"📁 Output in: {self.output_base}")
        print(f"📊 Dimensioni: {self.parser.width}x{self.parser.height}")
        print(f"📊 Offset pixel: {self.parser.pixel_offset}")
        print(f"📊 BPP: {self.parser.bpp}")
        print(f"📊 Pixel totali: {self.parser.get_pixel_len()}")
        print("-" * 50)
        
        # Pixel
        self.generate_pixel_modifications()
        self.generate_pixel_deletions()
        self.generate_pixel_insert_00()
        self.generate_pixel_insert_FF()
        
        # Header
        self.generate_header_mix()      # Larghezza + Altezza insieme
        self.generate_header_offset()   # Solo offset
        self.generate_header_bpp()      # Solo BPP
        
        print(f"✅ Completato {self.input_path.name}")

# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Glitcher - Modifica di file BMP"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_glitch_output',
                        help='Directory di output principale (default: bmp_glitch_output)')
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"❌ Directory input non trovata: {input_dir}")
        sys.exit(1)
    
    bmp_files = []
    for ext in ['.bmp', '.BMP']:
        bmp_files.extend(input_dir.glob(f"*{ext}"))
    
    if not bmp_files:
        print(f"❌ Nessun file BMP trovato in {input_dir}")
        sys.exit(1)
    
    print(f"🔍 Trovati {len(bmp_files)} file BMP")
    print(f"📁 Output principale: {output_dir}")
    print("=" * 70)
    
    for bmp_path in bmp_files:
        img_output = output_dir / bmp_path.stem
        ensure_dir(img_output)
        glitcher = BMPGlitcher(bmp_path, img_output)
        glitcher.run_all()
    
    print("\n" + "=" * 70)
    print("✅ TUTTE LE IMMAGINI PROCESSATE!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
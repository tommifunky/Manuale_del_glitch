#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audacity-Style BMP Glitcher (Batch & Viewable) - CORRETTO
Replica esattamente le manipolazioni di Audacity su dati RAW (8-bit, 16-bit, 24-bit, U-Law),
ma preserva la struttura del file per garantire che ogni output sia un BMP apribile.
"""

import os
import sys
import random
import struct
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Callable, Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("❌ ERRORE: numpy è richiesto per questo script. Installa con: pip install numpy")
    sys.exit(1)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  AVVERTIMENTO: Pillow non trovato. La tecnica 'Header Swap' (rotazione) sarà saltata.")
    print("   Installa con: pip install pillow")

# ======================================================================
# 1. INTERPRETE FORMATI AUDIO (Replica esatta di Audacity)
# ======================================================================

class AudioInterpreter:
    """Converte byte grezzi in array numerici e viceversa, come Audacity."""
    
    @staticmethod
    def to_samples(data: bytes, fmt: str) -> np.ndarray:
        """Converte bytes in campioni audio secondo il formato."""
        if fmt == '8bit':
            return np.frombuffer(data, dtype=np.uint8).astype(np.float32)
        elif fmt == '16bit':
            return np.frombuffer(data, dtype=np.int16).astype(np.float32)
        elif fmt == '24bit':
            # Gestione robusta del 24-bit little-endian con segno
            arr = np.frombuffer(data, dtype=np.uint8)
            valid_len = (len(arr) // 3) * 3
            arr = arr[:valid_len].reshape(-1, 3)
            
            padded = np.zeros((len(arr), 4), dtype=np.uint8)
            padded[:, :3] = arr
            
            # Sign extension: se il bit più significativo del 3° byte è 1, il numero è negativo
            sign_bit = (arr[:, 2] & 0x80).astype(bool)
            padded[sign_bit, 3] = 0xFF
            
            return padded.view(np.int32).astype(np.float32).flatten()
            
        elif fmt == 'ulaw':
            # Decodifica U-Law ITU-T G.711
            u = np.frombuffer(data, dtype=np.uint8)
            u = ~u & 0xFF
            sign = (u & 0x80).astype(np.float32)
            exponent = ((u >> 4) & 0x07).astype(np.float32)
            mantissa = (u & 0x0F).astype(np.float32)
            sample = (mantissa * 8.0) + 132.0
            sample = sample * (2.0 ** exponent)
            return np.where(sign > 0, -sample, sample)
        else:
            raise ValueError(f"Formato non supportato: {fmt}")

    @staticmethod
    def from_samples(samples: np.ndarray, fmt: str, original_len: int) -> bytes:
        """Converte campioni audio nuovamente in byte grezzi, mantenendo la lunghezza originale."""
        # Appiattisce l'array per evitare problemi di shape (broadcasting)
        samples = np.asarray(samples).flatten()
        
        if fmt == '8bit':
            clipped = np.clip(samples, 0, 255).astype(np.uint8)
        elif fmt == '16bit':
            clipped = np.clip(samples, -32768, 32767).astype(np.int16)
        elif fmt == '24bit':
            clipped = np.clip(samples, -8388608, 8388607).astype(np.int32)
            
            # Estrazione esplicita e sicura dei 3 byte little-endian
            b0 = (clipped & 0xFF).astype(np.uint8)
            b1 = ((clipped >> 8) & 0xFF).astype(np.uint8)
            b2 = ((clipped >> 16) & 0xFF).astype(np.uint8)
            
            bytes_24 = np.empty((len(clipped), 3), dtype=np.uint8)
            bytes_24[:, 0] = b0
            bytes_24[:, 1] = b1
            bytes_24[:, 2] = b2
            
            clipped = bytes_24.flatten()
            
        elif fmt == 'ulaw':
            # Codifica U-Law
            sign = np.where(samples < 0, 0x80, 0).astype(np.int32)
            linear = np.abs(samples).astype(np.int32) + 132
            linear = np.clip(linear, 0, 32635)
            
            # Calcolo esponente e mantissa vettorizzato
            exponent = np.zeros_like(linear, dtype=np.int32)
            for i in range(7, -1, -1):
                exponent = np.where(linear >= (1 << (i + 3)), i, exponent)
            
            mantissa = (linear >> (exponent + 3)) & 0x0F
            u = ~(sign | (exponent << 4) | mantissa) & 0xFF
            clipped = u.astype(np.uint8)
        else:
            raise ValueError(f"Formato non supportato: {fmt}")
            
        result = clipped.tobytes()
        # Padding o troncamento per garantire lunghezza identica all'originale (cruciale per l'header BMP)
        if len(result) < original_len:
            result += b'\x00' * (original_len - len(result))
        return result[:original_len]

# ======================================================================
# 2. EFFETTI AUDIO (Replica degli effetti di Audacity)
# ======================================================================

class Effects:
    @staticmethod
    def echo(samples: np.ndarray, delay_samples: int, decay: float) -> np.ndarray:
        """Audacity: Effetto > Eco"""
        out = np.copy(samples)
        if delay_samples > 0 and delay_samples < len(samples):
            out[delay_samples:] += samples[:-delay_samples] * decay
        return out

    @staticmethod
    def distort(samples: np.ndarray, drive: float) -> np.ndarray:
        """Audacity: Effetto > Distorsione (Soft Clipping / Tanh)"""
        max_val = np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1.0
        normalized = samples / max_val
        distorted = np.tanh(normalized * drive)
        return distorted * max_val

    @staticmethod
    def duplicate_overlay(samples: np.ndarray, shift: int) -> np.ndarray:
        """Audacity: Duplica traccia, sposta di X secondi, mixa (50% volume ciascuna)"""
        out = np.copy(samples) * 0.5
        if shift > 0 and shift < len(samples):
            out[shift:] += samples[:-shift] * 0.5
        elif shift < 0:
            shift = abs(shift)
            out[:-shift] += samples[shift:] * 0.5
        return out

    @staticmethod
    def reverse_chunks(samples: np.ndarray, chunk_size: int) -> np.ndarray:
        """Audacity: Seleziona blocchi e Inverti"""
        out = np.copy(samples)
        for i in range(0, len(samples) - chunk_size + 1, chunk_size):
            out[i:i+chunk_size] = samples[i:i+chunk_size][::-1]
        return out

    @staticmethod
    def remove_pieces(samples: np.ndarray, piece_size: int, density: float) -> np.ndarray:
        """Audacity: Seleziona pezzi casuali e applica 'Silenzio' (o rumore)"""
        out = np.copy(samples)
        num_pieces = int((len(samples) // piece_size) * density)
        # Evita errori se num_pieces è 0 o troppo alto
        num_pieces = max(0, min(num_pieces, len(samples) - piece_size))
        if num_pieces > 0:
            indices = random.sample(range(0, len(samples) - piece_size), num_pieces)
            for idx in indices:
                noise = np.random.uniform(np.min(samples), np.max(samples), piece_size)
                out[idx:idx+piece_size] = noise
        return out

    @staticmethod
    def stretch_stutter(samples: np.ndarray, stretch_factor: int) -> np.ndarray:
        """Audacity: Simulazione allungamento/stutter raw (duplica campioni)"""
        out = np.copy(samples)
        if stretch_factor > 1 and len(samples) > stretch_factor:
            out[stretch_factor:] = samples[:-stretch_factor]
        return out

# ======================================================================
# 3. MOTORE DI GLITCH
# ======================================================================

class BMPGlitcher:
    def __init__(self, input_path: Path, output_base: Path, all_images: List[Path]):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        self.all_images = all_images 
        
        with open(input_path, 'rb') as f:
            self.raw_data = f.read()
            
        if self.raw_data[:2] != b'BM':
            print(f"⚠️  {input_path.name} non è un BMP valido.")
            self.is_valid = False
            return
            
        self.is_valid = True
        self.data_offset = struct.unpack('<I', self.raw_data[10:14])[0]
        self.header = self.raw_data[:self.data_offset]
        self.pixel_data = self.raw_data[self.data_offset:]
        self.original_len = len(self.pixel_data)

    def save_bmp(self, pixel_data: bytes, folder: Path, filename: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{filename}.bmp"
        with open(path, 'wb') as f:
            f.write(self.header)      # Header originale intatto = FILE APRIIBILE
            f.write(pixel_data)
        return path

    def apply_and_save(self, effect_func: Callable, fmt: str, folder: Path, suffix: str) -> Path:
        """Applica un effetto interpretando i dati come un formato audio specifico."""
        samples = AudioInterpreter.to_samples(self.pixel_data, fmt)
        modified_samples = effect_func(samples)
        new_bytes = AudioInterpreter.from_samples(modified_samples, fmt, self.original_len)
        
        fname = f"{self.base_name}_{fmt}_{suffix}"
        return self.save_bmp(new_bytes, folder, fname)

    def run_all_techniques(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name}")
        base_folder = self.output_base / self.base_name
        base_folder.mkdir(parents=True, exist_ok=True)

        formats = ['8bit', '16bit', '24bit', 'ulaw']
        file_list = []

        # --- 1. ECHI DIVERSI ---
        folder = base_folder / "01_Echi"
        for fmt in formats:
            for delay_mult in [0.05, 0.1, 0.2]:
                delay = int(len(self.pixel_data) * delay_mult)
                decay = random.uniform(0.3, 0.8)
                effect = lambda s, d=delay, dc=decay: Effects.echo(s, d, dc)
                path = self.apply_and_save(effect, fmt, folder, f"echo_d{int(delay_mult*100)}_dec{int(decay*10)}")
                file_list.append((path.name, f"Eco {fmt}", f"Delay {delay_mult}, Decay {decay:.1f}"))

        # --- 2. ALLUNGAMENTO / STUTTER ---
        folder = base_folder / "02_Allungamento_Stutter"
        for fmt in formats:
            for factor in [2, 5, 10, 50]:
                effect = lambda s, f=factor: Effects.stretch_stutter(s, f)
                path = self.apply_and_save(effect, fmt, folder, f"stutter_x{factor}")
                file_list.append((path.name, f"Stutter {fmt}", f"Fattore {factor}"))

        # --- 3. DISTORSIONE ---
        folder = base_folder / "03_Distorsione"
        for fmt in formats:
            for drive in [2.0, 5.0, 10.0, 20.0]:
                effect = lambda s, d=drive: Effects.distort(s, d)
                path = self.apply_and_save(effect, fmt, folder, f"dist_drive{int(drive)}")
                file_list.append((path.name, f"Distorsione {fmt}", f"Drive {drive}"))

        # --- 4. DUPLICA E SOVRAPPONI (2 Tracce) ---
        folder = base_folder / "04_Duplica_Sovrapponi"
        for fmt in formats:
            for shift_pct in [0.1, 0.25, 0.5]:
                shift = int(len(self.pixel_data) * shift_pct)
                effect = lambda s, sh=shift: Effects.duplicate_overlay(s, sh)
                path = self.apply_and_save(effect, fmt, folder, f"overlay_shift{int(shift_pct*100)}")
                file_list.append((path.name, f"Overlay {fmt}", f"Shift {shift_pct*100}%"))

        # --- 5. REVERSE A BLOCCHI ---
        folder = base_folder / "05_Reverse_Blocchi"
        for fmt in formats:
            for chunk in [512, 1024, 2048, 4096]:
                effect = lambda s, c=chunk: Effects.reverse_chunks(s, c)
                path = self.apply_and_save(effect, fmt, folder, f"rev_chunk{chunk}")
                file_list.append((path.name, f"Reverse {fmt}", f"Chunk {chunk} byte"))

        # --- 6. RIMUOVI PEZZI (Sostituiti con rumore) ---
        folder = base_folder / "06_Rimuovi_Pezzi"
        for fmt in formats:
            for density in [0.1, 0.3, 0.5]:
                piece_size = random.choice([256, 512, 1024])
                effect = lambda s, p=piece_size, d=density: Effects.remove_pieces(s, p, d)
                path = self.apply_and_save(effect, fmt, folder, f"remove_dens{int(density*10)}")
                file_list.append((path.name, f"Rimozione {fmt}", f"Densità {density}"))

        # --- 7. HEADER SWAP (Richiede PIL) ---
        if HAS_PIL and len(self.all_images) > 0:
            folder = base_folder / "07_Header_Swap"
            other_path = random.choice([p for p in self.all_images if p != self.input_path]) if len(self.all_images) > 1 else self.input_path
            
            try:
                img_other = Image.open(other_path)
                img_rotated = img_other.rotate(90, expand=True)
                
                temp_path = self.output_base / "temp_rotated.bmp"
                img_rotated.save(temp_path, "BMP")
                
                with open(temp_path, 'rb') as f:
                    rotated_data = f.read()
                
                rot_offset = struct.unpack('<I', rotated_data[10:14])[0]
                rot_header = rotated_data[:rot_offset]
                rot_pixels = rotated_data[rot_offset:]
                
                # 1. Header Originale + Dati Ruotati
                if len(rot_pixels) > self.original_len:
                    swap_pixels_1 = rot_pixels[:self.original_len]
                else:
                    swap_pixels_1 = rot_pixels + b'\x00' * (self.original_len - len(rot_pixels))
                
                path1 = self.save_bmp(swap_pixels_1, folder, f"{self.base_name}_headerMIO_dataROTATA")
                file_list.append((path1.name, "Header Swap", "Mio Header + Dati Ruotati"))

                # 2. Header Ruotato + Dati Originali
                target_len = len(rot_pixels)
                if len(self.pixel_data) > target_len:
                    swap_pixels_2 = self.pixel_data[:target_len]
                else:
                    swap_pixels_2 = self.pixel_data + b'\x00' * (target_len - len(self.pixel_data))
                
                class TempGlitcher:
                    def __init__(self, hdr, orig_len):
                        self.header = hdr
                        self.original_len = orig_len
                    def save_bmp(self, pix, fld, fnm):
                        fld.mkdir(parents=True, exist_ok=True)
                        pth = fld / f"{fnm}.bmp"
                        with open(pth, 'wb') as f:
                            f.write(self.header)
                            f.write(pix)
                        return pth
                
                tg = TempGlitcher(rot_header, target_len)
                path2 = tg.save_bmp(swap_pixels_2, folder, f"{other_path.stem}_headerROTATO_dataMIO")
                file_list.append((path2.name, "Header Swap Inverso", "Header Ruotato + Miei Dati"))
                
                temp_path.unlink() # Pulisci
            except Exception as e:
                print(f"   ⚠️  Header Swap fallito per {other_path.name}: {e}")

        # --- 8. UNIONE IMMAGINI (Splicing) ---
        if len(self.all_images) > 1:
            folder = base_folder / "08_Unione_Immagini"
            other_path = random.choice([p for p in self.all_images if p != self.input_path])
            with open(other_path, 'rb') as f:
                other_raw = f.read()
            other_offset = struct.unpack('<I', other_raw[10:14])[0]
            other_pixels = other_raw[other_offset:]
            
            min_len = min(self.original_len, len(other_pixels))
            
            for fmt in ['8bit', '16bit']:
                for splice_pct in [0.25, 0.5, 0.75]:
                    splice_point = int(min_len * splice_pct)
                    
                    mixed = bytearray(self.pixel_data[:splice_point])
                    mixed.extend(other_pixels[splice_point:min_len])
                    
                    if len(mixed) < self.original_len:
                        mixed.extend(b'\x00' * (self.original_len - len(mixed)))
                    
                    path = self.save_bmp(bytes(mixed), folder, f"{self.base_name}_splice_{int(splice_pct*100)}_{other_path.stem}")
                    file_list.append((path.name, f"Splice {fmt}", f"{int(splice_pct*100)}% da {other_path.name}"))

        # Genera README
        self._generate_readme(base_folder, file_list)
        print(f"   ✅ Generate {len(file_list)} varianti per {self.base_name}")

    def _generate_readme(self, folder: Path, file_list: List[Tuple[str, str, str]]):
        readme_path = folder / "README_AUDACITY_RECIPES.txt"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("RICETTE AUDACITY PER RIPRODURRE QUESTI GLITCH\n")
            f.write("=" * 70 + "\n\n")
            f.write("ISTRUZIONI BASE:\n")
            f.write("1. Apri Audacity.\n")
            f.write("2. File > Importa > Dati Grezzi (Raw Data).\n")
            f.write("3. Scegli il formato indicato (8-bit, 16-bit, 24-bit o U-Law), Codifica Little-Endian.\n")
            f.write("4. Applica l'effetto descritto.\n")
            f.write("5. File > Esporta > Esporta come Dati Grezzi (Raw).\n")
            f.write("6. Rinomina il file da .raw a .bmp.\n\n")
            f.write("=" * 70 + "\n")
            f.write("DETTAGLIO FILE GENERATI\n")
            f.write("=" * 70 + "\n\n")
            f.write("| File | Formato Audacity | Effetto da applicare |\n")
            f.write("|------|------------------|----------------------|\n")
            for name, fmt, desc in file_list:
                f.write(f"| {name} | {fmt} | {desc} |\n")
            
            f.write("\n" + "=" * 70 + "\n")
            f.write("NOTE SULLE TECNICHE SPECIALI\n")
            f.write("=" * 70 + "\n")
            f.write("• HEADER SWAP: Richiede di ruotare un'immagine in un editor, esportarla, \n  e incollare il suo header (primi 54+ byte) su un'altra immagine con un editor esadecimale.\n")
            f.write("• UNIONE IMMAGINI: Copia i byte da un'immagine e incollali a metà del payload di un'altra.\n")

# ======================================================================
# 4. MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="Audacity-Style BMP Glitcher (Batch)")
    parser.add_argument('-i', '--input-dir', default='.', help='Directory contenente i BMP')
    parser.add_argument('-o', '--output-dir', default='audacity_bmp_glitch_output', help='Directory di output')
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"❌ Directory input non trovata: {input_dir}")
        sys.exit(1)
    
    bmp_files = list(input_dir.glob("*.bmp")) + list(input_dir.glob("*.BMP"))
    if not bmp_files:
        print(f"❌ Nessun file BMP trovato in {input_dir}")
        sys.exit(1)
    
    print(f"🔍 Trovati {len(bmp_files)} file BMP")
    print(f"⚡ Motore: NumPy vettorizzato (velocità massima)")
    print("=" * 70)
    
    for bmp_path in bmp_files:
        glitcher = BMPGlitcher(bmp_path, output_dir, bmp_files)
        glitcher.run_all_techniques()
    
    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("💡 Ogni cartella contiene un README con le istruzioni per replicare il glitch in Audacity.")
    print("=" * 70)

if __name__ == "__main__":
    main()
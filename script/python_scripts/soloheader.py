#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Header Mixer - Modifica solo larghezza e altezza dei file BMP.
Gestisce correttamente l'altezza con segno (BMP usa signed int per l'altezza).
"""

import os
import sys
import random
import shutil
import argparse
import struct
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

# ======================================================================
# UTILITY
# ======================================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def clamp(val: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(val, max_val))

def write_readme(folder: Path, file_list: List[Tuple[str, str]], 
                 original_w: int, original_h: int, 
                 ratios: List[float], random_count: int) -> None:
    readme_path = folder / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("BMP HEADER MIX - Varianti di larghezza e altezza\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"📐 Originale: {original_w} x {abs(original_h)} pixel (altezza con segno: {original_h})\n")
        f.write(f"📊 Rapporti scalati: {', '.join(str(r) for r in ratios)}\n")
        f.write(f"🎲 Combinazioni casuali: {random_count}\n\n")
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
        f.write("• I valori di larghezza e altezza sono nei byte 18-25 (little-endian).\n")
        f.write("• L'altezza è un intero con segno (negativo = origine in alto a sinistra).\n")

# ======================================================================
# BMP PARSER (con supporto signed per altezza)
# ======================================================================

class BMPParser:
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        self._parse_header()
    
    def _parse_header(self):
        data = self.data
        if len(data) < 54:
            raise ValueError("File BMP troppo piccolo (minimo 54 byte).")
        # Larghezza: unsigned 32-bit
        self.width = struct.unpack('<I', data[18:22])[0]
        # Altezza: signed 32-bit (valori negativi indicano orientamento dall'alto)
        self.height = struct.unpack('<i', data[22:26])[0]
    
    def set_width(self, width: int):
        self.width = width
        struct.pack_into('<I', self.data, 18, width)
    
    def set_height(self, height: int):
        self.height = height
        struct.pack_into('<i', self.data, 22, height)
    
    def save(self, path: Path) -> None:
        with open(path, 'wb') as f:
            f.write(self.data)

# ======================================================================
# HEADER MIXER
# ======================================================================

class HeaderMixer:
    def __init__(self, input_path: Path, output_dir: Path, 
                 min_dim: int = 1, max_dim: int = 10000):
        self.input_path = input_path
        self.output_dir = output_dir
        self.min_dim = min_dim
        self.max_dim = max_dim
        self.base_name = input_path.stem
        
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        
        try:
            self.parser = BMPParser(self.data)
        except ValueError as e:
            print(f"⚠️  {input_path.name}: {e} → salto.")
            self.parser = None
    
    def _make_variant(self, new_w: int, new_h: int, suffix: str) -> Tuple[Optional[Path], Optional[str]]:
        """Crea una variante con le nuove dimensioni e restituisce (percorso, descrizione)."""
        # Clamp per sicurezza
        new_w = clamp(new_w, self.min_dim, self.max_dim)
        # Per l'altezza, manteniamo il segno originale se possibile
        # Se l'originale era negativo, anche la nuova altezza dovrebbe essere negativa
        # per preservare l'orientamento. Ma se new_h è positivo, applichiamo il segno originale.
        original_h = self.parser.height
        sign = -1 if original_h < 0 else 1
        # Usiamo il valore assoluto per calcolare, poi riapplichiamo il segno
        new_h_abs = abs(new_h)
        new_h_abs = clamp(new_h_abs, self.min_dim, self.max_dim)
        new_h = sign * new_h_abs
        
        # Se le dimensioni sono identiche all'originale, non generare
        if new_w == self.parser.width and new_h == self.parser.height:
            return None, None
        
        new_data = bytearray(self.data)
        parser = BMPParser(new_data)
        parser.set_width(new_w)
        parser.set_height(new_h)
        
        fname = f"{self.base_name}_{suffix}.bmp"
        path = self.output_dir / fname
        parser.save(path)
        desc = f"Dimensioni: {self.parser.width}x{abs(self.parser.height)} ({self.parser.height}) → {new_w}x{abs(new_h)} ({new_h})"
        return path, desc
    
    def generate(self, ratios: Optional[List[float]] = None, 
                 random_count: int = 10,
                 seed: Optional[int] = None) -> None:
        if self.parser is None:
            return
        
        if seed is not None:
            random.seed(seed)
        
        ensure_dir(self.output_dir)
        
        # Copia originale
        orig_path = self.output_dir / f"{self.base_name}_original.bmp"
        shutil.copy2(self.input_path, orig_path)
        file_list = [(orig_path.name, f"Originale ({self.parser.width}x{abs(self.parser.height)})")]
        
        original_w = self.parser.width
        original_h = self.parser.height
        original_h_abs = abs(original_h)
        sign = -1 if original_h < 0 else 1
        
        # 1. Varianti proporzionali (stesso rapporto, mantenendo segno)
        if ratios is None:
            ratios = [0.10, 0.25, 0.50, 0.75, 1.25, 1.50, 2.00, 3.00, 5.00]
        
        for i, ratio in enumerate(ratios, 1):
            new_w = int(original_w * ratio)
            new_h_abs = int(original_h_abs * ratio)
            new_h = sign * new_h_abs
            # Clamp
            new_w = clamp(new_w, self.min_dim, self.max_dim)
            new_h_abs = clamp(new_h_abs, self.min_dim, self.max_dim)
            new_h = sign * new_h_abs
            if new_w == original_w and new_h == original_h:
                continue
            suffix = f"ratio_{int(ratio*100):03d}"
            path, desc = self._make_variant(new_w, new_h, suffix)
            if path:
                file_list.append((path.name, desc))
        
        # 2. Varianti casuali (larghezza e altezza indipendenti)
        for i in range(1, random_count + 1):
            factor_w = random.uniform(0.1, 5.0)
            factor_h = random.uniform(0.1, 5.0)
            new_w = int(original_w * factor_w)
            new_h_abs = int(original_h_abs * factor_h)
            new_w = clamp(new_w, self.min_dim, self.max_dim)
            new_h_abs = clamp(new_h_abs, self.min_dim, self.max_dim)
            new_h = sign * new_h_abs
            if new_w == original_w and new_h == original_h:
                continue
            suffix = f"rand_{i:03d}"
            path, desc = self._make_variant(new_w, new_h, suffix)
            if path:
                file_list.append((path.name, desc))
        
        # README
        write_readme(self.output_dir, file_list, original_w, original_h, ratios, random_count)
        
        print(f"   ✅ header_mix: {len(file_list)-1} varianti generate per {self.input_path.name}")

# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Header Mix - Modifica solo larghezza e altezza dei BMP (supporta altezza con segno)"
    )
    parser.add_argument('-i', '--input', required=True,
                        help='Percorso del file BMP da elaborare (oppure directory)')
    parser.add_argument('-o', '--output', default='header_mix_output',
                        help='Directory di output (default: header_mix_output)')
    parser.add_argument('-r', '--ratios', nargs='+', type=float,
                        help='Lista di rapporti per le varianti proporzionali (es. 0.5 1.5 2.0)')
    parser.add_argument('-n', '--random', type=int, default=10,
                        help='Numero di varianti casuali (default: 10)')
    parser.add_argument('--min-dim', type=int, default=1,
                        help='Dimensione minima consentita (default: 1)')
    parser.add_argument('--max-dim', type=int, default=10000,
                        help='Dimensione massima consentita (default: 10000)')
    parser.add_argument('--seed', type=int, default=None,
                        help='Seme per il generatore casuale (per riproducibilità)')
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input non trovato: {input_path}")
        sys.exit(1)
    
    output_dir = Path(args.output)
    ensure_dir(output_dir)
    
    if input_path.is_dir():
        bmp_files = list(input_path.glob('*.bmp')) + list(input_path.glob('*.BMP'))
        if not bmp_files:
            print(f"❌ Nessun file BMP trovato in {input_path}")
            sys.exit(1)
        print(f"🔍 Trovati {len(bmp_files)} file BMP")
        for bmp_file in bmp_files:
            img_out = output_dir / bmp_file.stem
            mixer = HeaderMixer(bmp_file, img_out, args.min_dim, args.max_dim)
            mixer.generate(ratios=args.ratios, random_count=args.random, seed=args.seed)
    else:
        mixer = HeaderMixer(input_path, output_dir, args.min_dim, args.max_dim)
        mixer.generate(ratios=args.ratios, random_count=args.random, seed=args.seed)
    
    print(f"\n✅ Tutto completato. Risultati in: {output_dir}")

if __name__ == "__main__":
    main()
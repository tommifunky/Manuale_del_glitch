#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JPEG SOS Glitcher - Esplorazione strutturata di 4 tecniche sulla zona SOS
Genera per ogni immagine una gerarchia di cartelle:
- Tecnica (sostituzione, inserimento, rimozione, duplicazione)
  - livelli/ (1, 10, 100, 1000, 10000, 100000 byte) - 20 varianti per livello
  - varianti_multiple/ (suddivisione in 2-3 blocchi) - 20 varianti per combinazione
  - varianti_random/ (30 esperimenti casuali)
Ogni cartella contiene un README.txt con la descrizione di ogni file.
"""

import os
import sys
import random
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional, Any

# ======================================================================
# CONFIGURAZIONE
# ======================================================================

VARIANTI_PER_LIVELLO = 20  # Numero di varianti per ogni livello (standard e multiple)
RANDOM_EXPERIMENTS = 30    # Numero di esperimenti casuali per la sottocartella random

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

def find_jpeg_files(directory: Path) -> List[Path]:
    """Trova tutti i file JPEG nella directory."""
    jpegs = []
    for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
        jpegs.extend(directory.glob(f"*{ext}"))
    return jpegs

# ======================================================================
# JPEG PARSER (SOS focused)
# ======================================================================

class JPEGParser:
    """Parser per estrarre la zona SOS (Start of Scan)."""
    
    def __init__(self, data: bytes):
        self.data = data
        self.sos_data_start = None
        self.sos_data_end = None
        self._parse_sos()
    
    def _parse_sos(self):
        data = self.data
        n = len(data)
        i = 0
        while i < n - 1:
            if data[i] == 0xFF and data[i+1] == 0xDA:
                if i + 3 > n:
                    break
                header_len = (data[i+2] << 8) | data[i+3]
                self.sos_data_start = i + 2 + header_len
                # Cerca il prossimo marker per la fine dei dati SOS
                for j in range(self.sos_data_start, n - 1):
                    if data[j] == 0xFF and data[j+1] != 0x00:
                        self.sos_data_end = j
                        break
                if self.sos_data_end is None:
                    self.sos_data_end = n
                break
            i += 1

# ======================================================================
# SOS GLITCHER
# ======================================================================

class SOSGlitcher:
    def __init__(self, input_path: Path, output_base: Path):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.parser = JPEGParser(self.data)
        if self.parser.sos_data_start is None:
            self.valid = False
        else:
            self.valid = True
            self.sos_start = self.parser.sos_data_start
            self.sos_end = self.parser.sos_data_end
            self.sos_len = self.sos_end - self.sos_start
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.jpg'):
            filename += '.jpg'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    # ------------------------------------------------------------------
    # UTILITY PER MODIFICHE
    # ------------------------------------------------------------------
    
    def _generate_positions(self, num_bytes: int, num_parts: int = 1) -> List[List[int]]:
        """
        Genera un insieme di posizioni per modificare num_bytes totali,
        suddivisi in num_parts blocchi contigui di dimensioni approssimativamente uguali.
        Restituisce una lista di liste, dove ogni lista contiene le posizioni di un blocco.
        """
        if num_parts < 1 or num_bytes < num_parts:
            num_parts = 1
        # Distribuisci i byte tra i blocchi
        base = num_bytes // num_parts
        remainder = num_bytes % num_parts
        part_sizes = [base + (1 if i < remainder else 0) for i in range(num_parts)]
        
        # Genera posizioni di partenza per ogni blocco, assicurandosi che non si sovrappongano
        max_attempts = 100
        for _ in range(max_attempts):
            starts = []
            valid = True
            for size in part_sizes:
                max_start = self.sos_end - self.sos_start - size
                if max_start < 0:
                    valid = False
                    break
                # Cerca una posizione che non si sovrapponga ai blocchi esistenti
                attempts = 50
                found = False
                for _ in range(attempts):
                    start = random.randint(0, max_start)
                    # Verifica sovrapposizione con i blocchi già generati
                    overlap = False
                    for existing_start, existing_size in starts:
                        if (start < existing_start + existing_size and
                            start + size > existing_start):
                            overlap = True
                            break
                    if not overlap:
                        starts.append((start, size))
                        found = True
                        break
                if not found:
                    valid = False
                    break
            if valid:
                # Converti in liste di posizioni assolute
                result = []
                for s, sz in starts:
                    absolute_start = self.sos_start + s
                    result.append(list(range(absolute_start, absolute_start + sz)))
                return result
        # Fallback: se non riesce a trovare posizioni non sovrapposte, usa posizioni casuali singole
        positions = random.sample(range(self.sos_start, self.sos_end), num_bytes)
        return [positions]
    
    # ------------------------------------------------------------------
    # TECNICA 1: SOSTITUZIONE
    # ------------------------------------------------------------------
    
    def apply_substitution(self, positions: List[int]) -> bytearray:
        """Sostituisce byte nelle posizioni date con byte casuali."""
        new_data = bytearray(self.data)
        for pos in positions:
            if self.sos_start <= pos < self.sos_end:
                new_data[pos] = random_byte()
        return new_data
    
    def technique_substitution(self):
        base_folder = self.output_base / "substitution"
        ensure_dir(base_folder)
        
        # ---- 1. Livelli standard (20 varianti per livello) ----
        levels = [1, 10, 100, 1000, 10000, 100000]
        folder_levels = base_folder / "livelli"
        ensure_dir(folder_levels)
        file_list_levels = []
        
        for n in levels:
            if n > self.sos_len:
                continue
            for v in range(VARIANTI_PER_LIVELLO):
                positions = random.sample(range(self.sos_start, self.sos_end), n)
                new_data = self.apply_substitution(positions)
                fname = f"{self.base_name}_sub_{n}_v{v+1:02d}"
                self.save_image(new_data, folder_levels, fname)
                file_list_levels.append((fname, f"{n} byte (var {v+1})", f"{n} posizioni casuali"))
        
        desc_levels = f"Sostituzione di byte singoli in posizioni casuali. Livelli: {', '.join(str(l) for l in levels if l <= self.sos_len)}. {VARIANTI_PER_LIVELLO} varianti per livello."
        generate_readme(folder_levels, "Sostituzione - Livelli standard", desc_levels, file_list_levels)
        print(f"   ✅ substitution/livelli: {len(file_list_levels)} versioni")
        
        # ---- 2. Varianti multiple (blocchi) ----
        folder_multiple = base_folder / "varianti_multiple"
        ensure_dir(folder_multiple)
        file_list_multiple = []
        
        for n in levels:
            if n > self.sos_len or n < 3:
                continue
            for num_parts in [2, 3]:
                if n < num_parts:
                    continue
                for v in range(VARIANTI_PER_LIVELLO):
                    parts = self._generate_positions(n, num_parts)
                    if not parts:
                        continue
                    all_positions = [pos for block in parts for pos in block]
                    new_data = self.apply_substitution(all_positions)
                    fname = f"{self.base_name}_sub_{n}_{num_parts}parts_v{v+1:02d}"
                    self.save_image(new_data, folder_multiple, fname)
                    sizes = ", ".join(str(len(block)) for block in parts)
                    file_list_multiple.append((fname, f"{n} byte in {num_parts} blocchi (var {v+1})", f"dimensioni: {sizes}"))
        
        desc_multiple = f"Sostituzione di byte suddivisa in blocchi contigui. {VARIANTI_PER_LIVELLO} varianti per combinazione."
        generate_readme(folder_multiple, "Sostituzione - Varianti multiple", desc_multiple, file_list_multiple)
        print(f"   ✅ substitution/varianti_multiple: {len(file_list_multiple)} versioni")
        
        # ---- 3. Varianti randomiche ----
        folder_random = base_folder / "varianti_random"
        ensure_dir(folder_random)
        file_list_random = []
        
        for i in range(RANDOM_EXPERIMENTS):
            num_blocks = random.randint(1, min(6, self.sos_len))
            total_bytes = random.randint(1, min(1000, self.sos_len))
            if total_bytes < num_blocks:
                total_bytes = num_blocks
            parts = self._generate_positions(total_bytes, num_blocks)
            if not parts:
                continue
            all_positions = [pos for block in parts for pos in block]
            new_data = self.apply_substitution(all_positions)
            fname = f"{self.base_name}_sub_rand_{i+1}"
            self.save_image(new_data, folder_random, fname)
            sizes = ", ".join(str(len(block)) for block in parts)
            file_list_random.append((fname, f"{total_bytes} byte in {num_blocks} blocchi", f"dimensioni: {sizes}"))
        
        desc_random = f"{RANDOM_EXPERIMENTS} esperimenti casuali di sostituzione."
        generate_readme(folder_random, "Sostituzione - Varianti randomiche", desc_random, file_list_random)
        print(f"   ✅ substitution/varianti_random: {len(file_list_random)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 2: INSERIMENTO
    # ------------------------------------------------------------------
    
    def apply_insertion(self, positions: List[Tuple[int, int]]) -> bytearray:
        """
        Inserisce byte casuali nelle posizioni date.
        positions: lista di tuple (offset, size) relative all'inizio dei dati SOS.
        """
        new_data = bytearray(self.data)
        # Ordina le posizioni in ordine decrescente per non alterare gli indici durante l'inserimento
        sorted_positions = sorted(positions, key=lambda x: x[0], reverse=True)
        for offset, size in sorted_positions:
            insert_pos = self.sos_start + offset
            ins_bytes = random_bytes(size)
            for b in reversed(ins_bytes):
                new_data.insert(insert_pos, b)
        return new_data
    
    def technique_insertion(self):
        base_folder = self.output_base / "insertion"
        ensure_dir(base_folder)
        
        # ---- 1. Livelli standard ----
        levels = [1, 10, 100, 1000, 10000, 100000]
        folder_levels = base_folder / "livelli"
        ensure_dir(folder_levels)
        file_list_levels = []
        
        for n in levels:
            if n > self.sos_len:
                continue
            for v in range(VARIANTI_PER_LIVELLO):
                offset = random.randint(0, self.sos_len)
                new_data = self.apply_insertion([(offset, n)])
                fname = f"{self.base_name}_ins_{n}_v{v+1:02d}"
                self.save_image(new_data, folder_levels, fname)
                file_list_levels.append((fname, f"{n} byte (var {v+1})", f"offset {offset}"))
        
        desc_levels = f"Inserimento di byte in un singolo blocco. Livelli: {', '.join(str(l) for l in levels if l <= self.sos_len)}. {VARIANTI_PER_LIVELLO} varianti per livello."
        generate_readme(folder_levels, "Inserimento - Livelli standard", desc_levels, file_list_levels)
        print(f"   ✅ insertion/livelli: {len(file_list_levels)} versioni")
        
        # ---- 2. Varianti multiple ----
        folder_multiple = base_folder / "varianti_multiple"
        ensure_dir(folder_multiple)
        file_list_multiple = []
        
        for n in levels:
            if n > self.sos_len or n < 3:
                continue
            for num_parts in [2, 3]:
                if n < num_parts:
                    continue
                for v in range(VARIANTI_PER_LIVELLO):
                    base = n // num_parts
                    rem = n % num_parts
                    sizes = [base + (1 if i < rem else 0) for i in range(num_parts)]
                    offsets = []
                    # Genera offset per ogni blocco (non sovrapposti)
                    attempts = 50
                    found = False
                    for _ in range(attempts):
                        temp_offsets = []
                        current_offset = 0
                        valid = True
                        for size in sizes:
                            max_offset = self.sos_len - current_offset
                            if max_offset < size:
                                valid = False
                                break
                            off = random.randint(0, max_offset - size)
                            temp_offsets.append((current_offset + off, size))
                            current_offset += off + size
                        if valid:
                            offsets = temp_offsets
                            found = True
                            break
                    if not found:
                        continue
                    new_data = self.apply_insertion(offsets)
                    sizes_str = ", ".join(str(s) for s in sizes)
                    fname = f"{self.base_name}_ins_{n}_{num_parts}parts_v{v+1:02d}"
                    self.save_image(new_data, folder_multiple, fname)
                    file_list_multiple.append((fname, f"{n} byte in {num_parts} blocchi (var {v+1})", f"dimensioni: {sizes_str}"))
        
        desc_multiple = f"Inserimento di byte suddivisa in blocchi contigui. {VARIANTI_PER_LIVELLO} varianti per combinazione."
        generate_readme(folder_multiple, "Inserimento - Varianti multiple", desc_multiple, file_list_multiple)
        print(f"   ✅ insertion/varianti_multiple: {len(file_list_multiple)} versioni")
        
        # ---- 3. Varianti randomiche ----
        folder_random = base_folder / "varianti_random"
        ensure_dir(folder_random)
        file_list_random = []
        
        for i in range(RANDOM_EXPERIMENTS):
            num_blocks = random.randint(1, min(6, self.sos_len))
            total_bytes = random.randint(1, min(1000, self.sos_len))
            if total_bytes < num_blocks:
                total_bytes = num_blocks
            base = total_bytes // num_blocks
            rem = total_bytes % num_blocks
            sizes = [base + (1 if j < rem else 0) for j in range(num_blocks)]
            offsets = []
            current_offset = 0
            valid = True
            for size in sizes:
                max_offset = self.sos_len - current_offset
                if max_offset < size:
                    valid = False
                    break
                off = random.randint(0, max_offset - size)
                offsets.append((current_offset + off, size))
                current_offset += off + size
            if not valid or len(offsets) != num_blocks:
                continue
            new_data = self.apply_insertion(offsets)
            sizes_str = ", ".join(str(s) for s in sizes)
            fname = f"{self.base_name}_ins_rand_{i+1}"
            self.save_image(new_data, folder_random, fname)
            file_list_random.append((fname, f"{total_bytes} byte in {num_blocks} blocchi", f"dimensioni: {sizes_str}"))
        
        desc_random = f"{RANDOM_EXPERIMENTS} esperimenti casuali di inserimento."
        generate_readme(folder_random, "Inserimento - Varianti randomiche", desc_random, file_list_random)
        print(f"   ✅ insertion/varianti_random: {len(file_list_random)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 3: RIMOZIONE
    # ------------------------------------------------------------------
    
    def apply_deletion(self, positions: List[Tuple[int, int]]) -> bytearray:
        """
        Elimina byte dai dati SOS.
        positions: lista di tuple (offset, size) relative all'inizio dei dati SOS.
        """
        new_data = bytearray(self.data)
        # Ordina le posizioni in ordine decrescente per non alterare gli indici durante l'eliminazione
        sorted_positions = sorted(positions, key=lambda x: x[0], reverse=True)
        for offset, size in sorted_positions:
            start = self.sos_start + offset
            end = start + size
            if end <= len(new_data):
                del new_data[start:end]
        return new_data
    
    def technique_deletion(self):
        base_folder = self.output_base / "deletion"
        ensure_dir(base_folder)
        
        # ---- 1. Livelli standard ----
        levels = [1, 10, 100, 1000, 10000, 100000]
        folder_levels = base_folder / "livelli"
        ensure_dir(folder_levels)
        file_list_levels = []
        
        for n in levels:
            if n > self.sos_len:
                continue
            for v in range(VARIANTI_PER_LIVELLO):
                offset = random.randint(0, self.sos_len - n)
                new_data = self.apply_deletion([(offset, n)])
                fname = f"{self.base_name}_del_{n}_v{v+1:02d}"
                self.save_image(new_data, folder_levels, fname)
                file_list_levels.append((fname, f"{n} byte (var {v+1})", f"offset {offset}"))
        
        desc_levels = f"Eliminazione di byte in un singolo blocco. Livelli: {', '.join(str(l) for l in levels if l <= self.sos_len)}. {VARIANTI_PER_LIVELLO} varianti per livello."
        generate_readme(folder_levels, "Rimozione - Livelli standard", desc_levels, file_list_levels)
        print(f"   ✅ deletion/livelli: {len(file_list_levels)} versioni")
        
        # ---- 2. Varianti multiple ----
        folder_multiple = base_folder / "varianti_multiple"
        ensure_dir(folder_multiple)
        file_list_multiple = []
        
        for n in levels:
            if n > self.sos_len or n < 3:
                continue
            for num_parts in [2, 3]:
                if n < num_parts:
                    continue
                for v in range(VARIANTI_PER_LIVELLO):
                    base = n // num_parts
                    rem = n % num_parts
                    sizes = [base + (1 if i < rem else 0) for i in range(num_parts)]
                    offsets = []
                    current_offset = 0
                    valid = True
                    for size in sizes:
                        max_offset = self.sos_len - current_offset
                        if max_offset < size:
                            valid = False
                            break
                        off = random.randint(0, max_offset - size)
                        offsets.append((current_offset + off, size))
                        current_offset += off + size
                    if not valid or len(offsets) != num_parts:
                        continue
                    new_data = self.apply_deletion(offsets)
                    sizes_str = ", ".join(str(s) for s in sizes)
                    fname = f"{self.base_name}_del_{n}_{num_parts}parts_v{v+1:02d}"
                    self.save_image(new_data, folder_multiple, fname)
                    file_list_multiple.append((fname, f"{n} byte in {num_parts} blocchi (var {v+1})", f"dimensioni: {sizes_str}"))
        
        desc_multiple = f"Eliminazione di byte suddivisa in blocchi contigui. {VARIANTI_PER_LIVELLO} varianti per combinazione."
        generate_readme(folder_multiple, "Rimozione - Varianti multiple", desc_multiple, file_list_multiple)
        print(f"   ✅ deletion/varianti_multiple: {len(file_list_multiple)} versioni")
        
        # ---- 3. Varianti randomiche ----
        folder_random = base_folder / "varianti_random"
        ensure_dir(folder_random)
        file_list_random = []
        
        for i in range(RANDOM_EXPERIMENTS):
            num_blocks = random.randint(1, min(6, self.sos_len))
            total_bytes = random.randint(1, min(1000, self.sos_len))
            if total_bytes < num_blocks:
                total_bytes = num_blocks
            base = total_bytes // num_blocks
            rem = total_bytes % num_blocks
            sizes = [base + (1 if j < rem else 0) for j in range(num_blocks)]
            offsets = []
            current_offset = 0
            valid = True
            for size in sizes:
                max_offset = self.sos_len - current_offset
                if max_offset < size:
                    valid = False
                    break
                off = random.randint(0, max_offset - size)
                offsets.append((current_offset + off, size))
                current_offset += off + size
            if not valid or len(offsets) != num_blocks:
                continue
            new_data = self.apply_deletion(offsets)
            sizes_str = ", ".join(str(s) for s in sizes)
            fname = f"{self.base_name}_del_rand_{i+1}"
            self.save_image(new_data, folder_random, fname)
            file_list_random.append((fname, f"{total_bytes} byte in {num_blocks} blocchi", f"dimensioni: {sizes_str}"))
        
        desc_random = f"{RANDOM_EXPERIMENTS} esperimenti casuali di eliminazione."
        generate_readme(folder_random, "Rimozione - Varianti randomiche", desc_random, file_list_random)
        print(f"   ✅ deletion/varianti_random: {len(file_list_random)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 4: DUPLICAZIONE
    # ------------------------------------------------------------------
    
    def apply_duplication(self, positions: List[Tuple[int, int]]) -> bytearray:
        """
        Duplica byte nei dati SOS.
        positions: lista di tuple (offset, size) relative all'inizio dei dati SOS.
        """
        new_data = bytearray(self.data)
        # Ordina le posizioni in ordine decrescente per non alterare gli indici durante l'inserimento
        sorted_positions = sorted(positions, key=lambda x: x[0], reverse=True)
        for offset, size in sorted_positions:
            start = self.sos_start + offset
            dup_bytes = bytes(new_data[start:start+size])
            insert_pos = start + size
            for b in reversed(dup_bytes):
                new_data.insert(insert_pos, b)
        return new_data
    
    def technique_duplication(self):
        base_folder = self.output_base / "duplication"
        ensure_dir(base_folder)
        
        # ---- 1. Livelli standard ----
        levels = [1, 10, 100, 1000, 10000, 100000]
        folder_levels = base_folder / "livelli"
        ensure_dir(folder_levels)
        file_list_levels = []
        
        for n in levels:
            if n > self.sos_len:
                continue
            for v in range(VARIANTI_PER_LIVELLO):
                offset = random.randint(0, self.sos_len - n)
                new_data = self.apply_duplication([(offset, n)])
                fname = f"{self.base_name}_dup_{n}_v{v+1:02d}"
                self.save_image(new_data, folder_levels, fname)
                file_list_levels.append((fname, f"{n} byte (var {v+1})", f"offset {offset}"))
        
        desc_levels = f"Duplicazione di byte in un singolo blocco. Livelli: {', '.join(str(l) for l in levels if l <= self.sos_len)}. {VARIANTI_PER_LIVELLO} varianti per livello."
        generate_readme(folder_levels, "Duplicazione - Livelli standard", desc_levels, file_list_levels)
        print(f"   ✅ duplication/livelli: {len(file_list_levels)} versioni")
        
        # ---- 2. Varianti multiple ----
        folder_multiple = base_folder / "varianti_multiple"
        ensure_dir(folder_multiple)
        file_list_multiple = []
        
        for n in levels:
            if n > self.sos_len or n < 3:
                continue
            for num_parts in [2, 3]:
                if n < num_parts:
                    continue
                for v in range(VARIANTI_PER_LIVELLO):
                    base = n // num_parts
                    rem = n % num_parts
                    sizes = [base + (1 if i < rem else 0) for i in range(num_parts)]
                    offsets = []
                    current_offset = 0
                    valid = True
                    for size in sizes:
                        max_offset = self.sos_len - current_offset
                        if max_offset < size:
                            valid = False
                            break
                        off = random.randint(0, max_offset - size)
                        offsets.append((current_offset + off, size))
                        current_offset += off + size
                    if not valid or len(offsets) != num_parts:
                        continue
                    new_data = self.apply_duplication(offsets)
                    sizes_str = ", ".join(str(s) for s in sizes)
                    fname = f"{self.base_name}_dup_{n}_{num_parts}parts_v{v+1:02d}"
                    self.save_image(new_data, folder_multiple, fname)
                    file_list_multiple.append((fname, f"{n} byte in {num_parts} blocchi (var {v+1})", f"dimensioni: {sizes_str}"))
        
        desc_multiple = f"Duplicazione di byte suddivisa in blocchi contigui. {VARIANTI_PER_LIVELLO} varianti per combinazione."
        generate_readme(folder_multiple, "Duplicazione - Varianti multiple", desc_multiple, file_list_multiple)
        print(f"   ✅ duplication/varianti_multiple: {len(file_list_multiple)} versioni")
        
        # ---- 3. Varianti randomiche ----
        folder_random = base_folder / "varianti_random"
        ensure_dir(folder_random)
        file_list_random = []
        
        for i in range(RANDOM_EXPERIMENTS):
            num_blocks = random.randint(1, min(6, self.sos_len))
            total_bytes = random.randint(1, min(1000, self.sos_len))
            if total_bytes < num_blocks:
                total_bytes = num_blocks
            base = total_bytes // num_blocks
            rem = total_bytes % num_blocks
            sizes = [base + (1 if j < rem else 0) for j in range(num_blocks)]
            offsets = []
            current_offset = 0
            valid = True
            for size in sizes:
                max_offset = self.sos_len - current_offset
                if max_offset < size:
                    valid = False
                    break
                off = random.randint(0, max_offset - size)
                offsets.append((current_offset + off, size))
                current_offset += off + size
            if not valid or len(offsets) != num_blocks:
                continue
            new_data = self.apply_duplication(offsets)
            sizes_str = ", ".join(str(s) for s in sizes)
            fname = f"{self.base_name}_dup_rand_{i+1}"
            self.save_image(new_data, folder_random, fname)
            file_list_random.append((fname, f"{total_bytes} byte in {num_blocks} blocchi", f"dimensioni: {sizes_str}"))
        
        desc_random = f"{RANDOM_EXPERIMENTS} esperimenti casuali di duplicazione."
        generate_readme(folder_random, "Duplicazione - Varianti randomiche", desc_random, file_list_random)
        print(f"   ✅ duplication/varianti_random: {len(file_list_random)} versioni")
    
    # ------------------------------------------------------------------
    # RUN ALL
    # ------------------------------------------------------------------
    
    def run_all(self):
        if not self.valid:
            print(f"⚠️  Nessun segmento SOS in {self.input_path.name}, salto.")
            return
        
        print(f"\n📷 Elaborazione di: {self.input_path.name}")
        print(f"📁 Output in: {self.output_base}")
        print(f"📊 Dati SOS: {self.sos_len} byte (da {self.sos_start} a {self.sos_end})")
        print("-" * 50)
        
        self.technique_substitution()
        self.technique_insertion()
        self.technique_deletion()
        self.technique_duplication()
        
        print(f"✅ Completato {self.input_path.name}")

# ======================================================================
# README GENERATOR
# ======================================================================

def generate_readme(folder: Path, title: str, description: str,
                    file_list: List[Tuple[str, str, str]]) -> Path:
    """Crea un README dettagliato con la descrizione di ogni file."""
    readme_path = folder / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"{title}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"📁 Immagine originale: {folder.parent.parent.name}.jpg\n\n")
        f.write("─" * 70 + "\n")
        f.write("DESCRIZIONE\n")
        f.write("─" * 70 + "\n\n")
        f.write(description + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("FILE GENERATI\n")
        f.write("─" * 70 + "\n\n")
        if file_list:
            f.write("| # | Nome file | Modifica | Dettaglio |\n")
            f.write("|---|-----------|----------|-----------|\n")
            for idx, (name, mod, note) in enumerate(file_list, 1):
                f.write(f"| {idx} | {name} | {mod} | {note} |\n")
        else:
            f.write("Nessun file generato (probabilmente la dimensione dei dati SOS è troppo piccola per i livelli richiesti).\n")
        f.write("\n")
        f.write("─" * 70 + "\n")
        f.write("NOTE FINALI\n")
        f.write("─" * 70 + "\n\n")
        f.write("• Tutte le modifiche sono state applicate esclusivamente alla zona SOS (Start of Scan), i dati compressi dell'immagine.\n")
        f.write("• In HexFiend, puoi replicare manualmente queste modifiche navigando nell'area SOS.\n")
        f.write("• Conserva sempre l'originale: le modifiche sono permanenti.\n")
    return readme_path

# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="JPEG SOS Glitcher - Esplorazione strutturata di 4 tecniche"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file JPEG (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='sos_glitch_detailed',
                        help='Directory di output principale (default: sos_glitch_detailed)')
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"❌ Directory input non trovata: {input_dir}")
        sys.exit(1)
    
    jpeg_files = find_jpeg_files(input_dir)
    if not jpeg_files:
        print(f"❌ Nessun file JPEG trovato in {input_dir}")
        sys.exit(1)
    
    print(f"🔍 Trovati {len(jpeg_files)} file JPEG")
    print(f"📁 Output principale: {output_dir}")
    print("=" * 70)
    
    for jpg_path in jpeg_files:
        img_output = output_dir / jpg_path.stem
        ensure_dir(img_output)
        glitcher = SOSGlitcher(jpg_path, img_output)
        glitcher.run_all()
    
    print("\n" + "=" * 70)
    print("✅ TUTTE LE IMMAGINI PROCESSATE!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
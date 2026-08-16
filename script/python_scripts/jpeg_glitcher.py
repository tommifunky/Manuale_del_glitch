#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JPEG Glitcher Pro - Manipolazione avanzata di segmenti JPEG
Genera glitch su APPn (con sottocartelle per tipo), DQT, SOF (con modifica componenti e subsampling), DHT, SOS.
Ora con livelli micro e documentazione per ogni sottocartella.
"""

import os
import sys
import random
import struct
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional, Any

# ======================================================================
# UTILITY (uguale a prima)
# ======================================================================

def find_jpeg_file(directory: str = ".") -> Optional[Path]:
    directory = Path(directory)
    for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
        for f in directory.glob(f"*{ext}"):
            return f
    return None

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def random_byte() -> int:
    return random.randint(0, 255)

def random_bytes(n: int) -> bytes:
    return bytes(random_byte() for _ in range(n))

def clamp(val: int, min_val: int = 0, max_val: int = 255) -> int:
    return max(min_val, min(val, max_val))

def format_hex(b: int) -> str:
    return f"0x{b:02X}"

def format_hex_bytes(data: bytes, max_len: int = 16) -> str:
    if len(data) > max_len:
        return " ".join(format_hex(b) for b in data[:max_len]) + " ..."
    return " ".join(format_hex(b) for b in data)

def generate_random_levels(max_val: int, count: int = 20) -> List[int]:
    if max_val <= 1:
        return []
    count = min(count, max_val)
    levels = set()
    while len(levels) < count:
        levels.add(random.randint(1, max_val))
    return sorted(levels)

def generate_micro_levels(max_val: int) -> List[int]:
    base = [1, 2, 3, 5, 8, 10, 12, 15, 18, 20, 25, 30, 35, 40, 50,
            60, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000,
            1500, 2000, 3000, 5000]
    return [l for l in base if l <= max_val]

# ======================================================================
# JPEG PARSER (uguale)
# ======================================================================

class JPEGParser:
    def __init__(self, data: bytes):
        self.data = data
        self.segments = []  # (start, marker, length, payload_start, payload_end)
        self._parse()
    
    def _parse(self):
        data = self.data
        i = 0
        n = len(data)
        while i < n - 1:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = (data[i] << 8) | data[i+1]
            if marker in [0xFFD8, 0xFFD9, 0xFF01] or (0xFFD0 <= marker <= 0xFFD7):
                seg_len = 0
                payload_start = i + 2
                payload_end = i + 2
                self.segments.append((i, marker, seg_len, payload_start, payload_end))
                i += 2
                continue
            if i + 3 > n:
                break
            seg_len = (data[i+2] << 8) | data[i+3]
            payload_start = i + 4
            payload_end = i + 2 + seg_len
            self.segments.append((i, marker, seg_len, payload_start, payload_end))
            i += 2 + seg_len
    
    def get_segments_by_marker(self, marker_byte: int) -> List[Tuple[int, int, int, int, int]]:
        return [seg for seg in self.segments if (seg[1] & 0xFF00) == (marker_byte << 8)]
    
    def get_segment_by_marker_exact(self, marker: int) -> List[Tuple[int, int, int, int, int]]:
        return [seg for seg in self.segments if seg[1] == marker]
    
    def get_first_segment(self, marker: int) -> Optional[Tuple[int, int, int, int, int]]:
        segs = self.get_segment_by_marker_exact(marker)
        return segs[0] if segs else None
    
    def get_sos_data_range(self) -> Tuple[int, int]:
        sos_seg = self.get_first_segment(0xFFDA)
        if not sos_seg:
            return (0, 0)
        start = sos_seg[3]
        eoi_seg = self.get_first_segment(0xFFD9)
        if eoi_seg:
            end = eoi_seg[0]
        else:
            end = len(self.data)
        return (start, end)

# ======================================================================
# GENERATORE DI README (uguale)
# ======================================================================

def generate_readme(folder: Path, title: str, description: str, 
                    tech_details: str, hex_instructions: str,
                    file_list: List[Tuple[str, str, str]]) -> Path:
    readme_path = folder / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"{title}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"📁 Immagine originale: {folder.parent.name}.jpg\n\n")
        f.write("─" * 70 + "\n")
        f.write("DESCRIZIONE\n")
        f.write("─" * 70 + "\n\n")
        f.write(description + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("DETTAGLI TECNICI\n")
        f.write("─" * 70 + "\n\n")
        f.write(tech_details + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("VERSIONI GENERATE\n")
        f.write("─" * 70 + "\n\n")
        f.write("| # | Nome file | Modifica | Note |\n")
        f.write("|---|-----------|----------|------|\n")
        for idx, (name, mod, note) in enumerate(file_list, 1):
            f.write(f"| {idx} | {name} | {mod} | {note} |\n")
        f.write("\n")
        f.write("─" * 70 + "\n")
        f.write("COME RIFARE MANUALMENTE CON HEXFIEND\n")
        f.write("─" * 70 + "\n\n")
        f.write(hex_instructions + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("NOTE\n")
        f.write("─" * 70 + "\n\n")
        f.write("• Alcune immagini potrebbero non essere visualizzabili. Questo è normale nel glitch art.\n")
        f.write("• Per HexFiend: apri il file, modifica i byte come descritto, salva.\n")
    return readme_path

# ======================================================================
# TECNICHE DI MODIFICA
# ======================================================================

class JPEGGlitcherPro:
    def __init__(self, input_path: Path, output_dir: Path):
        self.input_path = input_path
        self.output_dir = output_dir
        self.base_name = input_path.stem
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.parser = JPEGParser(self.data)
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.jpg'):
            filename += '.jpg'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    # ------------------------------------------
    # TECNICA APPn - con SOTTOCARTELLE per tipo
    # ------------------------------------------
    def technique_appn(self):
        base_folder = self.output_dir / "APPn"
        ensure_dir(base_folder)
        
        # Raccogli tutti i segmenti APPn (0xE0 - 0xEF)
        appn_segments = []
        for marker in range(0xFFE0, 0xFFF0):  # APP0..APP15
            segs = self.parser.get_segment_by_marker_exact(marker)
            if segs:
                appn_segments.extend([(marker, s) for s in segs])
        
        if not appn_segments:
            print("⚠️  Nessun segmento APPn trovato. Provo con COM...")
            self.technique_com()
            return
        
        # Raggruppa per tipo APPn
        # Dizionario: marker -> lista di segmenti
        appn_dict: Dict[int, List] = {}
        for marker, seg in appn_segments:
            if marker not in appn_dict:
                appn_dict[marker] = []
            appn_dict[marker].append(seg)
        
        # Mappa marker -> nome descrittivo
        appn_names = {
            0xFFE0: "APP0_JFIF",
            0xFFE1: "APP1_EXIF",
            0xFFE2: "APP2_ICC",
            0xFFE3: "APP3",
            0xFFE4: "APP4",
            0xFFE5: "APP5",
            0xFFE6: "APP6",
            0xFFE7: "APP7",
            0xFFE8: "APP8",
            0xFFE9: "APP9",
            0xFFEA: "APP10",
            0xFFEB: "APP11",
            0xFFEC: "APP12",
            0xFFED: "APP13",
            0xFFEE: "APP14",
            0xFFEF: "APP15"
        }
        
        for marker, segs in appn_dict.items():
            # Crea sottocartella per questo tipo
            subfolder = base_folder / appn_names.get(marker, f"APP{marker-0xFFE0:X}")
            ensure_dir(subfolder)
            file_list = []
            
            # Prendi il payload più grande per questo tipo
            max_payload = max(s[4] - s[3] for s in segs)
            all_levels = generate_micro_levels(max_payload)
            random_levels = generate_random_levels(max_payload, 20)
            all_levels = sorted(set(all_levels + random_levels))
            
            for n in all_levels:
                seg = random.choice(segs)
                start, end = seg[3], seg[4]
                if end - start < n:
                    continue
                new_data = bytearray(self.data)
                positions = random.sample(range(start, end), n)
                for pos in positions:
                    new_data[pos] = random_byte()
                fname = f"{self.base_name}_{appn_names.get(marker, f'app{marker-0xFFE0}')}_rand{n}"
                self.save_image(new_data, subfolder, fname)
                file_list.append((fname+".jpg", f"{n} byte casuali", f"segmento {marker:04X} a {seg[0]:X}"))
            
            # Allungamento del segmento (modifica campo lunghezza)
            for seg in segs[:1]:  # solo il primo per non esagerare
                old_len = seg[2]
                new_len = old_len + 100
                if new_len < 65535:
                    new_data = bytearray(self.data)
                    new_data[seg[0]+2] = (new_len >> 8) & 0xFF
                    new_data[seg[0]+3] = new_len & 0xFF
                    insert_pos = seg[3] + old_len - 50
                    for _ in range(100):
                        new_data.insert(insert_pos, random_byte())
                    fname = f"{self.base_name}_{appn_names.get(marker, f'app{marker-0xFFE0}')}_lengthen"
                    self.save_image(new_data, subfolder, fname)
                    file_list.append((fname+".jpg", "allungamento segmento", "modifica campo lunghezza"))
            
            # README per questa sottocartella
            desc = f"Modifica del segmento {appn_names.get(marker, f'APP{marker-0xFFE0}')} ({marker:04X}).\n"
            desc += "Questo segmento contiene metadati (EXIF, profili colore, commenti, ecc.)."
            tech = f"Trovati {len(segs)} segmenti. Livelli: {', '.join(map(str, all_levels[:10]))} ..."
            hex_inst = f"Cerca il marker {marker:04X}, modifica il payload."
            generate_readme(subfolder, f"APPn – {appn_names.get(marker, f'APP{marker-0xFFE0}')}", 
                            desc, tech, hex_inst, file_list)
            print(f"   ✅ {appn_names.get(marker, f'APP{marker-0xFFE0}')}: {len(file_list)} versioni")
    
    # ------------------------------------------
    # TECNICA COM (commenti) - alternativa
    # ------------------------------------------
    def technique_com(self):
        folder = self.output_dir / "COM_comments"
        ensure_dir(folder)
        
        com_segments = self.parser.get_segment_by_marker_exact(0xFFFE)
        if not com_segments:
            print("⚠️  Nessun segmento COM trovato.")
            return
        
        file_list = []
        max_payload = max(seg[4] - seg[3] for seg in com_segments)
        all_levels = generate_micro_levels(max_payload)
        random_levels = generate_random_levels(max_payload, 20)
        all_levels = sorted(set(all_levels + random_levels))
        
        for n in all_levels:
            seg = random.choice(com_segments)
            start, end = seg[3], seg[4]
            if end - start < n:
                continue
            new_data = bytearray(self.data)
            positions = random.sample(range(start, end), n)
            for pos in positions:
                new_data[pos] = random_byte()
            fname = f"{self.base_name}_com_rand{n}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"{n} byte casuali", "segmento COM"))
        
        # Allungamento
        for seg in com_segments[:1]:
            old_len = seg[2]
            new_len = old_len + 100
            if new_len < 65535:
                new_data = bytearray(self.data)
                new_data[seg[0]+2] = (new_len >> 8) & 0xFF
                new_data[seg[0]+3] = new_len & 0xFF
                insert_pos = seg[3] + old_len - 50
                for _ in range(100):
                    new_data.insert(insert_pos, random_byte())
                fname = f"{self.base_name}_com_lengthen"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", "allungamento segmento", "modifica campo lunghezza"))
        
        desc = "Modifica il segmento COM (commenti)."
        tech = f"Trovati {len(com_segments)} segmenti. Livelli: {', '.join(map(str, all_levels[:10]))} ..."
        hex_inst = "Cerca FF FE, modifica il payload."
        generate_readme(folder, "COM – Commenti", desc, tech, hex_inst, file_list)
        print(f"✅ COM: {len(file_list)} versioni")
    
    # ------------------------------------------
    # TECNICA DQT (tabelle di quantizzazione)
    # ------------------------------------------
    def technique_dqt(self):
        folder = self.output_dir / "DQT"
        ensure_dir(folder)
        
        dqt_segments = self.parser.get_segment_by_marker_exact(0xFFDB)
        if not dqt_segments:
            print("⚠️  Nessun segmento DQT, salto.")
            return
        
        file_list = []
        max_coeff = max(seg[4] - seg[3] for seg in dqt_segments)
        all_levels = generate_micro_levels(max_coeff)
        random_levels = generate_random_levels(max_coeff, 20)
        all_levels = sorted(set(all_levels + random_levels))
        
        for n in all_levels:
            seg = random.choice(dqt_segments)
            start, end = seg[3], seg[4]
            coeff_len = end - start
            if coeff_len < n:
                continue
            new_data = bytearray(self.data)
            positions = random.sample(range(start, end), n)
            for pos in positions:
                op = random.choice(['mult2', 'mult3', 'half', 'zero'])
                val = new_data[pos]
                if op == 'mult2':
                    new_data[pos] = clamp(val * 2)
                elif op == 'mult3':
                    new_data[pos] = clamp(val * 3)
                elif op == 'half':
                    new_data[pos] = clamp(val // 2)
                else:
                    new_data[pos] = 0
            fname = f"{self.base_name}_dqt_{n}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"{n} coefficienti modificati", f"offset {start:X}"))
        
        desc = "Modifica i coefficienti delle tabelle di quantizzazione (DQT)."
        tech = f"Trovati {len(dqt_segments)} segmenti DQT. Livelli: {', '.join(map(str, all_levels[:10]))} ..."
        hex_inst = "Cerca FF DB, dopo i primi 4 byte trovi i coefficienti. Modificali."
        generate_readme(folder, "DQT – Tabelle di quantizzazione", desc, tech, hex_inst, file_list)
        print(f"✅ DQT: {len(file_list)} versioni")
    
    # ------------------------------------------
    # TECNICA SOF (dimensioni, componenti, subsampling)
    # ------------------------------------------
    def technique_sof(self):
        folder = self.output_dir / "SOF"
        ensure_dir(folder)
        
        # Cerca SOF0 (baseline) o SOF1 (extended sequential)
        sof_seg = self.parser.get_first_segment(0xFFC0) or self.parser.get_first_segment(0xFFC1)
        if not sof_seg:
            print("⚠️  Nessun segmento SOF, salto.")
            return
        
        file_list = []
        start, end = sof_seg[3], sof_seg[4]
        if end - start < 7:
            return
        
        # Estrai parametri
        precision = self.data[start]
        height = (self.data[start+1] << 8) | self.data[start+2]
        width = (self.data[start+3] << 8) | self.data[start+4]
        num_components = self.data[start+5]  # di solito 3 per YCbCr
        # I componenti iniziano a start+6
        comp_start = start + 6
        components = []
        for i in range(num_components):
            if comp_start + i*3 + 2 < end:
                comp_id = self.data[comp_start + i*3]
                h_samp = (self.data[comp_start + i*3 + 1] >> 4) & 0x0F  # fattore di campionamento orizzontale
                v_samp = self.data[comp_start + i*3 + 1] & 0x0F        # fattore di campionamento verticale
                q_table = self.data[comp_start + i*3 + 2]
                components.append((comp_id, h_samp, v_samp, q_table))
        
        # 1. Modifica larghezza (variazioni piccole e grandi)
        for delta in [1, 2, 5, 10, 20, 50]:
            for new_w in [width + delta, width - delta]:
                if new_w < 1 or new_w > 65535:
                    continue
                new_data = bytearray(self.data)
                new_data[start+3] = (new_w >> 8) & 0xFF
                new_data[start+4] = new_w & 0xFF
                fname = f"{self.base_name}_sof_w{new_w}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"larghezza: {new_w}", "modifica SOF"))
        
        # 2. Modifica altezza
        for delta in [1, 2, 5, 10, 20, 50]:
            for new_h in [height + delta, height - delta]:
                if new_h < 1 or new_h > 65535:
                    continue
                new_data = bytearray(self.data)
                new_data[start+1] = (new_h >> 8) & 0xFF
                new_data[start+2] = new_h & 0xFF
                fname = f"{self.base_name}_sof_h{new_h}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"altezza: {new_h}", "modifica SOF"))
        
        # 3. Modifica numero di componenti (solo se >1)
        if num_components > 1:
            for new_num in [1, 2, 4, 5]:
                if new_num == num_components or new_num > 10:
                    continue
                new_data = bytearray(self.data)
                # Cambia il numero di componenti
                new_data[start+5] = new_num
                # Dobbiamo anche aggiustare il payload (troncare o aggiungere)
                # Qui tronchiamo semplicemente i dati dei componenti al nuovo numero
                # Ma attenzione: bisogna anche aggiornare la lunghezza del segmento!
                # Per semplicità, modifichiamo solo il campo numero, ma il decoder potrebbe fallire.
                fname = f"{self.base_name}_sof_comp{new_num}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"componenti: {new_num}", "modifica SOF (numero componenti)"))
        
        # 4. Modifica sottocampionamento (h_samp, v_samp) per il primo componente (solitamente Y)
        if components:
            comp = components[0]
            comp_id, h_samp, v_samp, q_table = comp
            # Variazioni
            for new_h in [1, 2, 4]:
                if new_h == h_samp:
                    continue
                new_data = bytearray(self.data)
                pos = comp_start + 1  # il byte che contiene h_samp e v_samp
                # mantieni v_samp, cambia h_samp
                new_data[pos] = (new_h << 4) | (v_samp & 0x0F)
                fname = f"{self.base_name}_sof_hsamp{new_h}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"h_samp: {new_h}", "modifica sottocampionamento orizzontale"))
            
            for new_v in [1, 2, 4]:
                if new_v == v_samp:
                    continue
                new_data = bytearray(self.data)
                pos = comp_start + 1
                new_data[pos] = ((h_samp & 0x0F) << 4) | (new_v & 0x0F)
                fname = f"{self.base_name}_sof_vsamp{new_v}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"v_samp: {new_v}", "modifica sottocampionamento verticale"))
        
        desc = "Modifica i parametri nel segmento SOF: larghezza, altezza, numero di componenti, sottocampionamento."
        tech = f"SOF a {sof_seg[0]:X}. Originale: {width}x{height}, {num_components} componenti.\n"
        tech += f"Componenti: {components}"
        hex_inst = """Cerca FF C0/C1. 
- byte 5-6: altezza, 7-8: larghezza (big-endian)
- byte 9: numero di componenti
- da byte 10: per ogni componente (3 byte): ID, fattori (h e v), tabella di quantizzazione
"""
        generate_readme(folder, "SOF – Dimensioni, componenti e sottocampionamento", desc, tech, hex_inst, file_list)
        print(f"✅ SOF: {len(file_list)} versioni")
    
    # ------------------------------------------
    # TECNICA DHT (Huffman) - sicura (solo lunghezze)
    # ------------------------------------------
    def technique_dht(self):
        folder = self.output_dir / "DHT"
        ensure_dir(folder)
        
        dht_segments = self.parser.get_segment_by_marker_exact(0xFFC4)
        if not dht_segments:
            print("⚠️  Nessun segmento DHT, salto.")
            return
        
        file_list = []
        for seg in dht_segments:
            start, end = seg[3], seg[4]
            size = end - start
            if size < 10:
                continue
            
            all_levels = generate_micro_levels(size)
            random_levels = generate_random_levels(size, 20)
            all_levels = sorted(set(all_levels + random_levels))
            
            for n in all_levels:
                new_data = bytearray(self.data)
                # Modifica solo le lunghezze dei codici (primi 16 byte)
                code_len_start = start + 1
                code_len_end = min(start + 17, end)
                available_len = code_len_end - code_len_start
                if available_len < 1:
                    continue
                n_eff = min(n, available_len)
                positions = random.sample(range(code_len_start, code_len_end), n_eff)
                for pos in positions:
                    val = new_data[pos]
                    if val > 1:
                        new_data[pos] = max(1, val + random.choice([-1, 1]))
                    else:
                        new_data[pos] = val + 1
                fname = f"{self.base_name}_dht_safe_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n_eff} byte modificati (sicuro)", "solo lunghezze codici"))
            
            # Scambio di tabelle DHT (se ce ne sono almeno 2)
            if len(dht_segments) >= 2:
                seg1, seg2 = dht_segments[0], dht_segments[1]
                new_data = bytearray(self.data)
                start1, end1 = seg1[3], seg1[4]
                start2, end2 = seg2[3], seg2[4]
                len1 = end1 - start1
                len2 = end2 - start2
                if len1 > 0 and len2 > 0:
                    swap_len = min(len1, len2)
                    new_data[start1:start1+swap_len], new_data[start2:start2+swap_len] = \
                        new_data[start2:start2+swap_len], new_data[start1:start1+swap_len]
                    fname = f"{self.base_name}_dht_swap"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", "scambio tabelle DHT", "scambio tra due DHT"))
        
        desc = "Modifica le tabelle di Huffman (DHT) in modo sicuro: solo le lunghezze dei codici.\n"
        desc += "Inoltre, scambia tabelle DHT se ce ne sono multiple."
        tech = f"Trovati {len(dht_segments)} segmenti DHT."
        hex_inst = "Cerca FF C4. I primi 16 byte del payload sono le lunghezze dei codici. Modificali leggermente."
        generate_readme(folder, "DHT – Tabelle di Huffman (sicuro)", desc, tech, hex_inst, file_list)
        print(f"✅ DHT: {len(file_list)} versioni")
    
    # ------------------------------------------
    # TECNICA SOS - con micro livelli
    # ------------------------------------------
    def technique_sos(self):
        base_folder = self.output_dir / "SOS"
        ensure_dir(base_folder)
        
        sos_start, sos_end = self.parser.get_sos_data_range()
        if sos_start == 0 or sos_end == 0:
            print("⚠️  Nessun dato compresso trovato (SOS mancante).")
            return
        
        comp_size = sos_end - sos_start
        print(f"   Dati compressi: da {sos_start} a {sos_end}, {comp_size} byte")
        
        subdirs = {
            "random_substitution": "Sostituisce byte con valori casuali.",
            "zero_substitution": "Sostituisce byte con 0x00.",
            "ff_substitution": "Sostituisce byte con 0xFF.",
            "multiplication": "Moltiplica i byte per 2 o 3 (clamp).",
            "deletion": "Elimina byte consecutivi.",
            "duplication": "Duplica byte consecutivi.",
            "insertion": "Inserisce byte casuali."
        }
        
        for subname, desc in subdirs.items():
            folder = base_folder / subname
            ensure_dir(folder)
            file_list = []
            
            # Genera micro levels + casuali
            if subname in ["random_substitution", "zero_substitution", "ff_substitution", "multiplication"]:
                all_levels = generate_micro_levels(comp_size-1)
                random_levels = generate_random_levels(comp_size-1, 20)
                all_levels = sorted(set(all_levels + random_levels))
            else:
                max_level = min(comp_size-1, 2000)
                all_levels = generate_micro_levels(max_level)
                random_levels = generate_random_levels(max_level, 20)
                all_levels = sorted(set(all_levels + random_levels))
            
            for n in all_levels:
                if n >= comp_size:
                    continue
                new_data = bytearray(self.data)
                if subname == "random_substitution":
                    positions = random.sample(range(sos_start, sos_end), n)
                    for pos in positions:
                        new_data[pos] = random_byte()
                    fname = f"{self.base_name}_sos_rand{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"{n} byte casuali", f"offset {sos_start:X}"))
                
                elif subname == "zero_substitution":
                    positions = random.sample(range(sos_start, sos_end), n)
                    for pos in positions:
                        new_data[pos] = 0x00
                    fname = f"{self.base_name}_sos_zero{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"{n} byte impostati a 0x00", ""))
                
                elif subname == "ff_substitution":
                    positions = random.sample(range(sos_start, sos_end), n)
                    for pos in positions:
                        new_data[pos] = 0xFF
                    fname = f"{self.base_name}_sos_ff{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"{n} byte impostati a 0xFF", ""))
                
                elif subname == "multiplication":
                    positions = random.sample(range(sos_start, sos_end), n)
                    factor = random.choice([2, 3])
                    for pos in positions:
                        val = new_data[pos]
                        new_data[pos] = clamp(val * factor)
                    fname = f"{self.base_name}_sos_mul{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"{n} byte moltiplicati x{factor}", ""))
                
                elif subname == "deletion":
                    if n >= comp_size:
                        continue
                    del_pos = random.randint(sos_start, sos_end - n)
                    del new_data[del_pos:del_pos+n]
                    fname = f"{self.base_name}_sos_del{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"eliminati {n} byte da {del_pos:X}", ""))
                
                elif subname == "duplication":
                    if n >= comp_size:
                        continue
                    start_pos = random.randint(sos_start, sos_end - n)
                    dup_bytes = bytes(new_data[start_pos:start_pos+n])
                    insert_pos = start_pos + n
                    for b in reversed(dup_bytes):
                        new_data.insert(insert_pos, b)
                    fname = f"{self.base_name}_sos_dup{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"duplicati {n} byte", f"da {start_pos:X}"))
                
                elif subname == "insertion":
                    insert_pos = random.randint(sos_start, sos_end)
                    ins_bytes = random_bytes(n)
                    for b in reversed(ins_bytes):
                        new_data.insert(insert_pos, b)
                    fname = f"{self.base_name}_sos_ins{n}"
                    self.save_image(new_data, folder, fname)
                    file_list.append((fname+".jpg", f"inseriti {n} byte casuali", f"a {insert_pos:X}"))
            
            # README
            tech = f"Livelli utilizzati: {', '.join(map(str, all_levels[:10]))} ... (totale {len(all_levels)})"
            hex_inst = f"Vai a {sos_start:X}, applica la modifica descritta."
            generate_readme(folder, f"SOS – {subname.replace('_',' ').title()}", 
                            desc, tech, hex_inst, file_list)
            print(f"   ✅ {subname}: {len(file_list)} versioni")
    
    # ------------------------------------------
    # RUN ALL
    # ------------------------------------------
    def run_all(self):
        print(f"\n🚀 Avvio glitch per: {self.input_path.name}")
        print(f"📁 Output: {self.output_dir}")
        print("=" * 70)
        self.technique_appn()
        self.technique_dqt()
        self.technique_sof()
        self.technique_dht()
        self.technique_sos()
        print("\n✅ Tutte le tecniche completate!")

# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="JPEG Glitcher Pro")
    parser.add_argument('-i', '--input', help='Percorso JPEG (default: primo trovato)')
    parser.add_argument('-o', '--output', default='glitch_output', help='Cartella output')
    args = parser.parse_args()
    
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ File non trovato: {input_path}")
            sys.exit(1)
    else:
        input_path = find_jpeg_file(".")
        if not input_path:
            print("❌ Nessun file JPEG trovato.")
            sys.exit(1)
        print(f"📷 Usando: {input_path.name}")
    
    glitcher = JPEGGlitcherPro(input_path, Path(args.output))
    glitcher.run_all()

if __name__ == "__main__":
    main()
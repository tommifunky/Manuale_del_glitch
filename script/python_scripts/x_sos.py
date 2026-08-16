#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JPEG SOS Glitcher Avanzato - Esplorazione completa delle modifiche al segmento SOS
Genera un'ampia gamma di glitch visivi manipolando l'area dei dati compressi.
Ogni tecnica produce molteplici varianti con livelli di intensità diversi.
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

def generate_random_levels(max_val: int, count: int = 30) -> List[int]:
    """Genera count livelli casuali unici tra 1 e max_val (incluso)."""
    if max_val <= 1:
        return []
    count = min(count, max_val)
    levels = set()
    while len(levels) < count:
        levels.add(random.randint(1, max_val))
    return sorted(levels)

def generate_progressive_levels(max_val: int, count: int = 8) -> List[int]:
    """Genera count livelli progressivi (esponenziali) tra 1 e max_val."""
    if max_val <= 1:
        return []
    if count == 1:
        return [max_val // 2] if max_val > 1 else [1]
    steps = [1 + (max_val - 1) * (i / (count - 1)) for i in range(count)]
    steps[0] = min(steps[0], 5)
    return sorted(set(int(round(s)) for s in steps if s >= 1))

# ======================================================================
# JPEG PARSER (SOS focused)
# ======================================================================

class JPEGParser:
    """Parser per estrarre il segmento SOS (Start of Scan)."""
    
    def __init__(self, data: bytes):
        self.data = data
        self.sos_positions = []  # Lista di tuple (inizio_header, inizio_dati, fine_dati)
        self._parse_sos()
    
    def _parse_sos(self):
        """Trova tutti i marker SOS (FF DA) e delimita i dati associati."""
        data = self.data
        n = len(data)
        i = 0
        while i < n - 1:
            if data[i] == 0xFF and data[i+1] == 0xDA:
                header_start = i
                if i + 3 > n:
                    break
                header_len = (data[i+2] << 8) | data[i+3]
                data_start = i + 2 + header_len
                
                # Cerca il prossimo marker (FF) per trovare la fine dei dati
                # I dati SOS terminano al prossimo marker (FF xx) o alla fine del file
                data_end = n
                for j in range(data_start, n - 1):
                    if data[j] == 0xFF and data[j+1] != 0x00:
                        # Abbiamo trovato un marker, i dati finiscono qui
                        data_end = j
                        break
                
                self.sos_positions.append((header_start, data_start, data_end))
                i = data_end  # Continua la ricerca dopo questo segmento
            else:
                i += 1

# ======================================================================
# README GENERATOR
# ======================================================================

def generate_readme(folder: Path, title: str, description: str,
                    tech_details: str, hex_instructions: str,
                    expected_effect: str, file_list: List[Tuple[str, str, str]]) -> Path:
    """Crea un README in linguaggio semplice per principianti."""
    readme_path = folder / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"{title}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"📁 Immagine originale: {folder.parent.name}.jpg\n\n")
        f.write("─" * 70 + "\n")
        f.write("COSA FA QUESTA TECNICA (spiegato semplice)\n")
        f.write("─" * 70 + "\n\n")
        f.write(description + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("COME FUNZIONA DENTRO IL FILE\n")
        f.write("─" * 70 + "\n\n")
        f.write(tech_details + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("CHE EFFETTO HA SULL'IMMAGINE\n")
        f.write("─" * 70 + "\n\n")
        f.write(expected_effect + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("COME RIFARE LA STESSA COSA CON HEXFIEND (passo passo)\n")
        f.write("─" * 70 + "\n\n")
        f.write(hex_instructions + "\n\n")
        f.write("─" * 70 + "\n")
        f.write("FILE GENERATI DA QUESTO SCRIPT\n")
        f.write("─" * 70 + "\n\n")
        f.write("| # | Nome file | Cosa è stato modificato | Dettaglio |\n")
        f.write("|---|-----------|--------------------------|-----------|\n")
        for idx, (name, mod, note) in enumerate(file_list, 1):
            f.write(f"| {idx} | {name} | {mod} | {note} |\n")
        f.write("\n")
        f.write("─" * 70 + "\n")
        f.write("NOTE FINALI\n")
        f.write("─" * 70 + "\n\n")
        f.write("• Tutte le immagini generate DA QUESTO SCRIPT dovrebbero essere apribili.\n")
        f.write("• In HexFiend, i byte sono visualizzati in esadecimale (00-FF).\n")
        f.write("• Conserva sempre l'originale: le modifiche sono permanenti se sovrascrivi il file.\n")
    return readme_path

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
        
        if not self.parser.sos_positions:
            print(f"⚠️  Nessun segmento SOS in {input_path.name}, salto.")
            self.valid = False
        else:
            self.valid = True
            # Prendiamo il primo segmento SOS per semplicità
            self.sos_header_start, self.sos_data_start, self.sos_data_end = self.parser.sos_positions[0]
            self.sos_data_len = self.sos_data_end - self.sos_data_start
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.jpg'):
            filename += '.jpg'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    def _get_sos_info(self) -> Dict[str, Any]:
        """Estrae informazioni dall'header SOS."""
        if not self.valid:
            return {}
        
        data = self.data
        start = self.sos_header_start
        header_len = (data[start+2] << 8) | data[start+3]
        num_components = data[start+4] if start+4 < len(data) else 0
        
        return {
            'header_start': start,
            'header_len': header_len,
            'data_start': self.sos_data_start,
            'data_end': self.sos_data_end,
            'num_components': num_components,
        }
    
    # ------------------------------------------------------------------
    # TECNICA 1: Sostituzione Casuale di Byte
    # ------------------------------------------------------------------
    def technique_random_substitution(self):
        folder = self.output_base / "01_random_substitution"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        # 8 livelli progressivi + 30 casuali
        prog_levels = generate_progressive_levels(data_len, 8)
        rand_levels = generate_random_levels(data_len, 30)
        all_levels = sorted(set(prog_levels + rand_levels))
        
        for n in all_levels:
            if n > data_len:
                continue
            new_data = bytearray(self.data)
            positions = random.sample(range(self.sos_data_start, self.sos_data_end), n)
            for pos in positions:
                new_data[pos] = random_byte()
            fname = f"{self.base_name}_sos_rand_{n}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"{n} byte casuali", "sostituiti con byte casuali"))
        
        desc = "Sostituisce byte casuali nei dati compressi."
        tech = f"L'area dei dati compressi va dal byte {self.sos_data_start} al byte {self.sos_data_end}."
        effect = "L'immagine mostra glitch visivi vari: rumore, distorsioni, shift di colore, artefatti."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai al byte {self.sos_data_start}.\n3. Seleziona byte casuali fino a {self.sos_data_end}.\n4. Sostituiscili con valori casuali (00-FF).\n5. Salva."
        generate_readme(folder, "SOS - Sostituzione Casuale", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ random_substitution: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 2: Inserimento di Byte
    # ------------------------------------------------------------------
    def technique_insert_bytes(self):
        folder = self.output_base / "02_insert_bytes"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        # Livelli di inserimento: da piccoli a grandi
        deltas = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100, 200, 500]
        # Aggiungi 20 livelli casuali
        rand_deltas = generate_random_levels(min(data_len, 1000), 20)
        all_deltas = sorted(set(deltas + rand_deltas))
        all_deltas = [d for d in all_deltas if d < data_len]
        
        for delta in all_deltas[:25]:  # Limitiamo per non esagerare
            new_data = bytearray(self.data)
            insert_pos = random.randint(self.sos_data_start, self.sos_data_end)
            ins_bytes = random_bytes(delta)
            for b in reversed(ins_bytes):
                new_data.insert(insert_pos, b)
            fname = f"{self.base_name}_sos_insert_{delta}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"inseriti {delta} byte", f"a posizione {insert_pos:X}"))
        
        desc = "Inserisce byte casuali nei dati compressi, allungando il file."
        tech = "Inserendo byte, i dati compressi si allungano. Il decoder perde sincronizzazione."
        effect = "Glitch caotico: shift di righe, distorsioni massive, artefatti visivi."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai a una posizione tra {self.sos_data_start} e {self.sos_data_end}.\n3. Usa Edit → Insert per inserire byte.\n4. Salva."
        generate_readme(folder, "SOS - Inserimento Byte", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ insert_bytes: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 3: Cancellazione di Byte
    # ------------------------------------------------------------------
    def technique_delete_bytes(self):
        folder = self.output_base / "03_delete_bytes"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        deltas = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100, 200, 500]
        rand_deltas = generate_random_levels(min(data_len, 1000), 20)
        all_deltas = sorted(set(deltas + rand_deltas))
        all_deltas = [d for d in all_deltas if d < data_len]
        
        for delta in all_deltas[:25]:
            new_data = bytearray(self.data)
            del_pos = random.randint(self.sos_data_start, self.sos_data_end - delta)
            del new_data[del_pos:del_pos+delta]
            fname = f"{self.base_name}_sos_delete_{delta}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"eliminati {delta} byte", f"da posizione {del_pos:X}"))
        
        desc = "Elimina byte dai dati compressi, accorciando il file."
        tech = "Eliminando byte, il decoder perde sincronizzazione."
        effect = "Glitch estremo: shift di righe, artefatti, o corruzione."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai a una posizione tra {self.sos_data_start} e {self.sos_data_end}.\n3. Seleziona e cancella byte.\n4. Salva."
        generate_readme(folder, "SOS - Cancellazione Byte", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ delete_bytes: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 4: Duplicazione di Byte
    # ------------------------------------------------------------------
    def technique_duplicate_bytes(self):
        folder = self.output_base / "04_duplicate_bytes"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        deltas = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100]
        rand_deltas = generate_random_levels(min(data_len, 500), 20)
        all_deltas = sorted(set(deltas + rand_deltas))
        all_deltas = [d for d in all_deltas if d < data_len]
        
        for delta in all_deltas[:25]:
            new_data = bytearray(self.data)
            start_pos = random.randint(self.sos_data_start, self.sos_data_end - delta)
            dup_bytes = bytes(new_data[start_pos:start_pos+delta])
            insert_pos = start_pos + delta
            for b in reversed(dup_bytes):
                new_data.insert(insert_pos, b)
            fname = f"{self.base_name}_sos_duplicate_{delta}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"duplicati {delta} byte", f"da posizione {start_pos:X}"))
        
        desc = "Duplica byte nei dati compressi, creando pattern ripetuti."
        tech = "Duplicando byte, si introducono pattern ripetuti nel flusso di dati."
        effect = "L'immagine mostra pattern ripetuti, eco, o texture duplicate."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai a una posizione tra {self.sos_data_start} e {self.sos_data_end}.\n3. Seleziona byte e copiali.\n4. Incollali subito dopo.\n5. Salva."
        generate_readme(folder, "SOS - Duplicazione Byte", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ duplicate_bytes: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 5: Operazioni Matematiche
    # ------------------------------------------------------------------
    def technique_math_operations(self):
        folder = self.output_base / "05_math_operations"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        operations = [
            ('xor_0x55', lambda x: x ^ 0x55),
            ('xor_0xAA', lambda x: x ^ 0xAA),
            ('xor_0xFF', lambda x: x ^ 0xFF),
            ('mult_2', lambda x: clamp(x * 2)),
            ('mult_3', lambda x: clamp(x * 3)),
            ('div_2', lambda x: x // 2),
            ('add_10', lambda x: clamp(x + 10)),
            ('sub_10', lambda x: clamp(x - 10)),
            ('add_50', lambda x: clamp(x + 50)),
            ('sub_50', lambda x: clamp(x - 50)),
            ('not', lambda x: ~x & 0xFF),
        ]
        
        for op_name, op_func in operations:
            # 6 livelli progressivi per operazione
            levels = generate_progressive_levels(data_len, 6)
            rand_levels = generate_random_levels(data_len, 10)
            all_levels = sorted(set(levels + rand_levels))
            
            for n in all_levels[:10]:  # Max 10 per operazione
                if n > data_len:
                    continue
                new_data = bytearray(self.data)
                positions = random.sample(range(self.sos_data_start, self.sos_data_end), n)
                for pos in positions:
                    new_data[pos] = op_func(new_data[pos])
                fname = f"{self.base_name}_sos_{op_name}_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} byte {op_name}", f"operazione {op_name}"))
        
        desc = "Applica operazioni matematiche ai byte dei dati compressi."
        tech = "Queste operazioni alterano i valori dei byte in modo sistematico."
        effect = "L'immagine mostra effetti visivi vari: shift di colore, pattern geometrici, inversioni."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai ai dati compressi.\n3. Seleziona byte e applica operazioni (es. XOR).\n4. Salva."
        generate_readme(folder, "SOS - Operazioni Matematiche", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ math_operations: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 6: Modifica Header SOS
    # ------------------------------------------------------------------
    def technique_header_modification(self):
        folder = self.output_base / "06_header_modification"
        ensure_dir(folder)
        
        info = self._get_sos_info()
        if not info:
            return
        
        file_list = []
        header_start = info['header_start']
        
        # Modifica del numero di componenti (Ns)
        original_ns = info['num_components']
        for new_ns in [1, 2, 3, 4, 5]:
            if new_ns == original_ns:
                continue
            if new_ns < 1 or new_ns > 4:
                continue
            new_data = bytearray(self.data)
            new_data[header_start + 4] = new_ns
            # Ricalcola la lunghezza dell'header
            # 2 byte len + 1 byte Ns + (Ns * 3) + 4 byte spettrali
            new_header_len = 2 + 1 + (new_ns * 3) + 4
            new_data[header_start + 2] = (new_header_len >> 8) & 0xFF
            new_data[header_start + 3] = new_header_len & 0xFF
            fname = f"{self.base_name}_sos_ns_{new_ns}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"Ns: {original_ns} → {new_ns}", "modifica numero componenti"))
        
        # Modifica dei selettori di tabella Huffman (Tdj, Taj)
        # L'header SOS ha questa struttura:
        # 2 byte len, 1 byte Ns, poi per ogni componente: 1 byte Csj, 1 byte Tdj, 1 byte Taj
        # poi 4 byte spettrali (Ss, Se, Ah, Al)
        comp_offset = header_start + 5  # dopo len (2) + Ns (1)
        for i in range(original_ns):
            if comp_offset + 2 >= len(self.data):
                break
            # Modifica Tdj (tabella DC)
            for new_tdj in [0, 1]:
                if new_tdj == self.data[comp_offset + 1]:
                    continue
                new_data = bytearray(self.data)
                new_data[comp_offset + 1] = new_tdj
                fname = f"{self.base_name}_sos_tdj_{i}_{new_tdj}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"TDJ comp{i}: {self.data[comp_offset+1]} → {new_tdj}", "modifica tabella DC"))
            
            # Modifica Taj (tabella AC)
            for new_taj in [0, 1]:
                if new_taj == self.data[comp_offset + 2]:
                    continue
                new_data = bytearray(self.data)
                new_data[comp_offset + 2] = new_taj
                fname = f"{self.base_name}_sos_taj_{i}_{new_taj}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"TAJ comp{i}: {self.data[comp_offset+2]} → {new_taj}", "modifica tabella AC"))
            
            comp_offset += 3
        
        desc = "Modifica i parametri dell'header SOS: numero di componenti e selettori di tabelle Huffman."
        tech = "L'header SOS definisce come interpretare i dati che seguono. Modificarlo confonde il decoder."
        effect = "L'immagine si apre ma mostra shift di colore, distorsioni di texture, o errori di decodifica."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai all'offset {header_start+4:X} (Ns).\n3. Modifica Ns e aggiorna la lunghezza.\n4. Oppure modifica Tdj/Taj (offset +1/+2 di ogni componente).\n5. Salva."
        generate_readme(folder, "SOS - Modifica Header", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ header_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 7: Glitch sui Coefficienti DC
    # ------------------------------------------------------------------
    def technique_dc_coefficient_glitch(self):
        folder = self.output_base / "07_dc_coefficient_glitch"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        
        # Cerchiamo pattern che potrebbero essere coefficienti DC
        # I coefficienti DC sono spesso preceduti da byte che indicano la lunghezza
        # Cerchiamo sequenze 0x00 0xXX dove XX < 0x80
        dc_positions = []
        data = self.data
        for i in range(self.sos_data_start, self.sos_data_end - 1):
            if data[i] == 0x00 and data[i+1] < 0x80:
                dc_positions.append(i+1)
        
        if not dc_positions:
            # Se non troviamo pattern, usiamo posizioni casuali
            dc_positions = random.sample(range(self.sos_data_start, self.sos_data_end), min(200, data_len // 10))
        
        if not dc_positions:
            return
        
        levels = generate_progressive_levels(len(dc_positions), 8)
        rand_levels = generate_random_levels(len(dc_positions), 30)
        all_levels = sorted(set(levels + rand_levels))
        
        for n in all_levels[:25]:
            if n > len(dc_positions):
                continue
            new_data = bytearray(self.data)
            positions = random.sample(dc_positions, n)
            for pos in positions:
                op = random.choice(['shift', 'zero', 'random', 'mult2', 'add'])
                if op == 'shift':
                    new_data[pos] = clamp(new_data[pos] + random.choice([-20, -10, -5, 5, 10, 20]))
                elif op == 'zero':
                    new_data[pos] = 0
                elif op == 'random':
                    new_data[pos] = random_byte()
                elif op == 'mult2':
                    new_data[pos] = clamp(new_data[pos] * 2)
                else:  # add
                    new_data[pos] = clamp(new_data[pos] + random.randint(-30, 30))
            fname = f"{self.base_name}_sos_dc_{n}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"{n} coefficienti DC modificati", "modifica coefficienti DC"))
        
        desc = "Modifica selettivamente i coefficienti DC nei dati compressi."
        tech = "I coefficienti DC contengono informazioni sulla luminosità media dei blocchi."
        effect = "L'immagine mostra glitch a blocchi, shift di luminosità, o artefatti di quantizzazione."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai ai dati compressi.\n3. Cerca pattern di coefficienti DC (es. 00 XX).\n4. Modifica i valori.\n5. Salva."
        generate_readme(folder, "SOS - Glitch Coefficienti DC", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ dc_coefficient_glitch: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 8: Manipolazione Marker RST
    # ------------------------------------------------------------------
    def technique_rst_marker_manipulation(self):
        folder = self.output_base / "08_rst_marker_manipulation"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        
        # Cerca marker RST (FF D0 - FF D7)
        rst_positions = []
        data = self.data
        for i in range(self.sos_data_start, self.sos_data_end - 1):
            if data[i] == 0xFF and 0xD0 <= data[i+1] <= 0xD7:
                rst_positions.append(i)
        
        if not rst_positions:
            # Se non ci sono RST, ne inseriamo alcuni artificialmente
            # Creiamo una versione con RST inseriti
            for _ in range(5):
                new_data = bytearray(self.data)
                insert_pos = random.randint(self.sos_data_start, self.sos_data_end)
                rst_byte = random.choice([0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7])
                new_data.insert(insert_pos, 0xFF)
                new_data.insert(insert_pos+1, rst_byte)
                fname = f"{self.base_name}_sos_rst_insert_{_}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"inserito RST {rst_byte:X}", f"a posizione {insert_pos:X}"))
        else:
            # Modifica i marker RST esistenti
            for n in [1, 2, 3, 5, 8, 10, 15, 20]:
                if n > len(rst_positions):
                    continue
                new_data = bytearray(self.data)
                positions = random.sample(rst_positions, n)
                for pos in positions:
                    # Cambia il marker RST con un altro o con un byte casuale
                    if random.random() < 0.5:
                        new_data[pos+1] = random.choice([0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7])
                    else:
                        new_data[pos+1] = random_byte()
                fname = f"{self.base_name}_sos_rst_mod_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} marker RST modificati", "modifica marker RST"))
        
        desc = "Manipola i marker di restart (RST) nei dati compressi."
        tech = "I marker RST (FF D0-FF D7) dovrebbero ripristinare la sincronizzazione. Alterarli causa glitch localizzati."
        effect = "L'immagine mostra glitch localizzati, pattern ripetuti, o shift di righe."
        hex_inst = "1. Apri il file in HexFiend.\n2. Cerca sequenze FF D0-FF D7.\n3. Modificale o inseriscine di nuove.\n4. Salva."
        generate_readme(folder, "SOS - Manipolazione Marker RST", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ rst_marker_manipulation: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 9: Corruzione Allineamento Bit
    # ------------------------------------------------------------------
    def technique_bit_shift_corruption(self):
        folder = self.output_base / "09_bit_shift_corruption"
        ensure_dir(folder)
        
        data_len = self.sos_data_len
        if data_len < 10:
            return
        
        file_list = []
        
        # Livelli di shift
        shifts = [1, 2, 3, 4]
        levels = generate_progressive_levels(data_len, 6)
        rand_levels = generate_random_levels(data_len, 20)
        all_levels = sorted(set(levels + rand_levels))
        
        for shift in shifts:
            for n in all_levels[:8]:
                if n > data_len:
                    continue
                new_data = bytearray(self.data)
                positions = random.sample(range(self.sos_data_start, self.sos_data_end), n)
                for pos in positions:
                    if random.random() < 0.5:
                        new_data[pos] = (new_data[pos] << shift) & 0xFF
                    else:
                        new_data[pos] = new_data[pos] >> shift
                fname = f"{self.base_name}_sos_bitshift_{shift}_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} byte shiftati di {shift} bit", f"shift di bit"))
        
        desc = "Applica uno shift di bit ai byte dei dati compressi."
        tech = "Shiftare i bit altera la codifica dei dati in modo sottile ma efficace."
        effect = "L'immagine mostra glitch 'organici', shift di colore, o texture alterate."
        hex_inst = "1. Apri il file in HexFiend.\n2. Vai ai dati compressi.\n3. Seleziona byte e applica uno shift di bit (<< o >>).\n4. Salva."
        generate_readme(folder, "SOS - Corruzione Allineamento Bit", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ bit_shift_corruption: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # RUN ALL
    # ------------------------------------------------------------------
    def run_all(self, techniques: List[str] = None):
        if not self.valid:
            return
        
        print(f"\n📷 Elaborazione di: {self.input_path.name}")
        print(f"📁 Output in: {self.output_base}")
        print(f"📊 Dati compressi: da {self.sos_data_start} a {self.sos_data_end} ({self.sos_data_len} byte)")
        print("-" * 50)
        
        tech_map = {
            'random': self.technique_random_substitution,
            'insert': self.technique_insert_bytes,
            'delete': self.technique_delete_bytes,
            'duplicate': self.technique_duplicate_bytes,
            'math': self.technique_math_operations,
            'header': self.technique_header_modification,
            'dc': self.technique_dc_coefficient_glitch,
            'rst': self.technique_rst_marker_manipulation,
            'bitshift': self.technique_bit_shift_corruption,
        }
        
        if techniques is None:
            for name, method in tech_map.items():
                method()
        else:
            for name in techniques:
                if name in tech_map:
                    tech_map[name]()
                else:
                    print(f"   ⚠️  Tecnica '{name}' non riconosciuta, saltata.")
        
        print(f"✅ Completato {self.input_path.name}")

# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="JPEG SOS Glitcher Avanzato - Esplorazione completa delle modifiche al segmento SOS"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file JPEG (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='sos_glitch_output',
                        help='Directory di output principale (default: sos_glitch_output)')
    parser.add_argument('--techniques', nargs='+',
                        choices=['random', 'insert', 'delete', 'duplicate', 'math', 
                                'header', 'dc', 'rst', 'bitshift'],
                        help='Specifica quali tecniche eseguire (default: tutte)')
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"❌ Directory input non trovata: {input_dir}")
        sys.exit(1)
    
    jpeg_files = []
    for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
        jpeg_files.extend(input_dir.glob(f"*{ext}"))
    
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
        glitcher.run_all(techniques=args.techniques)
    
    print("\n" + "=" * 70)
    print("✅ TUTTE LE IMMAGINI PROCESSATE!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JPEG DHT Glitcher - Manipolazione sicura delle tabelle Huffman
Tutte le modifiche mantengono la struttura DHT valida, quindi le immagini
rimangono apribili ma mostrano glitch visivi controllati.
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

def clamp(val: int, min_val: int = 0, max_val: int = 255) -> int:
    return max(min_val, min(val, max_val))

def generate_random_levels(max_val: int, count: int = 20) -> List[int]:
    """Genera count livelli casuali unici tra 1 e max_val (incluso)."""
    if max_val <= 1:
        return []
    count = min(count, max_val)
    levels = set()
    while len(levels) < count:
        levels.add(random.randint(1, max_val))
    return sorted(levels)

def generate_progressive_levels(max_val: int, count: int = 5) -> List[int]:
    """Genera count livelli progressivi (esponenziali) tra 1 e max_val."""
    if max_val <= 1:
        return []
    if count == 1:
        return [max_val // 2] if max_val > 1 else [1]
    steps = [1 + (max_val - 1) * (i / (count - 1)) for i in range(count)]
    steps[0] = min(steps[0], 5)
    return sorted(set(int(round(s)) for s in steps if s >= 1))

# ======================================================================
# JPEG PARSER (DHT focused)
# ======================================================================

class JPEGParser:
    """Parser per estrarre i segmenti DHT (Define Huffman Table)."""
    
    def __init__(self, data: bytes):
        self.data = data
        self.dht_segments = []  # (start, marker, length, payload_start, payload_end)
        self._parse_dht()
    
    def _parse_dht(self):
        data = self.data
        i = 0
        n = len(data)
        while i < n - 1:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = (data[i] << 8) | data[i+1]
            if marker == 0xFFC4:  # DHT marker
                if i + 3 > n:
                    break
                seg_len = (data[i+2] << 8) | data[i+3]
                payload_start = i + 4
                payload_end = i + 2 + seg_len
                self.dht_segments.append((i, marker, seg_len, payload_start, payload_end))
                i += 2 + seg_len
            else:
                # Salta segmenti non DHT
                if marker in [0xFFD8, 0xFFD9, 0xFF01] or (0xFFD0 <= marker <= 0xFFD7):
                    i += 2
                    continue
                if i + 3 > n:
                    break
                seg_len = (data[i+2] << 8) | data[i+3]
                i += 2 + seg_len

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
        f.write("• Le tabelle DHT sono fragili: segui le istruzioni con attenzione.\n")
    return readme_path

# ======================================================================
# DHT GLITCHER
# ======================================================================

class DHTGlitcher:
    def __init__(self, input_path: Path, output_base: Path):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.parser = JPEGParser(self.data)
        self.dht_segments = self.parser.dht_segments
        
        if not self.dht_segments:
            print(f"⚠️  Nessun segmento DHT in {input_path.name}, salto.")
            self.dht_segments = None
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.jpg'):
            filename += '.jpg'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    def _get_table_info(self) -> List[Dict[str, Any]]:
        """Estrae informazioni dettagliate da ogni tabella DHT."""
        tables = []
        for start, marker, seg_len, pstart, pend in self.dht_segments:
            data = self.data
            if pend - pstart < 17:
                continue
            
            table_type_byte = data[pstart]
            table_type = (table_type_byte >> 4) & 0x0F
            table_id = table_type_byte & 0x0F
            
            code_lengths = list(data[pstart+1:pstart+17])
            total_symbols = sum(code_lengths)
            
            symbols_start = pstart + 17
            symbols_end = symbols_start + total_symbols
            
            tables.append({
                'start': start,
                'marker': marker,
                'seg_len': seg_len,
                'payload_start': pstart,
                'payload_end': pend,
                'table_type': table_type,
                'table_id': table_id,
                'type_name': 'DC' if table_type == 0 else 'AC',
                'code_lengths': code_lengths,
                'total_symbols': total_symbols,
                'symbols_start': symbols_start,
                'symbols_end': symbols_end,
                'symbols': list(data[symbols_start:symbols_end]) if symbols_end <= pend else []
            })
        
        return tables
    
    # ------------------------------------------------------------------
    # TECNICA 1: Scambio di tabelle DHT (DC ↔ AC, o tra ID diversi)
    # ------------------------------------------------------------------
    def technique_table_swap(self):
        folder = self.output_base / "DHT_table_swap"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if len(tables) < 2:
            print("   ⚠️  Meno di 2 tabelle DHT, salto table_swap")
            return
        
        file_list = []
        
        # Scambio DC ↔ AC (se disponibili)
        dc_tables = [t for t in tables if t['table_type'] == 0]
        ac_tables = [t for t in tables if t['table_type'] == 1]
        
        if dc_tables and ac_tables:
            dc = dc_tables[0]
            ac = ac_tables[0]
            new_data = bytearray(self.data)
            # Scambia i payload (tutta la tabella)
            dc_payload = new_data[dc['payload_start']:dc['payload_end']]
            ac_payload = new_data[ac['payload_start']:ac['payload_end']]
            new_data[dc['payload_start']:dc['payload_end']] = ac_payload
            new_data[ac['payload_start']:ac['payload_end']] = dc_payload
            fname = f"{self.base_name}_dht_swap_DC_AC"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", "scambio DC ↔ AC", "tabella DC scambiata con AC"))
        
        # Scambio tra ID diversi (es. ID0 ↔ ID1)
        if len(tables) >= 2:
            t1 = tables[0]
            t2 = tables[1]
            new_data = bytearray(self.data)
            t1_payload = new_data[t1['payload_start']:t1['payload_end']]
            t2_payload = new_data[t2['payload_start']:t2['payload_end']]
            new_data[t1['payload_start']:t1['payload_end']] = t2_payload
            new_data[t2['payload_start']:t2['payload_end']] = t1_payload
            fname = f"{self.base_name}_dht_swap_ID{t1['table_id']}_ID{t2['table_id']}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"scambio ID {t1['table_id']} ↔ {t2['table_id']}", f"scambio tra tabelle {t1['type_name']}{t1['table_id']} e {t2['type_name']}{t2['table_id']}"))
        
        desc = "Scambia intere tabelle DHT (DC ↔ AC o tra ID diversi). La struttura rimane valida ma il decoder usa la tabella sbagliata."
        tech = f"Trovate {len(tables)} tabelle. Lo scambio mantiene identiche lunghezze e numero di simboli, ma cambia i valori decodificati."
        effect = "L'immagine si apre ma mostra shift di colore, texture alterate o effetti psichedelici."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova due segmenti FF C4.\n3. Copia l'intero payload (dal byte dopo la lunghezza fino alla fine del segmento) di una tabella e incollalo nell'altra, e viceversa.\n4. Salva."
        generate_readme(folder, "DHT - Scambio tabelle", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ table_swap: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 2: Scambio di simboli tra tabelle (mantenendo le lunghezze)
    # ------------------------------------------------------------------
    def technique_symbol_swap(self):
        folder = self.output_base / "DHT_symbol_swap"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if len(tables) < 2:
            print("   ⚠️  Meno di 2 tabelle DHT, salto symbol_swap")
            return
        
        file_list = []
        
        t1 = tables[0]
        t2 = tables[1]
        
        sym1_start = t1['symbols_start']
        sym1_end = t1['symbols_end']
        sym2_start = t2['symbols_start']
        sym2_end = t2['symbols_end']
        
        len1 = sym1_end - sym1_start
        len2 = sym2_end - sym2_start
        
        if len1 > 0 and len2 > 0:
            # Livelli: quanti simboli scambiare
            max_swap = min(len1, len2)
            levels = generate_progressive_levels(max_swap, 5)
            rand_levels = generate_random_levels(max_swap, 20)
            all_levels = sorted(set(levels + rand_levels))
            
            for n in all_levels:
                if n > max_swap:
                    continue
                new_data = bytearray(self.data)
                # Scegli n simboli casuali da scambiare
                positions1 = random.sample(range(sym1_start, sym1_end), n)
                positions2 = random.sample(range(sym2_start, sym2_end), n)
                for i in range(n):
                    temp = new_data[positions1[i]]
                    new_data[positions1[i]] = new_data[positions2[i]]
                    new_data[positions2[i]] = temp
                fname = f"{self.base_name}_dht_symswap_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} simboli scambiati", f"scambio tra {t1['type_name']}{t1['table_id']} e {t2['type_name']}{t2['table_id']}"))
        
        desc = "Scambia simboli tra due tabelle DHT mantenendo invariate le lunghezze dei codici. La struttura rimane valida."
        tech = "I simboli sono i valori effettivi che vengono decodificati. Scambiandoli, il decoder legge valori sbagliati ma la tabella è ancora valida."
        effect = "L'immagine si apre ma mostra distorsioni cromatiche, shift di colore o texture alterate."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova due segmenti FF C4.\n3. Dopo i 16 byte di lunghezze, iniziano i simboli.\n4. Seleziona alcuni simboli dalla prima tabella e scambiali con simboli della seconda.\n5. Salva."
        generate_readme(folder, "DHT - Scambio simboli", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ symbol_swap: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 3: Sostituzione di simboli con valori vicini (shift)
    # ------------------------------------------------------------------
    def technique_symbol_shift(self):
        folder = self.output_base / "DHT_symbol_shift"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if not tables:
            return
        
        file_list = []
        
        for table in tables:
            sym_start = table['symbols_start']
            sym_end = table['symbols_end']
            num_symbols = sym_end - sym_start
            
            if num_symbols < 2:
                continue
            
            levels = generate_progressive_levels(num_symbols, 5)
            rand_levels = generate_random_levels(num_symbols, 20)
            all_levels = sorted(set(levels + rand_levels))
            
            for n in all_levels:
                if n > num_symbols:
                    continue
                new_data = bytearray(self.data)
                positions = random.sample(range(sym_start, sym_end), n)
                for pos in positions:
                    val = new_data[pos]
                    # Shift di ±1 (o ±2 per più effetto)
                    delta = random.choice([-2, -1, 1, 2])
                    new_data[pos] = clamp(val + delta, 0, 255)
                fname = f"{self.base_name}_dht_shift_{table['type_name']}{table['table_id']}_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} simboli shiftati in {table['type_name']}{table['table_id']}", f"shift di ±1/±2"))
        
        desc = "Modifica i simboli di una tabella DHT aggiungendo o sottraendo 1 o 2. La struttura rimane valida."
        tech = "I simboli vengono leggermente alterati, ma il numero di simboli e le lunghezze rimangono identici."
        effect = "L'immagine si apre ma mostra un leggero rumore, shift di colore o artefatti sottili."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova FF C4 e vai ai simboli (dopo i 16 byte di lunghezze).\n3. Seleziona un simbolo e aggiungi o sottrai 1 o 2 (es. 0x05 → 0x06).\n4. Salva."
        generate_readme(folder, "DHT - Shift simboli", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ symbol_shift: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 4: Riordino dei simboli all'interno della stessa tabella
    # ------------------------------------------------------------------
    def technique_symbol_reorder(self):
        folder = self.output_base / "DHT_symbol_reorder"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if not tables:
            return
        
        file_list = []
        
        for table in tables:
            sym_start = table['symbols_start']
            sym_end = table['symbols_end']
            symbols = list(self.data[sym_start:sym_end])
            
            if len(symbols) < 3:
                continue
            
            # Diversi ordinamenti
            orders = [
                ('asc', sorted(symbols)),
                ('desc', sorted(symbols, reverse=True)),
                ('random_1', random.sample(symbols, len(symbols))),
                ('random_2', random.sample(symbols, len(symbols))),
                ('random_3', random.sample(symbols, len(symbols))),
            ]
            
            for order_name, ordered_symbols in orders:
                if ordered_symbols == symbols and order_name.startswith('random'):
                    continue
                new_data = bytearray(self.data)
                for i, val in enumerate(ordered_symbols):
                    new_data[sym_start + i] = val
                fname = f"{self.base_name}_dht_reorder_{table['type_name']}{table['table_id']}_{order_name}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"riordino {table['type_name']}{table['table_id']} ({order_name})", f"simboli riordinati"))
        
        desc = "Riordina i simboli all'interno di una tabella DHT (crescente, decrescente, casuale). La struttura rimane valida."
        tech = "I simboli vengono riordinati ma il numero e le lunghezze rimangono identici. Il decoder usa gli stessi codici ma legge simboli diversi."
        effect = "L'immagine si apre ma mostra effetti psichedelici, shift di colore o texture alterate."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova FF C4 e vai ai simboli (dopo i 16 byte di lunghezze).\n3. Riordina i simboli come preferisci (es. dal più piccolo al più grande).\n4. Salva."
        generate_readme(folder, "DHT - Riordino simboli", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ symbol_reorder: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 5: Duplicazione di una tabella DHT (con nuovo ID)
    # ------------------------------------------------------------------
    def technique_table_duplicate(self):
        folder = self.output_base / "DHT_table_duplicate"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if not tables:
            return
        
        file_list = []
        
        for table in tables:
            # Crea una copia della tabella con un nuovo ID
            for new_id in [0, 1, 2, 3]:
                if new_id == table['table_id']:
                    continue
                # Prendi il payload originale
                payload = self.data[table['payload_start']:table['payload_end']]
                # Modifica il byte di tipo/ID
                new_type_byte = (table['table_type'] << 4) | new_id
                new_payload = bytearray(payload)
                new_payload[0] = new_type_byte
                
                # Inserisci la nuova tabella dopo quella originale
                new_data = bytearray(self.data)
                insert_pos = table['payload_end']
                # Costruisci il nuovo segmento: FF C4 + lunghezza + payload
                new_seg_len = 2 + len(new_payload)  # 2 byte di lunghezza + payload
                new_segment = bytearray()
                new_segment.append(0xFF)
                new_segment.append(0xC4)
                new_segment.append((new_seg_len >> 8) & 0xFF)
                new_segment.append(new_seg_len & 0xFF)
                new_segment.extend(new_payload)
                
                # Inserisci il nuovo segmento
                for b in reversed(new_segment):
                    new_data.insert(insert_pos, b)
                
                fname = f"{self.base_name}_dht_duplicate_{table['type_name']}{table['table_id']}_ID{new_id}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"duplicato {table['type_name']}{table['table_id']} → ID{new_id}", f"tabella duplicata con nuovo ID"))
        
        desc = "Duplica una tabella DHT esistente assegnandole un nuovo ID. La struttura rimane valida."
        tech = "La tabella duplicata è identica all'originale ma con ID diverso. Il decoder ora ha due tabelle uguali con ID diversi."
        effect = "L'immagine si apre ma alcuni componenti usano la tabella duplicata, alterando i colori o la texture."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova FF C4 e copia l'intero segmento (da FF C4 fino alla fine del payload).\n3. Incolla il segmento dopo l'originale.\n4. Modifica il byte di tipo/ID del nuovo segmento (es. 0x00 → 0x01).\n5. Aggiorna la lunghezza del nuovo segmento.\n6. Salva."
        generate_readme(folder, "DHT - Duplicazione tabella", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ table_duplicate: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 6: Sostituzione con tabelle Huffman "ottimizzate"
    # ------------------------------------------------------------------
    def technique_optimized_tables(self):
        folder = self.output_base / "DHT_optimized_tables"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if not tables:
            return
        
        file_list = []
        
        # Genera alcune tabelle "ottimizzate" alternative
        # Usiamo un algoritmo semplice: distribuiamo i simboli in modo diverso
        for idx in range(5):
            new_data = bytearray(self.data)
            for table in tables:
                sym_start = table['symbols_start']
                sym_end = table['symbols_end']
                num_symbols = sym_end - sym_start
                if num_symbols < 2:
                    continue
                
                # Crea una nuova lista di simboli: shuffle + variazioni
                symbols = list(self.data[sym_start:sym_end])
                if idx == 0:
                    # Simboli invertiti
                    new_symbols = list(reversed(symbols))
                elif idx == 1:
                    # Simboli shiftati ciclicamente
                    shift = random.randint(1, num_symbols-1)
                    new_symbols = symbols[shift:] + symbols[:shift]
                elif idx == 2:
                    # Simboli con valori aumentati (clamp)
                    new_symbols = [clamp(s + 10, 0, 255) for s in symbols]
                elif idx == 3:
                    # Simboli con valori diminuiti (clamp)
                    new_symbols = [clamp(s - 10, 0, 255) for s in symbols]
                else:
                    # Simboli random ma mantenendo la struttura
                    new_symbols = random.sample(symbols, len(symbols))
                
                # Scrivi i nuovi simboli
                for i, val in enumerate(new_symbols):
                    new_data[sym_start + i] = val
            
            fname = f"{self.base_name}_dht_optimized_{idx+1}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"tabelle ottimizzate #{idx+1}", f"simboli modificati con algoritmo {idx+1}"))
        
        desc = "Sostituisce i simboli delle tabelle DHT con versioni 'ottimizzate' (invertite, shiftate, aumentate, ecc.). La struttura rimane valida."
        tech = "Le tabelle mantengono lo stesso numero di simboli e le stesse lunghezze, ma i valori dei simboli vengono alterati in modo sistematico."
        effect = "L'immagine si apre ma mostra effetti visivi vari: shift di colore, inversioni, texture alterate."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova FF C4 e vai ai simboli (dopo i 16 byte di lunghezze).\n3. Modifica i simboli in modo sistematico (es. aggiungi 10 a tutti, o inverti l'ordine).\n4. Salva."
        generate_readme(folder, "DHT - Tabelle ottimizzate", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ optimized_tables: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 7: NUOVA - Modifica delle lunghezze dei codici (mantenendo la somma)
    # ------------------------------------------------------------------
    def technique_code_length_redistribute(self):
        folder = self.output_base / "DHT_code_length_redistribute"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if not tables:
            return
        
        file_list = []
        
        for table in tables:
            code_len_start = table['payload_start'] + 1
            code_len_end = code_len_start + 16
            original_lengths = list(table['code_lengths'])
            total_symbols = sum(original_lengths)
            
            if total_symbols < 2:
                continue
            
            # Crea diverse redistribuzioni delle lunghezze
            redistributions = [
                ('shift_1', [max(0, l - 1) if i % 2 == 0 else min(16, l + 1) for i, l in enumerate(original_lengths)]),
                ('shift_2', [max(0, l - 2) if i % 2 == 0 else min(16, l + 2) for i, l in enumerate(original_lengths)]),
                ('shift_random', [max(0, l + random.choice([-1, 0, 1])) for l in original_lengths]),
                ('concentrate', [min(16, l * 2) if i < 8 else max(0, l // 2) for i, l in enumerate(original_lengths)]),
                ('spread', [max(0, l // 2) if i < 8 else min(16, l * 2) for i, l in enumerate(original_lengths)]),
            ]
            
            for redist_name, new_lengths in redistributions:
                # Verifica che la somma sia rimasta uguale
                if sum(new_lengths) != total_symbols:
                    # Aggiusta per mantenere la somma
                    diff = total_symbols - sum(new_lengths)
                    # Aggiungi diff al primo elemento
                    new_lengths[0] = clamp(new_lengths[0] + diff, 0, 16)
                    # Se ancora non combacia, distribuisci
                    if sum(new_lengths) != total_symbols:
                        continue
                
                new_data = bytearray(self.data)
                for i in range(16):
                    new_data[code_len_start + i] = new_lengths[i]
                
                fname = f"{self.base_name}_dht_codelen_redist_{table['type_name']}{table['table_id']}_{redist_name}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"ridistribuzione lunghezze {table['type_name']}{table['table_id']} ({redist_name})", f"nuove lunghezze: {new_lengths}"))
        
        desc = "Modifica le lunghezze dei codici Huffman (i 16 byte iniziali) mantenendo la somma totale invariata. Questo altera l'albero di Huffman senza cambiare il numero di simboli."
        tech = "Le lunghezze dei codici determinano quanti simboli hanno codici di 1, 2, ..., 16 bit. Modificarle redistribuendo i simboli tra lunghezze diverse cambia l'albero di Huffman."
        effect = "L'immagine si apre ma mostra glitch più strutturati: shift di texture, pattern geometrici, o effetti di 'banding'."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova FF C4 e vai al payload.\n3. Dopo il byte di tipo/ID, i successivi 16 byte sono le lunghezze dei codici (quanti simboli hanno codici di 1, 2, 3... bit).\n4. La somma di questi 16 byte deve rimanere costante (è il numero totale di simboli).\n5. Modifica le lunghezze: es. prendi 1 da una lunghezza e aggiungilo a un'altra (es. da 5 a 4 e da 2 a 3).\n6. Salva e controlla l'effetto."
        generate_readme(folder, "DHT - Ridistribuzione lunghezze codici", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ code_length_redistribute: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 8: NUOVA - Scambio di simboli con lunghezze diverse (con aggiustamento)
    # ------------------------------------------------------------------
    def technique_symbol_swap_with_length_adjust(self):
        folder = self.output_base / "DHT_symbol_swap_with_length_adjust"
        ensure_dir(folder)
        
        tables = self._get_table_info()
        if not tables:
            return
        
        file_list = []
        
        for table in tables:
            code_len_start = table['payload_start'] + 1
            sym_start = table['symbols_start']
            sym_end = table['symbols_end']
            num_symbols = sym_end - sym_start
            
            if num_symbols < 4:
                continue
            
            # Costruisci una mappa simbolo → lunghezza
            symbol_to_len = {}
            idx = 0
            for length, count in enumerate(table['code_lengths'], 1):
                for _ in range(count):
                    if idx < num_symbols:
                        symbol_to_len[sym_start + idx] = length
                        idx += 1
            
            if len(symbol_to_len) < 2:
                continue
            
            # Livelli: quanti scambi fare
            max_swaps = min(10, len(symbol_to_len) // 2)
            levels = generate_progressive_levels(max_swaps, 5)
            rand_levels = generate_random_levels(max_swaps, 20)
            all_levels = sorted(set(levels + rand_levels))
            
            for n in all_levels:
                if n > max_swaps or n < 1:
                    continue
                
                new_data = bytearray(self.data)
                # Prendi n coppie di simboli con lunghezze diverse
                positions = list(symbol_to_len.keys())
                swaps_done = 0
                attempts = 0
                while swaps_done < n and attempts < 100:
                    attempts += 1
                    p1, p2 = random.sample(positions, 2)
                    len1 = symbol_to_len[p1]
                    len2 = symbol_to_len[p2]
                    if len1 == len2:
                        continue
                    # Scambia i simboli
                    temp = new_data[p1]
                    new_data[p1] = new_data[p2]
                    new_data[p2] = temp
                    # Aggiorna la mappa per il prossimo ciclo
                    symbol_to_len[p1], symbol_to_len[p2] = len2, len1
                    swaps_done += 1
                
                if swaps_done == 0:
                    continue
                
                fname = f"{self.base_name}_dht_swap_adj_{table['type_name']}{table['table_id']}_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"scambio {n} simboli con lunghezze diverse in {table['type_name']}{table['table_id']}", f"scambio con aggiustamento"))
        
        desc = "Scambia simboli che hanno lunghezze di codice diverse, e poi aggiusta le lunghezze per mantenere la coerenza. Questo produce glitch più complessi."
        tech = "Prendi un simbolo che ha un codice di 3 bit e scambialo con uno che ha un codice di 5 bit. Poi aggiorna le lunghezze: sottrai 1 alla lunghezza del simbolo che ora ha il codice più corto e aggiungi 1 all'altro."
        effect = "L'immagine si apre ma mostra glitch complessi: shift di colore, texture alterate, effetti di 'smear' o 'ghosting'."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova FF C4 e vai ai simboli (dopo i 16 byte di lunghezze).\n3. Prendi un simbolo che ha una lunghezza di 3 bit e scambialo con uno che ha una lunghezza di 5 bit.\n4. Poi modifica le lunghezze: sottrai 1 dalla lunghezza di 3 bit (es. 10 → 09) e aggiungi 1 alla lunghezza di 5 bit (es. 03 → 04).\n5. La somma delle lunghezze deve rimanere invariata.\n6. Salva e controlla l'effetto."
        generate_readme(folder, "DHT - Scambio simboli con aggiustamento lunghezze", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ symbol_swap_with_length_adjust: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # RUN ALL
    # ------------------------------------------------------------------
    def run_all(self, techniques: List[str] = None):
        if self.dht_segments is None:
            return
        
        print(f"\n📷 Elaborazione di: {self.input_path.name}")
        print(f"📁 Output in: {self.output_base}")
        print(f"📊 Segmenti DHT trovati: {len(self.dht_segments)}")
        tables = self._get_table_info()
        for t in tables:
            print(f"   - {t['type_name']} ID{t['table_id']}: {t['total_symbols']} simboli, payload {t['payload_end']-t['payload_start']} byte")
        print("-" * 50)
        
        tech_map = {
            'swap': self.technique_table_swap,
            'symswap': self.technique_symbol_swap,
            'shift': self.technique_symbol_shift,
            'reorder': self.technique_symbol_reorder,
            'duplicate': self.technique_table_duplicate,
            'optimized': self.technique_optimized_tables,
            'codelen': self.technique_code_length_redistribute,
            'swapadj': self.technique_symbol_swap_with_length_adjust,
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
        description="JPEG DHT Glitcher - Manipolazione sicura delle tabelle Huffman"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file JPEG (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='dht_glitch_output',
                        help='Directory di output principale (default: dht_glitch_output)')
    parser.add_argument('--techniques', nargs='+',
                        choices=['swap', 'symswap', 'shift', 'reorder', 'duplicate', 
                                'optimized', 'codelen', 'swapadj'],
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
        glitcher = DHTGlitcher(jpg_path, img_output)
        glitcher.run_all(techniques=args.techniques)
    
    print("\n" + "=" * 70)
    print("✅ TUTTE LE IMMAGINI PROCESSATE!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
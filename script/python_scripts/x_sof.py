#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JPEG SOF Glitcher - Esplorazione completa delle modifiche al segmento SOF
Processa tutti i JPEG in una cartella e per ognuno genera una struttura di cartelle
con varianti di glitch basate esclusivamente sulla modifica del segmento SOF.
Ogni tecnica ha 5 livelli graduali + 20 varianti casuali, con documentazione chiara.
"""

import os
import sys
import random
import shutil
import argparse
import math
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

def generate_dimension_levels(base_value: int, count: int = 5) -> List[int]:
    """Genera livelli di dimensioni: piccole variazioni + variazioni grandi."""
    if base_value <= 1:
        return []
    # Variazioni percentuali: ±5%, ±10%, ±20%, ±50%, ±100%
    variations = [0.05, 0.10, 0.20, 0.50, 1.00]
    levels = set()
    for var in variations:
        for sign in [-1, 1]:
            new_val = int(base_value + (base_value * var * sign))
            if new_val >= 1:
                levels.add(new_val)
    # Aggiungi alcuni valori fissi
    for val in [10, 20, 50, 100, 200, 500, 1000]:
        levels.add(val)
    # Filtra e ordina
    levels = sorted([v for v in levels if v >= 1 and v <= 65535])
    return levels[:count]

# ======================================================================
# JPEG PARSER (SOF focused)
# ======================================================================

class JPEGParser:
    """Parser per estrarre il segmento SOF (Start of Frame)."""
    
    def __init__(self, data: bytes):
        self.data = data
        self.sof_segment = None  # (start, marker, length, payload_start, payload_end)
        self._parse_sof()
    
    def _parse_sof(self):
        data = self.data
        i = 0
        n = len(data)
        # Marker SOF possibili: FF C0, FF C1, FF C2, FF C3, FF C5, FF C6, FF C7, FF C9, FF CA, FF CB, FF CD, FF CE, FF CF
        sof_markers = [0xFFC0, 0xFFC1, 0xFFC2, 0xFFC3, 0xFFC5, 0xFFC6, 0xFFC7, 
                       0xFFC9, 0xFFCA, 0xFFCB, 0xFFCD, 0xFFCE, 0xFFCF]
        
        while i < n - 1:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = (data[i] << 8) | data[i+1]
            
            if marker in sof_markers:
                if i + 3 > n:
                    break
                seg_len = (data[i+2] << 8) | data[i+3]
                payload_start = i + 4
                payload_end = i + 2 + seg_len
                self.sof_segment = (i, marker, seg_len, payload_start, payload_end)
                break  # Prendiamo solo il primo SOF trovato
            else:
                # Salta segmenti non SOF
                if marker in [0xFFD8, 0xFFD9, 0xFF01] or (0xFFD0 <= marker <= 0xFFD7):
                    i += 2
                    continue
                if i + 3 > n:
                    break
                seg_len = (data[i+2] << 8) | data[i+3]
                i += 2 + seg_len

# ======================================================================
# README GENERATOR (spiegato semplice)
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
        f.write("• Se l'immagine non si apre, è normale: fa parte del glitch. Puoi provare a riaprila con altri programmi.\n")
        f.write("• In HexFiend, i byte sono visualizzati in esadecimale (00-FF). Ogni coppia di cifre esadecimali rappresenta un byte.\n")
        f.write("• Conserva sempre l'originale: le modifiche sono permanenti se sovrascrivi il file.\n")
    return readme_path

# ======================================================================
# SOF GLITCHER
# ======================================================================

class SOFGlitcher:
    def __init__(self, input_path: Path, output_base: Path):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.parser = JPEGParser(self.data)
        self.sof_segment = self.parser.sof_segment
        
        if not self.sof_segment:
            print(f"⚠️  Nessun segmento SOF in {input_path.name}, salto.")
            self.sof_segment = None
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.jpg'):
            filename += '.jpg'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    def _get_sof_info(self) -> Dict[str, Any]:
        """Estrae le informazioni dal segmento SOF."""
        if not self.sof_segment:
            return {}
        start, marker, seg_len, pstart, pend = self.sof_segment
        data = self.data
        
        if pend - pstart < 7:
            return {}
        
        # Struttura del payload SOF:
        # byte 0: precisione (8 per JPEG standard)
        # byte 1-2: altezza (big-endian)
        # byte 3-4: larghezza (big-endian)
        # byte 5: numero di componenti
        # poi per ogni componente: 3 byte (ID, fattori di campionamento, tabella quantizzazione)
        
        precision = data[pstart]
        height = (data[pstart+1] << 8) | data[pstart+2]
        width = (data[pstart+3] << 8) | data[pstart+4]
        num_components = data[pstart+5]
        
        components = []
        comp_start = pstart + 6
        for i in range(num_components):
            if comp_start + 2 < pend:
                comp_id = data[comp_start]
                sampling = data[comp_start+1]  # bit alti: orizzontale, bit bassi: verticale
                qtable = data[comp_start+2]
                components.append({
                    'id': comp_id,
                    'sampling': sampling,
                    'h_sampling': (sampling >> 4) & 0x0F,
                    'v_sampling': sampling & 0x0F,
                    'qtable': qtable,
                    'offset': comp_start
                })
                comp_start += 3
        
        return {
            'start': start,
            'marker': marker,
            'payload_start': pstart,
            'payload_end': pend,
            'precision': precision,
            'height': height,
            'width': width,
            'num_components': num_components,
            'components': components
        }
    
    # ------------------------------------------------------------------
    # TECNICA 1: Modifica Larghezza
    # ------------------------------------------------------------------
    def technique_width_modification(self):
        folder = self.output_base / "SOF_width_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        original_width = info['width']
        pstart = info['payload_start']
        file_list = []
        
        # Genera livelli: variazioni percentuali + casuali
        levels = generate_dimension_levels(original_width, 8)
        # Aggiungi livelli casuali (20)
        random_levels = []
        for _ in range(20):
            # Random tra 1 e 65535, ma con distribuzione che preferisce valori estremi
            if random.random() < 0.3:
                # Valori molto piccoli
                new_w = random.randint(1, 50)
            elif random.random() < 0.6:
                # Valori medi
                new_w = random.randint(50, original_width * 2)
            else:
                # Valori grandi
                new_w = random.randint(original_width * 2, 65535)
            if new_w >= 1 and new_w != original_width:
                random_levels.append(new_w)
        random_levels = sorted(set(random_levels))[:20]
        all_levels = sorted(set(levels + random_levels))
        
        for new_width in all_levels:
            if new_width < 1 or new_width > 65535 or new_width == original_width:
                continue
            new_data = bytearray(self.data)
            # Scrivi larghezza (big-endian)
            new_data[pstart+3] = (new_width >> 8) & 0xFF
            new_data[pstart+4] = new_width & 0xFF
            fname = f"{self.base_name}_sof_w_{new_width}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"larghezza: {original_width} → {new_width}", f"delta: {new_width - original_width:+d}"))
        
        desc = "Questa tecnica cambia la larghezza dell'immagine modificando il valore nel segmento SOF. Il decoder usa questo valore per determinare quante colonne di pixel ci sono."
        tech = f"Larghezza originale: {original_width} pixel. Il valore è memorizzato in 2 byte (big-endian) agli offset {pstart+3:X} e {pstart+4:X}."
        effect = "L'immagine può risultare allungata o schiacciata orizzontalmente. Se la larghezza è troppo diversa, possono apparire distorsioni, bande di colore o l'immagine potrebbe non aprirsi."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai all'offset {pstart+3:X} (3 byte dopo l'inizio del payload SOF).\n3. I byte {pstart+3:X}-{pstart+4:X} contengono la larghezza in big-endian.\n4. Modifica questi byte con il nuovo valore (es. se vuoi 800 pixel, scrivi 03 20).\n5. Salva e apri l'immagine per vedere l'effetto."
        generate_readme(folder, "SOF - Modifica Larghezza", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ width_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 2: Modifica Altezza
    # ------------------------------------------------------------------
    def technique_height_modification(self):
        folder = self.output_base / "SOF_height_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        original_height = info['height']
        pstart = info['payload_start']
        file_list = []
        
        levels = generate_dimension_levels(original_height, 8)
        random_levels = []
        for _ in range(20):
            if random.random() < 0.3:
                new_h = random.randint(1, 50)
            elif random.random() < 0.6:
                new_h = random.randint(50, original_height * 2)
            else:
                new_h = random.randint(original_height * 2, 65535)
            if new_h >= 1 and new_h != original_height:
                random_levels.append(new_h)
        random_levels = sorted(set(random_levels))[:20]
        all_levels = sorted(set(levels + random_levels))
        
        for new_height in all_levels:
            if new_height < 1 or new_height > 65535 or new_height == original_height:
                continue
            new_data = bytearray(self.data)
            new_data[pstart+1] = (new_height >> 8) & 0xFF
            new_data[pstart+2] = new_height & 0xFF
            fname = f"{self.base_name}_sof_h_{new_height}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"altezza: {original_height} → {new_height}", f"delta: {new_height - original_height:+d}"))
        
        desc = "Questa tecnica cambia l'altezza dell'immagine modificando il valore nel segmento SOF. Il decoder usa questo valore per determinare quante righe di pixel ci sono."
        tech = f"Altezza originale: {original_height} pixel. Il valore è memorizzato in 2 byte (big-endian) agli offset {pstart+1:X} e {pstart+2:X}."
        effect = "L'immagine può risultare allungata o schiacciata verticalmente. Grandi variazioni possono causare glitch visivi interessanti."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai all'offset {pstart+1:X} (1 byte dopo l'inizio del payload SOF).\n3. I byte {pstart+1:X}-{pstart+2:X} contengono l'altezza in big-endian.\n4. Modifica questi byte con il nuovo valore (es. se vuoi 600 pixel, scrivi 02 58).\n5. Salva e apri l'immagine."
        generate_readme(folder, "SOF - Modifica Altezza", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ height_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 3: Modifica Larghezza e Altezza insieme
    # ------------------------------------------------------------------
    def technique_both_dimensions(self):
        folder = self.output_base / "SOF_both_dimensions"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        original_width = info['width']
        original_height = info['height']
        pstart = info['payload_start']
        file_list = []
        
        # Genera 5 combinazioni progressive + 20 casuali
        # Progressive: proporzioni mantenute ma dimensioni cambiate
        ratios = [0.25, 0.5, 0.75, 1.5, 2.0]
        for ratio in ratios:
            new_w = int(original_width * ratio)
            new_h = int(original_height * ratio)
            if new_w < 1 or new_w > 65535 or new_h < 1 or new_h > 65535:
                continue
            if new_w == original_width and new_h == original_height:
                continue
            new_data = bytearray(self.data)
            new_data[pstart+1] = (new_h >> 8) & 0xFF
            new_data[pstart+2] = new_h & 0xFF
            new_data[pstart+3] = (new_w >> 8) & 0xFF
            new_data[pstart+4] = new_w & 0xFF
            fname = f"{self.base_name}_sof_both_{new_w}x{new_h}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"dimensioni: {original_width}x{original_height} → {new_w}x{new_h}", f"rapporto: {ratio}"))
        
        # 20 combinazioni casuali (larghezza e altezza indipendenti)
        for _ in range(20):
            # Larghezza casuale
            if random.random() < 0.3:
                new_w = random.randint(1, 100)
            elif random.random() < 0.6:
                new_w = random.randint(100, original_width * 2)
            else:
                new_w = random.randint(original_width * 2, 65535)
            # Altezza casuale
            if random.random() < 0.3:
                new_h = random.randint(1, 100)
            elif random.random() < 0.6:
                new_h = random.randint(100, original_height * 2)
            else:
                new_h = random.randint(original_height * 2, 65535)
            
            if new_w < 1 or new_w > 65535 or new_h < 1 or new_h > 65535:
                continue
            if new_w == original_width and new_h == original_height:
                continue
            
            new_data = bytearray(self.data)
            new_data[pstart+1] = (new_h >> 8) & 0xFF
            new_data[pstart+2] = new_h & 0xFF
            new_data[pstart+3] = (new_w >> 8) & 0xFF
            new_data[pstart+4] = new_w & 0xFF
            fname = f"{self.base_name}_sof_both_rand_{new_w}x{new_h}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"dimensioni random: {new_w}x{new_h}", "larghezza e altezza casuali"))
        
        desc = "Questa tecnica modifica sia la larghezza che l'altezza dell'immagine, mantenendo o alterando le proporzioni."
        tech = f"Dimensioni originali: {original_width}x{original_height}. Le modifiche possono essere proporzionali (rapporto costante) o indipendenti."
        effect = "L'immagine può essere deformata in modi complessi: allungata, schiacciata, o con proporzioni completamente alterate."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai al payload SOF (offset {pstart:X}).\n3. Modifica i byte {pstart+1:X}-{pstart+2:X} per l'altezza e {pstart+3:X}-{pstart+4:X} per la larghezza.\n4. Salva e osserva il risultato."
        generate_readme(folder, "SOF - Modifica Entrambe le Dimensioni", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ both_dimensions: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 4: Modifica Precisione (con valori estremi)
    # ------------------------------------------------------------------
    def technique_precision_modification(self):
        folder = self.output_base / "SOF_precision_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        original_precision = info['precision']
        pstart = info['payload_start']
        file_list = []
        
        # Valori possibili per la precisione: standard + estremi
        precision_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 24, 32, 48, 64]
        # Aggiungi valori casuali
        for _ in range(15):
            precision_values.append(random.randint(1, 63))
        all_values = sorted(set(precision_values))
        
        for new_precision in all_values:
            if new_precision == original_precision:
                continue
            if new_precision < 1 or new_precision > 255:
                continue
            new_data = bytearray(self.data)
            new_data[pstart] = new_precision
            fname = f"{self.base_name}_sof_prec_{new_precision}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"precisione: {original_precision} → {new_precision}", f"cambio profondità colore"))
        
        desc = "Questa tecnica modifica la precisione dei pixel nel segmento SOF. La precisione indica quanti bit per componente di colore (di solito 8)."
        tech = f"Precisione originale: {original_precision} bit. Sono stati usati valori estremi come 1, 3, 7, 9, 15, 31, 63 per massimizzare il glitch."
        effect = "Cambiare la precisione può alterare i colori, creare banding estremo, inversioni di colore, o rendere l'immagine completamente astratta."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai all'offset {pstart:X} (inizio payload SOF).\n3. Il primo byte è la precisione.\n4. Modifica questo byte con valori estremi (es. 01, 03, 07, 0F, 1F, 3F).\n5. Salva e prova ad aprire l'immagine."
        generate_readme(folder, "SOF - Modifica Precisione (estreme)", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ precision_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 5: Modifica Numero Componenti (con valori anomali)
    # ------------------------------------------------------------------
    def technique_components_modification(self):
        folder = self.output_base / "SOF_components_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        original_num = info['num_components']
        pstart = info['payload_start']
        file_list = []
        
        # Valori possibili: standard + anomali (0, 5, 7, 12, 15)
        component_values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20]
        # Aggiungi valori casuali
        for _ in range(10):
            component_values.append(random.randint(0, 20))
        all_values = sorted(set(component_values))
        
        for new_num in all_values:
            if new_num == original_num:
                continue
            if new_num < 0 or new_num > 20:
                continue
            
            # Dobbiamo anche aggiustare i byte dei componenti
            new_data = bytearray(self.data)
            
            if new_num > original_num:
                # Aggiungi componenti (con valori fittizi)
                insert_pos = info['components'][-1]['offset'] + 3 if info['components'] else pstart + 6
                for _ in range(new_num - original_num):
                    # ID casuale, sampling 0x11 (1x1), qtable 0
                    new_data.insert(insert_pos, 0)
                    new_data.insert(insert_pos, 0x11)
                    new_data.insert(insert_pos, random.randint(1, 3))
                new_data[pstart+5] = new_num
                start, marker, seg_len, ps, pe = self.sof_segment
                new_len = seg_len + (new_num - original_num) * 3
                new_data[start+2] = (new_len >> 8) & 0xFF
                new_data[start+3] = new_len & 0xFF
            else:
                # Rimuovi componenti dalla fine
                if info['components']:
                    last_comp = info['components'][-1]
                    remove_start = last_comp['offset']
                    remove_end = remove_start + 3 * (original_num - new_num)
                    if remove_end <= len(new_data):
                        del new_data[remove_start:remove_end]
                new_data[pstart+5] = new_num
                start, marker, seg_len, ps, pe = self.sof_segment
                new_len = seg_len - (original_num - new_num) * 3
                if new_len >= 6:
                    new_data[start+2] = (new_len >> 8) & 0xFF
                    new_data[start+3] = new_len & 0xFF
            
            fname = f"{self.base_name}_sof_comp_{new_num}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"componenti: {original_num} → {new_num}", f"cambio numero canali colore"))
        
        desc = "Questa tecnica modifica il numero di componenti di colore, includendo valori anomali come 0, 5, 7, 12, 15 che confondono il decoder."
        tech = f"Numero originale di componenti: {original_num}. Valori anomali fanno sì che il decoder cerchi componenti che non esistono, leggendo byte a caso."
        effect = "L'immagine può perdere colore, mostrare artefatti cromatici estremi, o diventare completamente caotica."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai al payload SOF (offset {pstart:X}).\n3. Il byte 5 (offset {pstart+5:X}) è il numero di componenti.\n4. Modificalo con valori anomali (es. 00, 05, 07, 0C, 0F).\n5. Aggiorna la lunghezza e i byte dei componenti di conseguenza."
        generate_readme(folder, "SOF - Modifica Componenti (anomali)", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ components_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 6: Modifica Sottocampionamento
    # ------------------------------------------------------------------
    def technique_sampling_modification(self):
        folder = self.output_base / "SOF_sampling_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info or not info['components']:
            return
        
        pstart = info['payload_start']
        file_list = []
        
        sampling_values = [0x11, 0x21, 0x12, 0x22, 0x31, 0x13, 0x33, 0x41, 0x14, 0x44]
        
        for comp in info['components']:
            original_sampling = comp['sampling']
            offset = comp['offset'] + 1
            
            new_samplings = []
            for val in sampling_values:
                if val != original_sampling:
                    new_samplings.append(val)
            for _ in range(10):
                h = random.randint(1, 4)
                v = random.randint(1, 4)
                new_val = (h << 4) | v
                if new_val != original_sampling:
                    new_samplings.append(new_val)
            all_values = sorted(set(new_samplings))[:25]
            
            for new_sampling in all_values:
                if new_sampling == original_sampling:
                    continue
                if new_sampling < 0x11 or new_sampling > 0xFF:
                    continue
                new_data = bytearray(self.data)
                new_data[offset] = new_sampling
                comp_name = f"comp{comp['id']}"
                fname = f"{self.base_name}_sof_sampling_{comp_name}_{new_sampling:X}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"sampling comp{comp['id']}: {original_sampling:X} → {new_sampling:X}", f"cambio sottocampionamento"))
        
        desc = "Questa tecnica modifica i fattori di sottocampionamento di un componente colore."
        tech = "Il sampling è espresso in 2 cifre esadecimali: la prima è il fattore orizzontale, la seconda il verticale (es. 0x21 = 2x1)."
        effect = "Cambiare il sottocampionamento altera la risoluzione dei canali di colore, causando shift di colore, aliasing, o effetti di sfocatura selettiva."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Trova il componente che vuoi modificare.\n3. Il byte di sampling è il secondo byte del componente.\n4. Modificali (es. 0x11 → 0x22).\n5. Salva e controlla l'effetto."
        generate_readme(folder, "SOF - Modifica Sottocampionamento", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ sampling_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 7: Scambio Sottocampionamento tra Componenti
    # ------------------------------------------------------------------
    def technique_sampling_swap(self):
        folder = self.output_base / "SOF_sampling_swap"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info or len(info['components']) < 2:
            return
        
        file_list = []
        
        comp1 = info['components'][0]
        comp2 = info['components'][1]
        
        offset1 = comp1['offset'] + 1
        offset2 = comp2['offset'] + 1
        sampling1 = comp1['sampling']
        sampling2 = comp2['sampling']
        
        if sampling1 == sampling2:
            new_data = bytearray(self.data)
            new_data[offset1] = 0x22
            new_data[offset2] = 0x11
        else:
            new_data = bytearray(self.data)
            new_data[offset1] = sampling2
            new_data[offset2] = sampling1
        
        fname = f"{self.base_name}_sof_sampling_swap"
        self.save_image(new_data, folder, fname)
        file_list = [(fname+".jpg", f"scambio sampling tra comp1 e comp2", f"{sampling1:X} ↔ {sampling2:X}")]
        
        desc = "Questa tecnica scambia i fattori di sottocampionamento tra due componenti colore."
        tech = f"Componente 1: {sampling1:X}, Componente 2: {sampling2:X}. Scambiandoli, il decoder usa i valori sbagliati."
        effect = "L'immagine mostra shift di colore, aliasing su alcuni canali, o effetti di 'smear' (strisciamento)."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Trova il componente 1 (offset {offset1:X}) e il componente 2 (offset {offset2:X}).\n3. Scambia i valori dei byte di sampling.\n4. Salva e osserva l'effetto."
        generate_readme(folder, "SOF - Scambio Sottocampionamento", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ sampling_swap: 1 versione")
    
    # ------------------------------------------------------------------
    # TECNICA 8: NUOVA - Cambio Marker SOF (tipo di compressione)
    # ------------------------------------------------------------------
    def technique_marker_modification(self):
        folder = self.output_base / "SOF_marker_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        original_marker = info['marker']
        start = info['start']
        file_list = []
        
        # Tutti i possibili marker SOF
        all_markers = [
            0xFFC0, 0xFFC1, 0xFFC2, 0xFFC3, 0xFFC5, 0xFFC6, 
            0xFFC7, 0xFFC9, 0xFFCA, 0xFFCB, 0xFFCD, 0xFFCE, 0xFFCF
        ]
        # Descrizioni dei marker
        marker_names = {
            0xFFC0: "Baseline DCT",
            0xFFC1: "Extended sequential DCT",
            0xFFC2: "Progressive DCT",
            0xFFC3: "Lossless (sequential)",
            0xFFC5: "Extended sequential, arithmetic coding",
            0xFFC6: "Progressive, arithmetic coding",
            0xFFC7: "Lossless, arithmetic coding",
            0xFFC9: "Extended sequential, Huffman, differential",
            0xFFCA: "Progressive, Huffman, differential",
            0xFFCB: "Lossless, Huffman, differential",
            0xFFCD: "Extended sequential, arithmetic, differential",
            0xFFCE: "Progressive, arithmetic, differential",
            0xFFCF: "Lossless, arithmetic, differential"
        }
        
        for new_marker in all_markers:
            if new_marker == original_marker:
                continue
            new_data = bytearray(self.data)
            new_data[start] = (new_marker >> 8) & 0xFF
            new_data[start+1] = new_marker & 0xFF
            marker_name = marker_names.get(new_marker, f"{new_marker:X}")
            fname = f"{self.base_name}_sof_marker_{new_marker:X}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"marker: {marker_names.get(original_marker, original_marker)} → {marker_name}", f"cambio tipo compressione"))
        
        desc = "Questa tecnica cambia il tipo di marker SOF, che determina il metodo di compressione usato (baseline, progressive, lossless, ecc.)."
        tech = f"Marker originale: {marker_names.get(original_marker, f'{original_marker:X}')}. Ogni marker indica un diverso algoritmo di compressione."
        effect = "Il decoder tenta di decodificare l'immagine con un metodo diverso, producendo glitch spesso spettacolari: distorsioni improvvise, colori invertiti, immagini che si 'caricano' in modo strano."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai all'offset {start:X} (inizio SOF).\n3. I byte {start:X}-{start+1:X} sono il marker (es. FF C0).\n4. Modificali con un altro marker valido (es. FF C2 per progressive, FF C1 per extended).\n5. Salva e osserva l'effetto."
        generate_readme(folder, "SOF - Cambio Marker", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ marker_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 9: NUOVA - Modifica ID Componenti
    # ------------------------------------------------------------------
    def technique_component_id_modification(self):
        folder = self.output_base / "SOF_component_id_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info or not info['components']:
            return
        
        file_list = []
        
        # Per ogni componente, modifichiamo l'ID
        for comp in info['components']:
            original_id = comp['id']
            offset = comp['offset']  # il byte dell'ID è il primo del componente
            
            # Possibili ID (1,2,3 per Y,Cb,Cr; altri valori sono anomali)
            possible_ids = [1, 2, 3, 4, 5, 6, 7, 8, 10, 15]
            # Aggiungi valori casuali
            for _ in range(10):
                possible_ids.append(random.randint(1, 20))
            all_ids = sorted(set(possible_ids))
            
            for new_id in all_ids:
                if new_id == original_id:
                    continue
                if new_id < 0 or new_id > 255:
                    continue
                new_data = bytearray(self.data)
                new_data[offset] = new_id
                comp_name = f"comp{original_id}"
                fname = f"{self.base_name}_sof_id_{comp_name}_{new_id}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"ID comp{original_id}: {original_id} → {new_id}", f"cambio ID componente"))
        
        desc = "Questa tecnica modifica l'ID di un componente colore (es. luminanza 1 → 3, crominanza 3 → 1). Il decoder usa l'ID per sapere quale canale elaborare."
        tech = "Ogni componente ha un ID univoco (di solito 1, 2, 3). Cambiandoli, il decoder usa i canali di colore sbagliati per ricostruire l'immagine."
        effect = "Colori completamente shiftati, effetti psichedelici, negativi, o immagini con canali di colore scambiati."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Trova il componente che vuoi modificare (es. componente 0 = luminanza).\n3. Il primo byte del componente è l'ID.\n4. Modificalo (es. 01 → 03).\n5. Salva e osserva l'effetto."
        generate_readme(folder, "SOF - Modifica ID Componenti", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ component_id_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 10: NUOVA - Modifica Tabella Quantizzazione (Tq)
    # ------------------------------------------------------------------
    def technique_qtable_modification(self):
        folder = self.output_base / "SOF_qtable_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info or not info['components']:
            return
        
        file_list = []
        
        for comp in info['components']:
            original_qtable = comp['qtable']
            offset = comp['offset'] + 2  # il byte Tq è il terzo del componente
            
            # Possibili Tq (0, 1, 2, 3, più valori anomali)
            possible_tables = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 15]
            # Aggiungi valori casuali
            for _ in range(10):
                possible_tables.append(random.randint(0, 15))
            all_tables = sorted(set(possible_tables))
            
            for new_tq in all_tables:
                if new_tq == original_qtable:
                    continue
                if new_tq < 0 or new_tq > 255:
                    continue
                new_data = bytearray(self.data)
                new_data[offset] = new_tq
                comp_name = f"comp{comp['id']}"
                fname = f"{self.base_name}_sof_tq_{comp_name}_{new_tq}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"Tq comp{comp['id']}: {original_qtable} → {new_tq}", f"cambio tabella quantizzazione"))
        
        desc = "Questa tecnica modifica la tabella di quantizzazione (Tq) associata a un componente colore. La Tq determina la qualità di compressione di quel canale."
        tech = "Ogni componente usa una tabella DQT specifica (0 o 1 di solito). Cambiandola, un canale viene compresso più o meno dell'altro."
        effect = "Shift di qualità tra canali di colore. Una parte dell'immagine sarà più compressa dell'altra, creando artefatti asimmetrici o distorsioni di colore."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Trova il componente che vuoi modificare.\n3. Il terzo byte del componente è il Tq.\n4. Modificalo (es. 00 → 01).\n5. Salva e controlla l'effetto."
        generate_readme(folder, "SOF - Modifica Tabelle Quantizzazione", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ qtable_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 11: NUOVA - Modifica Lunghezza del Segmento SOF
    # ------------------------------------------------------------------
    def technique_length_modification(self):
        folder = self.output_base / "SOF_length_modification"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        start, marker, seg_len, pstart, pend = info['start'], info['marker'], self.sof_segment[2], info['payload_start'], info['payload_end']
        file_list = []
        
        # Deltas di lunghezza (positivi e negativi)
        deltas = [10, 20, 50, 100, 200, 500, -10, -20, -50, -100]
        
        for delta in deltas:
            new_len = seg_len + delta
            if new_len < 6 or new_len > 65535:
                continue
            
            new_data = bytearray(self.data)
            # Aggiorna la lunghezza (2 byte dopo il marker)
            new_data[start+2] = (new_len >> 8) & 0xFF
            new_data[start+3] = new_len & 0xFF
            
            if delta > 0:
                # Inserisci byte casuali alla fine del payload
                insert_pos = pend
                for _ in range(delta):
                    new_data.insert(insert_pos, random_byte())
            elif delta < 0:
                # Rimuovi byte dalla fine del payload
                del_start = pend + delta
                if del_start > pstart:  # non cancellare tutto il payload
                    del new_data[del_start:pend]
            
            fname = f"{self.base_name}_sof_len_{delta:+d}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"lunghezza {delta:+d} byte", f"nuova lunghezza: {new_len}"))
        
        desc = "Questa tecnica modifica il campo 'lunghezza' del segmento SOF, alterando quanti byte il decoder considera parte del segmento."
        tech = f"Lunghezza originale: {seg_len} byte. Modificandola, il decoder legge troppi o troppo pochi byte, desincronizzando tutto il resto del file."
        effect = "Glitch estremo: l'immagine spesso non si apre o mostra frammenti di altri segmenti del file. Effetti caotici e imprevedibili."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai all'offset {start+2:X} (2 byte dopo il marker).\n3. Modifica la lunghezza in big-endian.\n4. Se aumenti la lunghezza, aggiungi byte; se la diminuisci, rimuovili.\n5. Salva e prova ad aprire l'immagine."
        generate_readme(folder, "SOF - Modifica Lunghezza", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ length_modification: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 12: NUOVA - Inserimento/Rimozione Byte nel Payload
    # ------------------------------------------------------------------
    def technique_insert_delete_bytes(self):
        folder = self.output_base / "SOF_insert_delete_bytes"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info:
            return
        
        start, marker, seg_len, pstart, pend = info['start'], info['marker'], self.sof_segment[2], info['payload_start'], info['payload_end']
        file_list = []
        
        # Deltas piccoli per inserimenti/eliminazioni a metà payload
        deltas = [1, 2, 3, 5, 10, -1, -2, -3, -5, -10]
        
        for delta in deltas:
            new_len = seg_len + delta
            if new_len < 6 or new_len > 65535:
                continue
            
            new_data = bytearray(self.data)
            new_data[start+2] = (new_len >> 8) & 0xFF
            new_data[start+3] = new_len & 0xFF
            
            # Inserisci o rimuovi a metà del payload
            mid_point = pstart + (pend - pstart) // 2
            
            if delta > 0:
                for _ in range(delta):
                    new_data.insert(mid_point, random_byte())
            else:
                del_end = mid_point + abs(delta)
                if del_end <= len(new_data):
                    del new_data[mid_point:del_end]
            
            fname = f"{self.base_name}_sof_insdel_{delta:+d}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"ins/del {delta:+d} byte", f"nuova lunghezza: {new_len}"))
        
        desc = "Questa tecnica inserisce o rimuove byte all'interno del payload SOF (non solo alla fine), causando uno shift di tutti i byte successivi."
        tech = "Inserire o rimuovere byte nel mezzo del payload sposta tutti i byte successivi, creando glitch di sincronizzazione."
        effect = "Glitch caotico, spesso con shift di righe, blocchi di colore, o immagini completamente frammentate."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai al payload SOF (offset {pstart:X}).\n3. Inserisci o rimuovi byte a metà payload.\n4. Aggiorna il campo lunghezza (offset {start+2:X}).\n5. Salva e controlla il risultato."
        generate_readme(folder, "SOF - Inserimento/Eliminazione Byte", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ insert_delete_bytes: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 13: NUOVA - Scambio Interi Componenti
    # ------------------------------------------------------------------
    def technique_component_swap_all(self):
        folder = self.output_base / "SOF_component_swap_all"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info or len(info['components']) < 2:
            return
        
        file_list = []
        
        # Prendi i primi due componenti
        comp1 = info['components'][0]
        comp2 = info['components'][1]
        
        offset1 = comp1['offset']
        offset2 = comp2['offset']
        
        # Scambia tutti i 3 byte (ID, sampling, qtable)
        new_data = bytearray(self.data)
        # Copia i 3 byte del componente 1
        temp = new_data[offset1:offset1+3]
        new_data[offset1:offset1+3] = new_data[offset2:offset2+3]
        new_data[offset2:offset2+3] = temp
        
        fname = f"{self.base_name}_sof_comp_swap"
        self.save_image(new_data, folder, fname)
        file_list = [(fname+".jpg", "scambio interi componenti", f"componenti {comp1['id']} ↔ {comp2['id']} scambiati")]
        
        desc = "Questa tecnica scambia tutti i byte di due componenti colore (ID, sampling, qtable), confondendo completamente il decoder."
        tech = f"Componente 1: ID={comp1['id']}, sampling={comp1['sampling']:X}, qtable={comp1['qtable']}. Componente 2: ID={comp2['id']}, sampling={comp2['sampling']:X}, qtable={comp2['qtable']}."
        effect = "Il decoder usa informazioni completamente sbagliate per ogni canale. Risultato: colori distorti, texture stranissime, effetti psichedelici."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Trova il componente 1 (offset {offset1:X}) e il componente 2 (offset {offset2:X}).\n3. Scambia i 3 byte di ogni componente.\n4. Salva e osserva l'effetto."
        generate_readme(folder, "SOF - Scambio Interi Componenti", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ component_swap_all: 1 versione")
    
    # ------------------------------------------------------------------
    # TECNICA 14: NUOVA - Riordino Componenti
    # ------------------------------------------------------------------
    def technique_component_reorder(self):
        folder = self.output_base / "SOF_component_reorder"
        ensure_dir(folder)
        
        info = self._get_sof_info()
        if not info or len(info['components']) < 3:
            return
        
        file_list = []
        
        # Crea diversi ordini dei componenti
        comps = info['components']
        num_comps = len(comps)
        orders = []
        
        # Ordine inverso
        orders.append(list(range(num_comps-1, -1, -1)))
        # Shift circolari
        for shift in [1, 2]:
            orders.append([(i + shift) % num_comps for i in range(num_comps)])
        # Ordine casuale
        for _ in range(3):
            order = list(range(num_comps))
            random.shuffle(order)
            if order != list(range(num_comps)):
                orders.append(order)
        
        for order_idx, order in enumerate(orders):
            if order == list(range(num_comps)):
                continue
            
            # Ricostruisci il payload SOF con l'ordine modificato
            new_data = bytearray(self.data)
            pstart = info['payload_start']
            
            # Mantieni precisione, dimensioni e numero componenti
            # Il numero di componenti rimane lo stesso
            
            # Riposiziona i componenti
            old_component_bytes = []
            for comp in comps:
                old_component_bytes.append(bytes(new_data[comp['offset']:comp['offset']+3]))
            
            # Scriviamo i componenti nel nuovo ordine
            write_pos = pstart + 6
            for idx in order:
                if idx < len(old_component_bytes):
                    new_data[write_pos:write_pos+3] = old_component_bytes[idx]
                    write_pos += 3
            
            # Aggiorna i componenti nella info per i README
            order_str = " → ".join([str(comps[i]['id']) for i in order])
            original_str = " → ".join([str(c['id']) for c in comps])
            
            fname = f"{self.base_name}_sof_reorder_{order_idx}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"ordine: {original_str} → {order_str}", f"riordino componenti"))
        
        desc = "Questa tecnica riordina i componenti colore nel SOF, cambiando l'ordine in cui vengono decodificati i canali."
        tech = f"Ordine originale: {[c['id'] for c in comps]}. Modificando l'ordine, i canali di colore vengono scambiati (es. il rosso diventa blu)."
        effect = "I canali di colore vengono scambiati, producendo shift di colore estremi e immagini con palette alterate."
        hex_inst = f"1. Apri il file in HexFiend.\n2. Vai al payload SOF (offset {pstart+6:X}).\n3. I componenti sono in sequenza di 3 byte ciascuno.\n4. Riordina i blocchi di 3 byte per cambiare l'ordine dei canali.\n5. Salva e osserva l'effetto."
        generate_readme(folder, "SOF - Riordino Componenti", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ component_reorder: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # RUN ALL
    # ------------------------------------------------------------------
    def run_all(self, techniques: List[str] = None):
        if self.sof_segment is None:
            return
        
        print(f"\n📷 Elaborazione di: {self.input_path.name}")
        print(f"📁 Output in: {self.output_base}")
        
        info = self._get_sof_info()
        if info:
            print(f"📊 Dimensioni originali: {info['width']}x{info['height']}")
            print(f"📊 Componenti: {info['num_components']}, Precisione: {info['precision']}")
        print("-" * 50)
        
        # Mappa delle tecniche (tutte)
        tech_map = {
            'width': self.technique_width_modification,
            'height': self.technique_height_modification,
            'both': self.technique_both_dimensions,
            'precision': self.technique_precision_modification,
            'components': self.technique_components_modification,
            'sampling': self.technique_sampling_modification,
            'sampling_swap': self.technique_sampling_swap,
            'marker': self.technique_marker_modification,
            'id': self.technique_component_id_modification,
            'qtable': self.technique_qtable_modification,
            'length': self.technique_length_modification,
            'insdel': self.technique_insert_delete_bytes,
            'swapall': self.technique_component_swap_all,
            'reorder': self.technique_component_reorder,
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
        description="JPEG SOF Glitcher - Esplorazione completa delle modifiche al segmento SOF"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file JPEG (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='sof_glitch_output',
                        help='Directory di output principale (default: sof_glitch_output)')
    parser.add_argument('--techniques', nargs='+',
                        choices=['width', 'height', 'both', 'precision', 'components', 'sampling', 'sampling_swap',
                                 'marker', 'id', 'qtable', 'length', 'insdel', 'swapall', 'reorder'],
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
        glitcher = SOFGlitcher(jpg_path, img_output)
        glitcher.run_all(techniques=args.techniques)
    
    print("\n" + "=" * 70)
    print("✅ TUTTE LE IMMAGINI PROCESSATE!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
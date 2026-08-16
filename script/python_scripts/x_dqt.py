#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JPEG DQT Glitcher - Esplorazione avanzata delle tabelle DQT
Ora con più tecniche, pattern spaziali e README chiari per principianti.
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
    path.mkdir(parents=True, exist_ok=True)

def random_byte() -> int:
    return random.randint(0, 255)

def clamp(val: int, min_val: int = 0, max_val: int = 255) -> int:
    return max(min_val, min(val, max_val))

def generate_random_levels(max_val: int, count: int = 20) -> List[int]:
    if max_val <= 1:
        return []
    count = min(count, max_val)
    levels = set()
    while len(levels) < count:
        levels.add(random.randint(1, max_val))
    return sorted(levels)

def generate_progressive_levels(max_val: int, count: int = 5) -> List[int]:
    if max_val <= 1:
        return []
    if count == 1:
        return [max_val // 2] if max_val > 1 else [1]
    steps = [1 + (max_val - 1) * (i / (count - 1)) for i in range(count)]
    steps[0] = min(steps[0], 5)
    return sorted(set(int(round(s)) for s in steps if s >= 1))

# ======================================================================
# JPEG PARSER (DQT focused)
# ======================================================================

class JPEGParser:
    def __init__(self, data: bytes):
        self.data = data
        self.dqt_segments = []  # (start, payload_start, payload_end)
        self._parse_dqt()
    
    def _parse_dqt(self):
        data = self.data
        i = 0
        n = len(data)
        while i < n - 1:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = (data[i] << 8) | data[i+1]
            if marker == 0xFFDB:
                if i + 3 > n:
                    break
                seg_len = (data[i+2] << 8) | data[i+3]
                payload_start = i + 4
                payload_end = i + 2 + seg_len
                self.dqt_segments.append((i, payload_start, payload_end))
                i += 2 + seg_len
            else:
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
# DQT GLITCHER (ESPANSO)
# ======================================================================

class DQTGlitcher:
    def __init__(self, input_path: Path, output_base: Path):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        with open(input_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.parser = JPEGParser(self.data)
        self.dqt_segments = self.parser.dqt_segments
        if not self.dqt_segments:
            print(f"⚠️  Nessun segmento DQT in {input_path.name}, salto.")
            self.dqt_segments = None
    
    def save_image(self, data: bytes, folder: Path, filename: str) -> Path:
        ensure_dir(folder)
        if not filename.endswith('.jpg'):
            filename += '.jpg'
        path = folder / filename
        with open(path, 'wb') as f:
            f.write(data)
        return path
    
    def _get_all_coeff_positions(self) -> List[Tuple[int, int, int]]:
        """Restituisce (posizione, valore_originale, indice_coeff) per tutti i coeff DQT."""
        positions = []
        for start, pstart, pend in self.dqt_segments:
            if pend - pstart < 65:
                continue
            # Il primo byte del payload è il byte di controllo (precision + table ID)
            # I coefficienti iniziano da pstart+1
            for idx, pos in enumerate(range(pstart + 1, pend)):
                positions.append((pos, self.data[pos], idx))  # idx da 0 a 63 per ogni tabella
        return positions
    
    def _modify_coeffs(self, positions: List[int], operation: str, factor: int = 0) -> bytearray:
        new_data = bytearray(self.data)
        for pos in positions:
            val = new_data[pos]
            if operation == 'random':
                new_data[pos] = random_byte()
            elif operation == 'zero':
                new_data[pos] = 0
            elif operation == 'mult':
                new_data[pos] = clamp(val * factor)
            elif operation == 'shift':
                new_data[pos] = clamp(val + factor)
            elif operation == 'max':
                new_data[pos] = 255
            elif operation == 'min':
                new_data[pos] = 0
        return new_data
    
    # ------------------------------------------------------------------
    # TECNICA 1: Sostituzione casuale
    # ------------------------------------------------------------------
    def technique_random_substitution(self):
        folder = self.output_base / "DQT_random_substitution"
        ensure_dir(folder)
        all_positions = self._get_all_coeff_positions()
        if not all_positions:
            return
        max_coeff = len(all_positions)
        prog_levels = generate_progressive_levels(max_coeff, 5)
        rand_levels = generate_random_levels(max_coeff, 20)
        all_levels = sorted(set(prog_levels + rand_levels))
        file_list = []
        for n in all_levels:
            if n > max_coeff: continue
            selected = [p for p, _, _ in random.sample(all_positions, n)]
            new_data = self._modify_coeffs(selected, 'random')
            fname = f"{self.base_name}_dqt_rand_{n}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"{n} numeri (detti coefficienti) cambiati a caso", "sostituiti con numeri casuali"))
        
        desc = "Questa tecnica cambia alcuni numeri (detti coefficienti) all'interno della tabella DQT, sostituendoli con altri numeri presi a caso."
        tech = "I coefficienti sono i valori che controllano il livello di dettaglio dell'immagine. Modificarli a caso produce glitch visivi di vario tipo: rumore, distorsioni, blocchi, ecc."
        effect = "L'immagine può diventare granulosa, con artefatti a scacchiera, oppure mostrare distorsioni cromatiche o di forma."
        hex_inst = "1. Apri il file in HexFiend.\n2. Cerca i byte 'FF DB' (sono l'inizio della tabella DQT).\n3. Dopo FF DB ci sono 2 byte che indicano la lunghezza, poi il payload: il primo byte è il tipo di tabella, poi seguono 64 valori (coefficienti) da 00 a FF.\n4. Seleziona alcuni di questi valori e sostituiscili con numeri casuali (es. 3A, 7F, 00, ecc.).\n5. Salva e apri l'immagine per vedere l'effetto."
        generate_readme(folder, "DQT - Sostituzione casuale", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ random_substitution: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 2: Azzeramento
    # ------------------------------------------------------------------
    def technique_zero_substitution(self):
        folder = self.output_base / "DQT_zero_substitution"
        ensure_dir(folder)
        all_positions = self._get_all_coeff_positions()
        if not all_positions:
            return
        max_coeff = len(all_positions)
        prog_levels = generate_progressive_levels(max_coeff, 5)
        rand_levels = generate_random_levels(max_coeff, 20)
        all_levels = sorted(set(prog_levels + rand_levels))
        file_list = []
        for n in all_levels:
            if n > max_coeff: continue
            selected = [p for p, _, _ in random.sample(all_positions, n)]
            new_data = self._modify_coeffs(selected, 'zero')
            fname = f"{self.base_name}_dqt_zero_{n}"
            self.save_image(new_data, folder, fname)
            file_list.append((fname+".jpg", f"{n} coefficienti azzerati (messi a 0)", "impostati a 0"))
        
        desc = "Questa tecnica imposta a zero alcuni coefficienti della tabella DQT. Azzerare un coefficiente significa eliminare quella parte di dettaglio."
        tech = "I coefficienti più alti (vicino a 255) rappresentano dettagli fini. Azzerandoli si perde nitidezza e compaiono blocchi."
        effect = "L'immagine diventa più sfocata, con aree piatte o a blocchi, specialmente se si azzerano i coefficienti delle alte frequenze."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova 'FF DB' e i 64 coefficienti successivi.\n3. Seleziona alcuni byte e scrivi '00' (zero) per azzerarli.\n4. Salva e osserva l'effetto."
        generate_readme(folder, "DQT - Azzeramento", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ zero_substitution: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 3: Moltiplicazione
    # ------------------------------------------------------------------
    def technique_multiplication(self):
        folder = self.output_base / "DQT_multiplication"
        ensure_dir(folder)
        all_positions = self._get_all_coeff_positions()
        if not all_positions:
            return
        max_coeff = len(all_positions)
        factors = [2, 3, 4, 0, 0.5]
        file_list = []
        for factor in factors:
            factor_name = str(factor).replace('.', '_')
            prog_levels = generate_progressive_levels(max_coeff, 5)
            rand_levels = generate_random_levels(max_coeff, 20)
            all_levels = sorted(set(prog_levels + rand_levels))
            for n in all_levels:
                if n > max_coeff: continue
                selected = [p for p, _, _ in random.sample(all_positions, n)]
                if factor == 0:
                    new_data = self._modify_coeffs(selected, 'zero')
                    op_label = "azzerati"
                else:
                    new_data = self._modify_coeffs(selected, 'mult', int(factor))
                    op_label = f"moltiplicati per {factor}"
                fname = f"{self.base_name}_dqt_mul_{factor_name}_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} coeff {op_label}", f"fattore {factor}"))
        
        desc = "Questa tecnica moltiplica i coefficienti DQT per un certo numero (2, 3, 4, 0.5, o 0). Cambiare il fattore altera il livello di compressione."
        tech = "Moltiplicare per un numero maggiore di 1 aumenta l'effetto di quantizzazione (più compressione), mentre per un numero minore di 1 lo riduce. Il fattore 0 è come azzerarli."
        effect = "A seconda del fattore, l'immagine può diventare più compressa (artefatti evidenti) o più dettagliata (ma con colori strani)."
        hex_inst = "1. Apri il file in HexFiend.\n2. Cerca 'FF DB' e vai ai 64 coefficienti.\n3. Seleziona un coefficiente, moltiplica il suo valore (es. 20 * 2 = 40) e riscrivilo in esadecimale (40 = 0x28).\n4. Ripeti per altri coefficienti, con diversi fattori.\n5. Salva e controlla il risultato."
        generate_readme(folder, "DQT - Moltiplicazione", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ multiplication: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 4: Shift (somma/sottrai)
    # ------------------------------------------------------------------
    def technique_shift_substitution(self):
        folder = self.output_base / "DQT_shift_substitution"
        ensure_dir(folder)
        all_positions = self._get_all_coeff_positions()
        if not all_positions:
            return
        max_coeff = len(all_positions)
        shifts = [-50, -20, -10, -5, 5, 10, 20, 50]
        file_list = []
        for shift in shifts:
            shift_name = f"{'+' if shift >= 0 else ''}{shift}"
            prog_levels = generate_progressive_levels(max_coeff, 5)
            rand_levels = generate_random_levels(max_coeff, 20)
            all_levels = sorted(set(prog_levels + rand_levels))
            for n in all_levels:
                if n > max_coeff: continue
                selected = [p for p, _, _ in random.sample(all_positions, n)]
                new_data = self._modify_coeffs(selected, 'shift', shift)
                fname = f"{self.base_name}_dqt_shift_{shift_name}_{n}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"{n} coeff shift {shift}", f"shift di {shift}"))
        
        desc = "Questa tecnica aggiunge o sottrae un valore costante a un certo numero di coefficienti. Per esempio, se un coefficiente vale 10 e aggiungi 20, diventa 30."
        tech = "Cambiare i coefficienti in questo modo sposta la scala delle frequenze, alterando il contrasto e i colori dell'immagine."
        effect = "L'immagine può diventare più chiara, più scura, o con tonalità di colore spostate (es. diventare rossastra o bluastra)."
        hex_inst = "1. Apri il file in HexFiend.\n2. Cerca 'FF DB' e i 64 coefficienti.\n3. Scegli un valore da aggiungere (es. 20). Prendi un coefficiente (es. 1A = 26 in decimale), aggiungi 20 (26+20=46), e riscrivi il risultato in esadecimale (46 = 0x2E).\n4. Per sottrarre, fai l'operazione inversa.\n5. Salva e guarda l'effetto."
        generate_readme(folder, "DQT - Shift", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ shift_substitution: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # TECNICA 5: Pattern spaziali (scacchiera, righe, colonne, frequenze)
    # ------------------------------------------------------------------
    def technique_spatial_patterns(self):
        folder = self.output_base / "DQT_spatial_patterns"
        ensure_dir(folder)
        all_positions = self._get_all_coeff_positions()
        if not all_positions:
            return
        
        # Organizziamo i coefficienti per posizione (0..63) all'interno della tabella 8x8
        coeff_by_index = {i: [] for i in range(64)}
        for pos, val, idx in all_positions:
            coeff_by_index[idx].append((pos, val))
        
        # Definiamo i pattern (spiegati in modo semplice)
        patterns = {
            'scacchiera': [i for i in range(64) if (i//8 + i%8) % 2 == 0],
            'righe_pari': [i for i in range(64) if (i//8) % 2 == 0],
            'righe_dispari': [i for i in range(64) if (i//8) % 2 == 1],
            'colonne_pari': [i for i in range(64) if (i%8) % 2 == 0],
            'colonne_dispari': [i for i in range(64) if (i%8) % 2 == 1],
            'basse_frequenze': list(range(0, 16)),  # 4x4 in alto a sinistra
            'alte_frequenze': list(range(48, 64))   # 4x4 in basso a destra
        }
        
        file_list = []
        for pattern_name, indices in patterns.items():
            positions_to_modify = []
            for idx in indices:
                if idx in coeff_by_index:
                    positions_to_modify.extend([p for p, v in coeff_by_index[idx]])
            if not positions_to_modify:
                continue
            # Applichiamo diverse operazioni su questo pattern
            operations = ['random', 'zero', 'mult2', 'shift20']
            for op in operations:
                if op == 'random':
                    new_data = self._modify_coeffs(positions_to_modify, 'random')
                    op_label = "casuale"
                elif op == 'zero':
                    new_data = self._modify_coeffs(positions_to_modify, 'zero')
                    op_label = "azzerato"
                elif op == 'mult2':
                    new_data = self._modify_coeffs(positions_to_modify, 'mult', 2)
                    op_label = "moltiplicato x2"
                elif op == 'shift20':
                    new_data = self._modify_coeffs(positions_to_modify, 'shift', 20)
                    op_label = "shift +20"
                fname = f"{self.base_name}_dqt_pattern_{pattern_name}_{op_label}"
                self.save_image(new_data, folder, fname)
                file_list.append((fname+".jpg", f"pattern {pattern_name} ({op_label})", f"modifica {op_label} su pattern"))
        
        desc = "Questa tecnica modifica i coefficienti solo in alcune posizioni specifiche all'interno della griglia 8x8, creando pattern geometrici come scacchiera, righe, colonne, o zone di frequenze."
        tech = "La tabella DQT è una griglia 8x8: ogni posizione corrisponde a una frequenza diversa. Modificare solo alcune posizioni produce effetti visivi organizzati."
        effect = "Si ottengono texture a scacchiera, bande orizzontali/verticali, o enfasi su dettagli fini (alte frequenze) o su zone sfocate (basse frequenze)."
        hex_inst = "1. Apri il file in HexFiend.\n2. Trova 'FF DB' e i 64 coefficienti disposti in una griglia 8x8 (leggi da sinistra a destra, poi riga successiva).\n3. Scegli un pattern (es. scacchiera: posizioni con indice pari).\n4. Modifica solo i byte in quelle posizioni (es. azzerali o moltiplicali).\n5. Lascia invariati gli altri byte. Salva."
        generate_readme(folder, "DQT - Pattern spaziali", desc, tech, hex_inst, effect, file_list)
        print(f"   ✅ spatial_patterns: {len(file_list)} versioni")
    
    # ------------------------------------------------------------------
    # RUN ALL (senza le tecniche swap e id_swap)
    # ------------------------------------------------------------------
    def run_all(self, techniques: List[str] = None):
        if self.dqt_segments is None:
            return
        
        print(f"\n📷 Elaborazione di: {self.input_path.name}")
        print(f"📁 Output in: {self.output_base}")
        print(f"📊 Tabelle DQT trovate: {len(self.dqt_segments)}")
        total_coeff = sum(seg[2] - seg[1] - 1 for seg in self.dqt_segments)
        print(f"📊 Coefficienti totali stimati: {total_coeff}")
        print("-" * 50)
        
        # Mappa dei nomi delle tecniche ai metodi (swap e id_swap rimosse)
        tech_map = {
            'random': self.technique_random_substitution,
            'zero': self.technique_zero_substitution,
            'mult': self.technique_multiplication,
            'shift': self.technique_shift_substitution,
            'pattern': self.technique_spatial_patterns,
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
        description="JPEG DQT Glitcher Avanzato - Esplorazione completa delle modifiche DQT"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file JPEG (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='dqt_glitch_output',
                        help='Directory di output principale (default: dqt_glitch_output)')
    parser.add_argument('--no-random', action='store_true',
                        help='Salta la generazione di livelli casuali (usa solo i 5 progressivi)')
    parser.add_argument('--techniques', nargs='+', 
                        choices=['random', 'zero', 'mult', 'shift', 'pattern'],
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
        glitcher = DQTGlitcher(jpg_path, img_output)
        glitcher.run_all(techniques=args.techniques)
    
    print("\n" + "=" * 70)
    print("✅ TUTTE LE IMMAGINI PROCESSATE!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
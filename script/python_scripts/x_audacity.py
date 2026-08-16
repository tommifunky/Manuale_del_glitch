#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Glitcher - Usa SoX (IDENTICO AD AUDACITY)
"""

import os
import sys
import random
import struct
import subprocess
import argparse
import tempfile
import numpy as np
from pathlib import Path
from typing import List, Dict

# ======================================================================
# 1. CONVERTITORE BMP ↔ RAW
# ======================================================================

class BMPConverter:
    @staticmethod
    def bmp_to_raw(bmp_path: Path, fmt: str, raw_path: Path, hdr_path: Path):
        with open(bmp_path, 'rb') as f:
            data = f.read()
        
        if data[:2] != b'BM':
            raise ValueError("Non è un BMP valido")
        
        offset = struct.unpack('<I', data[10:14])[0]
        header = data[:offset]
        pixels = data[offset:]
        
        with open(hdr_path, 'wb') as f:
            f.write(header)
        
        if fmt == '8bit':
            with open(raw_path, 'wb') as f:
                f.write(pixels)
        elif fmt == '16bit':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.int16)
            samples = (samples.astype(np.int32) - 128) * 256
            with open(raw_path, 'wb') as f:
                f.write(samples.astype(np.int16).tobytes())
        elif fmt == '24bit':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.int32)
            samples = (samples.astype(np.int32) - 128) * 65536
            with open(raw_path, 'wb') as f:
                for s in samples:
                    f.write(struct.pack('<i', s)[:3])
        else:
            raise ValueError(f"Formato non supportato: {fmt}")

    @staticmethod
    def raw_to_bmp(raw_path: Path, hdr_path: Path, bmp_path: Path, fmt: str, original_len: int):
        with open(hdr_path, 'rb') as f:
            header = f.read()
        
        with open(raw_path, 'rb') as f:
            raw_data = f.read()
        
        if fmt == '8bit':
            pixels = raw_data
        elif fmt == '16bit':
            # Assicura che la lunghezza sia multipla di 2
            if len(raw_data) % 2 != 0:
                raw_data = raw_data[:-1]  # tronca l'ultimo byte se dispari
            if len(raw_data) == 0:
                # Se non ci sono dati, restituisci zeri
                pixels = b'\x00' * original_len
            else:
                samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.int32)
                pixels = ((samples // 256) + 128).astype(np.uint8).tobytes()
        elif fmt == '24bit':
            # Assicura che la lunghezza sia multipla di 3
            if len(raw_data) % 3 != 0:
                raw_data = raw_data[:-(len(raw_data) % 3)]
            samples = []
            for i in range(0, len(raw_data), 3):
                if i+2 < len(raw_data):
                    val = int.from_bytes(raw_data[i:i+3], 'little', signed=True)
                    samples.append(val)
                else:
                    break
            if samples:
                samples = np.array(samples, dtype=np.int32)
                pixels = ((samples // 65536) + 128).astype(np.uint8).tobytes()
            else:
                pixels = b'\x00' * original_len
        else:
            raise ValueError(f"Formato non supportato: {fmt}")
        
        if len(pixels) < original_len:
            pixels += b'\x00' * (original_len - len(pixels))
        elif len(pixels) > original_len:
            pixels = pixels[:original_len]
        
        with open(bmp_path, 'wb') as f:
            f.write(header)
            f.write(pixels)

# ======================================================================
# 2. EFFETTI SOX (IDENTICI AD AUDACITY)
# ======================================================================

class SoxEffects:
    @staticmethod
    def _sox_format_flags(fmt: str) -> List[str]:
        if fmt == '8bit':
            return ['-e', 'unsigned-integer', '-b', '8']
        elif fmt == '16bit':
            return ['-e', 'signed-integer', '-b', '16']
        elif fmt == '24bit':
            return ['-e', 'signed-integer', '-b', '24']
        else:
            raise ValueError(f"Formato non supportato: {fmt}")

    @staticmethod
    def reverb(input_path: Path, output_path: Path, fmt: str, decay: float = 0.5, delay_ms: int = 100):
        flags = SoxEffects._sox_format_flags(fmt)
        room = int(decay * 100)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'reverb', str(room), '0', '100', '0'
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def echo(input_path: Path, output_path: Path, fmt: str, delay_ms: int = 100, decay: float = 0.5):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'echo', '0.8', '0.9', str(delay_ms/1000), str(decay)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def delay(input_path: Path, output_path: Path, fmt: str, delay_ms: int = 200, feedback: float = 0.3):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'echo', '1.0', str(feedback), str(delay_ms/1000), '0.0'
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def phaser(input_path: Path, output_path: Path, fmt: str, depth: int = 10, rate: float = 0.1):
        flags = SoxEffects._sox_format_flags(fmt)
        # depth viene scalato a delay (massimo 5), rate deve essere >= 0.1
        delay = max(0.1, depth / 10.0)
        rate = max(0.1, rate)  # assicura che rate >= 0.1
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'phaser', '0.5', '0.8', str(delay), '0.5', str(rate)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def distort(input_path: Path, output_path: Path, fmt: str, drive: float = 2.0):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'overdrive', str(drive)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def reverse(input_path: Path, output_path: Path, fmt: str):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'reverse'
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def amplify(input_path: Path, output_path: Path, fmt: str, gain: float):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'vol', str(gain)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def normalise(input_path: Path, output_path: Path, fmt: str, peak: float = 0.9):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'norm', str(peak)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

# ======================================================================
# 3. MOTORE PRINCIPALE
# ======================================================================

class BMPGlitcher:
    FORMATS = ['8bit', '16bit', '24bit']

    EFFECTS = {
        'Riverbero': {
            'funzione': SoxEffects.reverb,
            'varianti': [
                {'decay': 0.3, 'delay_ms': 50},
                {'decay': 0.5, 'delay_ms': 100},
                {'decay': 0.7, 'delay_ms': 150},
                {'decay': 0.9, 'delay_ms': 200},
                {'decay': 0.5, 'delay_ms': 300},
            ]
        },
        'Eco': {
            'funzione': SoxEffects.echo,
            'varianti': [
                {'delay_ms': 50, 'decay': 0.3},
                {'delay_ms': 100, 'decay': 0.5},
                {'delay_ms': 150, 'decay': 0.7},
                {'delay_ms': 200, 'decay': 0.9},
                {'delay_ms': 300, 'decay': 0.6},
            ]
        },
        'Delay': {
            'funzione': SoxEffects.delay,
            'varianti': [
                {'delay_ms': 100, 'feedback': 0.2},
                {'delay_ms': 150, 'feedback': 0.4},
                {'delay_ms': 200, 'feedback': 0.5},
                {'delay_ms': 250, 'feedback': 0.6},
                {'delay_ms': 300, 'feedback': 0.8},
            ]
        },
        'Phaser': {
            'funzione': SoxEffects.phaser,
            'varianti': [
                {'depth': 5, 'rate': 0.1},
                {'depth': 10, 'rate': 0.2},
                {'depth': 15, 'rate': 0.3},
                {'depth': 20, 'rate': 0.5},
                {'depth': 30, 'rate': 0.8},
            ]
        },
        'Distorsione': {
            'funzione': SoxEffects.distort,
            'varianti': [
                {'drive': 1.0},
                {'drive': 2.0},
                {'drive': 4.0},
                {'drive': 8.0},
                {'drive': 15.0},
            ]
        },
        'Reverse': {
            'funzione': SoxEffects.reverse,
            'varianti': [{}]
        },
        'Amplifica': {
            'funzione': SoxEffects.amplify,
            'varianti': [
                {'gain': 0.3},
                {'gain': 0.6},
                {'gain': 1.2},
                {'gain': 2.0},
                {'gain': 4.0},
            ]
        },
        'Normalizza': {
            'funzione': SoxEffects.normalise,
            'varianti': [
                {'peak': 0.3},
                {'peak': 0.5},
                {'peak': 0.7},
                {'peak': 0.9},
                {'peak': 0.95},
            ]
        },
    }

    def __init__(self, input_path: Path, output_base: Path):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem

        with open(input_path, 'rb') as f:
            self.raw_data = f.read()

        if self.raw_data[:2] != b'BM':
            print(f"⚠️  {self.input_path.name} non è un BMP valido.")
            self.is_valid = False
            return

        self.is_valid = True
        self.data_offset = struct.unpack('<I', self.raw_data[10:14])[0]
        self.header = self.raw_data[:self.data_offset]
        self.pixel_data = self.raw_data[self.data_offset:]
        self.original_len = len(self.pixel_data)

    def _applica_effetto(self, effetto_nome: str, variante: Dict, fmt: str,
                         folder: Path, suffix: str, sezione_start: float = 0.0,
                         sezione_end: float = 1.0) -> Path:
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
            raw_in = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix='.hdr', delete=False) as f:
            hdr_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
            raw_out = Path(f.name)

        BMPConverter.bmp_to_raw(self.input_path, fmt, raw_in, hdr_path)
        effetto_info = self.EFFECTS[effetto_nome]

        try:
            if sezione_start == 0 and sezione_end == 1:
                effetto_info['funzione'](raw_in, raw_out, fmt, **variante)
            else:
                with open(raw_in, 'rb') as f:
                    data = f.read()
                start = int(len(data) * sezione_start)
                end = int(len(data) * sezione_end)
                if start < end and start >= 0 and end <= len(data):
                    sezione = data[start:end]
                    with tempfile.NamedTemporaryFile(suffix='.sec', delete=False) as f:
                        sec_in = Path(f.name)
                        sec_in.write_bytes(sezione)
                    with tempfile.NamedTemporaryFile(suffix='.sec', delete=False) as f:
                        sec_out = Path(f.name)
                    effetto_info['funzione'](sec_in, sec_out, fmt, **variante)
                    new_sezione = sec_out.read_bytes()
                    new_data = data[:start] + new_sezione + data[end:]
                    raw_out.write_bytes(new_data)
                    sec_in.unlink(missing_ok=True)
                    sec_out.unlink(missing_ok=True)
                else:
                    effetto_info['funzione'](raw_in, raw_out, fmt, **variante)
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Errore SoX su {effetto_nome} con parametri {variante}, saltato.")
            print(f"      {e.stderr.decode()}")
            return None

        bmp_path = folder / f"{self.base_name}_{fmt}_{effetto_nome}_{suffix}.bmp"
        BMPConverter.raw_to_bmp(raw_out, hdr_path, bmp_path, fmt, self.original_len)

        for p in [raw_in, hdr_path, raw_out]:
            p.unlink(missing_ok=True)

        return bmp_path

    def run_all(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name}")
        base_folder = self.output_base / self.base_name
        base_folder.mkdir(parents=True, exist_ok=True)

        totali = 0

        for fmt in self.FORMATS:
            fmt_folder = base_folder / fmt
            fmt_folder.mkdir(parents=True, exist_ok=True)

            for effetto_nome, effetto_info in self.EFFECTS.items():
                effetto_folder = fmt_folder / effetto_nome
                effetto_folder.mkdir(parents=True, exist_ok=True)

                full_folder = effetto_folder / "Full"
                full_folder.mkdir(parents=True, exist_ok=True)

                for idx, variante in enumerate(effetto_info['varianti']):
                    path = self._applica_effetto(effetto_nome, variante, fmt,
                                                 full_folder, f"full_{idx:02d}")
                    if path is not None:
                        totali += 1

                random_folder = effetto_folder / "Random"
                random_folder.mkdir(parents=True, exist_ok=True)

                for i in range(20):
                    start_pct = random.uniform(0.0, 0.6)
                    end_pct = start_pct + random.uniform(0.1, 0.4)
                    end_pct = min(end_pct, 1.0)
                    variante = random.choice(effetto_info['varianti'])
                    path = self._applica_effetto(effetto_nome, variante, fmt,
                                                 random_folder, f"random_{i:02d}",
                                                 start_pct, end_pct)
                    if path is not None:
                        totali += 1

                # README
                readme_path = effetto_folder / "README.txt"
                with open(readme_path, 'w', encoding='utf-8') as rf:
                    rf.write(f"Effetto: {effetto_nome}\n")
                    rf.write(f"Formato: {fmt}\n")
                    rf.write(f"Immagine: {self.input_path.name}\n")
                    rf.write("-" * 60 + "\n\n")
                    rf.write("--- FULL ---\n")
                    for f in sorted(full_folder.glob("*.bmp")):
                        rf.write(f"  {f.name}\n")
                    rf.write("\n--- RANDOM ---\n")
                    for f in sorted(random_folder.glob("*.bmp")):
                        rf.write(f"  {f.name}\n")

        summary_readme = base_folder / "README_COMPLETO.txt"
        with open(summary_readme, 'w', encoding='utf-8') as sf:
            sf.write(f"Immagine originale: {self.input_path.name}\n")
            sf.write("=" * 60 + "\n")
            sf.write(f"Totale file generati: {totali}\n")
            sf.write("\nEffetti applicati:\n")
            for effetto in self.EFFECTS.keys():
                sf.write(f"  • {effetto}\n")

        print(f"   ✅ Generati {totali} file per {self.base_name}")

# ======================================================================
# 4. MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Glitcher - Usa SoX (IDENTICO AD AUDACITY)"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_glitch_output',
                        help='Directory di output (default: bmp_glitch_output)')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"❌ Directory input non trovata: {input_dir}")
        sys.exit(1)

    try:
        subprocess.run(['sox', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ SoX non trovato. Installa con: brew install sox (macOS) o apt install sox (Linux)")
        sys.exit(1)

    bmp_files = list(input_dir.glob("*.bmp")) + list(input_dir.glob("*.BMP"))
    if not bmp_files:
        print(f"❌ Nessun file BMP trovato in {input_dir}")
        sys.exit(1)

    print(f"🔍 Trovati {len(bmp_files)} file BMP")
    print("⚡ Usando SoX (IDENTICO AD AUDACITY)")
    print("=" * 70)

    for bmp_path in bmp_files:
        glitcher = BMPGlitcher(bmp_path, output_dir)
        glitcher.run_all()

    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
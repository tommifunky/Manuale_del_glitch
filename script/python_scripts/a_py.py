#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Glitcher - Usa SoX (IDENTICO AD AUDACITY)
Con sezioni grandi (metà immagine) e livelli ampliati.
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
from typing import List, Dict, Optional

# ======================================================================
# 1. CONVERTITORE BMP ↔ RAW (TUTTI I FORMATI)
# ======================================================================

class BMPConverter:
    FORMAT_NAMES = {
        '8bit': '8-bit PCM',
        '16bit': '16-bit PCM',
        '24bit': '24-bit PCM',
        '32bit': '32-bit PCM',
        '32bit_float': '32-bit Float',
        '64bit_float': '64-bit Float',
        'ulaw': 'U-Law',
        'alaw': 'A-Law',
    }

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
        elif fmt == '32bit':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.int32)
            samples = (samples.astype(np.int32) - 128) * 16777216
            with open(raw_path, 'wb') as f:
                f.write(samples.astype(np.int32).tobytes())
        elif fmt == '32bit_float':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.float32)
            samples = (samples - 128.0) / 128.0
            with open(raw_path, 'wb') as f:
                f.write(samples.astype(np.float32).tobytes())
        elif fmt == '64bit_float':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.float64)
            samples = (samples - 128.0) / 128.0
            with open(raw_path, 'wb') as f:
                f.write(samples.astype(np.float64).tobytes())
        elif fmt == 'ulaw':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.float32)
            samples = (samples - 128.0) / 128.0
            sign = np.where(samples < 0, 0x80, 0).astype(np.uint8)
            linear = np.abs(samples) * 32635
            linear = np.clip(linear, 0, 32635).astype(np.int32)
            exponent = np.zeros_like(linear, dtype=np.uint8)
            for i in range(7, -1, -1):
                exponent = np.where(linear >= (1 << (i + 3)), i, exponent)
            mantissa = ((linear >> (exponent + 3)) & 0x0F).astype(np.uint8)
            u = ~(sign | (exponent << 4) | mantissa) & 0xFF
            with open(raw_path, 'wb') as f:
                f.write(u.astype(np.uint8).tobytes())
        elif fmt == 'alaw':
            samples = np.frombuffer(pixels, dtype=np.uint8).astype(np.float32)
            samples = (samples - 128.0) / 128.0
            sign = np.where(samples < 0, 0x80, 0).astype(np.uint8)
            linear = np.abs(samples) * 4095
            linear = np.clip(linear, 0, 4095).astype(np.int32)
            exponent = np.zeros_like(linear, dtype=np.uint8)
            for i in range(7, -1, -1):
                exponent = np.where(linear >= (1 << (i + 1)), i, exponent)
            mantissa = ((linear >> (exponent + 1)) & 0x0F).astype(np.uint8)
            a = (sign | (exponent << 4) | mantissa) ^ 0x55
            with open(raw_path, 'wb') as f:
                f.write(a.astype(np.uint8).tobytes())
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
            if len(raw_data) % 2 != 0:
                raw_data = raw_data[:-1]
            if len(raw_data) == 0:
                pixels = b'\x00' * original_len
            else:
                samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.int32)
                pixels = ((samples // 256) + 128).astype(np.uint8).tobytes()
        elif fmt == '24bit':
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
        elif fmt == '32bit':
            if len(raw_data) % 4 != 0:
                raw_data = raw_data[:-(len(raw_data) % 4)]
            if len(raw_data) == 0:
                pixels = b'\x00' * original_len
            else:
                samples = np.frombuffer(raw_data, dtype=np.int32).astype(np.int32)
                pixels = ((samples // 16777216) + 128).astype(np.uint8).tobytes()
        elif fmt == '32bit_float':
            if len(raw_data) % 4 != 0:
                raw_data = raw_data[:-(len(raw_data) % 4)]
            if len(raw_data) == 0:
                pixels = b'\x00' * original_len
            else:
                samples = np.frombuffer(raw_data, dtype=np.float32)
                pixels = np.clip(samples * 128.0 + 128.0, 0, 255).astype(np.uint8).tobytes()
        elif fmt == '64bit_float':
            if len(raw_data) % 8 != 0:
                raw_data = raw_data[:-(len(raw_data) % 8)]
            if len(raw_data) == 0:
                pixels = b'\x00' * original_len
            else:
                samples = np.frombuffer(raw_data, dtype=np.float64)
                pixels = np.clip(samples * 128.0 + 128.0, 0, 255).astype(np.uint8).tobytes()
        elif fmt == 'ulaw':
            u = np.frombuffer(raw_data, dtype=np.uint8)
            u = ~u & 0xFF
            sign = (u & 0x80).astype(np.float32)
            exponent = ((u >> 4) & 0x07).astype(np.float32)
            mantissa = (u & 0x0F).astype(np.float32)
            sample = (mantissa * 8.0) + 132.0
            sample = sample * (2.0 ** exponent)
            sample = np.where(sign > 0, -sample, sample) / 32635.0
            pixels = np.clip(sample * 128.0 + 128.0, 0, 255).astype(np.uint8).tobytes()
        elif fmt == 'alaw':
            a = np.frombuffer(raw_data, dtype=np.uint8)
            a = a ^ 0x55
            sign = (a & 0x80).astype(np.float32)
            exponent = ((a >> 4) & 0x07).astype(np.float32)
            mantissa = (a & 0x0F).astype(np.float32)
            sample = (mantissa * 2.0) + 1.0
            sample = sample * (2.0 ** (exponent + 1)) - 1.0
            sample = np.where(sign > 0, -sample, sample) / 4095.0
            pixels = np.clip(sample * 128.0 + 128.0, 0, 255).astype(np.uint8).tobytes()
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
        elif fmt == '32bit':
            return ['-e', 'signed-integer', '-b', '32']
        elif fmt == '32bit_float':
            return ['-e', 'float', '-b', '32']
        elif fmt == '64bit_float':
            return ['-e', 'float', '-b', '64']
        elif fmt == 'ulaw':
            return ['-e', 'u-law', '-b', '8']
        elif fmt == 'alaw':
            return ['-e', 'a-law', '-b', '8']
        else:
            raise ValueError(f"Formato non supportato: {fmt}")

    @staticmethod
    def _run_sox(input_path: Path, output_path: Path, fmt: str, effect_name: str, *args):
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            effect_name
        ] + list(args)
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def reverb(input_path: Path, output_path: Path, fmt: str, decay: float = 0.5, delay_ms: int = 100):
        room = int(decay * 100)
        SoxEffects._run_sox(input_path, output_path, fmt, 'reverb', str(room), '0', '100', '0')

    @staticmethod
    def echo(input_path: Path, output_path: Path, fmt: str, delay_ms: int = 100, decay: float = 0.5):
        SoxEffects._run_sox(input_path, output_path, fmt, 'echo', '0.8', '0.9', str(delay_ms/1000), str(decay))

    @staticmethod
    def delay(input_path: Path, output_path: Path, fmt: str, delay_ms: int = 200, feedback: float = 0.3):
        SoxEffects._run_sox(input_path, output_path, fmt, 'echo', '1.0', str(feedback), str(delay_ms/1000), '0.0')

    @staticmethod
    def phaser(input_path: Path, output_path: Path, fmt: str, depth: int = 10, rate: float = 0.1):
        delay = max(0.1, depth / 10.0)
        rate = max(0.1, rate)
        SoxEffects._run_sox(input_path, output_path, fmt, 'phaser', '0.5', '0.8', str(delay), '0.5', str(rate))

    @staticmethod
    def distort(input_path: Path, output_path: Path, fmt: str, drive: float = 2.0):
        SoxEffects._run_sox(input_path, output_path, fmt, 'overdrive', str(drive))

    @staticmethod
    def reverse(input_path: Path, output_path: Path, fmt: str):
        SoxEffects._run_sox(input_path, output_path, fmt, 'reverse')

    @staticmethod
    def amplify(input_path: Path, output_path: Path, fmt: str, gain: float):
        SoxEffects._run_sox(input_path, output_path, fmt, 'vol', str(gain))

    @staticmethod
    def normalise(input_path: Path, output_path: Path, fmt: str, peak: float = 0.9):
        SoxEffects._run_sox(input_path, output_path, fmt, 'norm', str(peak))

# ======================================================================
# 3. MOTORE PRINCIPALE - CON SEZIONI GRANDI
# ======================================================================

class BMPGlitcher:
    FORMATS = ['8bit', '16bit', '24bit', '32bit', '32bit_float', '64bit_float', 'ulaw', 'alaw']
    FORMAT_NAMES = BMPConverter.FORMAT_NAMES

    # Effetti con livelli MOLTO ampliati (distanze enormi tra le varianti)
    EFFECTS = {
        'Riverbero': {
            'funzione': SoxEffects.reverb,
            'varianti': [
                {'decay': 0.1, 'delay_ms': 20},
                {'decay': 0.3, 'delay_ms': 50},
                {'decay': 0.5, 'delay_ms': 100},
                {'decay': 0.7, 'delay_ms': 200},
                {'decay': 0.9, 'delay_ms': 300},
                {'decay': 1.2, 'delay_ms': 500},
                {'decay': 0.2, 'delay_ms': 800},
                {'decay': 0.8, 'delay_ms': 50},
                {'decay': 0.4, 'delay_ms': 400},
                {'decay': 1.0, 'delay_ms': 150},
            ]
        },
        'Eco': {
            'funzione': SoxEffects.echo,
            'varianti': [
                {'delay_ms': 20, 'decay': 0.1},
                {'delay_ms': 50, 'decay': 0.2},
                {'delay_ms': 100, 'decay': 0.3},
                {'delay_ms': 200, 'decay': 0.5},
                {'delay_ms': 300, 'decay': 0.7},
                {'delay_ms': 500, 'decay': 0.9},
                {'delay_ms': 800, 'decay': 0.4},
                {'delay_ms': 1000, 'decay': 0.2},
                {'delay_ms': 50, 'decay': 0.8},
                {'delay_ms': 400, 'decay': 0.6},
            ]
        },
        'Delay': {
            'funzione': SoxEffects.delay,
            'varianti': [
                {'delay_ms': 20, 'feedback': 0.05},
                {'delay_ms': 50, 'feedback': 0.1},
                {'delay_ms': 100, 'feedback': 0.2},
                {'delay_ms': 200, 'feedback': 0.3},
                {'delay_ms': 300, 'feedback': 0.4},
                {'delay_ms': 500, 'feedback': 0.5},
                {'delay_ms': 700, 'feedback': 0.6},
                {'delay_ms': 1000, 'feedback': 0.8},
                {'delay_ms': 80, 'feedback': 0.7},
                {'delay_ms': 250, 'feedback': 0.9},
            ]
        },
        'Phaser': {
            'funzione': SoxEffects.phaser,
            'varianti': [
                {'depth': 3, 'rate': 0.1},
                {'depth': 5, 'rate': 0.15},
                {'depth': 10, 'rate': 0.2},
                {'depth': 15, 'rate': 0.3},
                {'depth': 20, 'rate': 0.4},
                {'depth': 25, 'rate': 0.5},
                {'depth': 30, 'rate': 0.6},
                {'depth': 40, 'rate': 0.8},
                {'depth': 8, 'rate': 0.5},
                {'depth': 18, 'rate': 0.1},
            ]
        },
        'Distorsione': {
            'funzione': SoxEffects.distort,
            'varianti': [
                {'drive': 0.2},
                {'drive': 0.5},
                {'drive': 1.0},
                {'drive': 2.0},
                {'drive': 4.0},
                {'drive': 8.0},
                {'drive': 12.0},
                {'drive': 18.0},
                {'drive': 25.0},
                {'drive': 40.0},
            ]
        },
        'Reverse': {
            'funzione': SoxEffects.reverse,
            'varianti': [{}] * 7
        },
        'Amplifica': {
            'funzione': SoxEffects.amplify,
            'varianti': [
                {'gain': 0.05},
                {'gain': 0.1},
                {'gain': 0.2},
                {'gain': 0.4},
                {'gain': 0.6},
                {'gain': 0.8},
                {'gain': 1.0},
                {'gain': 1.5},
                {'gain': 2.5},
                {'gain': 4.0},
                {'gain': 6.0},
                {'gain': 10.0},
            ]
        },
        'Normalizza': {
            'funzione': SoxEffects.normalise,
            'varianti': [
                {'peak': 0.05},
                {'peak': 0.1},
                {'peak': 0.2},
                {'peak': 0.3},
                {'peak': 0.4},
                {'peak': 0.5},
                {'peak': 0.6},
                {'peak': 0.7},
                {'peak': 0.8},
                {'peak': 0.9},
                {'peak': 0.95},
                {'peak': 0.99},
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
                         sezione_end: float = 1.0) -> Optional[Path]:
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
            raw_in = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix='.hdr', delete=False) as f:
            hdr_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
            raw_out = Path(f.name)

        try:
            BMPConverter.bmp_to_raw(self.input_path, fmt, raw_in, hdr_path)
        except Exception as e:
            print(f"   ⚠️  Errore conversione BMP→RAW su {fmt}: {e}")
            return None

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
            print(f"   ⚠️  Errore SoX su {effetto_nome} con {variante}, saltato.")
            if e.stderr:
                print(f"      {e.stderr.decode()}")
            return None
        except Exception as e:
            print(f"   ⚠️  Errore su {effetto_nome}: {e}")
            return None

        try:
            bmp_path = folder / f"{self.base_name}_{fmt}_{effetto_nome}_{suffix}.bmp"
            BMPConverter.raw_to_bmp(raw_out, hdr_path, bmp_path, fmt, self.original_len)
        except Exception as e:
            print(f"   ⚠️  Errore conversione RAW→BMP su {fmt}: {e}")
            return None
        finally:
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

        for fmt_key in self.FORMATS:
            fmt_name = self.FORMAT_NAMES[fmt_key]
            fmt_folder = base_folder / fmt_name
            fmt_folder.mkdir(parents=True, exist_ok=True)

            for effetto_nome, effetto_info in self.EFFECTS.items():
                effetto_folder = fmt_folder / effetto_nome
                effetto_folder.mkdir(parents=True, exist_ok=True)

                # ===== SECTION: effetto su metà immagine =====
                section_folder = effetto_folder / "Section"
                section_folder.mkdir(parents=True, exist_ok=True)

                # Sezione fissa: dal 30% al 70% (metà immagine)
                section_start = 0.30
                section_end = 0.70

                for idx, variante in enumerate(effetto_info['varianti']):
                    path = self._applica_effetto(effetto_nome, variante, fmt_key,
                                                 section_folder, f"section_{idx:02d}",
                                                 section_start, section_end)
                    if path is not None:
                        totali += 1

                # ===== RANDOM: sezioni casuali ma grandi =====
                random_folder = effetto_folder / "Random"
                random_folder.mkdir(parents=True, exist_ok=True)

                for i in range(15):
                    # Sezioni grandi: tra il 25% e il 55% del file
                    start_pct = random.uniform(0.0, 0.45)
                    end_pct = start_pct + random.uniform(0.25, 0.55)
                    end_pct = min(end_pct, 1.0)
                    start_pct = max(0.0, end_pct - 0.55)
                    variante = random.choice(effetto_info['varianti'])
                    path = self._applica_effetto(effetto_nome, variante, fmt_key,
                                                 random_folder, f"random_{i:02d}",
                                                 start_pct, end_pct)
                    if path is not None:
                        totali += 1

                # README
                readme_path = effetto_folder / "README.txt"
                with open(readme_path, 'w', encoding='utf-8') as rf:
                    rf.write(f"Effetto: {effetto_nome}\n")
                    rf.write(f"Formato: {fmt_name}\n")
                    rf.write(f"Immagine: {self.input_path.name}\n")
                    rf.write("-" * 60 + "\n\n")
                    rf.write("--- SECTION (effetto su metà immagine, 30%-70%) ---\n")
                    for f in sorted(section_folder.glob("*.bmp")):
                        rf.write(f"  {f.name}\n")
                    rf.write("\n--- RANDOM (sezioni casuali grandi, 25%-55%) ---\n")
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
    print("⚡ Sezioni: METÀ IMMAGINE (30%-70%) + casuali grandi (25%-55%)")
    print("⚡ Livelli: range ampliati per risultati più diversi")
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
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Effects - Distorsione, Phaser, Tremolo, Wahwah, Vocoder
50 FULL + 30 RANDOM per effetto e formato. Ogni formato ha seed diverso.
"""

import os
import sys
import struct
import subprocess
import argparse
import tempfile
import random
import math
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Callable

# ======================================================================
# 1. CONVERTITORE BMP ↔ RAW (IDENTICO)
# ======================================================================

class BMPConverter:
    FORMAT_NAMES = {
        '8bit': '8-bit PCM',
        '16bit': '16-bit PCM',
        '24bit': '24-bit PCM',
        '32bit': '32-bit PCM',
        '32bit_float': '32-bit Float',
        '64bit_float': '64-bit Float',
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
# 2. EFFETTI SOX (DISTORSIONE, PHASER, TREMOLO, WAHWAH, VOCODER)
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
        else:
            raise ValueError(f"Formato non supportato: {fmt}")

    @staticmethod
    def overdrive(input_path: Path, output_path: Path, fmt: str,
                  gain: float, colour: float) -> None:
        """Applica distorsione (overdrive) con gain e colour."""
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'overdrive', str(gain), str(colour)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def phaser(input_path: Path, output_path: Path, fmt: str,
               gain_in: float, gain_out: float, delay: float,
               decay: float, speed: float) -> None:
        """Applica phaser."""
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'phaser', str(gain_in), str(gain_out), str(delay),
            str(decay), str(speed)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def tremolo(input_path: Path, output_path: Path, fmt: str,
                freq: float, depth: float) -> None:
        """Applica tremolo."""
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'tremolo', str(freq), str(depth)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def wahwah(input_path: Path, output_path: Path, fmt: str,
               freq: float, depth: float) -> None:
        """Applica wah-wah."""
        flags = SoxEffects._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'wahwah', str(freq), str(depth)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def vocoder(input_path: Path, output_path: Path, fmt: str,
                carrier_freq: float, num_bands: int) -> None:
        """
        Applica vocoder usando una portante sinusoidale generata.
        I dati BMP sono il segnale modulante.
        """
        flags = SoxEffects._sox_format_flags(fmt)
        # Crea un file temporaneo per la portante (sinusoide)
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
            carrier_raw = Path(f.name)
        # Genera il segnale portante della stessa durata del modulante
        # Dobbiamo conoscere la durata: leggiamo la lunghezza del file di input
        with open(input_path, 'rb') as f:
            input_len = len(f.read())
        # La durata in secondi = campioni / sample_rate (44100)
        duration = input_len / 44100.0  # approssimato (mono, 1 canale)
        # Genera un tono puro con sox
        gen_cmd = [
            'sox', '-n', '-r', '44100', '-t', 'raw'] + flags + [str(carrier_raw),
            'synth', str(duration), 'sine', str(carrier_freq)
        ]
        subprocess.run(gen_cmd, check=True, capture_output=True)

        # Ora applica il vocoder
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(carrier_raw),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'vocoder', str(num_bands)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # Pulisci
        carrier_raw.unlink(missing_ok=True)


# ======================================================================
# 3. MOTORE PRINCIPALE (GENERICO PER QUALSIASI EFFETTO)
# ======================================================================

class BMPEffectProcessor:
    def __init__(self, input_path: Path, output_base: Path, effect_name: str):
        self.input_path = input_path
        self.output_base = output_base
        self.effect_name = effect_name
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

    def _genera_livelli(self, seed: int, count: int = 50, fmt_key: str = '') -> List[Dict]:
        """
        Genera parametri casuali per l'effetto corrente.
        I range sono specifici per formato e per effetto.
        """
        random.seed(seed)

        if self.effect_name == 'overdrive':
            if fmt_key == '8bit':
                gain_r = (0.5, 2.0); colour_r = (0.0, 0.5)
            elif fmt_key == '16bit':
                gain_r = (1.0, 5.0); colour_r = (0.0, 1.0)
            elif fmt_key == '24bit':
                gain_r = (2.0, 10.0); colour_r = (0.2, 1.0)
            elif fmt_key in ['32bit', '32bit_float']:
                gain_r = (3.0, 15.0); colour_r = (0.5, 1.0)
            elif fmt_key == '64bit_float':
                gain_r = (5.0, 20.0); colour_r = (0.8, 1.0)
            else:
                gain_r = (1.0, 6.0); colour_r = (0.0, 0.8)
            return [{'gain': random.uniform(*gain_r),
                     'colour': random.uniform(*colour_r)} for _ in range(count)]

        elif self.effect_name == 'phaser':
            if fmt_key == '8bit':
                gi = (0.2, 0.6); go = (0.2, 0.6); dly = (0.5, 2.0); dec = (0.1, 0.5); spd = (0.2, 1.0)
            elif fmt_key == '16bit':
                gi = (0.3, 0.7); go = (0.3, 0.8); dly = (1.0, 3.0); dec = (0.2, 0.6); spd = (0.5, 2.0)
            elif fmt_key == '24bit':
                gi = (0.4, 0.8); go = (0.4, 0.9); dly = (2.0, 5.0); dec = (0.3, 0.8); spd = (1.0, 3.0)
            elif fmt_key in ['32bit', '32bit_float']:
                gi = (0.5, 0.9); go = (0.5, 1.0); dly = (3.0, 8.0); dec = (0.4, 0.9); spd = (1.5, 4.0)
            elif fmt_key == '64bit_float':
                gi = (0.6, 1.0); go = (0.6, 1.2); dly = (4.0, 10.0); dec = (0.5, 0.95); spd = (2.0, 5.0)
            else:
                gi = (0.3, 0.7); go = (0.3, 0.8); dly = (1.0, 4.0); dec = (0.2, 0.7); spd = (0.5, 2.5)
            return [{'gain_in': random.uniform(*gi),
                     'gain_out': random.uniform(*go),
                     'delay': random.uniform(*dly),
                     'decay': random.uniform(*dec),
                     'speed': random.uniform(*spd)} for _ in range(count)]

        elif self.effect_name == 'tremolo':
            if fmt_key == '8bit':
                fr = (1.0, 5.0); dp = (0.1, 0.5)
            elif fmt_key == '16bit':
                fr = (2.0, 10.0); dp = (0.2, 0.8)
            elif fmt_key == '24bit':
                fr = (3.0, 15.0); dp = (0.3, 0.9)
            elif fmt_key in ['32bit', '32bit_float']:
                fr = (4.0, 20.0); dp = (0.4, 1.0)
            elif fmt_key == '64bit_float':
                fr = (5.0, 25.0); dp = (0.5, 1.0)
            else:
                fr = (2.0, 10.0); dp = (0.2, 0.8)
            return [{'freq': random.uniform(*fr),
                     'depth': random.uniform(*dp)} for _ in range(count)]

        elif self.effect_name == 'wahwah':
            if fmt_key == '8bit':
                fr = (100, 500); dp = (0.1, 0.5)
            elif fmt_key == '16bit':
                fr = (200, 800); dp = (0.2, 0.7)
            elif fmt_key == '24bit':
                fr = (300, 1200); dp = (0.3, 0.8)
            elif fmt_key in ['32bit', '32bit_float']:
                fr = (400, 1800); dp = (0.4, 0.9)
            elif fmt_key == '64bit_float':
                fr = (500, 2000); dp = (0.5, 1.0)
            else:
                fr = (200, 800); dp = (0.2, 0.7)
            return [{'freq': random.uniform(*fr),
                     'depth': random.uniform(*dp)} for _ in range(count)]

        elif self.effect_name == 'vocoder':
            # Parametri: carrier_freq (Hz) e num_bands (intero 4-20)
            if fmt_key == '8bit':
                cf = (200, 600); nb = (4, 10)
            elif fmt_key == '16bit':
                cf = (300, 800); nb = (6, 14)
            elif fmt_key == '24bit':
                cf = (400, 1000); nb = (8, 16)
            elif fmt_key in ['32bit', '32bit_float']:
                cf = (500, 1200); nb = (10, 18)
            elif fmt_key == '64bit_float':
                cf = (600, 1500); nb = (12, 20)
            else:
                cf = (300, 800); nb = (6, 14)
            return [{'carrier_freq': random.uniform(*cf),
                     'num_bands': int(random.uniform(*nb))} for _ in range(count)]

        else:
            return [{}] * count

    def _write_params_txt(self, folder: Path, filename: str, params: Dict,
                          fmt: str, sezione_start: float = 0.0, sezione_end: float = 1.0):
        """Scrive file .txt con i parametri dell'effetto."""
        txt_path = folder / f"{filename}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write(f"{self.effect_name.upper()} - PARAMETRI\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Immagine:           {self.input_path.name}\n")
            f.write(f"Formato:            {fmt}\n")
            f.write(f"Sezione applicata:  {sezione_start*100:.0f}% - {sezione_end*100:.0f}%\n")
            f.write("-" * 50 + "\n\n")
            f.write("PARAMETRI:\n")
            for k, v in params.items():
                if isinstance(v, float):
                    f.write(f"  {k}: {v:.3f}\n")
                else:
                    f.write(f"  {k}: {v}\n")
            f.write("\n" + "=" * 50 + "\n")
            f.write("COME RIPRODURRE IN AUDACITY (con effetto corrispondente):\n")
            f.write("=" * 50 + "\n")
            f.write("1. File → Importa → Dati Grezzi (Raw Data)\n")
            f.write("2. Scegli la codifica: {}\n".format(fmt))
            f.write("3. Applica l'effetto desiderato con i parametri sopra\n")
            f.write("4. File → Esporta → Dati Grezzi (Raw)\n")
            f.write("5. Rinomina il file da .raw a .bmp\n")

    def _process_single(self, fmt: str, folder: Path, params: Dict,
                        suffix: str, sezione_start: float = 0.0,
                        sezione_end: float = 1.0) -> Optional[Path]:
        """Applica l'effetto a tutto il file o a una sezione."""
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

        try:
            # Applica l'effetto usando la funzione corrispondente
            effect_func = getattr(SoxEffects, self.effect_name)
            if sezione_start == 0 and sezione_end == 1:
                effect_func(raw_in, raw_out, fmt, **params)
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
                    effect_func(sec_in, sec_out, fmt, **params)
                    new_sezione = sec_out.read_bytes()
                    new_data = data[:start] + new_sezione + data[end:]
                    raw_out.write_bytes(new_data)
                    sec_in.unlink(missing_ok=True)
                    sec_out.unlink(missing_ok=True)
                else:
                    effect_func(raw_in, raw_out, fmt, **params)
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Errore SoX ({self.effect_name}): {e.stderr.decode() if e.stderr else 'unknown'}")
            return None
        except Exception as e:
            print(f"   ⚠️  Errore: {e}")
            return None

        try:
            fname = f"{self.base_name}_{fmt}_{self.effect_name}_{suffix}.bmp"
            bmp_path = folder / fname
            BMPConverter.raw_to_bmp(raw_out, hdr_path, bmp_path, fmt, self.original_len)
            self._write_params_txt(folder, fname.replace('.bmp', ''), params, fmt, sezione_start, sezione_end)
        except Exception as e:
            print(f"   ⚠️  Errore conversione RAW→BMP su {fmt}: {e}")
            return None
        finally:
            for p in [raw_in, hdr_path, raw_out]:
                p.unlink(missing_ok=True)

        return bmp_path

    def _params_to_suffix(self, params: Dict) -> str:
        """Genera suffisso descrittivo dai parametri."""
        parts = []
        for k, v in params.items():
            if isinstance(v, float):
                parts.append(f"{k}{int(v*100):03d}" if v < 10 else f"{k}{int(v):03d}")
            else:
                parts.append(f"{k}{v}")
        return "_".join(parts)

    def process(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name} [EFFETTO: {self.effect_name}]")

        base_folder = self.output_base / self.base_name / self.effect_name.capitalize()
        base_folder.mkdir(parents=True, exist_ok=True)

        totali = 0

        for fmt_idx, (fmt_key, fmt_name) in enumerate(BMPConverter.FORMAT_NAMES.items()):
            fmt_folder = base_folder / fmt_name
            fmt_folder.mkdir(parents=True, exist_ok=True)

            # Seed diverso per formato
            livelli = self._genera_livelli(seed=fmt_idx * 77777 + 12345, count=50, fmt_key=fmt_key)

            # ---- FULL ----
            full_folder = fmt_folder / "Full"
            full_folder.mkdir(parents=True, exist_ok=True)

            for idx, params in enumerate(livelli):
                suffix = f"full_{idx:03d}_{self._params_to_suffix(params)}"
                path = self._process_single(fmt_key, full_folder, params, suffix)
                if path is not None:
                    totali += 1

            # ---- RANDOM ----
            random_folder = fmt_folder / "Random"
            random_folder.mkdir(parents=True, exist_ok=True)

            for i in range(30):
                start_pct = random.uniform(0.0, 0.4)
                end_pct = start_pct + random.uniform(0.2, 0.6)
                end_pct = min(end_pct, 1.0)
                start_pct = max(0.0, end_pct - 0.6)

                params = random.choice(livelli)
                suffix = (f"random_{i:03d}_{self._params_to_suffix(params)}"
                         f"_s{int(start_pct*100):02d}_e{int(end_pct*100):02d}")
                path = self._process_single(fmt_key, random_folder, params, suffix,
                                           start_pct, end_pct)
                if path is not None:
                    totali += 1

            # README
            readme_path = fmt_folder / "README.txt"
            with open(readme_path, 'w', encoding='utf-8') as rf:
                rf.write(f"{self.effect_name.upper()} - {self.input_path.name}\n")
                rf.write(f"Formato: {fmt_name}\n")
                rf.write("=" * 60 + "\n")
                rf.write("Parametri SoX usati:\n")
                rf.write(f"  Effetto: {self.effect_name}\n")
                rf.write(f"  {len(livelli)} livelli FULL + 30 RANDOM\n\n")
                rf.write("--- FULL ---\n")
                for f in sorted(full_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")
                rf.write("\n--- RANDOM ---\n")
                for f in sorted(random_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")

        summary_readme = base_folder / "README_COMPLETO.txt"
        with open(summary_readme, 'w', encoding='utf-8') as sf:
            sf.write(f"{self.effect_name.upper()} - {self.input_path.name}\n")
            sf.write("=" * 60 + "\n")
            sf.write(f"Totale file generati: {totali}\n")
            sf.write("\nPer ogni immagine è presente un file .txt con i parametri.\n")
            sf.write("\nFormati disponibili:\n")
            for fmt_name in BMPConverter.FORMAT_NAMES.values():
                sf.write(f"  • {fmt_name}\n")

        print(f"   ✅ Generati {totali} file ({self.effect_name}) per {self.base_name}")


# ======================================================================
# 4. MAIN - ESEGUE TUTTI GLI EFFETTI
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Effects - Distorsione, Phaser, Tremolo, Wahwah, Vocoder"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_effects_output',
                        help='Directory di output (default: bmp_effects_output)')
    parser.add_argument('--effects', nargs='+',
                        default=['overdrive', 'phaser', 'tremolo', 'wahwah', 'vocoder'],
                        help='Effetti da applicare (default: tutti)')
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
    print("⚡ EFFETTI: " + ", ".join(args.effects))
    print("⚡ 50 FULL + 30 RANDOM per formato per effetto")
    print("⚡ Formati: 8, 16, 24, 32-bit PCM + 32/64-bit Float")
    print("=" * 70)

    for bmp_path in bmp_files:
        for effect in args.effects:
            if effect not in ['overdrive', 'phaser', 'tremolo', 'wahwah', 'vocoder']:
                print(f"⚠️  Effetto '{effect}' non riconosciuto, saltato.")
                continue
            processor = BMPEffectProcessor(bmp_path, output_dir, effect)
            processor.process()

    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
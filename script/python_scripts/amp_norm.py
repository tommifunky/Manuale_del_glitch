#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Amplify & Normalize - Simula amplificazione e normalizzazione di Audacity
Con 50 livelli FULL + 30 RANDOM per formato. Ogni formato ha seed diverso.
"""

import os
import sys
import struct
import subprocess
import argparse
import tempfile
import random
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional

# ======================================================================
# 1. CONVERTITORE BMP ↔ RAW
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
# 2. AMPLIFICA E NORMALIZZA CON SOX
# ======================================================================

class SoxAmplify:
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
    def apply_gain(input_path: Path, output_path: Path, fmt: str, gain_db: float) -> None:
        """Applica amplificazione (gain) in dB."""
        flags = SoxAmplify._sox_format_flags(fmt)
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'gain', str(gain_db)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def apply_normalize(input_path: Path, output_path: Path, fmt: str,
                        type: str = 'peak', target_db: float = -1.0) -> None:
        """
        Applica normalizzazione.
        type: 'peak', 'rms', 'both'
        target_db: livello target in dB (tipicamente -1 a -6 per peak, -12 a -20 per RMS)
        """
        flags = SoxAmplify._sox_format_flags(fmt)
        if type == 'peak':
            cmd = [
                'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
                '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
                'norm', str(target_db)
            ]
        elif type == 'rms':
            cmd = [
                'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
                '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
                'norm', str(target_db), '--rms'
            ]
        elif type == 'both':
            cmd = [
                'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
                '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
                'norm', str(target_db), '--rms'
            ]
            # SoX non ha un'opzione "both", ma possiamo combinare:
            # Prima normalizza peak, poi RMS? In realtà norm con --rms fa RMS.
            # Per "both" faremo RMS, che è più comune in Audacity.
            # Se l'utente vuole entrambi, possiamo fare due passaggi, ma per semplicità usiamo RMS.
            pass
        else:
            raise ValueError(f"Tipo normalizzazione non supportato: {type}")
        subprocess.run(cmd, check=True, capture_output=True)


# ======================================================================
# 3. MOTORE PRINCIPALE (PER AMPLIFICA E NORMALIZZA)
# ======================================================================

class BMPAmplifyProcessor:
    def __init__(self, input_path: Path, output_base: Path, mode: str):
        self.input_path = input_path
        self.output_base = output_base
        self.mode = mode  # 'amplify' o 'normalize'
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
        """Genera parametri casuali per amplifica o normalizza."""
        random.seed(seed)

        if self.mode == 'amplify':
            # Guadagno in dB, range diversi per formato
            if fmt_key == '8bit':
                gain_range = (-12.0, 6.0)  # da attenuazione a lieve amplificazione
            elif fmt_key == '16bit':
                gain_range = (-24.0, 12.0)
            elif fmt_key == '24bit':
                gain_range = (-36.0, 18.0)
            elif fmt_key in ['32bit', '32bit_float']:
                gain_range = (-48.0, 24.0)
            elif fmt_key == '64bit_float':
                gain_range = (-60.0, 30.0)
            else:
                gain_range = (-20.0, 10.0)

            livelli = []
            for _ in range(count):
                gain_db = random.uniform(*gain_range)
                # 20% di probabilità di estremo (clipping o attenuazione estrema)
                if random.random() < 0.2:
                    gain_db = gain_db * random.uniform(1.5, 3.0)
                    gain_db = max(-80.0, min(60.0, gain_db))
                livelli.append({'gain_db': gain_db})
            return livelli

        elif self.mode == 'normalize':
            # Tipi di normalizzazione: peak, rms, both
            norm_types = ['peak', 'rms', 'both']
            # Target dB range
            if fmt_key == '8bit':
                target_range = (-6.0, -1.0)  # peak target
                target_range_rms = (-24.0, -12.0)
            elif fmt_key == '16bit':
                target_range = (-6.0, -1.0)
                target_range_rms = (-24.0, -12.0)
            elif fmt_key == '24bit':
                target_range = (-6.0, -1.0)
                target_range_rms = (-24.0, -12.0)
            elif fmt_key in ['32bit', '32bit_float']:
                target_range = (-12.0, -0.5)
                target_range_rms = (-30.0, -12.0)
            elif fmt_key == '64bit_float':
                target_range = (-12.0, -0.5)
                target_range_rms = (-36.0, -12.0)
            else:
                target_range = (-6.0, -1.0)
                target_range_rms = (-24.0, -12.0)

            livelli = []
            for _ in range(count):
                norm_type = random.choice(norm_types)
                if norm_type == 'peak':
                    target_db = random.uniform(*target_range)
                elif norm_type == 'rms':
                    target_db = random.uniform(*target_range_rms)
                else:  # both
                    # Per "both" usiamo RMS, ma con target un po' più alto
                    target_db = random.uniform(*target_range_rms)
                livelli.append({
                    'type': norm_type,
                    'target_db': target_db
                })
            return livelli
        else:
            return [{}] * count

    def _write_params_txt(self, folder: Path, filename: str, params: Dict,
                          fmt: str, sezione_start: float = 0.0, sezione_end: float = 1.0):
        """Scrive file .txt con i parametri dell'effetto."""
        txt_path = folder / f"{filename}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            if self.mode == 'amplify':
                f.write("AMPLIFICAZIONE - PARAMETRI\n")
            else:
                f.write("NORMALIZZAZIONE - PARAMETRI\n")
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
            f.write("COME RIPRODURRE IN AUDACITY:\n")
            f.write("=" * 50 + "\n")
            f.write("1. File → Importa → Dati Grezzi (Raw Data)\n")
            f.write("2. Scegli la codifica: {}\n".format(fmt))
            if self.mode == 'amplify':
                f.write("3. Effetto → Amplifica\n")
                f.write("4. Imposta il guadagno a {:.2f} dB\n".format(params.get('gain_db', 0)))
            else:
                f.write("3. Effetto → Normalizza\n")
                f.write("4. Imposta il tipo '{}' e target {:.2f} dB\n".format(
                    params.get('type', 'peak'), params.get('target_db', -1)))
            f.write("5. File → Esporta → Dati Grezzi (Raw)\n")
            f.write("6. Rinomina il file da .raw a .bmp\n")

    def _process_single(self, fmt: str, folder: Path, params: Dict,
                        suffix: str, sezione_start: float = 0.0,
                        sezione_end: float = 1.0) -> Optional[Path]:
        """Applica amplifica o normalizza a tutto il file o a una sezione."""
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
            # Funzione da chiamare
            if self.mode == 'amplify':
                apply_func = SoxAmplify.apply_gain
                func_args = {'gain_db': params['gain_db']}
            else:  # normalize
                apply_func = SoxAmplify.apply_normalize
                func_args = {'type': params['type'], 'target_db': params['target_db']}

            if sezione_start == 0 and sezione_end == 1:
                apply_func(raw_in, raw_out, fmt, **func_args)
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
                    apply_func(sec_in, sec_out, fmt, **func_args)
                    new_sezione = sec_out.read_bytes()
                    new_data = data[:start] + new_sezione + data[end:]
                    raw_out.write_bytes(new_data)
                    sec_in.unlink(missing_ok=True)
                    sec_out.unlink(missing_ok=True)
                else:
                    apply_func(raw_in, raw_out, fmt, **func_args)
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Errore SoX: {e.stderr.decode() if e.stderr else 'unknown'}")
            return None
        except Exception as e:
            print(f"   ⚠️  Errore: {e}")
            return None

        try:
            mode_prefix = 'amplify' if self.mode == 'amplify' else 'normalize'
            fname = f"{self.base_name}_{fmt}_{mode_prefix}_{suffix}.bmp"
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
        if self.mode == 'amplify':
            return f"gain{int(params['gain_db']*10):+04d}"  # es. gain+003, gain-012
        else:  # normalize
            return f"{params['type']}_{int(params['target_db']*10):+04d}"

    def process(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name} [MODE: {self.mode}]")

        base_folder = self.output_base / self.base_name / self.mode.capitalize()
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
                rf.write(f"{self.mode.upper()} - {self.input_path.name}\n")
                rf.write(f"Formato: {fmt_name}\n")
                rf.write("=" * 60 + "\n")
                rf.write("Parametri utilizzati:\n")
                if self.mode == 'amplify':
                    rf.write("  Gain in dB (range variabile per formato)\n")
                else:
                    rf.write("  Tipo normalizzazione: peak, rms, both (mappato su rms)\n")
                    rf.write("  Target dB (diverso per peak e rms)\n")
                rf.write(f"\n{len(livelli)} livelli FULL + 30 RANDOM\n\n")
                rf.write("--- FULL ---\n")
                for f in sorted(full_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")
                rf.write("\n--- RANDOM ---\n")
                for f in sorted(random_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")

        summary_readme = base_folder / "README_COMPLETO.txt"
        with open(summary_readme, 'w', encoding='utf-8') as sf:
            sf.write(f"{self.mode.upper()} - {self.input_path.name}\n")
            sf.write("=" * 60 + "\n")
            sf.write(f"Totale file generati: {totali}\n")
            sf.write("\nPer ogni immagine è presente un file .txt con i parametri.\n")
            sf.write("\nFormati disponibili:\n")
            for fmt_name in BMPConverter.FORMAT_NAMES.values():
                sf.write(f"  • {fmt_name}\n")

        print(f"   ✅ Generati {totali} file ({self.mode}) per {self.base_name}")


# ======================================================================
# 4. MAIN - ESEGUE AMPLIFICA E NORMALIZZA
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Amplify & Normalize - Simula amplificazione e normalizzazione di Audacity"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_amplify_output',
                        help='Directory di output (default: bmp_amplify_output)')
    parser.add_argument('--modes', nargs='+', default=['amplify', 'normalize'],
                        help='Modalità da eseguire: amplify, normalize (default: entrambe)')
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
    print("⚡ MODALITÀ: " + ", ".join(args.modes))
    print("⚡ 50 FULL + 30 RANDOM per formato per modalità")
    print("⚡ Formati: 8, 16, 24, 32-bit PCM + 32/64-bit Float")
    print("=" * 70)

    for bmp_path in bmp_files:
        for mode in args.modes:
            if mode not in ['amplify', 'normalize']:
                print(f"⚠️  Modalità '{mode}' non riconosciuta, saltata.")
                continue
            processor = BMPAmplifyProcessor(bmp_path, output_dir, mode)
            processor.process()

    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
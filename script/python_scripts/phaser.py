#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Phaser - Simula TUTTI i parametri del phaser di Audacity
Mappatura: dry/wet → gain-in/gain-out, LFO frequency → speed, depth → delay, feedback → decay
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
# 2. PHASER CON SOX (MAPPATURA PARAMETRI AUDACITY)
# ======================================================================

class SoxPhaser:
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
    def apply_phaser(input_path: Path, output_path: Path, fmt: str, 
                     gain_in: float, gain_out: float, delay: float, 
                     decay: float, speed: float, mode: str = ''):
        """Applica phaser con SoX."""
        flags = SoxPhaser._sox_format_flags(fmt)
        
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'phaser', str(gain_in), str(gain_out), str(delay), str(decay), str(speed)
        ]
        if mode:
            cmd.append(mode)
        subprocess.run(cmd, check=True, capture_output=True)


# ======================================================================
# 3. MOTORE PRINCIPALE
# ======================================================================

class BMPPhaser:
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

    def _genera_livelli(self, seed: int, count: int = 50, fmt_key: str = '') -> List[Dict]:
        """Genera count livelli di phaser con parametri DIVERSI per formato."""
        random.seed(seed)
        livelli = []
        
        # ===== Range DIFFERENTI per ogni formato =====
        if fmt_key == '8bit':
            delay_range = (0.1, 0.8)
            decay_range = (0.0, 0.3)
            speed_range = (0.05, 0.5)
            dry_range = (0.7, 1.0)
            wet_range = (0.1, 0.5)
            gain_out_range = (0.3, 0.8)
        elif fmt_key == '16bit':
            delay_range = (0.5, 2.5)
            decay_range = (0.1, 0.6)
            speed_range = (0.1, 1.5)
            dry_range = (0.4, 0.9)
            wet_range = (0.3, 0.8)
            gain_out_range = (0.3, 1.0)
        elif fmt_key == '24bit':
            delay_range = (1.0, 4.0)
            decay_range = (0.3, 0.85)
            speed_range = (0.2, 2.5)
            dry_range = (0.2, 0.7)
            wet_range = (0.5, 1.0)
            gain_out_range = (0.5, 1.0)
        elif fmt_key in ['32bit', '32bit_float']:
            delay_range = (2.0, 5.0)
            decay_range = (0.5, 0.95)
            speed_range = (0.5, 3.0)
            dry_range = (0.1, 0.5)
            wet_range = (0.7, 1.0)
            gain_out_range = (0.7, 1.0)
        elif fmt_key == '64bit_float':
            delay_range = (3.0, 5.0)
            decay_range = (0.6, 0.99)
            speed_range = (0.5, 3.0)
            dry_range = (0.05, 0.3)
            wet_range = (0.8, 1.2)
            gain_out_range = (0.8, 1.2)
        else:
            delay_range = (0.5, 3.0)
            decay_range = (0.1, 0.8)
            speed_range = (0.1, 2.0)
            dry_range = (0.3, 0.8)
            wet_range = (0.3, 0.8)
            gain_out_range = (0.3, 1.0)
        
        for _ in range(count):
            dry = random.uniform(dry_range[0], dry_range[1])
            wet = random.uniform(wet_range[0], wet_range[1])
            speed = random.uniform(speed_range[0], speed_range[1])
            delay = random.uniform(delay_range[0], delay_range[1])
            decay = random.uniform(decay_range[0], decay_range[1])
            mode = random.choice(['', '-s', '-t'])
            gain_out = random.uniform(gain_out_range[0], gain_out_range[1])
            
            if random.random() < 0.2:
                delay = min(5.0, delay * 1.8)
                decay = min(0.99, decay * 1.5)
            
            livelli.append({
                'gain_in': dry,
                'gain_out': wet * gain_out,
                'delay': delay,
                'decay': decay,
                'speed': speed,
                'mode': mode,
                'dry': dry,
                'wet': wet,
                'depth': delay,
                'feedback': decay,
                'lfo_freq': speed,
                'output_gain': gain_out,
            })
        return livelli

    def _write_params_txt(self, folder: Path, filename: str, params: Dict, 
                          fmt: str, sezione_start: float = 0.0, sezione_end: float = 1.0):
        """Scrive un file .txt con i parametri Audacity per l'immagine."""
        txt_path = folder / f"{filename}.txt"
        
        # Mappatura parametri Audacity
        # Stages → simulato con delay e decay
        stages = int(params['delay'] * 2) + 2  # da 2 a 12 stadi
        stages = min(stages, 12)
        stages = max(stages, 2)
        
        # Dry/Wet → basato su dry e wet
        dry_wet = int((params['wet'] / (params['dry'] + params['wet'])) * 100)
        dry_wet = min(dry_wet, 100)
        dry_wet = max(dry_wet, 0)
        
        # Feedback → decay convertito in percentuale
        feedback_pct = int(params['decay'] * 100)
        feedback_pct = min(feedback_pct, 100)
        
        # Output gain → in dB
        output_gain_db = int((params['output_gain'] - 0.5) * 20)
        output_gain_db = max(-60, min(20, output_gain_db))
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write("PHASER - PARAMETRI AUDACITY\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Immagine:           {self.input_path.name}\n")
            f.write(f"Formato:            {fmt}\n")
            f.write(f"Sezione applicata:  {sezione_start*100:.0f}% - {sezione_end*100:.0f}%\n")
            f.write("-" * 50 + "\n\n")
            
            f.write("PARAMETRI PHASER:\n")
            f.write("  Passaggi (Stages):      {:d}\n".format(stages))
            f.write("  Dry/Wet (%):            {:d}%\n".format(dry_wet))
            f.write("  Frequenza LFO (Hz):     {:.2f}\n".format(params['speed']))
            f.write("  Fase LFO iniziale (gradi):  {:.0f}\n".format(20.0 if params['mode'] == '-s' else 0.0))
            f.write("  Profondità:             {:.1f}\n".format(params['depth']))
            f.write("  Feedback (%):           {:d}%\n".format(feedback_pct))
            f.write("  Guadagno uscita (dB):   {:d}\n".format(output_gain_db))
            f.write("-" * 50 + "\n\n")
            
            f.write("PARAMETRI INTERNI (mapping SoX):\n")
            f.write("  gain-in (secco):        {:.2f}\n".format(params['dry']))
            f.write("  gain-out (elaborato):   {:.2f}\n".format(params['gain_out']))
            f.write("  delay (profondità):     {:.2f}\n".format(params['delay']))
            f.write("  decay (feedback):       {:.2f}\n".format(params['decay']))
            f.write("  speed (LFO):            {:.2f}\n".format(params['speed']))
            f.write("  mode (LFO shape):       {}\n".format(params['mode'] if params['mode'] else 'sinusoidale (default)'))
            f.write("\n" + "=" * 50 + "\n")
            f.write("COME RIPRODURRE IN AUDACITY:\n")
            f.write("=" * 50 + "\n")
            f.write("1. File → Importa → Dati Grezzi (Raw Data)\n")
            f.write("2. Scegli la codifica: {}\n".format(fmt))
            f.write("3. Effetto → Phaser\n")
            f.write("4. Imposta i parametri sopra\n")
            f.write("5. File → Esporta → Dati Grezzi (Raw)\n")
            f.write("6. Rinomina il file da .raw a .bmp\n")

    def _process_single(self, fmt: str, folder: Path, params: Dict, 
                        suffix: str, sezione_start: float = 0.0, 
                        sezione_end: float = 1.0) -> Optional[Path]:
        """Applica phaser a tutto il file o a una sezione."""
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
            if sezione_start == 0 and sezione_end == 1:
                SoxPhaser.apply_phaser(raw_in, raw_out, fmt,
                                      params['gain_in'], params['gain_out'],
                                      params['delay'], params['decay'],
                                      params['speed'], params['mode'])
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
                    SoxPhaser.apply_phaser(sec_in, sec_out, fmt,
                                          params['gain_in'], params['gain_out'],
                                          params['delay'], params['decay'],
                                          params['speed'], params['mode'])
                    new_sezione = sec_out.read_bytes()
                    new_data = data[:start] + new_sezione + data[end:]
                    raw_out.write_bytes(new_data)
                    sec_in.unlink(missing_ok=True)
                    sec_out.unlink(missing_ok=True)
                else:
                    SoxPhaser.apply_phaser(raw_in, raw_out, fmt,
                                          params['gain_in'], params['gain_out'],
                                          params['delay'], params['decay'],
                                          params['speed'], params['mode'])
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Errore SoX: {e.stderr.decode() if e.stderr else 'unknown'}")
            return None
        except Exception as e:
            print(f"   ⚠️  Errore: {e}")
            return None

        try:
            fname = f"{self.base_name}_{fmt}_phaser_{suffix}.bmp"
            bmp_path = folder / fname
            BMPConverter.raw_to_bmp(raw_out, hdr_path, bmp_path, fmt, self.original_len)
            
            # Scrivi il file .txt con i parametri
            self._write_params_txt(folder, fname.replace('.bmp', ''), params, fmt, sezione_start, sezione_end)
        except Exception as e:
            print(f"   ⚠️  Errore conversione RAW→BMP su {fmt}: {e}")
            return None
        finally:
            for p in [raw_in, hdr_path, raw_out]:
                p.unlink(missing_ok=True)

        return bmp_path

    def _params_to_suffix(self, params: Dict) -> str:
        """Genera un suffisso descrittivo dai parametri."""
        return (f"d{int(params['delay']*10):02d}"
                f"_r{int(params['speed']*100):03d}"
                f"_fb{int(params['decay']*10):02d}"
                f"_dr{int(params['dry']*10):02d}"
                f"_wet{int(params['wet']*10):02d}"
                f"_out{int(params['output_gain']*10):02d}"
                f"{'_s' if params['mode'] == '-s' else '_t' if params['mode'] == '-t' else ''}")

    def process(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name}")

        base_folder = self.output_base / self.base_name
        base_folder.mkdir(parents=True, exist_ok=True)

        phaser_folder = base_folder / "Phaser"
        phaser_folder.mkdir(parents=True, exist_ok=True)

        totali = 0

        for fmt_idx, (fmt_key, fmt_name) in enumerate(BMPConverter.FORMAT_NAMES.items()):
            fmt_folder = phaser_folder / fmt_name
            fmt_folder.mkdir(parents=True, exist_ok=True)

            # Seed diverso per ogni formato
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
                rf.write(f"PHASER - {self.input_path.name}\n")
                rf.write(f"Formato: {fmt_name}\n")
                rf.write("=" * 60 + "\n")
                rf.write("Parametri Audacity mappati su SoX:\n")
                rf.write("  dry/wet → gain-in/gain-out\n")
                rf.write("  LFO frequency → speed\n")
                rf.write("  Depth → delay\n")
                rf.write("  Feedback → decay\n")
                rf.write("  LFO phase → -s/-t (sinusoidale/triangolare)\n")
                rf.write("  Output gain → gain-out\n")
                rf.write(f"\n{len(livelli)} livelli FULL + 30 RANDOM\n\n")
                rf.write("--- FULL ---\n")
                for f in sorted(full_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")
                rf.write("\n--- RANDOM ---\n")
                for f in sorted(random_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")

        summary_readme = phaser_folder / "README_COMPLETO.txt"
        with open(summary_readme, 'w', encoding='utf-8') as sf:
            sf.write(f"PHASER - {self.input_path.name}\n")
            sf.write("=" * 60 + "\n")
            sf.write(f"Totale file generati: {totali}\n")
            sf.write("\nPer ogni immagine è presente un file .txt con i parametri Audacity.\n")
            sf.write("\nMappatura parametri Audacity → SoX:\n")
            sf.write("  Dry/Wet → gain-in (secco) / gain-out (elaborato + output)\n")
            sf.write("  LFO Frequency → speed (0.05-3.0 Hz)\n")
            sf.write("  Depth → delay (0.1-5.0)\n")
            sf.write("  Feedback → decay (0.0-0.95)\n")
            sf.write("  LFO Phase → -s (sinusoidale) / -t (triangolare)\n")
            sf.write("  Output Gain → gain-out (0.1-1.0)\n")
            sf.write("\nOgni formato ha un set di parametri DIVERSO.\n")

        print(f"   ✅ Generati {totali} file phaser per {self.base_name}")


# ======================================================================
# 4. MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Phaser - Simula TUTTI i parametri di Audacity"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_phaser_output',
                        help='Directory di output (default: bmp_phaser_output)')
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
    print("⚡ PHASER - TUTTI i parametri di Audacity mappati")
    print("⚡ 50 livelli FULL + 30 RANDOM per formato")
    print("⚡ Formati: 8, 16, 24, 32-bit PCM + 32/64-bit Float")
    print("⚡ Ogni formato ha parametri DIVERSI")
    print("=" * 70)

    for bmp_path in bmp_files:
        phaser = BMPPhaser(bmp_path, output_dir)
        phaser.process()

    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
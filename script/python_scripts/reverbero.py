#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Reverb - Simula TUTTI i parametri del riverbero di Audacity (mappati su SoX)
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
# 1. CONVERTITORE BMP ↔ RAW (IDENTICO A PRIMA)
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
# 2. RIVERBERO CON SOX (EFFETTO 'reverb')
# ======================================================================

class SoxReverb:
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
    def apply_reverb(input_path: Path, output_path: Path, fmt: str,
                     reverberance: float, hf_damping: float,
                     room_scale: float, stereo_depth: float,
                     pre_delay: float, wet_gain: float,
                     wet_only: bool = False):
        """
        Applica riverbero con SoX usando l'effetto 'reverb'.
        Parametri (tutti in percentuale 0-100, tranne pre_delay in ms e wet_gain in dB):
          - reverberance: 0-100 (default 50)
          - hf_damping: 0-100 (default 50)
          - room_scale: 0-100 (default 100)
          - stereo_depth: 0-100 (default 100)
          - pre_delay: 0-... ms (default 0)
          - wet_gain: -10..10 dB (default 0)
          - wet_only: True/False (default False)
        """
        flags = SoxReverb._sox_format_flags(fmt)
        
        # Costruisci comando SoX
        cmd = [
            'sox', '-t', 'raw', '-r', '44100'] + flags + [str(input_path),
            '-t', 'raw', '-r', '44100'] + flags + [str(output_path),
            'reverb',
            str(reverberance),
            str(hf_damping),
            str(room_scale),
            str(stereo_depth),
            str(pre_delay),
            str(wet_gain)
        ]
        if wet_only:
            cmd.append('wet-only')
        
        subprocess.run(cmd, check=True, capture_output=True)


# ======================================================================
# 3. MOTORE PRINCIPALE (ADATTATO PER RIVERBERO)
# ======================================================================

class BMPReverb:
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
        """Genera count livelli di riverbero con parametri DIVERSI per formato."""
        random.seed(seed)
        livelli = []
        
        # Range differenti per ogni formato (per dare varietà)
        if fmt_key == '8bit':
            # Riverbero leggero e corto
            rev_range = (20, 60)
            damp_range = (10, 50)
            room_range = (30, 80)
            stereo_range = (40, 100)
            pre_range = (0, 20)
            wet_range = (-6, 0)
        elif fmt_key == '16bit':
            rev_range = (30, 75)
            damp_range = (20, 60)
            room_range = (50, 90)
            stereo_range = (50, 100)
            pre_range = (0, 30)
            wet_range = (-3, 3)
        elif fmt_key == '24bit':
            rev_range = (40, 85)
            damp_range = (30, 70)
            room_range = (60, 100)
            stereo_range = (60, 100)
            pre_range = (5, 50)
            wet_range = (0, 6)
        elif fmt_key in ['32bit', '32bit_float']:
            rev_range = (50, 95)
            damp_range = (40, 80)
            room_range = (70, 100)
            stereo_range = (70, 100)
            pre_range = (10, 60)
            wet_range = (2, 10)
        elif fmt_key == '64bit_float':
            rev_range = (60, 100)
            damp_range = (50, 90)
            room_range = (80, 100)
            stereo_range = (80, 100)
            pre_range = (20, 80)
            wet_range = (4, 12)
        else:
            rev_range = (30, 80)
            damp_range = (20, 70)
            room_range = (50, 90)
            stereo_range = (50, 100)
            pre_range = (0, 40)
            wet_range = (0, 6)
        
        for _ in range(count):
            reverberance = random.uniform(rev_range[0], rev_range[1])
            hf_damping = random.uniform(damp_range[0], damp_range[1])
            room_scale = random.uniform(room_range[0], room_range[1])
            stereo_depth = random.uniform(stereo_range[0], stereo_range[1])
            pre_delay = random.uniform(pre_range[0], pre_range[1])
            wet_gain = random.uniform(wet_range[0], wet_range[1])
            wet_only = random.choice([False, True])  # a volte solo l'effetto
            
            # 15% di probabilità di riverbero "estremo"
            if random.random() < 0.15:
                reverberance = min(100, reverberance * 1.5)
                room_scale = min(100, room_scale * 1.3)
                pre_delay = min(120, pre_delay * 2)
            
            livelli.append({
                'reverberance': reverberance,
                'hf_damping': hf_damping,
                'room_scale': room_scale,
                'stereo_depth': stereo_depth,
                'pre_delay': pre_delay,
                'wet_gain': wet_gain,
                'wet_only': wet_only,
            })
        return livelli

    def _write_params_txt(self, folder: Path, filename: str, params: Dict,
                          fmt: str, sezione_start: float = 0.0, sezione_end: float = 1.0):
        """Scrive un file .txt con i parametri del riverbero (stile Audacity)."""
        txt_path = folder / f"{filename}.txt"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write("RIVERBERO - PARAMETRI (AUDACITY / SOX)\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Immagine:           {self.input_path.name}\n")
            f.write(f"Formato:            {fmt}\n")
            f.write(f"Sezione applicata:  {sezione_start*100:.0f}% - {sezione_end*100:.0f}%\n")
            f.write("-" * 50 + "\n\n")
            
            f.write("PARAMETRI RIVERBERO:\n")
            f.write("  Riverberanza (reverberance):    {:.1f}%\n".format(params['reverberance']))
            f.write("  Smorzamento HF (hf_damping):    {:.1f}%\n".format(params['hf_damping']))
            f.write("  Scala stanza (room_scale):      {:.1f}%\n".format(params['room_scale']))
            f.write("  Profondità stereo:              {:.1f}%\n".format(params['stereo_depth']))
            f.write("  Pre-delay:                      {:.1f} ms\n".format(params['pre_delay']))
            f.write("  Guadagno wet (wet_gain):        {:.1f} dB\n".format(params['wet_gain']))
            f.write("  Solo effetto (wet_only):        {}\n".format("Sì" if params['wet_only'] else "No"))
            f.write("\n" + "=" * 50 + "\n")
            f.write("COME RIPRODURRE IN AUDACITY (con effetto Riverbero):\n")
            f.write("=" * 50 + "\n")
            f.write("1. File → Importa → Dati Grezzi (Raw Data)\n")
            f.write("2. Scegli la codifica: {}\n".format(fmt))
            f.write("3. Effetto → Riverbero\n")
            f.write("4. Imposta i parametri sopra (mappatura diretta)\n")
            f.write("5. File → Esporta → Dati Grezzi (Raw)\n")
            f.write("6. Rinomina il file da .raw a .bmp\n")

    def _process_single(self, fmt: str, folder: Path, params: Dict,
                        suffix: str, sezione_start: float = 0.0,
                        sezione_end: float = 1.0) -> Optional[Path]:
        """Applica riverbero a tutto il file o a una sezione."""
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
                SoxReverb.apply_reverb(raw_in, raw_out, fmt,
                                       params['reverberance'],
                                       params['hf_damping'],
                                       params['room_scale'],
                                       params['stereo_depth'],
                                       params['pre_delay'],
                                       params['wet_gain'],
                                       params['wet_only'])
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
                    SoxReverb.apply_reverb(sec_in, sec_out, fmt,
                                           params['reverberance'],
                                           params['hf_damping'],
                                           params['room_scale'],
                                           params['stereo_depth'],
                                           params['pre_delay'],
                                           params['wet_gain'],
                                           params['wet_only'])
                    new_sezione = sec_out.read_bytes()
                    new_data = data[:start] + new_sezione + data[end:]
                    raw_out.write_bytes(new_data)
                    sec_in.unlink(missing_ok=True)
                    sec_out.unlink(missing_ok=True)
                else:
                    SoxReverb.apply_reverb(raw_in, raw_out, fmt,
                                           params['reverberance'],
                                           params['hf_damping'],
                                           params['room_scale'],
                                           params['stereo_depth'],
                                           params['pre_delay'],
                                           params['wet_gain'],
                                           params['wet_only'])
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Errore SoX: {e.stderr.decode() if e.stderr else 'unknown'}")
            return None
        except Exception as e:
            print(f"   ⚠️  Errore: {e}")
            return None

        try:
            fname = f"{self.base_name}_{fmt}_reverb_{suffix}.bmp"
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
        """Genera un suffisso descrittivo dai parametri."""
        return (f"rev{int(params['reverberance']):03d}"
                f"_dmp{int(params['hf_damping']):03d}"
                f"_rm{int(params['room_scale']):03d}"
                f"_st{int(params['stereo_depth']):03d}"
                f"_pd{int(params['pre_delay']):03d}"
                f"_wg{int(params['wet_gain']+10):02d}")

    def process(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name}")

        base_folder = self.output_base / self.base_name
        base_folder.mkdir(parents=True, exist_ok=True)

        reverb_folder = base_folder / "Riverbero"
        reverb_folder.mkdir(parents=True, exist_ok=True)

        totali = 0

        for fmt_idx, (fmt_key, fmt_name) in enumerate(BMPConverter.FORMAT_NAMES.items()):
            fmt_folder = reverb_folder / fmt_name
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
                rf.write(f"RIVERBERO - {self.input_path.name}\n")
                rf.write(f"Formato: {fmt_name}\n")
                rf.write("=" * 60 + "\n")
                rf.write("Parametri Audacity mappati su SoX (effetto 'reverb'):\n")
                rf.write("  Riverberanza → reverberance (%)\n")
                rf.write("  Smorzamento HF → hf_damping (%)\n")
                rf.write("  Scala stanza → room_scale (%)\n")
                rf.write("  Profondità stereo → stereo_depth (%)\n")
                rf.write("  Pre-delay → pre_delay (ms)\n")
                rf.write("  Guadagno wet → wet_gain (dB)\n")
                rf.write("  Solo effetto → wet_only (on/off)\n")
                rf.write(f"\n{len(livelli)} livelli FULL + 30 RANDOM\n\n")
                rf.write("--- FULL ---\n")
                for f in sorted(full_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")
                rf.write("\n--- RANDOM ---\n")
                for f in sorted(random_folder.glob("*.bmp")):
                    rf.write(f"  {f.name}\n")

        summary_readme = reverb_folder / "README_COMPLETO.txt"
        with open(summary_readme, 'w', encoding='utf-8') as sf:
            sf.write(f"RIVERBERO - {self.input_path.name}\n")
            sf.write("=" * 60 + "\n")
            sf.write(f"Totale file generati: {totali}\n")
            sf.write("\nPer ogni immagine è presente un file .txt con i parametri Audacity.\n")
            sf.write("\nMappatura parametri Audacity → SoX:\n")
            sf.write("  Riverberanza → reverberance (0-100%)\n")
            sf.write("  Smorzamento HF → hf_damping (0-100%)\n")
            sf.write("  Scala stanza → room_scale (0-100%)\n")
            sf.write("  Profondità stereo → stereo_depth (0-100%)\n")
            sf.write("  Pre-delay → pre_delay (0-... ms)\n")
            sf.write("  Guadagno wet → wet_gain (-10..+10 dB)\n")
            sf.write("  Solo effetto → wet_only (True/False)\n")
            sf.write("\nOgni formato ha un set di parametri DIVERSO.\n")
            sf.write("\nFormati disponibili:\n")
            for fmt_name in BMPConverter.FORMAT_NAMES.values():
                sf.write(f"  • {fmt_name}\n")

        print(f"   ✅ Generati {totali} file riverbero per {self.base_name}")


# ======================================================================
# 4. MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BMP Reverb - Simula TUTTI i parametri del riverbero di Audacity"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_reverb_output',
                        help='Directory di output (default: bmp_reverb_output)')
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
    print("⚡ RIVERBERO - TUTTI i parametri di Audacity mappati")
    print("⚡ 50 livelli FULL + 30 RANDOM per formato")
    print("⚡ Formati: 8, 16, 24, 32-bit PCM + 32/64-bit Float")
    print("⚡ Ogni formato ha parametri DIVERSI")
    print("=" * 70)

    for bmp_path in bmp_files:
        reverb = BMPReverb(bmp_path, output_dir)
        reverb.process()

    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
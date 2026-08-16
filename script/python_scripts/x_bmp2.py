#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMP Glitcher - TUTTI GLI EFFETTI AUDACITY
Genera migliaia di varianti glitchate con effetti Audacity su BMP.
Per ogni BMP: tutte le codifiche × tutti gli effetti × Full/HeaderExcluded/Random × livelli.
"""

import os
import sys
import random
import struct
import argparse
from pathlib import Path
from typing import List, Tuple, Callable, Optional, Dict
from io import BytesIO
import math

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("❌ ERRORE: numpy è richiesto. Installa con: pip install numpy")
    sys.exit(1)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  Pillow non trovato. HeaderSwap sarà saltato. Installa con: pip install pillow")

# ======================================================================
# 1. INTERPRETE FORMATI AUDIO
# ======================================================================

class AudioInterpreter:
    @staticmethod
    def to_samples(data: bytes, fmt: str) -> np.ndarray:
        if fmt == '8bit':
            return np.frombuffer(data, dtype=np.uint8).astype(np.float32)
        elif fmt == '16bit':
            return np.frombuffer(data, dtype=np.int16).astype(np.float32)
        elif fmt == '24bit':
            arr = np.frombuffer(data, dtype=np.uint8)
            valid_len = (len(arr) // 3) * 3
            arr = arr[:valid_len].reshape(-1, 3)
            padded = np.zeros((len(arr), 4), dtype=np.uint8)
            padded[:, :3] = arr
            sign_bit = (arr[:, 2] & 0x80).astype(bool)
            padded[sign_bit, 3] = 0xFF
            return padded.view(np.int32).astype(np.float32).flatten()
        elif fmt == '32bit':
            return np.frombuffer(data, dtype=np.int32).astype(np.float32)
        elif fmt == '32bit_float':
            return np.frombuffer(data, dtype=np.float32).astype(np.float32)
        elif fmt == '64bit_float':
            return np.frombuffer(data, dtype=np.float64).astype(np.float64)
        elif fmt == 'ulaw':
            u = np.frombuffer(data, dtype=np.uint8)
            u = ~u & 0xFF
            sign = (u & 0x80).astype(np.float32)
            exponent = ((u >> 4) & 0x07).astype(np.float32)
            mantissa = (u & 0x0F).astype(np.float32)
            sample = (mantissa * 8.0) + 132.0
            sample = sample * (2.0 ** exponent)
            return np.where(sign > 0, -sample, sample)
        elif fmt == 'alaw':
            a = np.frombuffer(data, dtype=np.uint8)
            a = a ^ 0x55
            sign = (a & 0x80).astype(np.float32)
            exponent = ((a >> 4) & 0x07).astype(np.float32)
            mantissa = (a & 0x0F).astype(np.float32)
            sample = (mantissa * 2.0) + 1.0
            sample = sample * (2.0 ** (exponent + 1)) - 1.0
            return np.where(sign > 0, -sample, sample)
        else:
            raise ValueError(f"Formato non supportato: {fmt}")

    @staticmethod
    def from_samples(samples: np.ndarray, fmt: str, original_len: int,
                     original_mean: Optional[float] = None,
                     original_std: Optional[float] = None) -> bytes:
        """Converte campioni in bytes. Se original_mean e original_std sono forniti, normalizza."""
        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        samples = np.asarray(samples).flatten()
        
        # Normalizzazione preserva media e deviazione standard (opzionale)
        if original_mean is not None and original_std is not None and original_std > 0:
            current_mean = np.mean(samples)
            current_std = np.std(samples)
            if current_std > 0:
                samples = (samples - current_mean) / current_std * original_std + original_mean
        
        if fmt == '8bit':
            clipped = np.clip(samples, 0, 255).astype(np.uint8)
        elif fmt == '16bit':
            clipped = np.clip(samples, -32768, 32767).astype(np.int16)
        elif fmt == '24bit':
            clipped = np.clip(samples, -8388608, 8388607).astype(np.int32)
            b0 = (clipped & 0xFF).astype(np.uint8)
            b1 = ((clipped >> 8) & 0xFF).astype(np.uint8)
            b2 = ((clipped >> 16) & 0xFF).astype(np.uint8)
            bytes_24 = np.empty((len(clipped), 3), dtype=np.uint8)
            bytes_24[:, 0] = b0
            bytes_24[:, 1] = b1
            bytes_24[:, 2] = b2
            clipped = bytes_24.flatten()
        elif fmt == '32bit':
            clipped = np.clip(samples, -2147483648, 2147483647).astype(np.int32)
        elif fmt == '32bit_float':
            clipped = samples.astype(np.float32)
        elif fmt == '64bit_float':
            clipped = samples.astype(np.float64)
        elif fmt == 'ulaw':
            sign = np.where(samples < 0, 0x80, 0).astype(np.int32)
            linear = np.abs(samples).astype(np.int32) + 132
            linear = np.clip(linear, 0, 32635)
            exponent = np.zeros_like(linear, dtype=np.int32)
            for i in range(7, -1, -1):
                exponent = np.where(linear >= (1 << (i + 3)), i, exponent)
            mantissa = (linear >> (exponent + 3)) & 0x0F
            u = ~(sign | (exponent << 4) | mantissa) & 0xFF
            clipped = u.astype(np.uint8)
        elif fmt == 'alaw':
            sign = np.where(samples < 0, 0x80, 0).astype(np.int32)
            linear = np.abs(samples).astype(np.int32)
            linear = np.clip(linear, 0, 4095)
            exponent = np.zeros_like(linear, dtype=np.int32)
            for i in range(7, -1, -1):
                exponent = np.where(linear >= (1 << (i + 1)), i, exponent)
            mantissa = (linear >> (exponent + 1)) & 0x0F
            a = (sign | (exponent << 4) | mantissa) ^ 0x55
            clipped = a.astype(np.uint8)
        else:
            raise ValueError(f"Formato non supportato: {fmt}")
        result = clipped.tobytes()
        if len(result) < original_len:
            result += b'\x00' * (original_len - len(result))
        return result[:original_len]

# ======================================================================
# 2. EFFETTI AUDACITY
# ======================================================================

class Effects:
    @staticmethod
    def amplify(samples: np.ndarray, gain: float) -> np.ndarray:
        return samples * gain

    @staticmethod
    def bass_treble(samples: np.ndarray, bass_gain: float, treble_gain: float,
                    cutoff_hz: float = 500, sample_rate: float = 44100) -> np.ndarray:
        """Bass & Treble: filtri shelving."""
        out = np.copy(samples)
        # Filtro shelving semplice per bassi
        alpha = 2.0 * np.pi * cutoff_hz / sample_rate
        if bass_gain != 0:
            b = np.array([1.0, -np.exp(-alpha)])
            a = np.array([1.0, -np.exp(-alpha) * (1.0 + bass_gain)])
            out = np.convolve(out, b, mode='same') / np.convolve(np.ones_like(out), a, mode='same')
        # Treble (shelving alto)
        if treble_gain != 0:
            alpha_t = 2.0 * np.pi * 2000.0 / sample_rate
            b = np.array([1.0 + treble_gain, -1.0])
            a = np.array([1.0, -1.0])
            out = np.convolve(out, b, mode='same') / np.convolve(np.ones_like(out), a, mode='same')
        return out

    @staticmethod
    def change_pitch(samples: np.ndarray, factor: float) -> np.ndarray:
        """Change Pitch: resample con interpolazione."""
        if factor <= 0:
            return samples
        indices = np.linspace(0, len(samples)-1, int(len(samples) * factor))
        indices = np.clip(indices, 0, len(samples)-1).astype(np.int32)
        return samples[indices]

    @staticmethod
    def change_speed(samples: np.ndarray, factor: float) -> np.ndarray:
        """Change Speed: stesso di change_pitch (senza pitch shift)."""
        if factor <= 0:
            return samples
        indices = np.linspace(0, len(samples)-1, int(len(samples) * factor))
        indices = np.clip(indices, 0, len(samples)-1).astype(np.int32)
        return samples[indices]

    @staticmethod
    def change_tempo(samples: np.ndarray, factor: float) -> np.ndarray:
        """Change Tempo: per BMP usiamo factor negativo per duplicare campioni."""
        if factor == 0:
            return samples
        if factor < 0:
            # Tempo negativo: duplica campioni per "rallentare" (crea eco/stutter)
            factor = abs(factor)
            out = np.repeat(samples, int(factor))
            if len(out) > len(samples):
                out = out[:len(samples)]
            else:
                out = np.pad(out, (0, len(samples)-len(out)), constant_values=0)
            return out
        else:
            # Tempo positivo: accorcia
            indices = np.linspace(0, len(samples)-1, int(len(samples) * factor))
            indices = np.clip(indices, 0, len(samples)-1).astype(np.int32)
            out = samples[indices]
            if len(out) < len(samples):
                out = np.pad(out, (0, len(samples)-len(out)), constant_values=0)
            return out[:len(samples)]

    @staticmethod
    def click_removal(samples: np.ndarray, threshold: float = 0.1) -> np.ndarray:
        """Click Removal: rileva picchi e li smussa."""
        out = np.copy(samples)
        # Rileva picchi (differenza > threshold * range)
        diff = np.abs(np.diff(samples))
        peak_mask = diff > threshold * np.max(diff)
        for i in np.where(peak_mask)[0]:
            if i > 1 and i < len(samples) - 2:
                out[i] = (samples[i-1] + samples[i+1]) / 2
        return out

    @staticmethod
    def distortion(samples: np.ndarray, drive: float) -> np.ndarray:
        """Distortion: soft clipping (tanh)."""
        max_val = np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1.0
        return np.tanh(samples / max_val * drive) * max_val

    @staticmethod
    def echo(samples: np.ndarray, delay: int, decay: float) -> np.ndarray:
        out = np.copy(samples)
        if delay > 0 and delay < len(samples):
            out[delay:] += samples[:-delay] * decay
        return out

    @staticmethod
    def fade_in_out(samples: np.ndarray, fade_in_len: int, fade_out_len: int) -> np.ndarray:
        out = np.copy(samples)
        if fade_in_len > 0:
            fade = np.linspace(0, 1, fade_in_len)
            out[:fade_in_len] *= fade
        if fade_out_len > 0:
            fade = np.linspace(1, 0, fade_out_len)
            out[-fade_out_len:] *= fade
        return out

    @staticmethod
    def filter_curve_random(samples: np.ndarray, strength: float = 1.0) -> np.ndarray:
        """Filter Curve Random: applica un filtro casuale usando FFT."""
        n = len(samples)
        fft = np.fft.rfft(samples)
        # Crea una curva casuale
        curve = np.ones(len(fft))
        for i in range(1, len(curve)):
            curve[i] = curve[i-1] * (1 + random.uniform(-0.1, 0.1) * strength)
        curve = np.clip(curve, 0.01, 10.0)
        return np.fft.irfft(fft * curve, n=n)

    @staticmethod
    def graphic_eq(samples: np.ndarray, bands: List[float]) -> np.ndarray:
        """Graphic EQ: applica guadagni a bande (10 bande)."""
        n = len(samples)
        fft = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(n)
        # Bande approssimative (0-20kHz)
        band_edges = np.linspace(0, 0.5, len(bands)+1)
        for i, gain in enumerate(bands):
            mask = (freqs >= band_edges[i]) & (freqs < band_edges[i+1])
            fft[mask] *= gain
        return np.fft.irfft(fft, n=n)

    @staticmethod
    def invert(samples: np.ndarray) -> np.ndarray:
        return -samples

    @staticmethod
    def loudness_normalisation(samples: np.ndarray, target_loudness: float = -14.0) -> np.ndarray:
        """Loudness Normalisation: regola il gain per raggiungere il target (EBU R128)."""
        rms = np.sqrt(np.mean(samples**2))
        if rms > 0:
            gain = 10 ** ((target_loudness - 20 * np.log10(rms)) / 20)
            return samples * gain
        return samples

    @staticmethod
    def normalise(samples: np.ndarray, peak: float = 0.9) -> np.ndarray:
        """Normalise: porta il picco al valore specificato."""
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            return samples / max_val * peak * np.max(samples)
        return samples

    @staticmethod
    def paulstretch(samples: np.ndarray, stretch_factor: float) -> np.ndarray:
        """Paulstretch: time stretching usando FFT (semplificato)."""
        if stretch_factor <= 1:
            return samples
        n = len(samples)
        window = np.hanning(256)
        step = int(256 // 2)
        # Semplice implementazione: duplica e blend
        out = np.copy(samples)
        for _ in range(int(stretch_factor)):
            out = np.concatenate([out, out[-256:] * 0.5 + out[:256] * 0.5])
        if len(out) > n:
            out = out[:n]
        else:
            out = np.pad(out, (0, n - len(out)), constant_values=0)
        return out

    @staticmethod
    def phaser(samples: np.ndarray, depth: int = 10, rate: float = 0.1) -> np.ndarray:
        out = np.copy(samples)
        if depth > 0:
            phase = np.linspace(0, 2*np.pi, len(samples))
            modulation = depth * np.sin(phase * rate)
            for i in range(len(samples) - depth):
                shift = int(modulation[i])
                if shift > 0 and i+shift < len(samples):
                    out[i] = samples[i+shift] * 0.5 + samples[i] * 0.5
        return out

    @staticmethod
    def reverse(samples: np.ndarray, chunk_size: int = None) -> np.ndarray:
        if chunk_size is None or chunk_size >= len(samples):
            return samples[::-1]
        out = np.copy(samples)
        for i in range(0, len(samples) - chunk_size + 1, chunk_size):
            out[i:i+chunk_size] = samples[i:i+chunk_size][::-1]
        return out

    @staticmethod
    def reverb(samples: np.ndarray, decay: float = 0.5, delay: int = 100) -> np.ndarray:
        out = np.copy(samples)
        if delay > 0 and delay < len(samples):
            reverb = np.zeros_like(samples)
            reverb[delay:] = samples[:-delay] * decay
            out += reverb
            for _ in range(3):
                reverb = np.roll(reverb, delay) * decay
                out += reverb
        return out

    @staticmethod
    def sliding_stretch(samples: np.ndarray, start_factor: float, end_factor: float) -> np.ndarray:
        """Sliding Stretch: cambio velocità variabile nel tempo."""
        if start_factor <= 0 or end_factor <= 0:
            return samples
        out = np.copy(samples)
        factors = np.linspace(start_factor, end_factor, len(samples))
        # Applica cambio velocità graduale
        for i in range(1, len(samples)):
            step = int(factors[i] * 2)
            if step > 0 and i+step < len(samples):
                out[i] = samples[i+step]
        return out

    @staticmethod
    def wahwah(samples: np.ndarray, depth: int = 10, rate: float = 0.2) -> np.ndarray:
        """Wah Wah: filtro passa-banda modulato."""
        out = np.copy(samples)
        if depth > 0:
            phase = np.linspace(0, 2*np.pi, len(samples))
            freq = depth * (0.5 + 0.5 * np.sin(phase * rate))
            # Applica filtro passa-banda
            for i in range(len(samples)):
                if i > 1:
                    out[i] = samples[i] * (0.5 + 0.5 * freq[i])
        return out

    @staticmethod
    def adjustable_fade_in(samples: np.ndarray, fade_len: int, curve_power: float = 1.0) -> np.ndarray:
        """Adjustable Fade In: fade con curva regolabile."""
        out = np.copy(samples)
        if fade_len > 0:
            fade = np.linspace(0, 1, fade_len) ** curve_power
            out[:fade_len] *= fade
        return out

    @staticmethod
    def delay_bmp(samples: np.ndarray, delay: int, feedback: float = 0.3) -> np.ndarray:
        """Delay specifico per BMP (con feedback)."""
        out = np.copy(samples)
        if delay > 0 and delay < len(samples):
            delayed = np.zeros_like(samples)
            delayed[delay:] = samples[:-delay] * feedback
            out += delayed
            for _ in range(2):
                delayed = np.roll(delayed, delay) * feedback
                out += delayed
        return out

# ======================================================================
# 3. MOTORE DI GLITCH
# ======================================================================

class BMPGlitcher:
    FORMAT_FOLDER_NAMES = {
        '8bit': '8-bit PCM',
        '16bit': '16-bit PCM',
        '24bit': '24-bit PCM',
        '32bit': '32-bit PCM',
        '32bit_float': '32-bit Float',
        '64bit_float': '64-bit Float',
        'ulaw': 'U-Law',
        'alaw': 'A-Law',
    }

    # Tutti gli effetti Audacity (22)
    EFFECT_NAMES = [
        'Amplify', 'BassTreble', 'ChangePitch', 'ChangeSpeed', 'ChangeTempo',
        'ClickRemoval', 'Distortion', 'Echo', 'FadeInOut', 'FilterCurve',
        'GraphicEQ', 'Invert', 'LoudnessNormalisation', 'Normalise', 'Paulstretch',
        'Phaser', 'Reverse', 'Reverb', 'SlidingStretch', 'WahWah',
        'AdjustableFadeIn', 'Delay'
    ]

    # Livelli per ogni effetto (5 livelli)
    EFFECT_LEVELS = {
        'Amplify': [0.5, 1.5, 2.0, 3.0, 5.0],
        'BassTreble': [(2.0, 2.0), (5.0, 5.0), (8.0, 8.0), (12.0, 12.0), (20.0, 20.0)],
        'ChangePitch': [0.5, 0.7, 0.9, 1.1, 1.3],
        'ChangeSpeed': [0.3, 0.5, 0.7, 1.3, 1.7],
        'ChangeTempo': [0.3, 0.5, 0.7, 1.3, 1.7],
        'ClickRemoval': [0.05, 0.1, 0.2, 0.4, 0.8],
        'Distortion': [1.0, 2.0, 4.0, 8.0, 15.0],
        'Echo': [(0.05, 0.3), (0.1, 0.5), (0.15, 0.7), (0.2, 0.9), (0.3, 0.6)],
        'FadeInOut': [(0.05, 0.05), (0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.5, 0.5)],
        'FilterCurve': [0.2, 0.5, 1.0, 2.0, 4.0],
        'GraphicEQ': [
            [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            [0.8, 0.8, 0.8, 0.8, 0.8, 1.2, 1.2, 1.2, 1.2, 1.2],
            [0.5, 0.7, 1.0, 1.5, 2.0, 2.0, 1.5, 1.0, 0.7, 0.5],
            [2.0, 1.5, 1.0, 0.7, 0.5, 0.5, 0.7, 1.0, 1.5, 2.0],
            [0.1, 0.2, 0.5, 1.0, 2.0, 2.0, 1.0, 0.5, 0.2, 0.1]
        ],
        'Invert': [1.0],  # Solo un livello
        'LoudnessNormalisation': [-20.0, -15.0, -10.0, -5.0, 0.0],
        'Normalise': [0.5, 0.7, 0.8, 0.9, 0.95],
        'Paulstretch': [1.5, 2.0, 3.0, 5.0, 10.0],
        'Phaser': [(5, 0.05), (10, 0.1), (15, 0.2), (20, 0.1), (30, 0.05)],
        'Reverse': [None, 128, 256, 512, 1024],
        'Reverb': [(0.3, 50), (0.5, 100), (0.7, 150), (0.9, 200), (0.5, 300)],
        'SlidingStretch': [(0.5, 1.5), (0.3, 2.0), (1.5, 0.5), (2.0, 0.3), (0.5, 0.5)],
        'WahWah': [(5, 0.1), (10, 0.2), (15, 0.3), (20, 0.1), (30, 0.2)],
        'AdjustableFadeIn': [(0.1, 0.5), (0.2, 1.0), (0.3, 2.0), (0.5, 3.0), (0.7, 4.0)],
        'Delay': [(0.1, 0.3), (0.15, 0.4), (0.2, 0.5), (0.25, 0.6), (0.3, 0.8)]
    }

    def __init__(self, input_path: Path, output_base: Path, all_bmp_files: List[Path],
                 assigned_effects: List[str] = None, preserve_contrast: bool = False):
        self.input_path = input_path
        self.output_base = output_base
        self.base_name = input_path.stem
        self.all_bmp_files = [p for p in all_bmp_files if p != input_path]
        self.assigned_effects = assigned_effects or self.EFFECT_NAMES
        self.preserve_contrast = preserve_contrast

        with open(input_path, 'rb') as f:
            self.raw_data = f.read()

        if self.raw_data[:2] != b'BM':
            print(f"⚠️  {input_path.name} non è un BMP valido.")
            self.is_valid = False
            return

        self.is_valid = True
        self.data_offset = struct.unpack('<I', self.raw_data[10:14])[0]
        self.header = self.raw_data[:self.data_offset]
        self.pixel_data = self.raw_data[self.data_offset:]
        self.original_len = len(self.pixel_data)

        # Calcola media e std originali per normalizzazione
        if self.preserve_contrast:
            samples = np.frombuffer(self.pixel_data, dtype=np.uint8).astype(np.float32)
            self.original_mean = np.mean(samples)
            self.original_std = np.std(samples)
            if self.original_std == 0:
                self.original_std = 1.0

    def save_bmp(self, pixel_data: bytes, folder: Path, filename: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{filename}.bmp"
        with open(path, 'wb') as f:
            f.write(self.header)
            f.write(pixel_data)
        return path

    def apply_effect_and_save(self, effect_func: Callable, fmt: str, folder: Path,
                              suffix: str, effect_name: str, params: Dict) -> Tuple[Path, Dict]:
        samples = AudioInterpreter.to_samples(self.pixel_data, fmt)
        modified = effect_func(samples)
        if self.preserve_contrast:
            new_bytes = AudioInterpreter.from_samples(modified, fmt, self.original_len,
                                                       self.original_mean, self.original_std)
        else:
            new_bytes = AudioInterpreter.from_samples(modified, fmt, self.original_len)
        fname = f"{self.base_name}_{fmt}_{effect_name}_{suffix}"
        path = self.save_bmp(new_bytes, folder, fname)
        info = {'effect': effect_name, 'format': fmt, 'params': params}
        return path, info

    def run_all(self):
        if not self.is_valid:
            return

        print(f"\n📷 Elaborazione: {self.input_path.name}")
        print(f"   Effetti assegnati: {len(self.assigned_effects)}")
        base_folder = self.output_base / self.base_name
        base_folder.mkdir(parents=True, exist_ok=True)

        for fmt_key, fmt_folder_name in self.FORMAT_FOLDER_NAMES.items():
            fmt_folder = base_folder / fmt_folder_name
            fmt_folder.mkdir(parents=True, exist_ok=True)
            format_readme_lines = []

            for effect_name in self.assigned_effects:
                effect_folder = fmt_folder / effect_name
                effect_folder.mkdir(parents=True, exist_ok=True)

                full_folder = effect_folder / "Full"
                full_folder.mkdir(parents=True, exist_ok=True)

                header_excluded_folder = effect_folder / "HeaderExcluded"
                header_excluded_folder.mkdir(parents=True, exist_ok=True)

                random_folder = effect_folder / "Random"
                random_folder.mkdir(parents=True, exist_ok=True)

                levels = self.EFFECT_LEVELS.get(effect_name, [1.0])

                # Genera Full e HeaderExcluded
                for idx, level_params in enumerate(levels):
                    effect_func = self._build_effect_func(effect_name, level_params)
                    params = self._build_params(effect_name, level_params)
                    suffix = f"level_{idx:02d}"
                    path, info = self.apply_effect_and_save(effect_func, fmt_key, full_folder,
                                                            suffix, effect_name, params)
                    desc = f"{path.name}: {effect_name} (Full) {self._params_to_desc(params)}"
                    format_readme_lines.append(desc)

                    path, info = self.apply_effect_and_save(effect_func, fmt_key, header_excluded_folder,
                                                            f"headerOnly_{suffix}", effect_name, params)
                    desc = f"{path.name}: {effect_name} (HeaderExcluded) {self._params_to_desc(params)}"
                    format_readme_lines.append(desc)

                # Genera Random (20 varianti su sezioni casuali)
                for i in range(20):
                    intensity = random.uniform(0.3, 2.0)
                    num_sections = random.randint(1, 5)
                    effect_type_lower = effect_name.lower()
                    def random_effect(s, etype=effect_type_lower, intensity=intensity, num=num_sections):
                        return self._random_section_effect(s, etype, intensity, num)
                    params = {'intensity': intensity, 'sections': num_sections}
                    suffix = f"random_{i:02d}"
                    path, info = self.apply_effect_and_save(random_effect, fmt_key, random_folder,
                                                            suffix, effect_name, params)
                    desc = f"{path.name}: {effect_name} (Random, sezioni {num_sections}, intensità {intensity:.2f})"
                    format_readme_lines.append(desc)

                # README per effetto
                readme_path = effect_folder / "README.txt"
                with open(readme_path, 'w', encoding='utf-8') as rf:
                    rf.write(f"Effetto: {effect_name}\n")
                    rf.write(f"Formato: {fmt_folder_name}\n")
                    rf.write(f"Immagine: {self.input_path.name}\n")
                    rf.write("-" * 60 + "\n\n")
                    rf.write("--- FULL ---\n")
                    for f in sorted(full_folder.glob("*.bmp")):
                        match = [line for line in format_readme_lines if f.name in line]
                        rf.write(f"  {match[0] if match else f.name}\n")
                    rf.write("\n--- HEADEREXCLUDED ---\n")
                    for f in sorted(header_excluded_folder.glob("*.bmp")):
                        match = [line for line in format_readme_lines if f.name in line]
                        rf.write(f"  {match[0] if match else f.name}\n")
                    rf.write("\n--- RANDOM ---\n")
                    for f in sorted(random_folder.glob("*.bmp")):
                        match = [line for line in format_readme_lines if f.name in line]
                        rf.write(f"  {match[0] if match else f.name}\n")

            # README riassuntivo formato
            summary_readme = fmt_folder / "README_COMPLETO.txt"
            with open(summary_readme, 'w', encoding='utf-8') as sf:
                sf.write(f"Formato: {fmt_folder_name}\n")
                sf.write(f"Immagine: {self.input_path.name}\n")
                sf.write("=" * 60 + "\n")
                sf.write(f"Totale file generati: {len(format_readme_lines)}\n\n")
                sf.write("\n".join(format_readme_lines))

        print(f"   ✅ Generazione completata per {self.base_name}")

    def _random_section_effect(self, samples: np.ndarray, effect_type: str,
                               intensity: float, num_sections: int = 1) -> np.ndarray:
        out = np.copy(samples)
        seg_len = len(samples)
        section_size = int(seg_len * random.uniform(0.1, 0.4))
        section_size = min(section_size, seg_len // 2)
        if section_size < 500:
            section_size = 500
            if section_size > seg_len // 2:
                section_size = seg_len // 2

        for _ in range(num_sections):
            start = random.randint(0, seg_len - section_size - 1)
            end = start + section_size
            section = out[start:end]

            if effect_type == 'amplify':
                gain = random.uniform(0.1, 5.0) * intensity
                out[start:end] = Effects.amplify(section, gain)
            elif effect_type == 'distortion':
                drive = random.uniform(1.0, 10.0) * intensity
                out[start:end] = Effects.distortion(section, drive)
            elif effect_type == 'echo':
                delay = int(section_size * random.uniform(0.05, 0.2))
                decay = random.uniform(0.3, 0.8) * intensity
                out[start:end] = Effects.echo(section, delay, decay)
            elif effect_type == 'reverse':
                out[start:end] = section[::-1]
            elif effect_type == 'phaser':
                depth = int(random.uniform(5, 30) * intensity)
                rate = random.uniform(0.05, 0.5) * intensity
                out[start:end] = Effects.phaser(section, depth, rate)
            elif effect_type == 'reverb':
                decay = random.uniform(0.2, 0.8) * intensity
                delay = int(section_size * random.uniform(0.05, 0.15))
                out[start:end] = Effects.reverb(section, decay, delay)
            elif effect_type == 'filtercurve':
                strength = random.uniform(0.2, 4.0) * intensity
                out[start:end] = Effects.filter_curve_random(section, strength)
            elif effect_type == 'wahwah':
                depth = int(random.uniform(5, 30) * intensity)
                rate = random.uniform(0.05, 0.5) * intensity
                out[start:end] = Effects.wahwah(section, depth, rate)
            elif effect_type == 'delay':
                delay = int(section_size * random.uniform(0.1, 0.4))
                feedback = random.uniform(0.0, 0.5) * intensity
                out[start:end] = Effects.delay_bmp(section, delay, feedback)
            elif effect_type == 'normalise':
                peak = random.uniform(0.3, 0.95) * intensity
                out[start:end] = Effects.normalise(section, peak)
            elif effect_type == 'invert':
                out[start:end] = -section
            elif effect_type == 'bass_treble':
                bass = random.uniform(1.0, 20.0) * intensity
                treble = random.uniform(1.0, 20.0) * intensity
                out[start:end] = Effects.bass_treble(section, bass, treble)
            elif effect_type == 'changepitch':
                factor = random.uniform(0.5, 2.0) * intensity
                out[start:end] = Effects.change_pitch(section, factor)
            elif effect_type == 'changespeed':
                factor = random.uniform(0.5, 2.0) * intensity
                out[start:end] = Effects.change_speed(section, factor)
            elif effect_type == 'changetempo':
                factor = -random.uniform(0.3, 2.0) * intensity
                out[start:end] = Effects.change_tempo(section, factor)
            elif effect_type == 'fadeinout':
                fade_len = int(section_size * random.uniform(0.05, 0.3))
                out[start:end] = Effects.fade_in_out(section, fade_len, fade_len)
            elif effect_type == 'adjustablefadein':
                fade_len = int(section_size * random.uniform(0.1, 0.5))
                power = random.uniform(0.5, 4.0) * intensity
                out[start:end] = Effects.adjustable_fade_in(section, fade_len, power)
            elif effect_type == 'paulstretch':
                factor = random.uniform(1.5, 10.0) * intensity
                out[start:end] = Effects.paulstretch(section, factor)
            elif effect_type == 'slidingstretch':
                start_f = random.uniform(0.3, 1.5)
                end_f = random.uniform(0.3, 1.5)
                out[start:end] = Effects.sliding_stretch(section, start_f, end_f)
            elif effect_type == 'clickremoval':
                threshold = random.uniform(0.05, 0.5) * intensity
                out[start:end] = Effects.click_removal(section, threshold)
            elif effect_type == 'graphiceq':
                bands = [random.uniform(0.1, 2.0) for _ in range(10)]
                out[start:end] = Effects.graphic_eq(section, bands)
            elif effect_type == 'loudnessnormalisation':
                target = random.uniform(-30.0, -5.0) * intensity
                out[start:end] = Effects.loudness_normalisation(section, target)

        return out

    def _build_effect_func(self, effect_name: str, params):
        if effect_name == 'Amplify':
            gain = params
            return lambda s: Effects.amplify(s, gain)
        elif effect_name == 'BassTreble':
            bass, treble = params
            return lambda s: Effects.bass_treble(s, bass, treble)
        elif effect_name == 'ChangePitch':
            factor = params
            return lambda s: Effects.change_pitch(s, factor)
        elif effect_name == 'ChangeSpeed':
            factor = params
            return lambda s: Effects.change_speed(s, factor)
        elif effect_name == 'ChangeTempo':
            factor = params
            return lambda s: Effects.change_tempo(s, factor)
        elif effect_name == 'ClickRemoval':
            threshold = params
            return lambda s: Effects.click_removal(s, threshold)
        elif effect_name == 'Distortion':
            drive = params
            return lambda s: Effects.distortion(s, drive)
        elif effect_name == 'Echo':
            delay_pct, decay = params
            return lambda s: Effects.echo(s, int(len(s) * delay_pct), decay)
        elif effect_name == 'FadeInOut':
            fade_in_pct, fade_out_pct = params
            return lambda s: Effects.fade_in_out(s, int(len(s) * fade_in_pct), int(len(s) * fade_out_pct))
        elif effect_name == 'FilterCurve':
            strength = params
            return lambda s: Effects.filter_curve_random(s, strength)
        elif effect_name == 'GraphicEQ':
            bands = params
            return lambda s: Effects.graphic_eq(s, bands)
        elif effect_name == 'Invert':
            return lambda s: -s
        elif effect_name == 'LoudnessNormalisation':
            target = params
            return lambda s: Effects.loudness_normalisation(s, target)
        elif effect_name == 'Normalise':
            peak = params
            return lambda s: Effects.normalise(s, peak)
        elif effect_name == 'Paulstretch':
            factor = params
            return lambda s: Effects.paulstretch(s, factor)
        elif effect_name == 'Phaser':
            depth, rate = params
            return lambda s: Effects.phaser(s, depth, rate)
        elif effect_name == 'Reverse':
            chunk = params
            return lambda s: Effects.reverse(s, chunk)
        elif effect_name == 'Reverb':
            decay, delay = params
            return lambda s: Effects.reverb(s, decay, delay)
        elif effect_name == 'SlidingStretch':
            start_f, end_f = params
            return lambda s: Effects.sliding_stretch(s, start_f, end_f)
        elif effect_name == 'WahWah':
            depth, rate = params
            return lambda s: Effects.wahwah(s, depth, rate)
        elif effect_name == 'AdjustableFadeIn':
            fade_pct, power = params
            return lambda s: Effects.adjustable_fade_in(s, int(len(s) * fade_pct), power)
        elif effect_name == 'Delay':
            delay_pct, feedback = params
            return lambda s: Effects.delay_bmp(s, int(len(s) * delay_pct), feedback)
        else:
            return lambda s: s

    def _build_params(self, effect_name: str, params):
        if effect_name == 'Amplify':
            return {'gain': params}
        elif effect_name == 'BassTreble':
            return {'bass': params[0], 'treble': params[1]}
        elif effect_name in ['ChangePitch', 'ChangeSpeed', 'ChangeTempo']:
            return {'factor': params}
        elif effect_name == 'ClickRemoval':
            return {'threshold': params}
        elif effect_name == 'Distortion':
            return {'drive': params}
        elif effect_name == 'Echo':
            return {'delay_pct': params[0], 'decay': params[1]}
        elif effect_name == 'FadeInOut':
            return {'fade_in': params[0], 'fade_out': params[1]}
        elif effect_name == 'FilterCurve':
            return {'strength': params}
        elif effect_name == 'GraphicEQ':
            return {'bands': params}
        elif effect_name == 'Invert':
            return {}
        elif effect_name == 'LoudnessNormalisation':
            return {'target': params}
        elif effect_name == 'Normalise':
            return {'peak': params}
        elif effect_name == 'Paulstretch':
            return {'factor': params}
        elif effect_name == 'Phaser':
            return {'depth': params[0], 'rate': params[1]}
        elif effect_name == 'Reverse':
            return {'chunk': params}
        elif effect_name == 'Reverb':
            return {'decay': params[0], 'delay': params[1]}
        elif effect_name == 'SlidingStretch':
            return {'start_factor': params[0], 'end_factor': params[1]}
        elif effect_name == 'WahWah':
            return {'depth': params[0], 'rate': params[1]}
        elif effect_name == 'AdjustableFadeIn':
            return {'fade_pct': params[0], 'power': params[1]}
        elif effect_name == 'Delay':
            return {'delay_pct': params[0], 'feedback': params[1]}
        else:
            return {}

    def _params_to_desc(self, params: Dict) -> str:
        return ", ".join(f"{k}={v}" for k, v in params.items())

# ======================================================================
# 4. MAIN
# ======================================================================

def distribute_effects(bmp_files: List[Path], output_dir: Path, preserve_contrast: bool = False):
    all_effects = BMPGlitcher.EFFECT_NAMES
    num_files = len(bmp_files)

    if num_files == 1:
        for bmp_path in bmp_files:
            glitcher = BMPGlitcher(bmp_path, output_dir, bmp_files, all_effects, preserve_contrast)
            glitcher.run_all()
        return

    effects_per_file = max(2, len(all_effects) // num_files)
    effects_per_file = min(effects_per_file, len(all_effects))

    shuffled_effects = all_effects.copy()
    random.shuffle(shuffled_effects)

    for idx, bmp_path in enumerate(bmp_files):
        start_idx = idx * effects_per_file
        end_idx = start_idx + effects_per_file
        if end_idx > len(shuffled_effects):
            assigned = shuffled_effects[start_idx:] + shuffled_effects[:end_idx - len(shuffled_effects)]
        else:
            assigned = shuffled_effects[start_idx:end_idx]
        if not assigned:
            assigned = [random.choice(all_effects)]
        glitcher = BMPGlitcher(bmp_path, output_dir, bmp_files, assigned, preserve_contrast)
        glitcher.run_all()

def main():
    parser = argparse.ArgumentParser(
        description="BMP Glitcher - TUTTI GLI EFFETTI AUDACITY"
    )
    parser.add_argument('-i', '--input-dir', default='.',
                        help='Directory contenente i file BMP (default: corrente)')
    parser.add_argument('-o', '--output-dir', default='bmp_glitch_output',
                        help='Directory di output (default: bmp_glitch_output)')
    parser.add_argument('--no-distribute', action='store_true',
                        help='Disabilita la distribuzione (tutti gli effetti su tutti i file)')
    parser.add_argument('--preserve-contrast', action='store_true',
                        help='Preserva il contrasto originale (evita sbiadimento)')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"❌ Directory input non trovata: {input_dir}")
        sys.exit(1)

    bmp_files = list(input_dir.glob("*.bmp")) + list(input_dir.glob("*.BMP"))
    if not bmp_files:
        print(f"❌ Nessun file BMP trovato in {input_dir}")
        sys.exit(1)

    print(f"🔍 Trovati {len(bmp_files)} file BMP")
    if args.preserve_contrast:
        print("⚡ Modalità: PRESERVA CONTRASTO (immagini meno sbiadite)")
    else:
        print("⚡ Modalità: STANDARD (come Audacity, potrebbe sbiadire)")

    if args.no_distribute:
        print("⚡ Modalità: TUTTI gli effetti su OGNI file")
        for bmp_path in bmp_files:
            glitcher = BMPGlitcher(bmp_path, output_dir, bmp_files,
                                   BMPGlitcher.EFFECT_NAMES, args.preserve_contrast)
            glitcher.run_all()
    else:
        print("⚡ Modalità: Distribuzione effetti tra i file")
        distribute_effects(bmp_files, output_dir, args.preserve_contrast)

    print("\n" + "=" * 80)
    print("✅ COMPLETATO!")
    print(f"📁 Risultati in: {output_dir}")
    print("=" * 80)

if __name__ == "__main__":
    main()
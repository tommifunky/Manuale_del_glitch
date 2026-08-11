# Manuale del glitch - Repository

Repository ufficiale del progetto di tesi *L'errore come strumento*, Bachelor of Arts in Comunicazione visiva, SUPSI Mendrisio (2025-2026).

**Studente:** Tommaso Stanga  
**Relatore:** Andreas Gysin

---

## Contenuto della repository
Manuale_del_glitch/
├── dataset/ # Immagini, video, modelli e font utilizzati
├── script/ # Script Python per la manipolazione dei file
│ ├── bmp/ # Script per il formato BMP
│ ├── jpeg/ # Script per il formato JPEG
│ └── gif/ # Script per il formato GIF
├── manuale/ # File sorgente del manuale
│ ├── dossier.pdf # Tra caso, deviazione e controllo
│ └── manuale.pdf # Manuale del glitch
├── schede/ # Schede singole in PDF (estrai e stampa)
└── README.md

text

---

## Script disponibili

### BMP

| Script | Descrizione |
|--------|-------------|
| `prova.py` | Primi esperimenti: overlay, splicing, reverse, delay |
| `swap_header.py` | Scambia header tra immagini (anche ruotate) |
| `soloheader.py` | Modifica solo larghezza e altezza del BMP |
| `x_bmp_hexfiend.py` | Modifica pixel (sostituzione, eliminazione, inserimento) e header |
| `a_py.py` | Databending con SoX (eco, riverbero, phaser, distorsione) |
| `echo.py` | Effetto eco (tutti i parametri di Audacity) |
| `phaser.py` | Effetto phaser (tutti i parametri di Audacity) |
| `reverbero.py` | Effetto riverbero (tutti i parametri di Audacity) |
| `distorsioni.py` | Distorsione, phaser, tremolo, wahwah, vocoder |
| `amp_norm.py` | Amplifica e normalizza (tutti i parametri di Audacity) |

### JPEG

| Script | Descrizione |
|--------|-------------|
| `x_sos.py` | Modifica segmento SOS (dati compressi) |
| `x_sof.py` | Modifica segmento SOF (dimensioni, componenti, precisione) |
| `x_dqt.py` | Modifica tabelle di quantizzazione DQT |
| `x_dht.py` | Modifica tabelle Huffman DHT |

### GIF

| Script | Descrizione |
|--------|-------------|
| `x_gif.py` | Modifica Global Color Table e Image Data |

---

## Installazione

### Dipendenze Python

```bash
pip install numpy pillow
SoX (per il databending)
macOS:

bash
brew install sox
Linux:

bash
sudo apt install sox
Utilizzo
Script Python
bash
# Esempio: BMP glitcher con SoX
python3 a_py.py -i ./input -o ./output

# Esempio: Modifica header BMP
python3 soloheader.py -i input.bmp -o output/ -n 10

# Esempio: Modifica SOS JPEG
python3 x_sos.py -i ./input -o ./output
Opzioni comuni
Opzione	Descrizione
-i, --input-dir	Directory contenente i file da elaborare
-o, --output-dir	Directory di output
-n, --random	Numero di varianti casuali
Per i dettagli delle opzioni specifiche di ogni script:

bash
python3 nome_script.py --help
Dataset
Le immagini, sequenze video, modelli 3D e font utilizzati sono nella cartella dataset/:

Immagini raster: classic test images (USC-SIPI Image Database)

Sequenze video: Akiyo, Coastguard, Foreman, Stefan

Modelli 3D: Bunny, Armadillo, Utah Teapot, Suzanne

Caratteri: Arial, Times New Roman

Licenza
Questo progetto è rilasciato sotto licenza Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

© Tommaso Stanga, 2026

Collegamenti
Repository GitHub

SUPSI Mendrisio

Contatti
Tommaso Stanga - [inserisci email]

Questo README è provvisorio e verrà aggiornato con la consegna finale.

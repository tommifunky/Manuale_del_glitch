# Manuale del glitch — Repository

Repository ufficiale del progetto di tesi *L'errore come strumento*,
Bachelor of Arts in Comunicazione visiva, SUPSI Mendrisio (2025–2026).

Studente: Tommaso Stanga<br>
Relatore: Andreas Gysin

---

## Contenuto della repository

```text
Manuale_del_glitch/
├── dataset/       # Immagini, video, modelli 3D e font utilizzati
├── script/        # Script per la manipolazione dei file
├── schede/        # Schede delle procedure in PDF
├── procedure/     # Procedure e documentazione delle tecniche
└── README.md
```

---

## Script disponibili

Gli script contenuti nella cartella `script/` permettono di sperimentare diverse tecniche di manipolazione e databending.

### BMP

| Script              | Descrizione                                                      |
| ------------------- | ---------------------------------------------------------------- |
| `prova.py`          | Primi esperimenti: overlay, splicing, reverse, delay             |
| `swap_header.py`    | Scambia header tra immagini, anche ruotate                       |
| `soloheader.py`     | Modifica larghezza e altezza del BMP                             |
| `x_bmp_hexfiend.py` | Modifica i dati dei pixel e l'header tramite operazioni sui byte |
| `a_py.py`           | Databending con SoX: eco, riverbero, phaser e distorsione        |
| `echo.py`           | Applica l'effetto eco                                            |
| `phaser.py`         | Applica l'effetto phaser                                         |
| `reverbero.py`      | Applica l'effetto riverbero                                      |
| `distorsioni.py`    | Applica distorsione, phaser, tremolo, wahwah e vocoder           |
| `amp_norm.py`       | Amplifica e normalizza il segnale                                |

### JPEG

| Script     | Descrizione                                                   |
| ---------- | ------------------------------------------------------------- |
| `x_sos.py` | Modifica il segmento SOS e i dati compressi                   |
| `x_sof.py` | Modifica il segmento SOF: dimensioni, componenti e precisione |
| `x_dqt.py` | Modifica le tabelle di quantizzazione DQT                     |
| `x_dht.py` | Modifica le tabelle Huffman DHT                               |

### GIF

| Script     | Descrizione                                     |
| ---------- | ----------------------------------------------- |
| `x_gif.py` | Modifica la Global Color Table e gli Image Data |

---

## Installazione

### Dipendenze Python

```bash
pip install numpy pillow
```

### SoX

Gli script che utilizzano il databending audio richiedono SoX.

macOS:

```bash
brew install sox
```

Linux:

```bash
sudo apt install sox
```

---

## Utilizzo

Gli script possono essere eseguiti da terminale.

Esempio: databending BMP con SoX:

```bash
python3 a_py.py -i ./input -o ./output
```

Esempio: modifica dell'header BMP:

```bash
python3 soloheader.py -i input.bmp -o output/ -n 10
```

Esempio: modifica del segmento SOS JPEG:

```bash
python3 x_sos.py -i ./input -o ./output
```

Per visualizzare le opzioni disponibili per ciascuno script:

```bash
python3 nome_script.py --help
```

---

## Dataset

La cartella `dataset/` contiene i file utilizzati per gli esperimenti del progetto.

* Immagini raster
* Sequenze video
* Modelli 3D
* Font

Tra i file utilizzati:

* Classic Test Images (USC-SIPI Image Database)
* Akiyo
* Coastguard
* Foreman
* Stefan
* Bunny
* Armadillo
* Utah Teapot
* Suzanne
* Arial
* Times New Roman

---

## Schede

La cartella `schede/` contiene le singole schede delle tecniche di glitch in formato PDF, pensate per essere consultate, estratte e stampate.

---

## Procedure

La cartella `procedure/` contiene la documentazione delle procedure utilizzate per la manipolazione dei diversi formati di file.

Le procedure descrivono i passaggi necessari per replicare gli esperimenti e ottenere i diversi risultati.

---

## Licenza

Questo progetto è rilasciato sotto licenza
Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

© Tommaso Stanga, 2026

---

## Collegamenti

* [Repository GitHub](https://github.com/tommifunky/Manuale_del_glitch/)
* [SUPSI Mendrisio](https://www.supsi.ch/mendrisio)

---

## Contatti

Tommaso Stanga — [inserisci email]

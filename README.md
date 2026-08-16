# Manuale del *glitch* digitale

Repository ufficiale del progetto di tesi *L'errore come strumento, Manuale del glitch digitale*,
Bachelor of Arts in Comunicazione visiva, SUPSI Mendrisio (2025–2026).

Studente: Tommaso Stanga  
Relatore: Andreas Gysin

---

## Contenuto della repository

```text
glitch/
├── dataset/                     # Immagini, video, modelli 3D e font utilizzati
│   ├── immagini/                # BMP, JPEG, GIF, TIFF
│   ├── immagini_in_movimento/   # Akiyo, Coastguard, Foreman, Stefan
│   ├── caratteri_tipografici/   # Arial.ttf, Times_New_Roman.ttf
│   └── modelli_tridimensionali/ # Bunny.obj, Armadillo.obj, Teapot.obj, Suzanne.obj
│
├── formati/                     # Schede tecniche dei formati digitali (PDF)
│   ├── BMP.pdf
│   ├── GIF.pdf
│   ├── JPEG.pdf
│   ├── OBJ.pdf
│   ├── TIFF.pdf
│   └── TTF.pdf
│
├── strumenti/                   # Schede degli strumenti utilizzati (PDF)
│   ├── Anteprima.pdf
│   ├── Audacity.pdf
│   ├── GIMP.pdf
│   ├── Hex_Fiend.pdf
│   └── TextEdit.pdf
│
├── procedure_generali/          # Procedure generali per l'uso degli strumenti (PDF)
│   ├── G1_Aprire_un_file_con_Hex_Fiend.pdf
│   ├── G2_Salvare_un_file_con_Hex_Fiend.pdf
│   ├── G3_Cercare_byte_con_Hex_Fiend.pdf
│   ├── G4_Raggiungere_un_offset_con_Hex_Fiend.pdf
│   ├── G5_Interpretare_valori_esadecimali_con_Hex_Fiend.pdf
│   ├── G6_Convertire_un_immagine_con_GIMP.pdf
│   ├── G7_Aprire_un_file_con_Audacity.pdf
│   ├── G8_Salvare_un_file_con_Audacity.pdf
│   ├── G9_Selezionare_i_dati_con_Audacity.pdf
│   ├── G10_Dividere_una_traccia_con_Audacity.pdf
│   ├── G11_Applicare_effetti_con_Audacity.pdf
│   ├── G12_Aprire_un_immagine_con_Anteprima.pdf
│   ├── G13_Duplicare_e_salvare_un_immagine_con_Anteprima.pdf
│   ├── G14_Aprire_un_file_con_TextEdit.pdf
│   ├── G15_Salvare_un_file_con_TextEdit.pdf
│   ├── G16_Cercare_elementi_con_TextEdit.pdf
│   ├── G17_Sostituire_valori_con_TextEdit.pdf
│   └── G18_Avviare_script_personalizzati.pdf
│
├── glitch_bmp/                  # Procedure per il glitch del formato BMP
│   ├── H1_Alterazione_delle_coordinate_spaziali/
│   │   ├── H1_Alterazione_delle_coordinate_spaziali.pdf
│   │   └── output/
│   ├── H2_Alterazione_della_profondità_cromatica/
│   ├── H3_Alterazione_dei_dati_pixel/
│   ├── H4_Databending_BMP/
│   ├── H5_Fusione_dei_dati_BMP/
│   └── H6_Scambio_header_BMP/
│
├── glitch_jpeg/                 # Procedure per il glitch del formato JPEG
│   ├── I1_Alterazione_del_segmento_SOS/
│   ├── I2_Alterazione_delle_dimensioni_SOF/
│   ├── I3_Alterazione_dei_componenti_colore_SOF/
│   ├── I4_Alterazione_del_segmento_DQT/
│   └── I5_Alterazione_del_segmento_DHT/
│
├── glitch_gif/                  # Procedure per il glitch del formato GIF
│   ├── K1_Alterazione_della_global_color_table/
│   └── K2_Alterazione_degli_image_data/
│
├── glitch_tiff/                 # Procedure per il glitch del formato TIFF
│   ├── L1_Alterazione_dei_dati_immagine/
│   ├── L2_Alterazione_delle_dimensioni_immagine/
│   └── L3_Databending_TIFF/
│
├── glitch_obj/                  # Procedure per il glitch del formato OBJ
│   ├── J1_Dislocazione_dei_vertici/
│   └── J2_Alterazione_delle_facce/
│
├── glitch_ttf/                  # Procedure per il glitch del formato TTF
│   ├── M1_Alterazione_della_struttura_TTF/
│   └── M2_Databending_tipografico/
│
├── script/                      # Script per automatizzare le alterazioni
│   ├── bmplab/
│   │   ├── N1_BMPlab.pdf
│   │   └── output/
│   ├── jpeglab/
│   │   ├── N2_JPEGlab.pdf
│   │   └── output/
│   ├── giflab/
│   │   ├── N3_GIFlab.pdf
│   │   └── output/
│   └── python_scripts/          # Script Python legacy
│
└── README.md
```

---

## Script disponibili

### BMPlab (Swift)

Script per la manipolazione dei file BMP tramite interfaccia grafica.

| File                        | Descrizione                                         |
| --------------------------- | --------------------------------------------------- |
| `script/bmplab/bmplab.swift` | Interfaccia per modificare pixel, profondità colore, dimensioni e header del BMP |

### JPEGlab (Swift)

Script per la manipolazione dei file JPEG tramite interfaccia grafica.

| File                         | Descrizione                                                     |
| ---------------------------- | --------------------------------------------------------------- |
| `script/jpeglab/jpeglab.swift` | Interfaccia per modificare SOS, SOF, DQT, DHT e header del JPEG |

### GIFlab (Swift)

Script per la manipolazione dei file GIF tramite interfaccia grafica.

| File                         | Descrizione                                                       |
| ---------------------------- | ----------------------------------------------------------------- |
| `script/giflab/giflab.swift`  | Interfaccia per modificare Global Color Table, Local Color Table e Image Data |

### Script Python (legacy)

Script Python per la manipolazione da terminale.

**BMP**

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

**JPEG**

| Script     | Descrizione                                                   |
| ---------- | ------------------------------------------------------------- |
| `x_sos.py` | Modifica il segmento SOS e i dati compressi                   |
| `x_sof.py` | Modifica il segmento SOF: dimensioni, componenti e precisione |
| `x_dqt.py` | Modifica le tabelle di quantizzazione DQT                     |
| `x_dht.py` | Modifica le tabelle Huffman DHT                               |

**GIF**

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

### Script Swift

Gli script Swift devono essere compilati prima dell'uso:

```bash
swiftc bmplab.swift -o bmplab
./bmplab percorso/file.bmp
```

### Script Python

Gli script Python possono essere eseguiti da terminale.

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

Le cartelle `formati/` e `strumenti/` contengono le schede tecniche in formato PDF, pensate per essere consultate, estratte e stampate.

---

## Procedure

Le cartelle `glitch_*` contengono le procedure dettagliate per la manipolazione dei diversi formati di file.

Ogni procedura è corredata da una cartella `output/` con le immagini di esempio, numerate progressivamente per facilitare il confronto.

Le procedure descrivono i passaggi necessari per replicare gli esperimenti e ottenere i diversi risultati.

---

## Licenza

Questo progetto è rilasciato sotto licenza
Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

© Tommaso Stanga, 2026

---

## Contatti
[@tommifunky](https://www.instagram.com/tommifunky/)
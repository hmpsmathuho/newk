# Best Value Bet Analyzer

Sistem analisis untuk menemukan **best value bet** dari pertandingan sepak bola dengan menggabungkan 200+ market odds dan data tim eksternal (termasuk kondisi terkini tim yang paling berpengaruh terhadap pertandingan berikutnya).

- **Input:** file `.mhtml` (hasil simpan halaman bandar / situs odds)
- **Output:** daftar best value bet terurut berdasarkan nilai *edge* / *expected value*

---

## 1. Tujuan

Mengidentifikasi taruhan dengan **nilai positif (positive EV)** — yaitu kondisi di mana probabilitas riil suatu kejadian lebih tinggi daripada probabilitas implisit (*implied probability*) yang ditawarkan bandar lewat odds.

```
Value (Edge) = (Probabilitas Riil × Odds Desimal) − 1
```

Jika `Edge > 0`, taruhan dianggap *value bet*.

---

## 2. Arsitektur Sistem

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  Input MHTML │ ──▶ │  Parser & Extract │ ──▶ │  Odds Normalizer   │
└──────────────┘     └──────────────────┘     └────────────────────┘
                                                         │
                            ┌────────────────────────────┘
                            ▼
                   ┌──────────────────┐     ┌────────────────────┐
                   │ External Data API │ ──▶ │  Team Form Engine  │
                   └──────────────────┘     └────────────────────┘
                                                         │
                                                         ▼
                                            ┌────────────────────┐
                                            │  Probability Model  │
                                            └────────────────────┘
                                                         │
                                                         ▼
                                            ┌────────────────────┐
                                            │  Value Bet Ranker   │
                                            └────────────────────┘
                                                         │
                                                         ▼
                                            ┌────────────────────┐
                                            │   Output: Best Bets │
                                            └────────────────────┘
```

---

## 3. Input: File MHTML

File `.mhtml` adalah arsip halaman web lengkap (HTML + resource) yang disimpan dari situs bandar/odds.

### Yang diekstrak dari MHTML
- Nama pertandingan (Home vs Away), liga, tanggal/jam kickoff.
- Daftar market (200+), contoh:
  - 1X2 (Match Result)
  - Over/Under (0.5 – 5.5)
  - Both Teams To Score (BTTS)
  - Asian Handicap
  - Correct Score
  - Double Chance, Draw No Bet
  - Half Time / Full Time, Corners, Cards, dll.
- Odds tiap selection beserta bandar penyedianya.

### Tahapan parsing
1. Decode container MIME `multipart/related` dari MHTML.
2. Ambil bagian HTML utama.
3. Parse DOM untuk menemukan tabel/blok market & odds.
4. Normalisasi nama market & selection ke skema internal yang konsisten.

---

## 4. Data Eksternal Tim

Data yang diambil dari sumber eksternal (API statistik / scraping) untuk menghitung probabilitas riil.

| Kategori | Data | Pengaruh |
|----------|------|----------|
| Form Terkini | 5–10 hasil terakhir (W/D/L) | Tinggi |
| Goal Stats | Rata-rata gol cetak/kebobolan, xG, xGA | Tinggi |
| Home/Away Split | Performa kandang vs tandang | Tinggi |
| Cedera & Suspensi | Pemain kunci absen | **Sangat Tinggi** |
| Head-to-Head | Riwayat pertemuan langsung | Sedang |
| Jadwal & Kelelahan | Jarak antar laga, kompetisi ganda | Sedang |
| Motivasi | Posisi klasemen, perebutan gelar/degradasi | Sedang–Tinggi |
| Cuaca/Lapangan | Kondisi non-teknis | Rendah–Sedang |

### Kondisi Terkini yang Paling Berpengaruh
Faktor dengan bobot tertinggi terhadap pertandingan **berikutnya**:
1. **Ketersediaan pemain kunci** (cedera/suspensi/rotasi).
2. **Momentum/form** beberapa laga terakhir (diberi pembobotan *recency* — laga terbaru bobot lebih besar).
3. **Konteks home/away** sesuai venue pertandingan yang dianalisis.
4. **Beban jadwal** (fatigue) dari laga sebelumnya.

---

## 5. Model Probabilitas

Menggabungkan beberapa pendekatan untuk estimasi probabilitas riil:

- **Poisson / Dixon-Coles** untuk distribusi gol → menurunkan probabilitas Over/Under, BTTS, Correct Score.
- **Elo / power rating** yang disesuaikan dengan form & home advantage → menurunkan probabilitas 1X2.
- **Penyesuaian (adjustment factor)** berbasis kondisi terkini tim (cedera, fatigue, motivasi).

```
P_riil(selection) = ModelDasar(selection) × AdjustmentFaktorTim
```

Lalu dibandingkan dengan implied probability:

```
ImpliedProb = 1 / OddsDesimal
Edge        = P_riil − ImpliedProb_tanpaMargin
```

> *Margin/overround* bandar dihilangkan dulu agar perbandingan adil.

---

## 6. Output: Best Value Bet

Hasil akhir berupa daftar terurut (ranked) berdasarkan edge / EV.

### Contoh format output
```
PERTANDINGAN: Arsenal vs Chelsea — 28 May 2026, 21:00
─────────────────────────────────────────────────────
RANK  MARKET           SELECTION     ODDS   P_RIIL  EDGE    EV     BANDAR
 1    Over/Under 2.5   Over          1.95   58.0%   +6.7%  +0.13   BandarA
 2    BTTS             Yes           1.80   60.5%   +5.0%  +0.09   BandarB
 3    Match Result     Home Win      2.10   52.0%   +4.2%  +0.09   BandarA
─────────────────────────────────────────────────────
CATATAN: Striker utama Chelsea cedera → goals against naik.
SARAN STAKE (Kelly 1/4): Bet #1 → 2.3% bankroll
```

### Field output
- `market`, `selection`, `odds`, `implied_prob`, `real_prob`
- `edge`, `expected_value`
- `bookmaker` (sumber odds terbaik)
- `confidence` (tingkat keyakinan model)
- `stake_suggestion` (opsional, Kelly Criterion / flat)
- `reasoning` (faktor utama yang mendorong nilai)

Format ekspor: **JSON**, **CSV**, dan tabel terminal.

---

## 7. Struktur Proyek

```
best-value-bet/
├── README.md
├── requirements.txt
├── config.yaml
├── data/
│   ├── input/            # file .mhtml
│   └── cache/            # cache data eksternal
├── src/
│   ├── parser/
│   │   ├── mhtml_parser.py
│   │   └── odds_extractor.py
│   ├── external/
│   │   ├── api_client.py
│   │   └── team_form.py
│   ├── model/
│   │   ├── poisson.py
│   │   ├── elo.py
│   │   └── adjustments.py
│   ├── value/
│   │   ├── edge_calculator.py
│   │   └── ranker.py
│   └── output/
│       └── exporter.py
├── tests/
└── main.py
```

---

## 8. Cara Pakai

```bash
# Instal dependensi
pip install -r requirements.txt

# Jalankan analisis
python main.py --input data/input/match.mhtml \
               --output results/best_bets.json \
               --min-edge 0.03 \
               --stake-method kelly
```

### Parameter penting
| Flag | Deskripsi | Default |
|------|-----------|---------|
| `--input` | Path file `.mhtml` | wajib |
| `--output` | Path file hasil | `stdout` |
| `--min-edge` | Edge minimum agar dianggap value | `0.02` |
| `--top` | Jumlah bet teratas ditampilkan | `10` |
| `--stake-method` | `kelly` / `flat` / `none` | `none` |

---

## 9. Konfigurasi (config.yaml)

```yaml
external_api:
  provider: "api-football"   # atau sumber lain
  api_key: "${API_KEY}"
  cache_ttl: 3600

model:
  recency_weight: 0.7        # bobot laga terbaru
  home_advantage: 0.25
  injury_impact: high

value:
  min_edge: 0.02
  remove_margin: true
  confidence_threshold: 0.6

staking:
  method: kelly
  kelly_fraction: 0.25       # quarter Kelly
  max_stake_pct: 0.05
```

---

## 10. Catatan & Disclaimer

- Model bersifat probabilistik; tidak ada jaminan hasil. *Value bet* meningkatkan ekspektasi jangka panjang, bukan memastikan kemenangan tiap taruhan.
- Kualitas output sangat bergantung pada **akurasi data eksternal** dan **kelengkapan parsing MHTML**.
- Selalu verifikasi kondisi terkini tim (lineup resmi biasanya rilis ~1 jam sebelum kickoff).
- Gunakan manajemen bankroll yang disiplin. Bertaruhlah secara bertanggung jawab.

"""Package existing evaluation records without editing or rescoring their values.

Requires openpyxl in the Python environment running this packaging script.
The original CSV files, not the Excel rendering, are the authoritative records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
JAKARTA = timezone(timedelta(hours=7))
ARCHIVE = "evaluation/archive/final_test_20261022"

# Source path, destination folder, workbook sheet. No metrics or reconciled labels.
RAW_TABLES = [
    (f"{ARCHIVE}/query_manifest_test_FROZEN.csv", "uji_akhir", "FINAL_KUERI"),
    (f"{ARCHIVE}/run_status.csv", "uji_akhir", "FINAL_STATUS"),
    (f"{ARCHIVE}/blind_judgment_pass1.csv", "uji_akhir", "FINAL_PASS1"),
    (f"{ARCHIVE}/blind_judgment_pass2.csv", "uji_akhir", "FINAL_PASS2"),
    (f"{ARCHIVE}/blind_mapping_PRIVATE.csv", "uji_akhir", "FINAL_MAPPING"),
    ("evaluation/manifests/query_manifest_validation_FROZEN.csv", "validasi_wlc", "VALID_KUERI"),
    ("evaluation/runs/wlc_validation/validation_run_status.csv", "validasi_wlc", "VALID_STATUS"),
    ("evaluation/runs/wlc_validation/pooled_candidates_PRIVATE.csv", "validasi_wlc", "VALID_KANDIDAT"),
    ("evaluation/runs/wlc_validation/wlc_runs_PRIVATE.csv", "validasi_wlc", "VALID_RUN_WLC"),
    ("evaluation/runs/wlc_validation/blind_judgment_pass1.csv", "validasi_wlc", "VALID_PASS1"),
    ("evaluation/runs/wlc_validation/blind_judgment_pass2.csv", "validasi_wlc", "VALID_PASS2"),
    ("evaluation/runs/wlc_validation/blind_mapping_PRIVATE.csv", "validasi_wlc", "VALID_MAPPING"),
    ("evaluation/query_manifest_pilot_FROZEN.csv", "pilot", "PILOT_KUERI"),
    ("evaluation/runs/pilot/run_status.csv", "pilot", "PILOT_STATUS"),
    ("evaluation/runs/pilot/blind_judgment_pass1.csv", "pilot", "PILOT_PASS1"),
    ("evaluation/runs/pilot/blind_judgment_pass2.csv", "pilot", "PILOT_PASS2"),
    ("evaluation/runs/pilot/blind_mapping_PRIVATE.csv", "pilot", "PILOT_MAPPING"),
]
REFERENCES = [
    f"{ARCHIVE}/python_version.txt",
    f"{ARCHIVE}/environment_freeze.txt",
    f"{ARCHIVE}/artifact_hashes.csv",
    f"{ARCHIVE}/query_manifest_test_FROZEN.csv.sha256",
    "evaluation/manifests/query_manifest_validation_FROZEN.csv.sha256",
    "evaluation/query_manifest_pilot_FROZEN.csv.sha256",
    "evaluation/manifests/wlc_selected_config_FROZEN.csv",
    "evaluation/manifests/wlc_selected_config_FROZEN.csv.sha256",
    "evaluation/manifests/source_sampling_record.json",
    "evaluation/runs/wlc_validation/wlc_validation_record.json",
    "evaluation/GRADING_RUBRIC.md",
    "evaluation/runs/pilot/rubic_grading.txt",
]
TEMPLATE = "evaluation/human_evaluation_template.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_table(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"Missing CSV header: {path}")
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueError(f"Inconsistent CSV columns: {path}")
    if any(len(value) > 32767 for row in rows for value in row):
        raise ValueError(f"A cell exceeds the Excel text limit: {path}")
    return rows


def add_text_sheet(workbook: Workbook, name: str, rows: list[list[str]]) -> None:
    sheet = workbook.create_sheet(name)
    for row in rows:
        sheet.append(row)
    for row in sheet:
        for cell in row:
            # Store literal text, including leading zeros, decimals and '=' signs.
            cell.data_type = "s"
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="AA462A")
        cell.font = Font(color="FFFFFF", bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        header = str(column[0].value or "")
        width = 55 if any(term in header for term in ["steps", "ingredients", "query_text", "notes", "path", "sumber"]) else 25
        sheet.column_dimensions[column[0].column_letter].width = width


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="artifacts/hasil_uji_coba_mentah_20261027")
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    if not output.is_relative_to(ROOT / "artifacts"):
        raise SystemExit("The output directory must be inside project/artifacts.")
    if output.exists() or output.with_suffix(".zip").exists():
        raise SystemExit("Output already exists. Choose a new --out path to preserve it.")

    tables = {source: read_table(ROOT / source) for source, _, _ in RAW_TABLES}
    tables[TEMPLATE] = read_table(ROOT / TEMPLATE)
    for source in REFERENCES:
        if not (ROOT / source).is_file():
            raise FileNotFoundError(source)
    record = json.loads((ROOT / "evaluation/runs/wlc_validation/wlc_validation_record.json").read_text(encoding="utf-8"))
    if sha256(ROOT / "evaluation/manifests/query_manifest_validation_FROZEN.csv") != record["validation_manifest_sha256"]:
        raise ValueError("The validation manifest does not match the existing run record.")
    # Check archived file bytes against the hashes recorded with that archive.
    with (ROOT / ARCHIVE / "artifact_hashes.csv").open(encoding="utf-8-sig", newline="") as handle:
        archived_hashes = {row["Path"].replace("\\", "/").split("/")[-1]: row["Hash"].lower()
                           for row in csv.DictReader(handle)}
    for source, _, _ in RAW_TABLES:
        if (source.startswith(ARCHIVE) and Path(source).name in archived_hashes
                and sha256(ROOT / source) != archived_hashes[Path(source).name]):
            raise ValueError(f"Archived checksum mismatch: {source}")

    output.mkdir(parents=True)
    workbook = Workbook()
    workbook.remove(workbook.active)
    add_text_sheet(workbook, "PETUNJUK", [
        ["Keterangan", "Isi"],
        ["Isi", "Salinan data evaluasi yang sudah ada di project; tidak dilakukan pengujian baru."],
        ["Sumber utama", "CSV dalam 01_file_asli disalin identik byte demi byte; Excel adalah salinan untuk dibaca."],
        ["Nilai", "Tidak dihitung ulang, digabung, dirata-rata, dibulatkan, dibersihkan, atau diisi nilai baru."],
        ["Uji akhir", "70 kueri; 258 kandidat pada setiap pass penilaian. Sumber: arsip final_test_20261022."],
        ["Validasi WLC", "30 kueri; 197 kandidat pooled pada setiap pass; hasil per konfigurasi tetap disimpan terpisah."],
        ["Pilot", "10 kueri; 48 kandidat pada setiap pass. Bukan bagian uji akhir."],
        ["Responden", "TEMPLATE_RESPONDEN hanya header. Belum ditemukan hasil responden yang terisi."],
        ["Identitas penilai", "Tidak ditambahkan. Konfirmasikan asal grade dan identitas penilai sebelum mengklaim penilaian manusia."],
        ["Versi", "Data historis, terutama arsip 22 Oktober 2026; tidak menyatakan evaluasi ulang kode UI/parser saat ini."],
        ["PRIVATE", "Mapping dapat membuka skor dan urutan asli. Jangan diberikan kepada penilai yang belum menyelesaikan blind grading."],
        ["Format sel", "Nilai CSV ditulis sebagai teks agar representasi asli tidak berubah; tidak ada formula atau grafik."],
        ["Verifikasi", "Daftar sumber, jumlah baris data, dan SHA-256 terdapat di DAFTAR_SUMBER serta manifest_sha256.csv."],
    ])
    inventory = []

    def copy_original(source: str, destination: Path, role: str, sheet: str = "") -> None:
        original = ROOT / source
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha256(original)
        shutil.copy2(original, target)
        if sha256(target) != before:
            raise ValueError(f"Copy differs from source: {source}")
        inventory.append({"kategori": role, "sumber": source, "salinan": destination.as_posix(),
                          "sheet_excel": sheet, "baris_data": str(len(tables[source]) - 1) if source in tables else "",
                          "ukuran_byte": str(original.stat().st_size), "sha256": before})

    for source, group, sheet in RAW_TABLES:
        copy_original(source, Path("01_file_asli") / group / Path(source).name, "data_per_kueri_atau_penilaian", sheet)
        add_text_sheet(workbook, sheet, tables[source])
    for source in REFERENCES:
        copy_original(source, Path("02_referensi") / source, "referensi_bukan_hasil_mentah")
    copy_original(TEMPLATE, Path("03_template_belum_diisi") / Path(TEMPLATE).name,
                  "template_kosong_bukan_hasil_uji", "TEMPLATE_RESPONDEN")
    add_text_sheet(workbook, "TEMPLATE_RESPONDEN", tables[TEMPLATE])
    inventory_rows = [list(inventory[0]), *[list(item.values()) for item in inventory]]
    add_text_sheet(workbook, "DAFTAR_SUMBER", inventory_rows)
    workbook_path = output / "DATA_UJI_MENTAH.xlsx"
    workbook.save(workbook_path)

    # Reopen the workbook and compare every source cell, not just row counts.
    checked = load_workbook(workbook_path, read_only=True, data_only=False)
    for source, _, sheet in RAW_TABLES + [(TEMPLATE, "", "TEMPLATE_RESPONDEN")]:
        actual = [["" if value is None else str(value) for value in row]
                  for row in checked[sheet].iter_rows(values_only=True)]
        if actual != tables[source]:
            raise ValueError(f"Excel differs from CSV: {source}")
    if any(cell.data_type == "f" for sheet in checked for row in sheet for cell in row):
        raise ValueError("Unexpected Excel formula.")
    checked.close()

    with (output / "manifest_sha256.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(inventory[0]))
        writer.writeheader()
        writer.writerows(inventory)
    report = {"packaged_at": datetime.now(JAKARTA).isoformat(), "new_evaluation_run": False,
              "original_files": len(inventory), "raw_tables": len(RAW_TABLES),
              "original_copy_hashes_match": True, "excel_cells_match_source_csv": True,
              "excel_formulas": 0, "respondent_result_rows": len(tables[TEMPLATE]) - 1,
              "workbook_sha256": sha256(workbook_path)}
    (output / "VERIFIKASI.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "README_PENGUMPULAN.md").write_text(README, encoding="utf-8")
    archive_path = output.with_suffix(".zip")
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(output.parent).as_posix())
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed.")
    print(json.dumps({"folder": str(output), "zip": str(archive_path), **report}, indent=2))


README = """# Berkas Hasil Uji Coba Dapuria — Data Sebelum Agregasi

## Berkas untuk dikumpulkan

1. `01_file_asli/` memuat CSV asli yang disalin tanpa mengubah byte, kolom, urutan baris, nilai, atau catatan. Inilah berkas utama untuk permintaan **file asli dan belum diolah**.
2. `DATA_UJI_MENTAH.xlsx` adalah salinan tabel agar mudah dibuka di Excel. Setiap sheet mengikuti satu CSV sumber. Sel ditulis sebagai teks, termasuk ID, angka, dan nilai kosong. Tidak ada penggabungan pass, pembersihan data, perhitungan metrik, formula, atau grafik.
3. `manifest_sha256.csv` menunjukkan path sumber, path salinan, nama sheet, jumlah baris data, ukuran file, dan checksum. `VERIFIKASI.json` mencatat pemeriksaan kesamaan file dan sel Excel.
4. `02_referensi/` berisi rubrik, catatan konfigurasi, serta rekaman environment yang sudah tersedia. File di folder ini merupakan pendukung, bukan data penilaian mentah.
5. `03_template_belum_diisi/` dan sheet `TEMPLATE_RESPONDEN` berisi template kosong. Jangan disajikan sebagai hasil pengujian responden.

ZIP berisi seluruh paket ini. Untuk permintaan file asli, sertakan ZIP atau folder CSV aslinya bersama Excel, bukan hanya Excel hasil konversi.

## Asal data dan ruang lingkup

| Kelompok | Masukan uji | Kandidat/penilaian yang tersedia |
| --- | --- | --- |
| Uji akhir | 70 kueri | 258 baris kandidat pada pass 1 dan 258 pada pass 2; mapping 516 baris |
| Validasi WLC | 30 kueri | 197 kandidat pooled pada masing-masing pass; 1.232 baris keluaran per konfigurasi WLC |
| Pilot | 10 kueri | 48 kandidat pada masing-masing pass; dipisahkan dari uji akhir |

Angka tersebut menjelaskan isi file, bukan rata-rata atau metrik performa. Dua pass bukan dua kelompok responden. Mapping dan tabel kandidat dapat merujuk resep yang sama; jangan menjumlahkan seluruh sheet sebagai jumlah percobaan atau responden.

Uji akhir berasal dari arsip `evaluation/archive/final_test_20261022`. Nilai arsip diperiksa terhadap checksum yang sudah tersimpan. Validasi dan pilot berasal dari file yang tersedia di `evaluation/runs/`, sedangkan masukan kueri berasal dari manifest yang dibekukan. Daftar sumber rinci tercantum dalam manifest paket.

Paket ini disiapkan pada 27 Oktober 2026 dari data historis yang sudah tersedia. **Tidak dilakukan eksperimen baru atau pengisian nilai oleh pembuat paket.** Hasil historis tidak otomatis merepresentasikan perubahan parser, pencocokan, dan UI sesudah run tersebut.

Grade dan notes disalin sebagaimana ditemukan. Identitas penilai, tanggal setiap penilaian, dan apakah penilaian dilakukan manusia tidak ditambahkan karena tidak tersedia sebagai metadata terverifikasi pada tabel tersebut. Konfirmasikan asal grade sebelum menyebutnya sebagai penilaian manusia atau responden.

## Data yang sengaja tidak dijadikan hasil mentah

- Rata-rata, nDCG, Precision, Success, agreement, dan tabel ringkasan metrik tidak dimasukkan sebagai data mentah.
- Label final hasil rekonsiliasi tidak menggantikan nilai asli pass 1 dan pass 2.
- Gambar serta database `artifacts/ui` memakai data preview untuk dokumentasi UI dan tidak dijadikan bukti eksperimen.
- Template responden masih kosong; belum ditemukan data responden yang terisi di project pada saat paket dibuat.

## Cara membaca sheet Excel

| Awalan/nama | Isi |
| --- | --- |
| `FINAL_` | Kueri, status, penilaian dua pass, dan mapping untuk uji akhir |
| `VALID_` | Kueri validasi, status, kandidat pooled, keluaran tiap bobot, dan penilaian dua pass |
| `PILOT_` | Data pilot terpisah |
| `TEMPLATE_RESPONDEN` | Header formulir responden, tanpa hasil penilaian |
| `DAFTAR_SUMBER` | Jejak sumber dan checksum setiap file |

`grade` merupakan nilai 0/1/2 sesuai rubrik yang disertakan. `notes` merupakan catatan yang sudah ada. `blind_code` adalah kode kandidat pada formulir blind grading. `original_rank` dan `final_score` adalah keluaran sistem yang dicatat pada file sumber, bukan perhitungan baru dalam workbook. `n_displayed` mencatat jumlah rekomendasi yang ditampilkan untuk kueri tersebut.

File berlabel `PRIVATE` dan sheet `MAPPING` membuka hubungan kode blind, resep, serta skor/urutan jika tersedia. Gunakan untuk pemeriksaan oleh pembimbing; jangan dibagikan kepada penilai yang masih menjalankan blind grading.

## Jika yang dimaksud pembimbing adalah uji pengguna atau black-box

Data di paket ini adalah data evaluasi rekomendasi yang sudah tersedia. Template responden kosong tidak memenuhi permintaan hasil penilaian pengguna. Jika diminta uji pengguna, lakukan sesi uji dan simpan jawaban asli menggunakan template. Jika diminta uji fungsi aplikasi, rekam hasil eksekusi skenario atau laporan pengujian sebenarnya dalam berkas terpisah. Jangan mengganti nama data rekomendasi ini menjadi hasil responden atau black-box.
"""


if __name__ == "__main__":
    main()

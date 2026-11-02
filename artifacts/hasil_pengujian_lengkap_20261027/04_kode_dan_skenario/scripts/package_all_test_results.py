"""Preserve historical evaluations and record a real automated test execution."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook, load_workbook

from package_raw_evaluation import JAKARTA, RAW_TABLES, ROOT, TEMPLATE, add_text_sheet, read_table, sha256

OUTPUT = ROOT / "artifacts/hasil_pengujian_lengkap_20261027"
HISTORICAL = ROOT / "artifacts/hasil_uji_coba_mentah_20261027"


def main() -> None:
    if OUTPUT.exists() or OUTPUT.with_suffix(".zip").exists():
        raise SystemExit("Output already exists; preserve it before making another package.")
    if not (HISTORICAL / "VERIFIKASI.json").is_file():
        raise SystemExit("Create the historical raw package first.")
    OUTPUT.mkdir()
    inventory = []

    def copy(source: Path, destination: Path, category: str) -> None:
        target = OUTPUT / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        checksum = sha256(source)
        shutil.copy2(source, target)
        assert sha256(target) == checksum
        inventory.append([category, source.relative_to(ROOT).as_posix(), destination.as_posix(), checksum])

    for source in sorted(HISTORICAL.rglob("*")):
        if source.is_file():
            copy(source, Path("01_evaluasi_mentah") / source.relative_to(HISTORICAL), "paket_historis")

    # Keep additional existing records, including processed results, in labeled folders.
    raw_names = {Path(source).name for source, _, _ in RAW_TABLES}
    for folder in [ROOT / "evaluation/runs", ROOT / "evaluation/archive"]:
        for source in sorted(folder.rglob("*")):
            if not source.is_file() or source.suffix not in {".csv", ".json", ".md", ".txt", ".sha256"}:
                continue
            if source.name in raw_names:
                destination = Path("01_evaluasi_mentah/tambahan_arsip") / source.relative_to(ROOT)
                category = "rekaman_sumber_tambahan"
            else:
                destination = Path("03_hasil_olahan_dan_referensi") / source.relative_to(ROOT)
                category = "olahan_atau_referensi_bukan_data_mentah"
            copy(source, destination, category)

    # Snapshot the exact source/scenarios used in the new automated test run.
    sources = [ROOT / name for name in ["app.py", "requirements.txt", "pyproject.toml", ".streamlit/config.toml"]]
    sources += sorted((ROOT / "src/dapuria").glob("*.py"))
    sources += sorted((ROOT / "tests").glob("*.py"))
    sources += sorted((ROOT / "scripts").glob("*.py"))
    sources += sorted((ROOT / "src/dapuria/assets").rglob("*.css"))
    sources += sorted((ROOT / "src/dapuria/assets/image").glob("*.png"))
    initial_hashes = {source: sha256(source) for source in sources}
    for source in sources:
        copy(source, Path("04_kode_dan_skenario") / source.relative_to(ROOT), "snapshot_kode_dan_skenario")

    logs = OUTPUT / "02_log_pengujian_otomatis"
    logs.mkdir()
    python = ROOT / ".venv/Scripts/python.exe"
    xml_path = logs / "pytest_junit.xml"
    command = [str(python), "-m", "pytest", "tests", "-vv", "-ra", f"--junitxml={xml_path}", "-o", "junit_logging=all"]
    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = datetime.now(JAKARTA)
    with (logs / "pytest_stdout_stderr.log").open("wb") as handle:
        completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=handle, stderr=subprocess.STDOUT, check=False)
    ended = datetime.now(JAKARTA)
    for filename, args in [("python_version.txt", [str(python), "--version"]),
                           ("environment_freeze.txt", [str(python), "-m", "pip", "freeze"])]:
        with (logs / filename).open("wb") as handle:
            subprocess.run(args, cwd=ROOT, env=environment, stdout=handle, stderr=subprocess.STDOUT, check=True)

    rows = [["classname", "test_name", "outcome", "duration_seconds", "original_log"]]
    if xml_path.is_file():
        for case in ET.parse(xml_path).getroot().iter("testcase"):
            outcome = next((tag for tag in ["failure", "error", "skipped"] if case.find(tag) is not None), "passed")
            rows.append([case.get("classname", ""), case.get("name", ""), outcome,
                         case.get("time", ""), "02_log_pengujian_otomatis/pytest_junit.xml"])
    with (logs / "salinan_per_kasus.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)
    record = {"started_at": started.isoformat(), "ended_at": ended.isoformat(), "command": command,
              "working_directory": str(ROOT), "exit_code": completed.returncode,
              "code_unchanged_during_run": all(sha256(path) == checksum for path, checksum in initial_hashes.items()),
              "test_cases": len(rows) - 1,
              "counts": {outcome: sum(row[2] == outcome for row in rows[1:])
                         for outcome in ["passed", "failure", "error", "skipped"]},
              "scope": "Actual pytest execution using existing unit/UI tests and their mocks; not a new production SBERT evaluation or respondent session."}
    (logs / "run_record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2), flush=True)

    workbook = Workbook()
    workbook.remove(workbook.active)
    add_text_sheet(workbook, "PETUNJUK", [
        ["Bagian", "Keterangan"],
        ["Evaluasi rekomendasi", "Data historis: 70 kueri uji akhir, 30 validasi WLC, dan 10 pilot. Nilai disalin tanpa dihitung ulang."],
        ["Tes otomatis", f"Eksekusi aktual tanggal {started.date().isoformat()}; lihat sheet OTOMATIS_KASUS dan log asli JUnit/stdout."],
        ["File asli", "CSV historis: 01_evaluasi_mentah; keluaran pytest asli: 02_log_pengujian_otomatis."],
        ["Hasil olahan", "Metrik, label final, dan rekonsiliasi lama dipisahkan di 03_hasil_olahan_dan_referensi. Bukan data mentah."],
        ["Responden", "TEMPLATE_RESPONDEN kosong. Tidak ditambahkan hasil, identitas, atau nilai responden."],
        ["Grading", "Grade historis disalin sebagaimana ditemukan. Asal dan identitas penilai perlu dikonfirmasi oleh pemilik penelitian."],
        ["Batas bukti", "Unit/UI tests menggunakan mocks sesuai kode. Tidak menggantikan uji pengguna atau pengujian model produksi."],
        ["Format", "Sel CSV/JUnit disalin sebagai teks; tidak ada formula, agregasi nilai, atau grafik pada workbook ini."],
    ])
    source_tables = {}
    for source, _, sheet in RAW_TABLES:
        source_tables[sheet] = read_table(ROOT / source)
        add_text_sheet(workbook, sheet, source_tables[sheet])
    source_tables["TEMPLATE_RESPONDEN"] = read_table(ROOT / TEMPLATE)
    source_tables["OTOMATIS_KASUS"] = rows
    for sheet in ["TEMPLATE_RESPONDEN", "OTOMATIS_KASUS"]:
        add_text_sheet(workbook, sheet, source_tables[sheet])
    add_text_sheet(workbook, "DAFTAR_SUMBER", [["kategori", "sumber", "salinan", "sha256"], *inventory])
    excel = OUTPUT / "HASIL_PENGUJIAN_LENGKAP.xlsx"
    workbook.save(excel)
    checked = load_workbook(excel, read_only=True, data_only=False)
    for sheet, expected in source_tables.items():
        actual = [["" if value is None else str(value) for value in row]
                  for row in checked[sheet].iter_rows(values_only=True)]
        assert actual == expected, sheet
    checked.close()
    with (OUTPUT / "manifest_salinan_sumber.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows([["kategori", "sumber", "salinan", "sha256"], *inventory])
    (OUTPUT / "README_MULAI_DI_SINI.md").write_text(README.format(date=started.date(), cases=len(rows) - 1,
                                                                 passed=record["counts"]["passed"], exit_code=completed.returncode), encoding="utf-8")
    files = [{"path": path.relative_to(OUTPUT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
             for path in sorted(OUTPUT.rglob("*")) if path.is_file()]
    (OUTPUT / "manifest_semua_berkas.json").write_text(json.dumps({"created_at": datetime.now(JAKARTA).isoformat(),
        "files": files, "copied_sources_verified": True, "excel_values_verified": True}, indent=2) + "\n", encoding="utf-8")
    with ZipFile(OUTPUT.with_suffix(".zip"), "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(OUTPUT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUTPUT.parent).as_posix())
    with ZipFile(OUTPUT.with_suffix(".zip")) as archive:
        assert archive.testzip() is None
    print(f"Complete package: {OUTPUT.with_suffix('.zip')}", flush=True)


README = """# Paket Lengkap Hasil Pengujian Dapuria

## Berkas utama

- **HASIL_PENGUJIAN_LENGKAP.xlsx**: tabel historis per kueri/penilaian dan salinan hasil per kasus tes otomatis, tanpa formula atau perhitungan metrik baru.
- **01_evaluasi_mentah/**: paket CSV asli evaluasi rekomendasi beserta tambahan salinan arsip/run yang tersedia. Sumber dan salinan identik byte demi byte; beberapa arsip berisi salinan data yang sama, sehingga jumlah file bukan jumlah eksperimen yang berbeda.
- **02_log_pengujian_otomatis/**: stdout/stderr dan JUnit asli dari eksekusi pytest baru, rekaman perintah, waktu, environment, dan salinan tabel per kasus.
- **03_hasil_olahan_dan_referensi/**: hasil metrik, agreement, rekonsiliasi, label final, dan catatan yang sudah tersedia. Bagian ini disertakan untuk kelengkapan, tetapi bukan data mentah.
- **04_kode_dan_skenario/**: salinan kode, test case, dan konfigurasi yang dipakai saat tes otomatis direkam.

Untuk permintaan **file asli dan belum diolah**, prioritaskan file CSV pada bagian 01 dan log/XML asli pada bagian 02. Excel merupakan salinan baca dari data tersebut. `salinan_per_kasus.csv` adalah konversi per kasus dari JUnit, bukan log sumber. Jangan mengganti data mentah dengan metrik ringkasan pada bagian 03.

## Cakupan dan tanggal

| Jenis | Isi | Kedudukan |
| --- | --- | --- |
| Uji akhir rekomendasi | 70 kueri, 258 kandidat pada setiap pass penilaian | Data historis dari arsip 22 Oktober 2026 |
| Validasi bobot WLC | 30 kueri, 197 kandidat pooled pada setiap pass, keluaran 11 konfigurasi | Data historis; dipisahkan dari uji akhir |
| Pilot | 10 kueri, 48 kandidat pada setiap pass | Uji pendahuluan; tidak digabung ke uji akhir |
| Tes otomatis aplikasi | {cases} kasus dieksekusi pada {date}; {passed} lulus; exit code {exit_code} | Eksekusi baru dari test suite yang tersedia |
| Penilaian responden | Belum ditemukan hasil terisi | Template tetap kosong |
| Uji black-box manual oleh pengguna | Belum ditemukan lembar hasil pelaksanaan | Tidak dibuat atau diisi sebagai hasil nyata |

Tes otomatis benar-benar dijalankan, tetapi sebagian layanan/model diganti dengan mocks sesuai skenario test. Kelulusan tes ini tidak membuktikan hasil pengukuran SBERT produksi, waktu respons produksi, atau penilaian pengguna. Durasi pada JUnit merupakan waktu eksekusi test, bukan benchmark aplikasi bagi pengguna.

Nilai grade historis tidak dibuat ulang. Metadata yang ditemukan belum menetapkan identitas penilai dan asal setiap grade; konfirmasikan hal tersebut sebelum menyebut data tersebut sebagai hasil responden atau penilaian manusia. Dua pass adalah dua putaran grading, bukan bukti dua responden berbeda.

Perbaikan UI/parser setelah run historis tidak mengubah atau memperbarui hasil rekomendasi tahun/tanggal tersebut secara otomatis. Pernyataan “tidak dilakukan eksperimen baru” dalam README paket bagian 01 merujuk evaluasi rekomendasi historis; tes otomatis pada bagian 02 direkam baru secara terpisah.

## Keutuhan data

`manifest_salinan_sumber.csv` memetakan setiap salinan ke sumber dan SHA-256. `manifest_semua_berkas.json` memuat checksum berkas dalam paket, termasuk log dan workbook. Salinan Excel diperiksa per sel terhadap CSV dan tabel JUnit.

Tidak ada rata-rata, normalisasi, penggabungan grade, pengisian nilai kosong, atau grafik baru dalam workbook. Hasil olahan lama tetap dipisahkan dan tidak dinamai sebagai data mentah. Database serta screenshot preview UI tidak digunakan sebagai hasil pengujian rekomendasi.

File PRIVATE/mapping dapat membuka skor dan urutan asli; gunakan untuk pemeriksaan pembimbing, bukan untuk penilai yang belum menyelesaikan blind grading.
"""


if __name__ == "__main__":
    main()

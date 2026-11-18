from pathlib import Path
import subprocess


def test_domestic_rankings_use_published_rows_and_isolate_request_states():
    subprocess.run(["node", str(Path(__file__).with_suffix(".cjs"))], check=True)

import urllib.request
import json
import uuid
from pathlib import Path

def test_batch_stream():
    url = "http://127.0.0.1:8000/api/batch/evaluate/stream"
    csv_path = Path("data/sample_batch_evaluation.csv")
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{csv_path.name}\"\r\n"
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_path.read_text(encoding='utf-8')}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "text/event-stream"}
    )
    events = []
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            decoded = line.decode("utf-8").strip()
            if decoded.startswith("data:"):
                ev = json.loads(decoded[5:].strip())
                events.append(ev.get("event"))
                if ev.get("event") == "ROW_PROCESSED":
                    print(f"Row {ev.get('row_id')}: Processed {ev.get('processed')}/{ev.get('total_rows')} ({ev.get('percentage')}%) [{ev.get('status')}]")
                elif ev.get("event") == "BATCH_COMPLETED":
                    print(f"Batch Completed! Total rows: {ev.get('total_rows')}")

    assert "BATCH_STARTED" in events
    assert "ROW_PROCESSED" in events
    assert "BATCH_COMPLETED" in events
    print("[PASS] /api/batch/evaluate/stream streaming test verified!")

if __name__ == "__main__":
    test_batch_stream()

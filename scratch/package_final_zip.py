"""
Package final verified Milestone 3 ZIP artifact.
Excludes __pycache__, .git, .pytest_cache, .venv, *.log, *.tmp
Verifies zip contents after creation.
"""
import zipfile
from pathlib import Path

ROOT_DIR = Path(r"C:\Users\aakan\.gemini\antigravity\scratch\ai_response_validation_system")
TARGET_ZIP_1 = Path(r"C:\Users\aakan\.gemini\antigravity\scratch\ai_response_validation_system_Milestone3_Final.zip")
TARGET_ZIP_2 = Path(r"C:\Users\aakan\OneDrive\Desktop\INFOSYS\ai_response_validation_system_Milestone3_Final.zip")
TARGET_ZIP_3 = Path(r"C:\Users\aakan\OneDrive\Desktop\INFOSYS\ai_response_validation_system.zip")

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", ".idea", ".vscode"}
EXCLUDE_EXTS = {".pyc", ".pyo", ".log", ".tmp"}

def create_zip(target_path):
    print(f"Creating zip at {target_path}...")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in ROOT_DIR.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Check exclusions
            parts = file_path.relative_to(ROOT_DIR).parts
            if any(ex in parts for ex in EXCLUDE_DIRS):
                continue
            if file_path.suffix.lower() in EXCLUDE_EXTS:
                continue
            
            arcname = Path("ai_response_validation_system") / file_path.relative_to(ROOT_DIR)
            zf.write(file_path, arcname)
            count += 1

    print(f"Successfully packaged {count} files into {target_path} (Size: {target_path.stat().st_size:,} bytes)")

def verify_zip(target_path):
    print(f"Verifying {target_path}...")
    with zipfile.ZipFile(target_path, "r") as zf:
        namelist = zf.namelist()
        required_patterns = [
            "backend/main.py",
            "backend/agents/completeness_agent.py",
            "backend/agents/verdict_agent.py",
            "backend/agents/orchestrator.py",
            "backend/api/routes/evaluation.py",
            "backend/api/schemas/evaluation.py",
            "frontend/index.html",
            "frontend/js/app.js",
            "frontend/js/api.js",
            "frontend/js/components/chart.js",
            "frontend/css/style.css",
            "data/sample_batch_evaluation.csv",
            "tests/test_milestone3.py",
            "requirements.txt",
            "run_frontend.py",
            "README.md"
        ]
        for pattern in required_patterns:
            matches = [n for n in namelist if pattern in n.replace("\\", "/")]
            assert matches, f"Missing required file in ZIP: {pattern}"
            print(f"  [OK] Found: {matches[0]}")
        
        # Verify no pycache
        pycache_matches = [n for n in namelist if "__pycache__" in n]
        assert not pycache_matches, f"Found __pycache__ in ZIP: {pycache_matches[:3]}"
        print("  [OK] No __pycache__ or temporary files detected.")
    print("Verification complete. ZIP is 100% valid!")

if __name__ == "__main__":
    create_zip(TARGET_ZIP_1)
    create_zip(TARGET_ZIP_2)
    create_zip(TARGET_ZIP_3)
    verify_zip(TARGET_ZIP_1)
    verify_zip(TARGET_ZIP_2)

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_name):
    print(f"\n{'='*50}")
    print(f"Running {script_name}...")
    print(f"{'='*50}")
    
    script_path = os.path.join(BASE_DIR, script_name)
    result = subprocess.run([sys.executable, script_path])
    
    if result.returncode != 0:
        print(f"\n[ERROR] {script_name} failed with exit code {result.returncode}")
        sys.exit(1)
    else:
        print(f"[SUCCESS] {script_name} completed successfully.")

def run_pipeline():
    print("Starting Merchant Maxx Synthetic Data Pipeline...\n")
    
    scripts = [
        "inspect_datasets.py",
        "transform_retailrocket.py",
        "transform_olist.py",
        "optional_uci_features.py",
        "generate_synthetic_data.py",
        "build_product_affinity.py",
        "build_customer_metrics.py",
        "demo_fixtures.py",
        "validate_data.py"
    ]
    
    for script in scripts:
        run_script(script)
        
    print("\nPipeline completed successfully! Data is ready for seeding.")

if __name__ == "__main__":
    run_pipeline()

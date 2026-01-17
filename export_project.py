import shutil
import os
import datetime

def make_archive():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base_name = f"KELION_PROJECT_FULL_{timestamp}"
    root_dir = os.getcwd()
    output_path = os.path.join(root_dir, base_name)
    
    # Create a cleaner zip by excluding sensitive/garbage dirs if possible, 
    # but user said "absolutely everything", so we basically include everything.
    # However, to avoid recursive loop if the zip is made inside, 
    # shutil.make_archive handles base_name usage well usually.
    
    print(f"Archiving entries in {root_dir}...")
    
    try:
        archive_path = shutil.make_archive(output_path, 'zip', root_dir)
        print(f"✅ Archive created successfully: {os.path.basename(archive_path)}")
        print(f"📂 Full path: {archive_path}")
    except Exception as e:
        print(f"❌ Error creating archive: {e}")

if __name__ == "__main__":
    make_archive()
